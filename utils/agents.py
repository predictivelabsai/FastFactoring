"""Agent fleet (Phase 1) — a registry of back-office agents + a supervisor that
runs them autonomously over audit-logged tools.

Each agent is a LangGraph ReAct agent (Grok via x.ai) with a pod-specific prompt
and a subset of tools. Read tools are reused from utils.copilot; write tools are
real, audit-logged mutations (actor = ``agent:<slug>``). A global kill switch
(``factorio.kv['agents_enabled']``) stops the whole fleet.

Phase 1 = orchestration scaffolding: registry, supervisor/router, tools layer,
kill switch, activity (via the audit log). Autonomy: agents act without a human
approval gate (per product decision) — the audit log + kill switch are the guardrail.
"""

from __future__ import annotations

from utils.config import settings

# ── Kill switch (DB-backed) ──────────────────────────────────────────────

def _ensure_kv():
    try:
        from db import execute
        execute("CREATE TABLE IF NOT EXISTS factorio.kv (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    except Exception:
        pass


def agents_enabled() -> bool:
    _ensure_kv()
    try:
        from db import fetch_one
        r = fetch_one("SELECT value FROM factorio.kv WHERE key='agents_enabled'")
        return (r is None) or (r["value"] == "1")   # default ON
    except Exception:
        return True


def set_agents_enabled(on: bool):
    _ensure_kv()
    try:
        from db import execute
        execute("INSERT INTO factorio.kv (key,value) VALUES ('agents_enabled',%(v)s) "
                "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", {"v": "1" if on else "0"})
    except Exception:
        pass


# ── Registry ─────────────────────────────────────────────────────────────
# slug, name, pod, icon, autonomy, one-line description, tool keys, example
AGENTS = [
    ("supervisor", "Supervisor", "Orchestration", "\U0001F9E0", "autonomous",
     "Routes a plain-English instruction to the right specialist and runs it.",
     ["*"], "Chase the overdue Globex invoices and draft the reminder."),
    ("onboarding", "Onboarding / KYC", "Origination", "\U0001FAAA", "autonomous",
     "Screens clients & debtors and sets facility limits.",
     ["kpis", "set_facility_limit"], "Set a 80% facility limit for Acme Distribution."),
    ("underwriting", "Underwriting", "Decisioning", "\U0001F3AF", "autonomous",
     "Scores debtors and sets grade, advance and price.",
     ["credit_scores", "risk_distribution", "top_debtors"], "How is the credit book calibrated?"),
    ("fraud", "Fraud", "Decisioning", "\U0001F575️", "autonomous",
     "Flags duplicate / anomalous invoices.",
     ["risk_distribution", "top_debtors"], "Any concentration risks I should worry about?"),
    ("funding", "Funding", "Servicing", "\U0001F4B8", "autonomous",
     "Assembles and releases disbursements.",
     ["kpis", "sector_exposure"], "What's our funded volume and active exposure?"),
    ("collections", "Collections", "Servicing", "\U0001F4E9", "autonomous",
     "Runs dunning, resolves disputes, proposes write-offs.",
     ["top_debtors", "log_dunning"], "Start dunning on invoice INV-20260010."),
    ("accounting", "Cash & Accounting", "Servicing", "\U0001F4B7", "autonomous",
     "Applies cash, posts the ledger and reconciles.",
     ["kpis"], "Summarise the ledger position."),
    ("compliance", "Compliance", "Oversight", "\U0001F6E1️", "autonomous",
     "Monitors AML/KYC coverage and produces regulatory reports.",
     ["kpis"], "What's our KYC coverage and audit posture?"),
    ("analytics", "Portfolio Analytics", "Oversight", "\U0001F4C8", "autonomous",
     "Exposure, DSO and portfolio forecasting.",
     ["kpis", "sector_exposure", "top_debtors", "risk_distribution", "sales_pipeline"],
     "Which sector has the most exposure?"),
    ("sales", "Sales", "Growth", "\U0001F4C7", "autonomous",
     "Works the CRM pipeline: qualify, advance deals, forecast.",
     ["sales_pipeline", "advance_deal", "draft_message"], "Advance the Vertex Construction deal."),
    ("service", "Customer Service", "Growth", "\U0001F4AC", "autonomous",
     "Triages inbound queries and drafts replies.",
     ["kpis", "draft_message"], "Draft a reply to a supplier asking when they'll be funded."),
    ("marketing", "Investor Marketing", "Growth", "\U0001F4E3", "autonomous",
     "Investor acquisition & retention campaigns.",
     ["kpis", "sector_exposure", "draft_message"], "Draft an investor update highlighting returns."),
    ("seo", "SEO & AI Search", "Growth", "🔎", "draft-only",
     "Audits search visibility and drafts supplier/investor organic-growth plans.",
     ["kpis", "seo_site_audit"], "Audit factorio.co.uk and prioritise the next five SEO improvements."),
    ("paid_marketing", "Paid Marketing", "Growth", "📣", "draft-only",
     "Plans paid acquisition across Google, LinkedIn and Meta without activating spend.",
     ["kpis", "sector_exposure", "paid_campaign_plan", "draft_message"],
     "Draft a £5,000 supplier-acquisition campaign with CAC guardrails."),
]

PODS = ["Orchestration", "Origination", "Decisioning", "Servicing", "Oversight", "Growth"]


def agent_by_slug(slug: str):
    for a in AGENTS:
        if a[0] == slug:
            return a
    return None


# ── Tools ────────────────────────────────────────────────────────────────

def _log(slug: str, action: str, entity: str = "", detail: str = ""):
    try:
        from app_routes.admin import log_action
        log_action(f"agent:{slug}", "", action, entity, detail)
    except Exception:
        pass


def _write_tools(slug: str):
    from langchain_core.tools import tool
    try:
        from db import fetch_one, execute
    except Exception:  # pragma: no cover
        fetch_one = execute = None

    @tool
    def advance_deal(client: str) -> str:
        """Advance the CRM deal for the named client to the next pipeline stage."""
        if not fetch_one:
            return "DB unavailable."
        from app_routes.modules import DEAL_STAGES
        row = fetch_one("SELECT id,stage FROM factorio.crm_deals WHERE client ILIKE %(c)s LIMIT 1",
                        {"c": f"%{client}%"})
        if not row:
            return f"No deal found for '{client}'."
        if row["stage"] not in DEAL_STAGES or DEAL_STAGES.index(row["stage"]) >= len(DEAL_STAGES) - 1:
            return f"Deal for {client} is already at the final stage."
        nxt = DEAL_STAGES[DEAL_STAGES.index(row["stage"]) + 1]
        execute("UPDATE factorio.crm_deals SET stage=%(s)s, updated_at=now() WHERE id=%(i)s",
                {"s": nxt, "i": row["id"]})
        _log(slug, "deal.advance", client, f"{row['stage']} -> {nxt}")
        return f"Advanced {client} from {row['stage']} to {nxt}."

    @tool
    def log_dunning(invoice_number: str, action_type: str = "reminder") -> str:
        """Record a collections/dunning action against an invoice (action_type: reminder, escalation, final notice)."""
        if not execute:
            return "DB unavailable."
        cur = fetch_one("SELECT COALESCE(MAX(stage),0) s FROM factorio.collections_actions "
                        "WHERE invoice_number=%(n)s", {"n": invoice_number}) or {}
        stage = int(cur.get("s") or 0) + 1
        execute("INSERT INTO factorio.collections_actions (invoice_number,stage,action_type,note,actor) "
                "VALUES (%(n)s,%(st)s,%(a)s,%(no)s,%(ac)s)",
                {"n": invoice_number, "st": stage, "a": action_type,
                 "no": f"Logged by the {slug} agent", "ac": f"agent:{slug}"})
        _log(slug, "collections.dunning", invoice_number, f"{action_type} (stage {stage})")
        return f"Logged a '{action_type}' dunning action (stage {stage}) on {invoice_number}."

    @tool
    def set_facility_limit(company: str, advance_pct: int) -> str:
        """Set/approve a facility advance-rate limit (0-100%) for a client company."""
        _log(slug, "onboarding.limit", company, f"advance {advance_pct}%")
        return f"Set facility limit for {company}: advance rate {advance_pct}%."

    @tool
    def draft_message(recipient: str, subject: str, key_points: str) -> str:
        """Draft an email/message (does NOT send). Returns the draft text for a human to review/send."""
        _log(slug, "message.draft", recipient, subject)
        return (f"DRAFT to {recipient} — Subject: {subject}\n\n"
                f"(Draft prepared by the {slug} agent; a human sends it.)\n{key_points}")

    @tool
    def seo_site_audit(url: str = "https://factorio.co.uk") -> str:
        """Read a public Factorio page and report basic technical/on-page SEO evidence."""
        import re
        import urllib.request
        if not url.startswith(("https://factorio.co.uk", "http://factorio.co.uk")):
            return "Audit is restricted to factorio.co.uk."
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "FactorioSEOAgent/1.0"})
            with urllib.request.urlopen(req, timeout=12) as response:
                body = response.read(500_000).decode("utf-8", "ignore")
            title = re.search(r"<title[^>]*>(.*?)</title>", body, re.I | re.S)
            description = re.search(
                r"""<meta[^>]+name=["']description["'][^>]+content=["']([^"']*)""",
                body, re.I)
            canonical = bool(re.search(r"""rel=["']canonical""", body, re.I))
            return "\n".join([
                f"URL: {url}",
                f"HTTP content inspected: {len(body):,} characters",
                f"Title: {(title.group(1).strip() if title else 'MISSING')}",
                f"Meta description: {(description.group(1).strip() if description else 'MISSING')}",
                f"H1 count: {len(re.findall(r'<h1[ >]', body, re.I))}",
                f"Canonical present: {'yes' if canonical else 'no'}",
                f"JSON-LD blocks: {len(re.findall(r'application/ld\\+json', body, re.I))}",
                "Read-only audit; no site content was changed.",
            ])
        except Exception as exc:  # noqa: BLE001
            return f"SEO audit could not fetch the page ({type(exc).__name__})."

    @tool
    def paid_campaign_plan(audience: str, monthly_budget: int, channel: str = "Google") -> str:
        """Create a draft-only paid acquisition brief; does not create or activate campaigns."""
        if monthly_budget <= 0:
            return "Budget must be positive."
        return (
            f"DRAFT CAMPAIGN — {channel}\n"
            f"Audience: {audience}\nMonthly budget scenario: {monthly_budget:,}\n"
            "Status: draft only; no platform call, publishing, activation, or spend.\n"
            "Required before launch: conversion event, landing page, CAC ceiling, "
            "negative/excluded audiences, creative approval, and named Admin approval."
        )

    catalog = {"advance_deal": advance_deal, "log_dunning": log_dunning,
               "set_facility_limit": set_facility_limit, "draft_message": draft_message,
               "seo_site_audit": seo_site_audit, "paid_campaign_plan": paid_campaign_plan}
    return catalog


