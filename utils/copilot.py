"""Dashboard copilot — a LangGraph ReAct agent over Grok (x.ai), streamed.

Pattern ported from the drvet cockpit: the copilot gets its context by exposing
the app's read-only data queries as LangChain **tools**, so the agent pulls real
numbers on demand (ReAct loop) rather than us stuffing page data into the prompt.
Answers stream token-by-token via ``answer_stream`` (async generator of
``(event, data)``) which the SSE route relays to the browser.

Grok is reached through langchain-openai's OpenAI-compatible ChatOpenAI at
``settings().xai_base_url``. Config via ``settings()`` — never os.environ.
"""

from __future__ import annotations

from utils.config import settings
from utils.money import fmt_money
from utils.prompts import load_prompt

_agent = None


def copilot_available() -> bool:
    return bool(settings().xai_api_key)


def _build_tools():
    from langchain_core.tools import tool
    try:
        from db import fetch_all, fetch_one
    except Exception:  # pragma: no cover
        fetch_all = fetch_one = None

    def _q(sql, one=False):
        if fetch_all is None:
            return None if one else []
        try:
            return (fetch_one if one else fetch_all)(sql)
        except Exception:
            return None if one else []

    @tool
    def platform_kpis() -> str:
        """Platform KPIs: total funded volume, invoice count, active exposures and client count."""
        r = _q("""SELECT COALESCE(SUM(f.amount_raised),0) funded,
                         COUNT(DISTINCT i.id) invoices,
                         COUNT(DISTINCT CASE WHEN i.status='funding' THEN i.id END) active,
                         COUNT(DISTINCT c.id) clients
                  FROM factorio.companies c
                  LEFT JOIN factorio.invoices i ON i.company_id=c.id
                  LEFT JOIN factorio.invoice_funding f ON f.invoice_id=i.id""", one=True) or {}
        return (f"Funded to date: {fmt_money(r.get('funded'))}. Invoices: {r.get('invoices',0)}. "
                f"Active exposures: {r.get('active',0)}. Clients & debtors: {r.get('clients',0)}.")

    @tool
    def sector_exposure() -> str:
        """Financed exposure grouped by industry sector."""
        rows = _q("""SELECT i.sector, COALESCE(SUM(i.amount),0) exp, COUNT(*) n
                     FROM factorio.invoices i WHERE i.status IN ('funding','funded')
                     GROUP BY i.sector ORDER BY exp DESC""")
        if not rows:
            return "No active exposure."
        return "; ".join(f"{r['sector']}: {fmt_money(r['exp'])} ({r['n']})" for r in rows[:10])

    @tool
    def top_debtors() -> str:
        """Largest debtor (buyer) concentrations by financed exposure."""
        rows = _q("""SELECT i.debtor_name, COALESCE(SUM(i.amount),0) exp, COUNT(*) n
                     FROM factorio.invoices i WHERE i.status IN ('funding','funded')
                     GROUP BY i.debtor_name ORDER BY exp DESC""")
        if not rows:
            return "No active exposure."
        return "; ".join(f"{r['debtor_name']}: {fmt_money(r['exp'])} ({r['n']})" for r in rows[:8])

    @tool
    def risk_distribution() -> str:
        """Distribution of invoices by risk grade (A–D) and default count."""
        rows = _q("SELECT risk_grade, COUNT(*) n FROM factorio.invoices GROUP BY risk_grade ORDER BY risk_grade")
        d = _q("SELECT COUNT(*) n FROM factorio.invoices WHERE status='defaulted'", one=True) or {}
        grades = ", ".join(f"{r['risk_grade']}: {r['n']}" for r in rows) or "n/a"
        return f"Risk grades — {grades}. Defaulted invoices: {d.get('n',0)}."

    @tool
    def sales_pipeline() -> str:
        """Back-office sales pipeline: open deals by stage and total open value."""
        try:
            from app_routes.modules import pipeline_summary
            return pipeline_summary()
        except Exception:
            return "Pipeline data unavailable."

    @tool
    def credit_scores() -> str:
        """Debtor credit-score distribution by grade, and model calibration (expected vs actual default)."""
        try:
            from app_routes.scoring import scores_summary, calibration
            cal = calibration()
            cal_s = "; ".join(f"{c['grade']} exp {c['expected']*100:.0f}% vs actual {c['actual']*100:.1f}%" for c in cal)
            return f"{scores_summary()}. Calibration — {cal_s}."
        except Exception:
            return "Scoring data unavailable."

    return [platform_kpis, sector_exposure, top_debtors, risk_distribution, sales_pipeline, credit_scores]


def _get_agent():
    global _agent
    if _agent is not None:
        return _agent
    cfg = settings()
    if not cfg.xai_api_key:
        return None
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent
    model = ChatOpenAI(model=cfg.xai_model, api_key=cfg.xai_api_key,
                       base_url=cfg.xai_base_url, temperature=0.2, timeout=60, max_retries=2)
    _agent = create_react_agent(model, _build_tools(),
                                prompt=load_prompt("backoffice_copilot.md"))
    return _agent


async def answer_stream(message: str):
    """Yield (event, data) tuples: ('token', str) | ('tool_start', {'name'}) | ('error', str)."""
    agent = _get_agent()
    if agent is None:
        yield ("token", "The copilot is not configured — set XAI_API_KEY.")
        return
    try:
        async for ev in agent.astream_events(
                {"messages": [{"role": "user", "content": message}]}, version="v2"):
            kind = ev.get("event")
            if kind == "on_chat_model_stream":
                chunk = ev["data"].get("chunk")
                content = getattr(chunk, "content", None)
                if content and isinstance(content, str) and not getattr(chunk, "tool_call_chunks", None):
                    yield ("token", content)
            elif kind == "on_tool_start":
                yield ("tool_start", {"name": ev.get("name", "tool")})
    except Exception as e:  # noqa: BLE001
        yield ("error", str(e))
