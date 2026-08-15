"""AI assistant routes — chat-based loan triage and investor reporting.

Two Grok-powered (x.ai) chat surfaces, both HTMX-driven with no server-side
session store: each turn round-trips the full transcript in a hidden field, the
server appends the new user/assistant turns and re-renders the panel.

  * /app/triage    — seller-facing invoice-application triage assistant
  * /app/assistant — investor-facing reporting assistant, grounded in the
                     current investor's own portfolio positions

Both degrade gracefully when XAI_API_KEY is unset (see utils.ai.ai_available).
"""

from __future__ import annotations

import html
import json
import re

from fasthtml.common import (
    Div, P, Span, Form, Input, Button, Textarea, NotStr, Hidden,
)

from app import rt
from utils.i18n import t, get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, list_investors, current_investor, current_role
from app_routes.portfolio import _load_positions, _compute
from utils import ai


# ── Rendering ───────────────────────────────────────────────────────────

def _render_markdown(text: str):
    """Minimal, safe markdown → HTML for assistant bubbles.

    Escapes first, then applies **bold**, `code`, and turns leading "- "/"* "
    into bullets. Newlines are preserved by ``whitespace-pre-wrap`` on the bubble.
    """
    esc = html.escape(text)
    esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
    esc = re.sub(r"`([^`]+)`", r"<code class='px-1 rounded bg-bg-raised'>\1</code>", esc)
    esc = re.sub(r"(?m)^\s*[-*]\s+", "• ", esc)
    return NotStr(esc)


def _bubble(role: str, content: str, lang: str):
    is_user = role == "user"
    who = t("ai_you", lang) if is_user else t("ai_bot", lang)
    align = "items-end" if is_user else "items-start"
    tone = ("bg-accent text-bg" if is_user
            else "bg-bg-elevated border border-line text-ink")
    body = content if is_user else _render_markdown(content)
    return Div(
        Span(who, cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-1"),
        Div(body, cls=f"px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap max-w-[85%] {tone}"),
        cls=f"flex flex-col {align} gap-0.5",
    )


def _chat_panel(kind: str, messages: list[dict], lang: str, *, thinking: bool = False):
    """Render the whole chat panel (messages + input form). Swapped as one unit."""
    send_url = f"/app/{'triage' if kind == 'triage' else 'assistant'}/send"
    placeholder = t(f"ai_{kind}_placeholder", lang)

    bubbles = [_bubble(m["role"], m["content"], lang) for m in messages]
    if thinking:
        bubbles.append(Div(
            Span(t("ai_bot", lang), cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-1"),
            Div(t("ai_thinking", lang), cls="px-4 py-3 rounded-2xl text-sm bg-bg-elevated border border-line text-ink-muted italic"),
            cls="flex flex-col items-start gap-0.5",
        ))

    disabled = not ai.ai_available()
    form = Form(
        Hidden(name="history", value=json.dumps(messages)),
        Div(
            Textarea(
                "", name="message", rows="2", placeholder=placeholder,
                required=True, disabled=disabled,
                cls="flex-1 resize-none bg-bg-elevated border border-line-bright rounded-2xl "
                    "px-4 py-3 text-sm text-ink focus:outline-none focus:border-accent disabled:opacity-50",
                onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();this.form.requestSubmit();}",
            ),
            Button(
                t("ai_send", lang), type="submit", disabled=disabled,
                cls="shrink-0 px-5 py-3 rounded-full text-sm font-medium bg-accent text-bg "
                    "hover:bg-ink transition-all disabled:opacity-50 self-end",
            ),
            cls="flex items-end gap-3",
        ),
        hx_post=send_url,
        hx_target=f"#chat-{kind}",
        hx_swap="outerHTML",
        hx_disabled_elt="find button, find textarea",
        cls="mt-4",
    )

    notice = (P(t("ai_disabled", lang), cls="text-xs text-ink-dim mt-3") if disabled else None)

    return Div(
        Div(*bubbles, cls="flex flex-col gap-5 overflow-y-auto max-h-[52vh] pr-1",
            id=f"chat-{kind}-log"),
        form,
        notice,
        id=f"chat-{kind}",
        cls="p-6 md:p-7 rounded-2xl bg-bg-raised/40 border border-line",
    )


def _greeting(kind: str, lang: str) -> list[dict]:
    return [{"role": "assistant", "content": t(f"ai_{kind}_greeting", lang)}]


def _parse_history(raw: str) -> list[dict]:
    try:
        h = json.loads(raw) if raw else []
        return [m for m in h if isinstance(m, dict) and m.get("role") in ("user", "assistant")]
    except (ValueError, TypeError):
        return []


# ── Triage (seller) ─────────────────────────────────────────────────────

@rt("/app/triage")
def triage(req):
    lang = get_lang(req)
    investors = list_investors(req)
    investor = current_investor(req, investors)
    return app_page(
        t("ai_triage_eyebrow", lang),
        Section_(
            Eyebrow(t("ai_triage_eyebrow", lang)),
            Heading(1, t("ai_triage_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("ai_triage_lede", lang), cls="mt-4 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        Section_(_chat_panel("triage", _greeting("triage", lang), lang), cls="border-t border-line pt-0"),
        current_path="/app/triage", lang=lang, role=current_role(req), investor=investor, investors=investors,
    )


@rt("/app/triage/send")
def triage_send(req, message: str = "", history: str = ""):
    lang = get_lang(req)
    msgs = _parse_history(history)
    message = (message or "").strip()
    if not message:
        return _chat_panel("triage", msgs, lang)
    msgs.append({"role": "user", "content": message})
    reply = ai.chat(ai.build_conversation(ai.triage_system_prompt(lang), msgs[:-1], message))
    msgs.append({"role": "assistant", "content": reply})
    return _chat_panel("triage", msgs, lang)


# ── Reporting (investor) ────────────────────────────────────────────────

@rt("/app/assistant")
def assistant(req):
    lang = get_lang(req)
    investors = list_investors(req)
    investor = current_investor(req, investors)
    return app_page(
        t("ai_assistant_eyebrow", lang),
        Section_(
            Eyebrow(t("ai_assistant_eyebrow", lang)),
            Heading(1, t("ai_assistant_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("ai_assistant_lede", lang), cls="mt-4 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        Section_(_chat_panel("assistant", _greeting("assistant", lang), lang), cls="border-t border-line pt-0"),
        current_path="/app/assistant", lang=lang, role=current_role(req), investor=investor, investors=investors,
    )


@rt("/app/assistant/send")
def assistant_send(req, message: str = "", history: str = ""):
    lang = get_lang(req)
    msgs = _parse_history(history)
    message = (message or "").strip()
    if not message:
        return _chat_panel("assistant", msgs, lang)
    msgs.append({"role": "user", "content": message})

    investor = current_investor(req)
    positions = _load_positions(investor["id"]) if investor else []
    metrics = _compute(positions)
    system = ai.reporting_system_prompt(ai.portfolio_context(investor, metrics, positions), lang)
    reply = ai.chat(ai.build_conversation(system, msgs[:-1], message))
    msgs.append({"role": "assistant", "content": reply})
    return _chat_panel("assistant", msgs, lang)