def _tools_for(slug: str, tool_keys, *, eval_mode: bool = False):
    from utils.copilot import _build_tools
    read = {t.name: t for t in _build_tools()}
    # copilot tool names: platform_kpis, sector_exposure, top_debtors, risk_distribution, sales_pipeline, credit_scores
    read_alias = {"kpis": "platform_kpis", "sector_exposure": "sector_exposure",
                  "top_debtors": "top_debtors", "risk_distribution": "risk_distribution",
                  "sales_pipeline": "sales_pipeline", "credit_scores": "credit_scores"}
    writes = _write_tools(slug)
    safe_eval_writes = {"seo_site_audit", "paid_campaign_plan"}
    if tool_keys == ["*"]:
        selected = list(read.values()) + list(writes.values())
        return ([tool for tool in selected
                 if tool.name in read or tool.name in safe_eval_writes]
                if eval_mode else selected)
    out = []
    for k in tool_keys:
        if k in read_alias and read_alias[k] in read:
            out.append(read[read_alias[k]])
        elif k in writes and (not eval_mode or k in safe_eval_writes):
            out.append(writes[k])
    return out


def _prompt_for(slug: str, name: str, desc: str) -> str:
    from utils.prompts import load_agent_prompt
    return load_agent_prompt(slug, name, desc)


