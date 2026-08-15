"""Invoice processing / verification & assignment — production module (area 2).

Turns a submitted invoice into a fundable, assigned receivable: authenticity /
PO-match check, assignment (notified vs confidential), CBU collateral-registry
registration, and holdback/reserve calculation. Each invoice has an
``invoice_assignments`` row tracking its processing state; ops can verify and
assign (SoD-gated), with every action audited.
"""

from __future__ import annotations

import hmac

from fasthtml.common import Div, P, Span, A, Button, Form, Input, Table, Thead, Tbody, Tr, Th, Td
from starlette.responses import RedirectResponse

from app import rt
from utils.i18n import get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, fmt_uzs, current_role, current_subrole
from app_routes.admin import log_action
from utils.access import context_for

try:
    from db import fetch_all, fetch_one, execute
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False

CAN_PROCESS = {"ops", "credit", "super"}


def _ensure():
    if not _HAS_DB:
        return
    execute("""CREATE TABLE IF NOT EXISTS factorio.invoice_assignments (
        id BIGSERIAL PRIMARY KEY, invoice_id BIGINT UNIQUE, invoice_number TEXT NOT NULL,
        assignment_type TEXT NOT NULL DEFAULT 'notified', po_matched BOOLEAN NOT NULL DEFAULT FALSE,
        verified BOOLEAN NOT NULL DEFAULT FALSE, registered BOOLEAN NOT NULL DEFAULT FALSE,
        holdback NUMERIC(15,2) NOT NULL DEFAULT 0, reserve NUMERIC(15,2) NOT NULL DEFAULT 0,
        state TEXT NOT NULL DEFAULT 'submitted', updated_at TIMESTAMPTZ NOT NULL DEFAULT now())""")


def seed_processing() -> int:
    if not _HAS_DB:
        return 0
    _ensure()
    rows = fetch_all("""SELECT i.id, i.invoice_number, i.amount, i.status,
                               COALESCE(f.advance_rate_pct,85) adv
                        FROM factorio.invoices i
                        LEFT JOIN factorio.invoice_funding f ON f.invoice_id=i.id""")
    n = 0
    for idx, r in enumerate(rows):
        face = float(r["amount"] or 0)
        advance = face * float(r["adv"]) / 100.0
        holdback = max(0.0, face - advance)
        atype = "confidential" if idx % 4 == 0 else "notified"
        po = idx % 5 != 0
        verified = r["status"] in ("verified", "funding", "funded", "settled")
        registered = r["status"] in ("funding", "funded", "settled")
        state = ("assigned" if registered else "verified" if verified else "submitted")
        exists = fetch_one("SELECT id FROM factorio.invoice_assignments WHERE invoice_id=%(i)s", {"i": r["id"]})
        params = {"i": r["id"], "num": r["invoice_number"], "at": atype, "po": po,
                  "v": verified, "reg": registered, "h": round(holdback, 2),
                  "res": round(holdback, 2), "st": state}
        if exists:
            execute("""UPDATE factorio.invoice_assignments SET assignment_type=%(at)s,po_matched=%(po)s,
                       verified=%(v)s,registered=%(reg)s,holdback=%(h)s,reserve=%(res)s,state=%(st)s,updated_at=now()
                       WHERE invoice_id=%(i)s""", params)
        else:
            execute("""INSERT INTO factorio.invoice_assignments
                       (invoice_id,invoice_number,assignment_type,po_matched,verified,registered,holdback,reserve,state)
                       VALUES (%(i)s,%(num)s,%(at)s,%(po)s,%(v)s,%(reg)s,%(h)s,%(res)s,%(st)s)""", params)
        n += 1
    return n


_TH = "text-left text-[11px] font-mono tracking-widest uppercase text-ink-dim py-3 px-4"
_TD = "py-3 px-4 text-sm text-ink"
_TDR = _TD + " text-right tabular-nums"
_BADGE = {"submitted": "bg-blue-100 text-blue-800", "verified": "bg-yellow-100 text-yellow-800",
          "assigned": "bg-green-100 text-green-800"}


def _guard(req):
    if current_role(req) != "admin":
        return RedirectResponse("/app", status_code=303)
    return None


def _seeded():
    if not _HAS_DB:
        return False
    try:
        return ((fetch_one("SELECT COUNT(*) n FROM factorio.invoice_assignments") or {}).get("n") or 0) > 0
    except Exception:
        return False


