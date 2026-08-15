"""Back-office workspace modules — CRM (sales pipeline), Drive, Docs, Mail.

Ports of the Fast* apps (FastCRM / FastDrive / FastDocs / FastMail) rendered
inside Factorio's left-nav app shell. **Persisted to Postgres** (step 10): each
module has a table, seeded once from the shapes below, with real write paths —
CRM deals advance stage, mail messages mark read — so state survives restarts.
"""

from __future__ import annotations

import hmac

from fasthtml.common import Div, P, Span, A, Button, Form, H3, Input, NotStr
from starlette.responses import RedirectResponse

from app import rt
from utils.i18n import get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, current_role, current_subrole
from utils.access import context_for

try:
    from db import fetch_all, fetch_one, execute
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False

# ── Seed data (mirrors the Fast* apps; loaded into Postgres on first use) ──
DEAL_STAGES = ["Qualification", "Demo", "Proposal", "Negotiation", "Ready to close"]
SEED_DEALS = [
    ("Globex Corporation", "Reverse-factoring programme", "Qualification", 120000, "Aziza K."),
    ("Bright Textiles", "Invoice discounting facility", "Qualification", 60000, "Bek T."),
    ("Meridian Logistics", "Factoring — logistics", "Demo", 45000, "Aziza K."),
    ("Grand Plaza Hotels", "Hospitality SCF", "Demo", 210000, "Dmitry P."),
    ("Greenfield Agro", "Seasonal working capital", "Proposal", 90000, "Bek T."),
    ("Summit Retail", "Supplier finance", "Proposal", 75000, "Aziza K."),
    ("Helios Energy", "Contractor receivables", "Negotiation", 320000, "Dmitry P."),
    ("Vitalis Pharma", "Healthcare receivables", "Negotiation", 130000, "Bek T."),
    ("Vertex Construction", "Milestone financing", "Ready to close", 180000, "Aziza K."),
]
SEED_FILES = [
    ("📁", "Client agreements", "folder", "—", "2d ago"),
    ("📁", "E-invoice exports", "folder", "—", "1d ago"),
    ("📄", "Globex_master_agreement.pdf", "pdf", "180 KB", "2d ago"),
    ("📄", "INV-1042_assignment.pdf", "pdf", "42 KB", "5h ago"),
    ("📊", "Portfolio_aging_2026Q3.xlsx", "sheet", "88 KB", "3h ago"),
    ("🖼️", "Warehouse_collateral.jpg", "image", "1.2 MB", "1d ago"),
    ("📄", "KYC_Greenfield_Agro.pdf", "pdf", "260 KB", "6h ago"),
]
SEED_DOCS = [
    ("Credit policy — v3", "Underwriting", "Advance rates, concentration limits and grade thresholds…", 1240, True),
    ("Onboarding checklist", "Operations", "KYC/AML steps for new clients and debtors…", 480, True),
    ("Collections playbook", "Collections", "Dunning cadence, dispute handling and write-off rules…", 760, False),
    ("SPV term sheet (DIFC)", "Capital", "Structure, waterfall and investor reporting…", 2100, False),
]
SEED_MAIL = [
    ("David Chen", "Re: Factorio proposal", "Thanks — let's schedule a call next week…", "10:24", False),
    ("Globex Corporation AP", "Invoice INV-20260012 confirmed", "We confirm the obligation on the e-invoice network…", "09:12", False),
    ("CRIF Bureau", "Debtor report ready", "The credit report for Meridian Logistics is available…", "Yesterday", True),
    ("Oleg Kim", "Pipeline review", "Attaching the updated deal list for this week…", "Yesterday", True),
    ("E-Invoice Network", "Daily e-invoice digest", "42 new buyer-confirmed invoices for your clients…", "Mon", True),
]