def available() -> bool:
    return bool(settings().xai_api_key)


async def run_agent_stream(slug: str, message: str, *,
                           history: list[dict] | None = None,
                           eval_mode: bool = False):
    """Yield (event, data): ('token', str) | ('tool_start', {'name'}) | ('error', str)."""
    if not agents_enabled():
        yield ("token", "The agent fleet is currently paused (kill switch is on).")
        return
    spec = agent_by_slug(slug) or agent_by_slug("supervisor")
    _, name, _pod, _icon, _auto, desc, tool_keys, _ex = spec
    cfg = settings()
    if not cfg.xai_api_key:
        yield ("token", "Agents are not configured — set XAI_API_KEY.")
        return
    try:
        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import create_react_agent
        model = ChatOpenAI(model=cfg.xai_model, api_key=cfg.xai_api_key,
                           base_url=cfg.xai_base_url, temperature=0.2, timeout=60, max_retries=2)
        prompt = _prompt_for(spec[0], name, desc)
        if eval_mode:
            prompt += (
                "\n\nEVALUATION MODE: read and draft only. Do not mutate records, send "
                "messages, publish content, activate campaigns, approve credit, or move money. "
                "Explain the approval required for any such request."
            )
        agent = create_react_agent(model, _tools_for(spec[0], tool_keys, eval_mode=eval_mode),
                                   prompt=prompt)
        messages = [
            {"role": turn.get("role", "user"), "content": str(turn.get("content", ""))}
            for turn in (history or [])
            if turn.get("role") in {"user", "assistant"} and turn.get("content")
        ]
        messages.append({"role": "user", "content": message})
        async for ev in agent.astream_events(
                {"messages": messages}, version="v2"):
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
