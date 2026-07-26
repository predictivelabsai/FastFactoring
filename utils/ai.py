"""AI layer — Grok (x.ai) chat, plus the two Factorio assistants.

Factorio uses Grok via x.ai's OpenAI-compatible Chat Completions API. Two
product-facing assistants are built on it:

  * triage     — a chat-based loan/invoice-application triage agent (seller side)
  * reporting  — a chat-based investor-reporting agent (investor side), grounded
                 in the current investor's own portfolio positions

The client is deliberately dependency-free (stdlib ``urllib``) so the app keeps
a small footprint; swap in the ``openai`` SDK later if streaming is needed.

Config is read through ``settings()`` (``XAI_API_KEY`` / ``XAI_MODEL`` /
``XAI_BASE_URL``) — never ``os.environ`` directly.
"""

from __future__ import annotations

import json
import base64
import urllib.error
import urllib.request

from utils.config import settings
from utils.prompts import load_prompt

# Roughly how many recent turns of a conversation we keep in-context.
MAX_HISTORY_TURNS = 12
_TIMEOUT_S = 60


def ai_available() -> bool:
    """True when an x.ai key is configured — routes degrade gracefully otherwise."""
    return bool(settings().xai_api_key)


def chat(messages: list[dict], *, temperature: float = 0.3,
         max_tokens: int = 900, model: str | None = None) -> str:
    """Call Grok chat-completions and return the assistant text.

    ``messages`` is the OpenAI-style list of ``{"role", "content"}`` dicts.
    Any transport/API error is returned as a short, user-safe string rather than
    raised, so a failed AI call never takes down a product page.
    """
    cfg = settings()
    if not cfg.xai_api_key:
        return ("The AI assistant is not configured yet — set XAI_API_KEY in the "
                "environment to enable it.")

    payload = json.dumps({
        "model": model or cfg.xai_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{cfg.xai_base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {cfg.xai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        return f"The AI assistant is temporarily unavailable (HTTP {e.code}). {detail}"
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as e:
        return f"The AI assistant is temporarily unavailable ({type(e).__name__})."


def extract_invoice(*, text: str = "",
                    images: list[tuple[bytes, str]] | None = None) -> dict:
    """Extract financing fields from Markdown or, for scans, invoice images."""
    cfg = settings()
    if not cfg.xai_api_key:
        raise RuntimeError("Invoice extraction is unavailable: XAI_API_KEY is not configured.")
    template = load_prompt("invoice_financing_extraction.md")
    prompt = template.replace("{invoice_text}", text[:40_000] or "[Read the attached invoice image.]")
    user_content: str | list[dict] = prompt
    if images:
        user_content = []
        for image_bytes, image_mime in images:
            encoded = base64.b64encode(image_bytes).decode("ascii")
            user_content.append(
                {"type": "image_url", "image_url": {
                    "url": f"data:{image_mime};base64,{encoded}", "detail": "high"}})
        user_content.append({"type": "text", "text": prompt})
    payload = json.dumps({
        "model": cfg.xai_model,
        "messages": [
            {"role": "system", "content": "Extract invoice data precisely. Return JSON only."},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0,
        "max_tokens": 2400,
        "response_format": {"type": "json_object"},
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{cfg.xai_base_url.rstrip('/')}/chat/completions", data=payload,
        headers={"Authorization": f"Bearer {cfg.xai_api_key}",
                 "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        content = result["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        parsed = json.loads(content)
        if not isinstance(parsed.get("invoice_data"), dict):
            raise ValueError("response has no invoice_data object")
        return parsed
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"xAI extraction failed (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as exc:
        raise RuntimeError(f"xAI extraction failed ({type(exc).__name__}).") from exc


def build_conversation(system_prompt: str, history: list[dict],
                       user_message: str) -> list[dict]:
    """Assemble a messages list: system + trimmed history + the new user turn."""
    trimmed = history[-(MAX_HISTORY_TURNS * 2):] if history else []
    return [{"role": "system", "content": system_prompt}, *trimmed,
            {"role": "user", "content": user_message}]


# ── Assistant 1: loan / invoice-application triage (seller side) ────────────

_LANG_NAMES = {"en": "English", "uz": "Uzbek", "ru": "Russian"}


def language_directive(lang: str) -> str:
    name = _LANG_NAMES.get(lang, "English")
    return "\n\n" + load_prompt("language_directive.md").format(language=name)


def triage_system_prompt(lang: str = "en") -> str:
    return load_prompt("invoice_triage.md") + language_directive(lang)


# ── Assistant 2: investor reporting (investor side) ─────────────────────────

def reporting_system_prompt(portfolio_context: str, lang: str = "en") -> str:
    return (f"{load_prompt('investor_reporting.md')}{language_directive(lang)}"
            f"\n\n=== PORTFOLIO DATA ===\n{portfolio_context}")


def portfolio_context(investor: dict | None, metrics: dict,
                      positions: list[dict]) -> str:
    """Render an investor's computed metrics + positions into a compact text block
    that grounds the reporting assistant. Kept plain-text and token-frugal."""
    if not investor:
        return "No investor selected; no portfolio data available."

    from utils.money import fmt_money as uzs  # display currency (USD default)

    lines = [
        f"Investor: {investor.get('username', '—')}",
        f"Account value: {uzs(metrics.get('account_value'))}",
        f"Net annual return: {metrics.get('net_annual_return', 0):.1f}%",
        f"Active invested: {uzs(metrics.get('active_invested'))}",
        f"Expected outstanding (interest): {uzs(metrics.get('expected_outstanding'))}",
        f"Interest received to date: {uzs(metrics.get('interest_received'))}",
        f"Write-offs: {uzs(metrics.get('writeoffs'))}",
        f"Positions: {len(positions)} "
        f"(active {len(metrics.get('active', []))}, "
        f"settled {len(metrics.get('settled', []))}, "
        f"defaulted {len(metrics.get('defaulted', []))})",
        "",
        "Position detail (invoice | debtor | sector | grade | invested | expected | status | due):",
    ]
    for p in positions[:60]:
        due = p.get("due_date")
        due_s = due.date().isoformat() if hasattr(due, "date") else (str(due) if due else "—")
        lines.append(
            f"- {p.get('invoice_number','—')} | {p.get('debtor_name','—')} | "
            f"{p.get('sector','—')} | {p.get('risk_grade','—')} | "
            f"{uzs(p.get('investment_amount'))} | {uzs(p.get('expected_return_amount'))} | "
            f"{p.get('status','—')} | {due_s}"
        )
    if len(positions) > 60:
        lines.append(f"...and {len(positions) - 60} more positions.")
    return "\n".join(lines)