def _ensure():
    if not _HAS_DB:
        return
    execute("""CREATE TABLE IF NOT EXISTS factorio.crm_deals (
        id BIGSERIAL PRIMARY KEY, client TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
        stage TEXT NOT NULL, value NUMERIC(15,2) NOT NULL DEFAULT 0, owner TEXT NOT NULL DEFAULT '',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
    execute("""CREATE TABLE IF NOT EXISTS factorio.drive_files (
        id BIGSERIAL PRIMARY KEY, icon TEXT NOT NULL DEFAULT '📄', name TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'file', size TEXT NOT NULL DEFAULT '—',
        updated_label TEXT NOT NULL DEFAULT '')""")
    execute("""CREATE TABLE IF NOT EXISTS factorio.workspace_docs (
        id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, folder TEXT NOT NULL DEFAULT '',
        excerpt TEXT NOT NULL DEFAULT '', words INT NOT NULL DEFAULT 0,
        published BOOLEAN NOT NULL DEFAULT FALSE)""")
    execute("""CREATE TABLE IF NOT EXISTS factorio.mail_messages (
        id BIGSERIAL PRIMARY KEY, sender TEXT NOT NULL, subject TEXT NOT NULL DEFAULT '',
        snippet TEXT NOT NULL DEFAULT '', when_label TEXT NOT NULL DEFAULT '',
        is_read BOOLEAN NOT NULL DEFAULT FALSE, sort_order INT NOT NULL DEFAULT 0)""")


def seed_workspace() -> dict:
    _ensure()
    if not _HAS_DB:
        return {}
    counts = {}
    if not fetch_one("SELECT 1 FROM factorio.crm_deals LIMIT 1"):
        for client, desc, stage, val, owner in SEED_DEALS:
            execute("INSERT INTO factorio.crm_deals (client,description,stage,value,owner) "
                    "VALUES (%(c)s,%(d)s,%(s)s,%(v)s,%(o)s)",
                    {"c": client, "d": desc, "s": stage, "v": val, "o": owner})
        counts["deals"] = len(SEED_DEALS)
    if not fetch_one("SELECT 1 FROM factorio.drive_files LIMIT 1"):
        for icon, name, kind, size, when in SEED_FILES:
            execute("INSERT INTO factorio.drive_files (icon,name,kind,size,updated_label) "
                    "VALUES (%(i)s,%(n)s,%(k)s,%(s)s,%(w)s)",
                    {"i": icon, "n": name, "k": kind, "s": size, "w": when})
        counts["files"] = len(SEED_FILES)
    if not fetch_one("SELECT 1 FROM factorio.workspace_docs LIMIT 1"):
        for title, folder, excerpt, words, pub in SEED_DOCS:
            execute("INSERT INTO factorio.workspace_docs (title,folder,excerpt,words,published) "
                    "VALUES (%(t)s,%(f)s,%(e)s,%(w)s,%(p)s)",
                    {"t": title, "f": folder, "e": excerpt, "w": words, "p": pub})
        counts["docs"] = len(SEED_DOCS)
    if not fetch_one("SELECT 1 FROM factorio.mail_messages LIMIT 1"):
        for i, (sender, subject, snippet, when, read) in enumerate(SEED_MAIL):
            execute("INSERT INTO factorio.mail_messages (sender,subject,snippet,when_label,is_read,sort_order) "
                    "VALUES (%(s)s,%(su)s,%(sn)s,%(w)s,%(r)s,%(o)s)",
                    {"s": sender, "su": subject, "sn": snippet, "w": when, "r": read, "o": i})
        counts["mail"] = len(SEED_MAIL)
    return counts


def _q(sql, params=None):
    if not _HAS_DB:
        return []
    try:
        return fetch_all(sql, params or {})
    except Exception:
        return []


def _usd(v):
    return f"${float(v):,.0f}"


# ── CRM ────────────────────────────────────────────────────────────────────

# Per-stage accent colour + win-probability (for weighted pipeline value).
STAGE_COLORS = {"Qualification": "#9AA98F", "Demo": "#C89B5B", "Proposal": "#5B8FB0",
                "Negotiation": "#C87F5B", "Ready to close": "#1F5D43"}
STAGE_PROB = {"Qualification": 0.10, "Demo": 0.25, "Proposal": 0.50,
              "Negotiation": 0.70, "Ready to close": 0.90}


def pipeline_summary() -> str:
    """One-line pipeline summary for the AI Assistant's sales_pipeline tool."""
    deals = _q("SELECT stage, value FROM factorio.crm_deals")
    if not deals:
        return "The sales pipeline has no deals yet."
    by = {}
    for d in deals:
        s = by.setdefault(d["stage"], [0, 0]); s[0] += 1; s[1] += float(d["value"])
    total = sum(v for _, v in by.values())
    weighted = sum(float(d["value"]) * STAGE_PROB.get(d["stage"], 0.3) for d in deals)
    parts = [f"{st}: {by[st][0]} deals / ${by[st][1]:,.0f}" for st in DEAL_STAGES if st in by]
    return (f"Open pipeline ${total:,.0f} across {len(deals)} deals "
            f"(${weighted:,.0f} weighted) — " + "; ".join(parts))


def _heat(value: float) -> str:
    return "#B83A3A" if value >= 200_000 else "#C89B5B" if value >= 100_000 else "#7A9E88"


def _kpi(label, value, sub=""):
    return Div(P(label, cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-2"),
              P(value, cls="text-2xl font-medium tracking-tight text-ink"),
              P(sub, cls="text-ink-muted text-xs mt-0.5") if sub else None,
              cls="p-5 rounded-2xl bg-bg-elevated border border-line")


@rt("/app/crm")
def crm(req):
    lang = get_lang(req)
    try:
        seed_workspace()
    except Exception:
        pass
    deals = _q("SELECT id,client,description,stage,value,owner FROM factorio.crm_deals ORDER BY value DESC")
    can_edit = current_role(req) == "admin"

    total_val = sum(float(d["value"]) for d in deals)
    weighted = sum(float(d["value"]) * STAGE_PROB.get(d["stage"], 0.3) for d in deals)
    ready = [d for d in deals if d["stage"] == "Ready to close"]
    summary = Div(
        _kpi("Open pipeline", _usd(total_val), f"{len(deals)} deals"),
        _kpi("Weighted value", _usd(weighted), "probability-adjusted"),
        _kpi("Ready to close", _usd(sum(float(d['value']) for d in ready)), f"{len(ready)} deals"),
        _kpi("Avg deal size", _usd(total_val / len(deals)) if deals else "$0", "across pipeline"),
        cls="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8")

    cols = []
    for stage in DEAL_STAGES:
        col_deals = [d for d in deals if d["stage"] == stage]
        total = sum(float(d["value"]) for d in col_deals)
        next_stage = DEAL_STAGES[DEAL_STAGES.index(stage) + 1] if stage != DEAL_STAGES[-1] else None
        color = STAGE_COLORS.get(stage, "#CFC8B4")
        cards = []
        for d in col_deals:
            v = float(d["value"])
            advance = None
            if can_edit and next_stage:
                advance = Form(
                    Input(type="hidden", name="deal_id", value=d["id"]),
                    Input(type="hidden", name="csrf", value=context_for(req).csrf_token),
                    Button(NotStr(f"→ {next_stage}"), type="submit",
                           cls="text-[11px] text-accent hover:underline mt-2 inline-block"),
                    method="post", action="/app/crm/advance",
                )
            cards.append(Div(
                Div(Span("", cls="inline-block w-2 h-2 rounded-full mr-2 align-middle",
                         style=f"background:{_heat(v)}"),
                    Span(d["client"], cls="text-sm font-medium text-ink align-middle"),
                    cls="mb-1"),
                P(d["description"], cls="text-xs text-ink-muted"),
                Div(Span(_usd(v), cls="text-sm font-semibold text-accent"),
                    Span(d["owner"], cls="text-[11px] text-ink-dim"),
                    cls="flex items-center justify-between mt-2"),
                advance,
                cls="p-3 rounded-xl bg-bg-elevated border border-line mb-2"))
        cols.append(Div(
            Div(Span(stage, cls="text-xs font-mono uppercase tracking-wider text-ink"),
                Span(f"{len(col_deals)} · {_usd(total)}", cls="text-[11px] text-ink-muted"),
                cls="flex items-center justify-between mb-3 pb-2 px-1",
                style=f"border-bottom:2px solid {color}"),
            *cards,
            cls="min-w-[228px] flex-1 p-2 rounded-2xl bg-bg-raised/40"))
    return app_page(
        "Sales pipeline",
        Section_(Eyebrow("Sales · CRM"),
                 Heading(1, "Sales pipeline", cls="mt-4"),
                 P(f"{len(deals)} open deals worth {_usd(total_val)} — {_usd(weighted)} weighted by stage.",
                   cls="mt-3 text-ink-muted max-w-3xl"),
                 cls="border-t border-line"),
        Section_(summary,
                 Div(*cols, cls="flex gap-3 overflow-x-auto pb-4"),
                 cls="border-t border-line"),
        current_path="/app/crm", lang=lang, role=current_role(req), subrole=current_subrole(req),
    )


@rt("/app/crm/advance", methods=["POST"])
def crm_advance(req, deal_id: int = 0, csrf: str = ""):
    if not csrf or not hmac.compare_digest(str(req.session.get("csrf_token") or ""), csrf):
        return RedirectResponse("/app", status_code=303)
    if current_role(req) == "admin" and _HAS_DB:
        row = fetch_one("SELECT stage FROM factorio.crm_deals WHERE id=%(i)s", {"i": deal_id})
        if row and row["stage"] in DEAL_STAGES:
            idx = DEAL_STAGES.index(row["stage"])
            if idx < len(DEAL_STAGES) - 1:
                execute("UPDATE factorio.crm_deals SET stage=%(s)s, updated_at=now() WHERE id=%(i)s",
                        {"s": DEAL_STAGES[idx + 1], "i": deal_id})
    return RedirectResponse("/app/crm", status_code=303)


# ── Drive ───────────────────────────────────────────────────────────────────

@rt("/app/drive")
def drive(req):
    lang = get_lang(req)
    try:
        seed_workspace()
    except Exception:
        pass
    files = _q("SELECT icon,name,kind,size,updated_label FROM factorio.drive_files ORDER BY id")
    tiles = [
        Div(Span(f["icon"], cls="text-3xl"),
            P(f["name"], cls="text-sm text-ink mt-2 truncate"),
            P(f"{f['size']} · {f['updated_label']}", cls="text-[11px] text-ink-dim mt-0.5"),
            cls="p-5 rounded-2xl bg-bg-elevated border border-line hover:border-accent transition-colors")
        for f in files
    ]
    return app_page(
        "Drive",
        Section_(Eyebrow("Workspace · Drive"),
                 Heading(1, "Document drive", cls="mt-4"),
                 P("Invoice, KYC and collateral documents — folders, sharing and public links.",
                   cls="mt-3 text-ink-muted max-w-3xl"), cls="border-t border-line"),
        Section_(Div(*tiles, cls="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4"),
                 cls="border-t border-line"),
        current_path="/app/drive", lang=lang, role=current_role(req), subrole=current_subrole(req),
    )


# ── Docs ─────────────────────────────────────────────────────────────────────

@rt("/app/docs")
def docs(req):
    lang = get_lang(req)
    try:
        seed_workspace()
    except Exception:
        pass
    rows = _q("SELECT title,folder,excerpt,words,published FROM factorio.workspace_docs ORDER BY id")
    cards = [
        Div(Div(Span(d["folder"], cls="text-[11px] font-mono uppercase tracking-wider text-accent"),
                Span("Published" if d["published"] else "Draft",
                     cls="text-[11px] " + ("text-green-700" if d["published"] else "text-ink-dim")),
                cls="flex items-center justify-between"),
            H3(d["title"], cls="text-ink text-lg font-medium mt-1"),
            P(d["excerpt"], cls="text-sm text-ink-muted mt-1"),
            P(f"{d['words']} words", cls="text-[11px] text-ink-dim mt-2"),
            cls="p-6 rounded-2xl bg-bg-elevated border border-line")
        for d in rows
    ]
    return app_page(
        "Docs",
        Section_(Eyebrow("Workspace · Docs"),
                 Heading(1, "Documents", cls="mt-4"),
                 P("Policies, playbooks and term sheets — block editor, templates and version history.",
                   cls="mt-3 text-ink-muted max-w-3xl"), cls="border-t border-line"),
        Section_(Div(*cards, cls="grid md:grid-cols-2 gap-4"), cls="border-t border-line"),
        current_path="/app/docs", lang=lang, role=current_role(req), subrole=current_subrole(req),
    )


# ── Mail ─────────────────────────────────────────────────────────────────────

@rt("/app/mail")
def mail(req):
    lang = get_lang(req)
    try:
        seed_workspace()
    except Exception:
        pass
    msgs = _q("SELECT id,sender,subject,snippet,when_label,is_read FROM factorio.mail_messages ORDER BY sort_order")
    unread = sum(1 for m in msgs if not m["is_read"])
    rows = [Form(
        Input(type="hidden", name="msg_id", value=m["id"]),
        Input(type="hidden", name="csrf", value=context_for(req).csrf_token),
        Button(
            Span("●", cls=("text-accent" if not m["is_read"] else "text-transparent") + " text-xs mr-3"),
            Div(P(m["sender"], cls="text-sm font-medium text-ink"),
                P(Span(m["subject"], cls="text-ink"), Span(" — " + m["snippet"], cls="text-ink-muted"),
                  cls="text-sm truncate"), cls="flex-1 min-w-0"),
            Span(m["when_label"], cls="text-[11px] text-ink-dim ml-3 whitespace-nowrap"),
            type="submit",
            cls="w-full flex items-center py-3 px-4 border-b border-line hover:bg-bg-raised/40 text-left",
        ),
        method="post", action="/app/mail/read",
    ) for m in msgs]
    return app_page(
        "Mail",
        Section_(Eyebrow("Workspace · Mail"),
                 Heading(1, "Inbox", cls="mt-4"),
                 P(f"{unread} unread · client, debtor and bureau correspondence — threads, labels and AI draft replies.",
                   cls="mt-3 text-ink-muted max-w-3xl"),
                 A("Borrower email templates →", href="/app/mail/templates",
                   cls="inline-block mt-4 text-sm text-accent"),
                 cls="border-t border-line"),
        Section_(Div(*rows, cls="rounded-2xl bg-bg-elevated border border-line overflow-hidden"),
                 cls="border-t border-line"),
        current_path="/app/mail", lang=lang, role=current_role(req), subrole=current_subrole(req),
    )


@rt("/app/mail/templates")
def mail_templates(req):
    if current_role(req) != "admin":
        return RedirectResponse("/app", status_code=303)
    from utils.email_templates import TEMPLATE_NAMES, render_email_template

    cards = []
    names = {
        "bank_connection": "Connect your bank account",
        "accounting_connection": "Connect your accounting system",
    }
    for kind in TEMPLATE_NAMES:
        rendered = render_email_template(
            kind, first_name="Julian", resume_url="https://factorio.co.uk/app"
        )
        cards.append(Div(
            Div(Span("DRAFT ONLY", cls="text-[10px] font-mono text-amber-700"),
                Span("Postmark not configured", cls="text-[10px] text-ink-dim"),
                cls="flex justify-between"),
            H3(names[kind], cls="text-lg font-semibold mt-3"),
            P("Subject: " + rendered["subject"], cls="text-sm font-medium mt-2"),
            P(rendered["preheader"], cls="text-xs text-ink-muted mt-1"),
            Div(P(rendered["body"], cls="text-sm leading-relaxed whitespace-pre-wrap"),
                cls="mt-5 p-5 rounded-xl bg-white border border-line"),
            cls="p-6 rounded-2xl bg-bg-elevated border border-line"))
    return app_page(
        "Borrower email templates",
        Section_(Eyebrow("Workspace · Transactional email"),
                 Heading(1, "Borrower connection reminders", cls="mt-4"),
                 P("Factorio-branded templates for paused bank connections and optional "
                   "accounting-system connections. Customer Service can render drafts; "
                   "delivery stays disabled until Postmark and approval controls are configured.",
                   cls="mt-3 text-ink-muted max-w-3xl"),
                 cls="border-t border-line"),
        Section_(Div(*cards, cls="grid xl:grid-cols-2 gap-6"), cls="border-t border-line"),
        current_path="/app/mail", lang=get_lang(req), role="admin",
        subrole=current_subrole(req),
    )


@rt("/app/mail/read", methods=["POST"])
def mail_read(req, msg_id: int = 0, csrf: str = ""):
    if not csrf or not hmac.compare_digest(str(req.session.get("csrf_token") or ""), csrf):
        return RedirectResponse("/app", status_code=303)
    if _HAS_DB:
        try:
            execute("UPDATE factorio.mail_messages SET is_read=TRUE WHERE id=%(i)s", {"i": msg_id})
        except Exception:
            pass
    return RedirectResponse("/app/mail", status_code=303)