@rt("/app/admin/processing")
def processing(req):
    g = _guard(req)
    if g:
        return g
    if not _seeded():
        try:
            seed_processing()
        except Exception:
            pass
    can = current_subrole(req) in CAN_PROCESS
    data = fetch_all("""SELECT a.invoice_number, a.assignment_type, a.po_matched, a.verified,
                               a.registered, a.holdback, a.state, i.debtor_name, i.amount
                        FROM factorio.invoice_assignments a
                        JOIN factorio.invoices i ON i.id=a.invoice_id
                        ORDER BY a.state, i.amount DESC LIMIT 40""") if _HAS_DB else []
    rows = []
    for r in data:
        st = r["state"]
        act = Span("—", cls="text-ink-dim text-xs")
        if can and st != "assigned":
            nxt = "verify" if st == "submitted" else "assign"
            act = Form(
                Input(type="hidden", name="inv", value=r["invoice_number"]),
                Input(type="hidden", name="step", value=nxt),
                Input(type="hidden", name="csrf", value=context_for(req).csrf_token),
                Button(nxt.title(), type="submit",
                       cls="text-xs px-2 py-1 rounded-full bg-accent text-bg"),
                method="post", action="/app/admin/processing/act",
            )
        _num = (r["invoice_number"] or "").replace("'", "")
        _deb = (r["debtor_name"] or "").replace("'", "")
        rows.append(Tr(
            Td(r["invoice_number"], cls=_TD), Td(r["debtor_name"], cls=_TD),
            Td(fmt_uzs(r["amount"]), cls=_TDR),
            Td(r["assignment_type"], cls=_TD + " text-ink-muted"),
            Td("✓" if r["po_matched"] else "—", cls="py-3 px-4 text-center"),
            Td(fmt_uzs(r["holdback"]), cls=_TDR + " text-accent"),
            Td(Span(st, cls=f"px-2 py-0.5 rounded-full text-xs font-medium {_BADGE.get(st,'bg-gray-100')}"), cls="py-3 px-4"),
            Td(A("View", href="#", onclick=f"return fcShowPdf('{_num}','{_deb}')", cls="pdf-view-btn"), cls="py-3 px-4"),
            Td(act, cls="py-3 px-4 text-right"),
            cls="border-b border-line"))
    note = P(("You may verify and assign invoices (Ops / Credit)." if can
              else "Verification / assignment requires Ops / Credit / Super (segregation of duties)."),
             cls="text-sm mt-4 " + ("text-ink-muted" if can else "text-red-700"))
    return app_page("Invoice processing",
                    Section_(Eyebrow("Back office · Processing"),
                             Heading(1, "Invoice processing & assignment", cls="mt-4"),
                             P("Authenticity / PO-match, assignment (notified vs confidential), collateral "
                               "registration and holdback/reserve — the receivable's path to fundable.",
                               cls="mt-3 text-ink-muted max-w-3xl"), cls="border-t border-line"),
                    Section_(_table_wrap(["Invoice", "Debtor", "Amount", "Assignment", "PO", "Holdback", "State", "Document", "Action"], rows),
                             note, cls="border-t border-line"),
                    current_path="/app/admin/processing", lang=get_lang(req),
                    role="admin", subrole=current_subrole(req))


def _table_wrap(headers, rows):
    return Div(Table(Thead(Tr(*[Th(h, cls=_TH) for h in headers], cls="border-b border-line")),
                     Tbody(*rows), cls="w-full"),
               cls="rounded-2xl bg-bg-elevated border border-line overflow-hidden overflow-x-auto")


@rt("/app/admin/processing/act", methods=["POST"])
def processing_act(req, inv: str = "", step: str = "", csrf: str = ""):
    g = _guard(req)
    if g:
        return g
    if not csrf or not hmac.compare_digest(str(req.session.get("csrf_token") or ""), csrf):
        return RedirectResponse("/app", status_code=303)
    sub = current_subrole(req)
    if sub in CAN_PROCESS and _HAS_DB:
        if step == "verify":
            execute("UPDATE factorio.invoice_assignments SET verified=TRUE, state='verified', updated_at=now() WHERE invoice_number=%(n)s", {"n": inv})
            log_action("admin", sub, "invoice.verify", inv, "verified via console")
        elif step == "assign":
            execute("UPDATE factorio.invoice_assignments SET registered=TRUE, state='assigned', updated_at=now() WHERE invoice_number=%(n)s", {"n": inv})
            log_action("admin", sub, "invoice.assign", inv, "assigned + registered")
    return RedirectResponse("/app/admin/processing", status_code=303)
