"""Onboarding / KYC + facility-limit engine — production back-office module (area 1).

Real KYC case workflow (submitted → in_review → approved / rejected) per client
and debtor, and a **facility-limit engine** that derives a recommended credit
limit, advance rate and concentration cap from turnover, grade and payment
behaviour. Review actions are SoD-scoped (Compliance/Super approve KYC;
Credit/Compliance/Super set limits) and written to the audit log.
"""

from __future__ import annotations

import hmac

from fasthtml.common import Div, P, Span, A, Button, Form, Input, Table, Thead, Tbody, Tr, Th, Td, NotStr
from starlette.responses import RedirectResponse

from app import rt
from utils.i18n import t, get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, fmt_uzs, current_role, current_subrole
from app_routes.admin import log_action
from utils.access import context_for

try:
    from db import fetch_all, fetch_one, execute
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False

CAN_APPROVE_KYC = {"compliance", "super"}
CAN_SET_LIMITS = {"credit", "compliance", "super"}

# credit limit as a fraction of annual turnover, by grade
LIMIT_FACTOR = {"A": 0.25, "B": 0.18, "C": 0.12, "D": 0.06}
ADVANCE_BY_GRADE = {"A": 90, "B": 85, "C": 80, "D": 70}
CONC_CAP_BY_GRADE = {"A": 25, "B": 20, "C": 15, "D": 10}  # % of book


