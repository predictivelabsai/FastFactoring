"""Back-office admin console + role-scoped pages.

RBAC roles are investor, supplier, payer, and admin. The single admin role has
full back-office authority; legacy subrole checks resolve to ``super`` only for
the authenticated sole-admin identity.

Every state-changing action is written to an **audit log**
(`factorio.audit_log`, created lazily). This is a demo: actions log and confirm
rather than mutating synthetic data destructively.
"""

from __future__ import annotations

import hmac
from datetime import date, datetime

from fasthtml.common import (
    Div, P, Span, A, Article, Table, Thead, Tbody, Tr, Th, Td, NotStr, Titled,
    Form, Select, Option, Button, Img, Input,
)
from starlette.responses import RedirectResponse, Response

from app import rt
from utils.i18n import t, get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, fmt_uzs, current_role, current_subrole
from utils.access import context_for

try:
    from db import connect, fetch_all, fetch_one, execute
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False

# Which sub-roles may perform which sensitive actions (segregation of duties).
CAN_APPROVE_FUNDING = {"finance", "super"}
CAN_SET_LIMITS = {"credit", "compliance", "super"}


# ── Audit log ─────────────────────────────────────────────────────────────

def _ensure_audit():
    if not _HAS_DB:
        return
    try:
        execute("""
            CREATE TABLE IF NOT EXISTS factorio.audit_log (
                id BIGSERIAL PRIMARY KEY,
                actor TEXT NOT NULL,
                role TEXT NOT NULL,
                action TEXT NOT NULL,
                entity TEXT NOT NULL DEFAULT '',
                detail TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    except Exception:
        pass


def log_action(role: str, subrole: str, action: str, entity: str = "", detail: str = ""):
    _ensure_audit()
    if not _HAS_DB:
        return
    try:
        actor = f"admin:{subrole}" if role == "admin" else role
        execute("INSERT INTO factorio.audit_log (actor, role, action, entity, detail) "
                "VALUES (%(a)s, %(r)s, %(ac)s, %(e)s, %(d)s)",
                {"a": actor, "r": role, "ac": action, "e": entity, "d": detail})
    except Exception:
        pass


def _audit_rows(limit: int = 40) -> list[dict]:
    _ensure_audit()
    if not _HAS_DB:
        return []
    try:
        rows = fetch_all("SELECT actor, role, action, entity, detail, created_at "
                         "FROM factorio.audit_log ORDER BY created_at DESC LIMIT %(n)s", {"n": limit})
        if not rows:  # seed a few illustrative entries the first time
            for a, r, ac, e in [
                ("admin:credit", "admin", "score.assign", "invoice INV-20260012"),
                ("admin:finance", "admin", "funding.release", "funding #14"),
                ("admin:compliance", "admin", "kyc.approve", "company Artel LLC"),
                ("admin:collections", "admin", "dunning.send", "invoice INV-20260007"),
            ]:
                log_action("admin", a.split(":")[1], ac, e, "seed")
            rows = fetch_all("SELECT actor, role, action, entity, detail, created_at "
                             "FROM factorio.audit_log ORDER BY created_at DESC LIMIT %(n)s", {"n": limit})
        return rows
    except Exception:
        return []


# ── shared UI ───────────────────────────────────────────────────────────

_TH = "text-left text-[11px] font-mono tracking-widest uppercase text-ink-dim py-3 px-4"
_TD = "py-3 px-4 text-sm text-ink"
_TDR = _TD + " text-right"


def _guard(req):
    """Only the admin role reaches /app/admin/*; others get bounced to /app."""
    if current_role(req) != "admin":
        return RedirectResponse("/app", status_code=303)
    return None


def _card(label, value, sub=""):
    return Article(
        P(label, cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-3"),
        P(value, cls="text-3xl md:text-4xl font-medium tracking-tighter text-ink mb-1"),
        P(sub, cls="text-ink-muted text-sm") if sub else None,
        cls="p-7 rounded-2xl bg-bg-elevated border border-line",
    )


def _table(headers, rows):
    return Div(Table(
        Thead(Tr(*[Th(h, cls=_TH) for h in headers], cls="border-b border-line")),
        Tbody(*rows),
        cls="w-full",
    ), cls="rounded-2xl bg-bg-elevated border border-line overflow-hidden overflow-x-auto")


def _view_btn(invoice_number: str, search: str = ""):
    """A 'View' pill that opens the invoice PDF in the right pane, highlighting `search`."""
    num = (invoice_number or "").replace("'", "")
    term = (search or "").replace("'", "")
    return A("View", href="#", onclick=f"return fcShowPdf('{num}','{term}')", cls="pdf-view-btn")


def _admin_page(req, current_path, title_key, *content):
    lang = get_lang(req)
    return app_page(
        t(title_key, lang),
        Section_(Eyebrow(t("admin_eyebrow", lang)),
                 Heading(1, t(title_key, lang), cls="mt-4 max-w-4xl"),
                 P(t("admin_lede", lang), cls="mt-4 text-ink-muted text-lg max-w-3xl leading-relaxed"),
                 cls="border-t border-line"),
        Section_(*content, cls="border-t border-line"),
        current_path=current_path, lang=lang,
        role="admin", subrole=current_subrole(req),
    )


def _q(sql, params=None, one=False):
    if not _HAS_DB:
        return None if one else []
    try:
        return (fetch_one if one else fetch_all)(sql, params or {})
    except Exception:
        return None if one else []


# ── Console ───────────────────────────────────────────────────────────────

@rt("/app/admin")
def admin_console(req):
    g = _guard(req)
    if g:
        return g
    lang = get_lang(req)
    stats = _q("""
        SELECT COUNT(DISTINCT c.id) AS clients,
               COUNT(DISTINCT i.id) AS invoices,
               COALESCE(SUM(f.amount_raised),0) AS funded,
               COUNT(DISTINCT CASE WHEN i.status='funding' THEN i.id END) AS active,
               COUNT(DISTINCT CASE WHEN i.status='defaulted' THEN i.id END) AS defaulted
        FROM factorio.companies c
        LEFT JOIN factorio.invoices i ON i.company_id = c.id
        LEFT JOIN factorio.invoice_funding f ON f.invoice_id = i.id
    """, one=True) or {}
    kpis = Div(
        _card(t("nav_admin_onboarding", lang), str(stats.get("clients", 0)), "clients & debtors"),
        _card("Invoices", str(stats.get("invoices", 0)), "in the book"),
        _card("Funded volume", fmt_uzs(stats.get("funded", 0)), "financed to date"),
        _card(t("nav_admin_risk", lang), str(stats.get("active", 0)), "active exposures"),
        cls="grid md:grid-cols-2 lg:grid-cols-4 gap-4",
    )
    # Every built function surfaced as a card, grouped by domain.
    groups = [
        ("grp_backoffice", [
            ("nav_admin_onboarding", "/app/admin/onboarding", "Clients, debtors, KYC & facility limits"),
            ("nav_processing", "/app/admin/processing", "Verification, assignment, holdback/reserve"),
            ("nav_admin_risk", "/app/admin/risk", "Scoring, exposure, aging, fraud checks"),
            ("nav_scoring", "/app/admin/scoring", "Multi-signal score + model back-testing"),
            ("nav_admin_funding", "/app/admin/funding", "Approvals (SoD), disbursement"),
            ("nav_collections", "/app/admin/collections", "Dunning, escalation, write-offs, provisioning"),
            ("nav_accounting", "/app/admin/accounting", "Double-entry ledger, trial balance, reconciliation"),
            ("nav_admin_reports", "/app/admin/reports", "DSO, recovery, default, portfolio"),
            ("nav_compliance", "/app/admin/compliance", "AML/KYC posture, retention, audit export"),
            ("nav_admin_audit", "/app/admin/audit", "Every action, immutable"),
            ("nav_integrations", "/app/admin/integrations", "Accounting, banking, bureau, e-sign, webhooks"),
        ]),
        ("mkt_eyebrow", [
            ("mkt_eyebrow", "/app/marketplace", "Browse fundable invoices"),
            ("nav_auctions", "/app/marketplace/auctions", "Reverse auction — bid the fee down"),
            ("nav_secondary", "/app/marketplace/secondary", "Secondary market — trade positions"),
        ]),
        ("sec_sales", [
            ("nav_pipeline", "/app/crm", "CRM deal pipeline by stage"),
        ]),
        ("sec_workspace", [
            ("nav_drive", "/app/drive", "Invoice, KYC & collateral documents"),
            ("nav_docs", "/app/docs", "Policies, playbooks, term sheets"),
            ("nav_mail", "/app/mail", "Client, debtor & bureau correspondence"),
        ]),
    ]

    def _group(title_key, items):
        cards = Div(*[
            A(Div(P(t(k, lang), cls="text-ink text-lg font-medium mb-1"),
                  P(desc, cls="text-ink-muted text-sm")),
              href=href, cls="block p-6 rounded-2xl bg-bg-elevated border border-line hover:border-accent transition-colors")
            for k, href, desc in items
        ], cls="grid md:grid-cols-2 lg:grid-cols-3 gap-4")
        return Div(
            P(t(title_key, lang), cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-3 mt-8"),
            cards)

    sections = Div(*[_group(k, items) for k, items in groups], cls="mt-2")
    return _admin_page(req, "/app/admin", "admin_h1", kpis, sections)


@rt("/app/admin/settings", methods=["GET", "POST"])
async def admin_global_settings(req):
    g = _guard(req)
    if g:
        return g
    from utils.money import SUPPORTED_CURRENCIES, display_currency, set_display_currency
    message = ""
    if req.method == "POST":
        form = await req.form()
        try:
            selected = set_display_currency(str(form.get("currency", "")))
            message = f"Global display currency changed to {selected}."
            log_action("admin", current_subrole(req), "settings.currency", "platform", selected)
        except ValueError:
            message = "Choose USD, GBP, EUR, or UZS."
    current = display_currency()
    selector = Form(
        Select(*[Option(code, value=code, selected=code == current)
                 for code in SUPPORTED_CURRENCIES],
               name="currency",
               cls="px-4 py-2.5 rounded-xl border border-line-bright bg-bg-elevated"),
        Button("Save global currency", type="submit",
               cls="px-5 py-2.5 rounded-full bg-accent text-bg font-medium"),
        method="post", action="/app/admin/settings",
        cls="flex flex-wrap items-center gap-3",
    )
    return _admin_page(
        req, "/app/admin/settings", "nav_global_settings",
        P(message, cls="mb-5 text-green-700") if message else None,
        P("Controls the display currency across dashboards, marketplace, portfolio, "
          "accounting, and other shared monetary views. Synthetic UZS-scale values "
          "are converted using the demo rates; source invoice currency remains unchanged.",
          cls="mb-5 text-ink-muted max-w-3xl"),
        selector,
    )


# Onboarding & facility limits are now the production module in app_routes/onboarding.py.


# ── Risk & underwriting ─────────────────────────────────────────────────

@rt("/app/admin/risk")
def admin_risk(req):
    g = _guard(req)
    if g:
        return g
    by_sector = _q("""
        SELECT i.sector, COUNT(*) AS n, COALESCE(SUM(i.amount),0) AS exposure
        FROM factorio.invoices i WHERE i.status IN ('funding','funded')
        GROUP BY i.sector ORDER BY exposure DESC
    """)
    by_debtor = _q("""
        SELECT i.debtor_name, COUNT(*) AS n, COALESCE(SUM(i.amount),0) AS exposure
        FROM factorio.invoices i WHERE i.status IN ('funding','funded')
        GROUP BY i.debtor_name ORDER BY exposure DESC LIMIT 8
    """)
    grades = _q("SELECT risk_grade, COUNT(*) AS n FROM factorio.invoices GROUP BY risk_grade ORDER BY risk_grade")
    dupes = _q("""
        SELECT debtor_name, amount, COUNT(*) AS n FROM factorio.invoices
        GROUP BY debtor_name, amount HAVING COUNT(*) > 1 ORDER BY n DESC LIMIT 5
    """)
    sec_rows = [Tr(Td(r["sector"], cls=_TD), Td(str(r["n"]), cls=_TDR),
                   Td(fmt_uzs(r["exposure"]), cls=_TDR + " text-accent"), cls="border-b border-line")
                for r in by_sector]
    deb_rows = [Tr(Td(r["debtor_name"], cls=_TD), Td(str(r["n"]), cls=_TDR),
                   Td(fmt_uzs(r["exposure"]), cls=_TDR + " text-accent"), cls="border-b border-line")
                for r in by_debtor]
    grade_str = "  ·  ".join(f"{r['risk_grade']}: {r['n']}" for r in grades)
    fraud = (P("No duplicate-invoice signals in the current book.", cls="text-ink-muted text-sm")
             if not dupes else Div(*[
                 P(f"⚠ {r['n']}× {r['debtor_name']} @ {fmt_uzs(r['amount'])} — review for duplication",
                   cls="text-sm text-red-700") for r in dupes]))
    return _admin_page(req, "/app/admin/risk", "nav_admin_risk",
                       Div(P("Risk-grade distribution", cls="text-sm font-medium text-ink mb-2"),
                           P(grade_str, cls="text-ink-muted"), cls="mb-6"),
                       Div(P("Exposure by sector", cls="text-sm font-medium text-ink mb-3"),
                           _table(["Sector", "Invoices", "Exposure"], sec_rows), cls="mb-8"),
                       Div(P("Concentration — top debtors", cls="text-sm font-medium text-ink mb-3"),
                           _table(["Debtor", "Invoices", "Exposure"], deb_rows), cls="mb-8"),
                       Div(P("Fraud / duplicate-invoice check", cls="text-sm font-medium text-ink mb-3"), fraud))


# ── Funding + collections (with SoD) ────────────────────────────────────

@rt("/app/admin/funding")
def admin_funding(req):
    g = _guard(req)
    if g:
        return g
    lang = get_lang(req)
    subrole = current_subrole(req)
    pipeline = _q("""
        SELECT i.invoice_number, i.debtor_name, i.amount, i.risk_grade, i.status,
               f.advance_rate_pct, f.amount_raised, f.funding_goal
        FROM factorio.invoices i
        LEFT JOIN factorio.invoice_funding f ON f.invoice_id = i.id
        WHERE i.status IN ('verified','funding') ORDER BY i.amount DESC LIMIT 25
    """)
    can_approve = subrole in CAN_APPROVE_FUNDING
    rows = []
    for p in pipeline:
        adv = fmt_uzs(float(p["amount"] or 0) * float(p["advance_rate_pct"] or 85) / 100)
        action = (Form(
                    Input(type="hidden", name="inv", value=p["invoice_number"]),
                    Input(type="hidden", name="csrf", value=context_for(req).csrf_token),
                    Button("Approve & release", type="submit",
                           cls="text-xs px-3 py-1 rounded-full bg-accent text-bg hover:bg-ink"),
                    method="post", action="/app/admin/funding/approve")
                  if can_approve else Span("—", cls="text-ink-dim text-xs"))
        rows.append(Tr(
            Td(p["invoice_number"], cls=_TD), Td(p["debtor_name"], cls=_TD),
            Td(p["risk_grade"], cls="py-3 px-4 text-center text-sm"),
            Td(fmt_uzs(p["amount"]), cls=_TDR), Td(adv, cls=_TDR + " text-accent"),
            Td(p["status"], cls=_TD), Td(action, cls="py-3 px-4 text-right"),
            cls="border-b border-line"))
    overdue = _q("""
        SELECT invoice_number, debtor_name, amount, due_date
        FROM factorio.invoices WHERE status='funding' AND due_date < CURRENT_DATE
        ORDER BY due_date LIMIT 12
    """)
    coll_rows = [Tr(Td(r["invoice_number"], cls=_TD), Td(r["debtor_name"], cls=_TD),
                    Td(fmt_uzs(r["amount"]), cls=_TDR),
                    Td(str(r["due_date"]), cls=_TD + " text-red-700"),
                    Td(Span("Dunning · reminder 2", cls="text-xs text-ink-muted"), cls="py-3 px-4"),
                    cls="border-b border-line") for r in overdue]
    sod = P(("You may approve funding (Finance / Super)." if can_approve else t("admin_restricted", lang)),
            cls="text-sm mb-4 " + ("text-ink-muted" if can_approve else "text-red-700"))
    return _admin_page(req, "/app/admin/funding", "nav_admin_funding",
                       sod,
                       Div(P("Funding pipeline", cls="text-sm font-medium text-ink mb-3"),
                           _table(["Invoice", "Debtor", "Grade", "Amount", "Advance", "Status", "Action"], rows),
                           cls="mb-8"),
                       Div(P("Collections — overdue", cls="text-sm font-medium text-ink mb-3"),
                           _table(["Invoice", "Debtor", "Amount", "Due", "Stage"], coll_rows)))


@rt("/app/admin/funding/approve", methods=["POST"])
def admin_funding_approve(req, inv: str = "", csrf: str = ""):
    g = _guard(req)
    if g:
        return g
    lang = get_lang(req)
    subrole = current_subrole(req)
    if not csrf or not hmac.compare_digest(str(req.session.get("csrf_token") or ""), csrf):
        return RedirectResponse("/app", status_code=303)
    if subrole not in CAN_APPROVE_FUNDING:
        msg = P(t("admin_restricted", lang), cls="text-red-700")
    else:
        released = False
        if _HAS_DB:
            try:
                with connect() as conn, conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(
                            """UPDATE factorio.invoices SET status='funded'
                                  WHERE invoice_number=%s AND status IN ('verified','funding')
                              RETURNING id""",
                            (inv,),
                        )
                        row = cur.fetchone()
                        if row:
                            cur.execute(
                                "UPDATE factorio.invoice_funding SET funding_status='funded' WHERE invoice_id=%s",
                                (row[0],),
                            )
                            released = True
            except Exception:
                released = False
        if released:
            log_action("admin", subrole, "funding.release", f"invoice {inv}", "approved via console")
            msg = P(NotStr(f"✔ Funding for <b>{inv}</b> approved and released. Action written to the audit log."),
                    cls="text-ink")
        else:
            msg = P("Funding was not released; the invoice was missing or no longer eligible.", cls="text-red-700")
    return _admin_page(req, "/app/admin/funding", "nav_admin_funding",
                       msg, P(A("← Back to funding", href="/app/admin/funding", cls="text-accent"), cls="mt-4"))


# ── Reports ─────────────────────────────────────────────────────────────

def _bars(rows, label_key, val_key, fmt=None):
    """Simple horizontal bar chart from (label, value) rows."""
    fmt = fmt or (lambda v: f"{v:,.0f}")
    mx = max((float(r[val_key] or 0) for r in rows), default=1) or 1
    out = []
    for r in rows:
        v = float(r[val_key] or 0)
        pct = max(2, round(v / mx * 100))
        out.append(Div(
            Div(Span(str(r[label_key]), cls="text-sm text-ink"),
                Span(fmt(v), cls="text-sm text-ink-muted tabular-nums"),
                cls="flex items-center justify-between mb-1"),
            Div(Div(cls="h-2 rounded-full bg-accent", style=f"width:{pct}%"),
                cls="h-2 rounded-full bg-bg-raised"),
            cls="mb-3"))
    return Div(*out)


@rt("/app/admin/reports")
def admin_reports(req):
    g = _guard(req)
    if g:
        return g
    m = _q("""
        SELECT COUNT(*) FILTER (WHERE status='settled') AS settled,
               COUNT(*) FILTER (WHERE status='defaulted') AS defaulted,
               COUNT(*) AS total,
               COALESCE(AVG(CASE WHEN status='settled' THEN (settlement_date - investment_date) END),0) AS avg_hold,
               COALESCE(SUM(investment_amount),0) AS deployed
        FROM factorio.investments
    """, one=True) or {}
    total = float(m.get("total") or 0) or 1
    settled = float(m.get("settled") or 0); defaulted = float(m.get("defaulted") or 0)
    dr = 100 * defaulted / total
    recovery = 100 * settled / (settled + defaulted) if (settled + defaulted) else 100.0
    fundedv = _q("SELECT COALESCE(SUM(amount_raised),0) v FROM factorio.invoice_funding", one=True) or {}
    dilution = _q("""SELECT COALESCE(SUM(i.amount) FILTER (WHERE i.status='defaulted'),0) d,
                            COALESCE(SUM(f.amount_raised),0) f
                     FROM factorio.invoices i JOIN factorio.invoice_funding f ON f.invoice_id=i.id""", one=True) or {}
    dil = 100 * float(dilution.get("d") or 0) / (float(dilution.get("f") or 0) or 1)
    by_sector = _q("""SELECT i.sector, COALESCE(SUM(f.amount_raised),0) AS funded
                      FROM factorio.invoices i JOIN factorio.invoice_funding f ON f.invoice_id=i.id
                      GROUP BY i.sector ORDER BY funded DESC""")
    by_month = _q("""SELECT to_char(date_trunc('month', i.issue_date),'Mon YYYY') AS mon,
                            date_trunc('month', i.issue_date) AS m,
                            COALESCE(SUM(f.amount_raised),0) AS funded
                     FROM factorio.invoices i JOIN factorio.invoice_funding f ON f.invoice_id=i.id
                     GROUP BY 1,2 ORDER BY m DESC LIMIT 8""")
    by_grade = _q("""SELECT risk_grade grade,
                            COUNT(*) FILTER (WHERE status IN ('settled','defaulted')) n,
                            COUNT(*) FILTER (WHERE status='defaulted') d
                     FROM factorio.invoices GROUP BY risk_grade ORDER BY risk_grade""")
    grade_rows = [Tr(Td(r["grade"], cls=_TD), Td(str(r["n"]), cls=_TDR),
                     Td(f"{(100*float(r['d'])/r['n']) if r['n'] else 0:.1f}%", cls=_TDR + " text-accent"),
                     cls="border-b border-line") for r in by_grade]
    kpis = Div(
        _card("DSO (avg hold)", f"{float(m.get('avg_hold') or 0):.0f} d", "settled positions"),
        _card("Default rate", f"{dr:.1f}%", "of positions"),
        _card("Recovery rate", f"{recovery:.0f}%", "settled vs terminal"),
        _card("Dilution", f"{dil:.1f}%", "write-offs / funded"),
        _card("Funded volume", fmt_uzs(fundedv.get("v", 0)), "to date"),
        _card("Capital deployed", fmt_uzs(m.get("deployed", 0)), "investor capital"),
        cls="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8",
    )
    return _admin_page(req, "/app/admin/reports", "nav_admin_reports",
                       kpis,
                       Div(P("Funded volume by month", cls="text-sm font-medium text-ink mb-3"),
                           _bars(list(reversed(by_month)), "mon", "funded", fmt=fmt_uzs),
                           cls="mb-8 max-w-2xl"),
                       Div(P("Funded volume by sector", cls="text-sm font-medium text-ink mb-3"),
                           _bars(by_sector, "sector", "funded", fmt=fmt_uzs),
                           cls="mb-8 max-w-2xl"),
                       Div(P("Default rate by grade (portfolio performance)", cls="text-sm font-medium text-ink mb-3"),
                           _table(["Grade", "Terminal", "Default rate"], grade_rows)))


# ── Audit log ─────────────────────────────────────────────────────────────

@rt("/app/admin/audit")
def admin_audit(req):
    g = _guard(req)
    if g:
        return g
    rows = []
    for r in _audit_rows(50):
        when = r["created_at"]
        wstr = when.strftime("%Y-%m-%d %H:%M") if hasattr(when, "strftime") else str(when)
        rows.append(Tr(
            Td(wstr, cls=_TD + " text-ink-muted whitespace-nowrap"),
            Td(r["actor"], cls=_TD), Td(r["action"], cls=_TD + " font-mono text-xs"),
            Td(r["entity"], cls=_TD), Td(r["detail"], cls=_TD + " text-ink-muted"),
            cls="border-b border-line"))
    return _admin_page(req, "/app/admin/audit", "nav_admin_audit",
                       _table(["When", "Actor", "Action", "Entity", "Detail"], rows))


# ── Seller & payer landings (role-scoped) ───────────────────────────────

@rt("/app/supplier")
def supplier_home(req):
    from utils.access import context_for
    ctx = context_for(req)
    if ctx.effective_role != "supplier" or not ctx.supplier_user_id:
        return Response("No supplier profile is linked to this account.", status_code=403)
    lang = get_lang(req)
    synthetic_clause = " AND i.is_synthetic=TRUE" if ctx.is_synthetic else ""
    apps = _q(f"""
        SELECT i.invoice_number, i.debtor_name, i.amount, i.risk_grade, i.status,
               f.id funding_id
        FROM factorio.invoices i
        LEFT JOIN factorio.invoice_funding f ON f.invoice_id=i.id
        WHERE i.seller_id=%(seller)s{synthetic_clause}
        ORDER BY i.id DESC LIMIT 12
    """, {"seller": ctx.supplier_user_id})
    rows = [Tr(Td(a["invoice_number"], cls=_TD), Td(a["debtor_name"], cls=_TD),
               Td(fmt_uzs(a["amount"]), cls=_TDR), Td(a["risk_grade"], cls="py-3 px-4 text-center text-sm"),
               Td(a["status"], cls=_TD),
               Td(A("Contract", href=f"/app/supplier/contract/{a['funding_id']}",
                    target="_blank", cls="text-accent") if a["funding_id"] else "—",
                  cls="py-3 px-4 text-right"),
               cls="border-b border-line") for a in apps]
    return app_page(
        t("nav_supplier", lang),
        Section_(Eyebrow(t("role_supplier", lang)),
                 Heading(1, t("nav_supplier", lang), cls="mt-4"),
                 P("Applications created with Factorio AI. Open a synthetic financing contract or start a new application.",
                   A(" Start with Factorio AI →", href="/app", cls="text-accent"),
                   cls="mt-4 text-ink-muted text-lg max-w-3xl"),
                 cls="border-t border-line"),
        Section_(_table(["Invoice", "Debtor", "Amount", "Grade", "Status", "Contract"], rows), cls="border-t border-line"),
        current_path="/app/supplier", lang=lang, role="supplier",
    )


@rt("/app/supplier/profile")
def supplier_profile(req):
    if current_role(req) != "supplier":
        return RedirectResponse("/app", status_code=303)
    lang = get_lang(req)
    from utils.access import context_for
    ctx = context_for(req)
    profile = _q("""SELECT c.name,c.registration_number,c.address,u.email
                     FROM factorio.users u
                     LEFT JOIN factorio.companies c ON c.id=%(company)s
                     WHERE u.id=%(supplier)s""",
                 {"company": ctx.company_id, "supplier": ctx.supplier_user_id}, one=True) or {}
    details = [
        ("Company", profile.get("name") or "Not linked"),
        ("Company number", profile.get("registration_number") or "Not linked"),
        ("Registered address", profile.get("address") or "Not provided"),
        ("Contact", profile.get("email") or ctx.email),
        ("Bank", "Not connected"),
        ("Account name", profile.get("name") or "Not configured"),
        ("Sort code", "Not configured"),
        ("Account number", "Not configured"),
        ("IBAN", "Not configured"),
        ("SWIFT / BIC", "Not configured"),
    ]
    rows = [Tr(Td(label, cls=_TD + " text-ink-muted"),
               Td(value, cls=_TD + " font-medium"),
               cls="border-b border-line") for label, value in details]
    connections = [
        ("/static/lloyds-bank.png", "Lloyds Bank", "Open Banking", "Planned",
         "Bank-account verification and transaction access will use a consent-based Open Banking connection."),
        ("/static/quickbooks-logo.svg", "QuickBooks", "Accounting", "Demo available",
         "Hypothetical connection for invoices, customers, payments, and reconciliation."),
        ("/static/xero-logo.svg", "Xero", "Accounting", "Demo available",
         "Hypothetical connection for receivables, contacts, and payment-status synchronisation."),
        ("/static/sage-logo.svg", "Sage", "Accounting", "Demo available",
         "Hypothetical connection for invoice import, ledger coding, and settlement reconciliation."),
    ]
    cards = Div(*[
        Article(
            Div(Img(src=logo, alt=f"{name} logo",
                    cls="w-full h-12 object-contain object-left"),
                Span(status, cls=("text-[11px] px-2.5 py-1 rounded-full "
                                  + ("bg-amber-50 text-amber-700" if status == "Planned"
                                     else "bg-green-50 text-green-700"))),
                cls="flex items-center justify-between gap-4"),
            P(kind, cls="text-[10px] font-mono uppercase tracking-widest text-ink-dim mt-5"),
            P(description, cls="text-sm text-ink-muted leading-relaxed mt-2"),
            Button("Connect later" if status == "Planned" else "Connect demo",
                   type="button", disabled=True,
                   cls="mt-5 px-4 py-2 rounded-full border border-line text-xs text-ink-muted cursor-not-allowed"),
            cls="p-6 rounded-2xl bg-bg-elevated border border-line",
        ) for logo, name, kind, status, description in connections
    ], cls="grid md:grid-cols-2 gap-4")
    return app_page(
        "My Profile",
        Section_(Eyebrow("Supplier account"), Heading(1, "My Profile", cls="mt-4"),
                 P("Synthetic company and settlement details used for this demo account.",
                   cls="mt-4 text-ink-muted text-lg max-w-3xl"),
                 cls="border-t border-line"),
        Section_(_table(["Field", "Details"], rows), cls="border-t border-line"),
        Section_(Eyebrow("Connections"),
                 Heading(2, "Banks & accounting", cls="mt-4"),
                 P("Synthetic integration choices for this demo supplier. No external account is currently connected.",
                   cls="mt-3 mb-8 text-ink-muted max-w-3xl"),
                 cards, cls="border-t border-line"),
        current_path="/app/supplier/profile", lang=lang, role="supplier",
    )


@rt("/app/payer")
def payer_home(req):
    from utils.access import context_for
    ctx = context_for(req)
    lang = get_lang(req)
    if ctx.effective_role != "payer":
        return Response("Payer access required.", status_code=403)
    if not ctx.payer_registration:
        return app_page(
            t("nav_payer", lang),
            Section_(Eyebrow("Payer account"), Heading(1, "Organisation linkage pending", cls="mt-4"),
                     P("Ask your administrator to link the company registration number whose invoices you may confirm.",
                       cls="mt-4 text-ink-muted text-lg max-w-3xl"), cls="border-t border-line"),
            current_path="/app/payer", lang=lang, role="payer")
    top = _q("""SELECT debtor_name FROM factorio.invoices
                 WHERE debtor_registration=%(registration)s ORDER BY id LIMIT 1""",
             {"registration": ctx.payer_registration}, one=True)
    debtor = (top or {}).get("debtor_name", ctx.payer_registration)
    invs = _q("""
        SELECT invoice_number, amount, due_date, status, payer_decision FROM factorio.invoices
        WHERE debtor_registration = %(registration)s ORDER BY due_date LIMIT 15
    """, {"registration": ctx.payer_registration})
    rows = []
    for i in invs:
        decision = str(i.get("payer_decision") or "")
        act = (Span(decision.title(), cls="text-xs text-green-700") if decision
               else Form(Input(type="hidden", name="csrf", value=ctx.csrf_token),
                         Input(type="hidden", name="invoice_number", value=i["invoice_number"]),
                         Button("Confirm", name="decision", value="confirmed", type="submit",
                                cls="text-xs px-2 py-1 rounded bg-accent text-white"),
                         Button("Dispute", name="decision", value="disputed", type="submit",
                                cls="text-xs px-2 py-1 rounded border border-line ml-1"),
                         action="/app/payer/invoice-action", method="post"))
        rows.append(Tr(Td(i["invoice_number"], cls=_TD), Td(fmt_uzs(i["amount"]), cls=_TDR),
                       Td(str(i["due_date"]), cls=_TD), Td(i["status"], cls=_TD),
                       Td(_view_btn(i["invoice_number"], debtor), cls="py-3 px-4"),
                       Td(act, cls="py-3 px-4 text-right"), cls="border-b border-line"))
    return app_page(
        t("nav_payer", lang),
        Section_(Eyebrow(t("role_payer", lang)),
                 Heading(1, t("nav_payer", lang), cls="mt-4"),
                 P(NotStr(f"Invoices where <b>{debtor}</b> is the debtor. Confirm the obligation so suppliers can be financed."),
                   cls="mt-4 text-ink-muted text-lg max-w-3xl"),
                 cls="border-t border-line"),
        Section_(_table(["Invoice", "Amount", "Due", "Status", "Document", ""], rows), cls="border-t border-line"),
        current_path="/app/payer", lang=lang, role="payer",
    )


@rt("/app/payer/invoice-action", methods=["POST"])
def payer_invoice_action(req, invoice_number: str = "", decision: str = "", csrf: str = ""):
    import hmac
    from utils.access import audit, context_for
    ctx = context_for(req)
    expected = str(req.session.get("csrf_token") or "")
    if (ctx.effective_role != "payer" or decision not in {"confirmed", "disputed"}
            or not expected or not hmac.compare_digest(expected, csrf)):
        return Response("Forbidden", status_code=403)
    synthetic_clause = " AND is_synthetic=TRUE" if ctx.is_synthetic else ""
    updated = fetch_one(
        f"""UPDATE factorio.invoices SET payer_decision=%(decision)s,
                payer_decided_at=now(),updated_at=now()
              WHERE invoice_number=%(invoice)s AND debtor_registration=%(registration)s
              {synthetic_clause} RETURNING id""",
        {"decision": decision, "invoice": invoice_number,
         "registration": ctx.payer_registration},
    )
    if not updated:
        audit(ctx, "payer_decision_denied", invoice_number, decision)
        return Response("Invoice not found", status_code=404)
    audit(ctx, "payer_invoice_" + decision, invoice_number,
          f"actual={ctx.actual_role};effective={ctx.effective_role};preview={ctx.preview}")
    return RedirectResponse("/app/payer", status_code=303)