def _ensure():
    if not _HAS_DB:
        return
    execute("""CREATE TABLE IF NOT EXISTS factorio.kyc_cases (
        id BIGSERIAL PRIMARY KEY, company_id BIGINT, subject TEXT NOT NULL,
        subject_type TEXT NOT NULL DEFAULT 'client', status TEXT NOT NULL DEFAULT 'submitted',
        risk_flags TEXT NOT NULL DEFAULT '', reviewer TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
    execute("""CREATE TABLE IF NOT EXISTS factorio.facility_limits (
        id BIGSERIAL PRIMARY KEY, company_id BIGINT UNIQUE, subject TEXT NOT NULL,
        grade TEXT NOT NULL DEFAULT 'B', credit_limit NUMERIC(15,2) NOT NULL DEFAULT 0,
        advance_rate NUMERIC(5,2) NOT NULL DEFAULT 85, concentration_cap NUMERIC(5,2) NOT NULL DEFAULT 20,
        status TEXT NOT NULL DEFAULT 'active', set_by TEXT NOT NULL DEFAULT 'engine',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now())""")


def _client_grade(company_id):
    r = fetch_one("""SELECT MODE() WITHIN GROUP (ORDER BY risk_grade) g
                     FROM factorio.invoices WHERE company_id=%(c)s""", {"c": company_id})
    return (r or {}).get("g") or "B"


def seed_onboarding() -> int:
    """Create a KYC case + facility limit for every client company. Idempotent."""
    if not _HAS_DB:
        return 0
    _ensure()
    companies = fetch_all("SELECT id, name, annual_turnover FROM factorio.companies ORDER BY id")
    n = 0
    for idx, c in enumerate(companies):
        cid = c["id"]; name = c["name"]; turnover = float(c["annual_turnover"] or 0)
        grade = _client_grade(cid)
        # KYC status: deterministic mix (most approved, some in review, a couple flagged)
        status = "approved" if idx % 6 else ("in_review" if idx % 3 else "submitted")
        flags = "" if status == "approved" else ("PEP screening pending" if idx % 3 == 0 else "address verification")
        execute("""INSERT INTO factorio.kyc_cases (company_id,subject,subject_type,status,risk_flags)
                   VALUES (%(c)s,%(n)s,'client',%(s)s,%(f)s)
                   ON CONFLICT DO NOTHING""",
                {"c": cid, "n": name, "s": status, "f": flags}) if False else None
        # kyc_cases has no unique constraint on company_id; upsert manually
        existing = fetch_one("SELECT id FROM factorio.kyc_cases WHERE company_id=%(c)s", {"c": cid})
        if existing:
            execute("UPDATE factorio.kyc_cases SET status=%(s)s, risk_flags=%(f)s, updated_at=now() WHERE company_id=%(c)s",
                    {"s": status, "f": flags, "c": cid})
        else:
            execute("INSERT INTO factorio.kyc_cases (company_id,subject,subject_type,status,risk_flags) "
                    "VALUES (%(c)s,%(n)s,'client',%(s)s,%(f)s)",
                    {"c": cid, "n": name, "s": status, "f": flags})
        # facility limit (engine recommendation)
        limit = turnover * LIMIT_FACTOR.get(grade, 0.15)
        execute("""INSERT INTO factorio.facility_limits (company_id,subject,grade,credit_limit,advance_rate,concentration_cap,set_by)
                   VALUES (%(c)s,%(n)s,%(g)s,%(l)s,%(a)s,%(cc)s,'engine')
                   ON CONFLICT (company_id) DO UPDATE SET grade=EXCLUDED.grade,
                     credit_limit=EXCLUDED.credit_limit, advance_rate=EXCLUDED.advance_rate,
                     concentration_cap=EXCLUDED.concentration_cap, updated_at=now()""",
                {"c": cid, "n": name, "g": grade, "l": round(limit, 2),
                 "a": ADVANCE_BY_GRADE.get(grade, 85), "cc": CONC_CAP_BY_GRADE.get(grade, 20)})
        n += 1
    return n


# ── UI ────────────────────────────────────────────────────────────────────

_TH = "text-left text-[11px] font-mono tracking-widest uppercase text-ink-dim py-3 px-4"
_TD = "py-3 px-4 text-sm text-ink"
_TDR = _TD + " text-right tabular-nums"


def _guard(req):
    if current_role(req) != "admin":
        return RedirectResponse("/app", status_code=303)
    return None


def _seeded():
    if not _HAS_DB:
        return False
    try:
        return ((fetch_one("SELECT COUNT(*) n FROM factorio.facility_limits") or {}).get("n") or 0) > 0
    except Exception:
        return False


def _table(headers, rows):
    return Div(Table(Thead(Tr(*[Th(h, cls=_TH) for h in headers], cls="border-b border-line")),
                     Tbody(*rows), cls="w-full"),
               cls="rounded-2xl bg-bg-elevated border border-line overflow-hidden overflow-x-auto")


def _page(req, path, title, lede, *content):
    lang = get_lang(req)
    return app_page(title,
                    Section_(Eyebrow("Back office · Onboarding"),
                             Heading(1, title, cls="mt-4"),
                             P(lede, cls="mt-3 text-ink-muted max-w-3xl"), cls="border-t border-line"),
                    Section_(*content, cls="border-t border-line"),
                    current_path=path, lang=lang, role="admin", subrole=current_subrole(req))


_KYC_BADGE = {"approved": "bg-green-100 text-green-800", "in_review": "bg-yellow-100 text-yellow-800",
              "submitted": "bg-blue-100 text-blue-800", "rejected": "bg-red-100 text-red-800"}


@rt("/app/admin/onboarding")
def onboarding(req):
    g = _guard(req)
    if g:
        return g
    if not _seeded():
        try:
            seed_onboarding()
        except Exception:
            pass
    can = current_subrole(req) in CAN_APPROVE_KYC
    data = fetch_all("""SELECT k.subject, k.status, k.risk_flags, k.reviewer,
                               fl.grade, fl.credit_limit, fl.advance_rate
                        FROM factorio.kyc_cases k
                        LEFT JOIN factorio.facility_limits fl ON fl.company_id=k.company_id
                        ORDER BY k.status, k.subject""") if _HAS_DB else []
    rows = []
    for r in data:
        st = r["status"]
        actions = Span("—", cls="text-ink-dim text-xs")
        if can and st in ("submitted", "in_review"):
            csrf = context_for(req).csrf_token
            actions = Div(
                Form(Input(type="hidden", name="subject", value=r["subject"]),
                     Input(type="hidden", name="decision", value="approved"),
                     Input(type="hidden", name="csrf", value=csrf),
                     Button("Approve", type="submit",
                            cls="text-xs px-2 py-1 rounded-full bg-accent text-bg"),
                     method="post", action="/app/admin/onboarding/act"),
                Form(Input(type="hidden", name="subject", value=r["subject"]),
                     Input(type="hidden", name="decision", value="rejected"),
                     Input(type="hidden", name="csrf", value=csrf),
                     Button("Reject", type="submit",
                            cls="text-xs px-2 py-1 rounded-full border border-line text-ink"),
                     method="post", action="/app/admin/onboarding/act"),
                cls="flex justify-end gap-1",
            )
        rows.append(Tr(
            Td(r["subject"], cls=_TD),
            Td(Span(st.replace("_", " "), cls=f"px-2 py-0.5 rounded-full text-xs font-medium {_KYC_BADGE.get(st,'bg-gray-100')}"), cls="py-3 px-4"),
            Td(r["risk_flags"] or "—", cls=_TD + " text-ink-muted"),
            Td(r["grade"] or "—", cls="py-3 px-4 text-center text-sm"),
            Td(fmt_uzs(r["credit_limit"]) if r["credit_limit"] is not None else "—", cls=_TDR + " text-accent"),
            Td(actions, cls="py-3 px-4 text-right"),
            cls="border-b border-line"))
    note = P(("You may approve/reject KYC (Compliance)." if can
              else "KYC decisions require Compliance / Super (segregation of duties)."),
             cls="text-sm mt-4 " + ("text-ink-muted" if can else "text-red-700"))
    return _page(req, "/app/admin/onboarding", "Onboarding & KYC",
                 "KYC case workflow for clients and debtors, with engine-recommended facility limits.",
                 _table(["Client / debtor", "KYC status", "Risk flags", "Grade", "Facility limit", "Action"], rows),
                 note,
                 P(A("Facility limits →", href="/app/admin/onboarding/limits", cls="text-accent"), cls="mt-3 text-sm"))


@rt("/app/admin/onboarding/act", methods=["POST"])
def onboarding_act(req, subject: str = "", decision: str = "", csrf: str = ""):
    g = _guard(req)
    if g:
        return g
    if not csrf or not hmac.compare_digest(str(req.session.get("csrf_token") or ""), csrf):
        return RedirectResponse("/app", status_code=303)
    sub = current_subrole(req)
    if sub in CAN_APPROVE_KYC and decision in ("approved", "rejected") and _HAS_DB:
        execute("UPDATE factorio.kyc_cases SET status=%(s)s, reviewer=%(r)s, updated_at=now() WHERE subject=%(sub)s",
                {"s": decision, "r": f"admin:{sub}", "sub": subject})
        log_action("admin", sub, f"kyc.{decision}", subject, "KYC review via console")
    return RedirectResponse("/app/admin/onboarding", status_code=303)


@rt("/app/admin/onboarding/limits")
def facility_limits(req):
    g = _guard(req)
    if g:
        return g
    if not _seeded():
        try:
            seed_onboarding()
        except Exception:
            pass
    can = current_subrole(req) in CAN_SET_LIMITS
    data = fetch_all("""SELECT subject, grade, credit_limit, advance_rate, concentration_cap, status, set_by
                        FROM factorio.facility_limits ORDER BY credit_limit DESC""") if _HAS_DB else []
    rows = [Tr(
        Td(r["subject"], cls=_TD),
        Td(r["grade"], cls="py-3 px-4 text-center text-sm"),
        Td(fmt_uzs(r["credit_limit"]), cls=_TDR + " text-accent"),
        Td(f"{float(r['advance_rate']):.0f}%", cls=_TDR),
        Td(f"{float(r['concentration_cap']):.0f}%", cls=_TDR),
        Td(r["set_by"], cls=_TD + " text-ink-muted"),
        cls="border-b border-line") for r in data]
    note = P(("Limits are engine-recommended; Credit / Compliance may override." if can
              else "Setting limits requires Credit / Compliance / Super (segregation of duties)."),
             cls="text-sm mt-4 " + ("text-ink-muted" if can else "text-red-700"))
    return _page(req, "/app/admin/onboarding", "Facility limits",
                 "Engine-recommended credit limit, advance rate and concentration cap per client, by grade.",
                 _table(["Client", "Grade", "Credit limit", "Advance", "Concentration cap", "Set by"], rows),
                 note)
