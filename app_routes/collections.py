"""Collections & credit management — production module (area 4).

A dunning workflow over overdue invoices: staged reminders → escalation → legal →
write-off, each recorded in ``collections_actions`` and audited. Plus a
**bad-debt provision** (exposure × expected default by grade) with a portfolio
total. Actions are SoD-scoped (Collections runs dunning; Finance/Compliance
approve write-offs).
"""

from __future__ import annotations

from fasthtml.common import Div, P, Span, A, Table, Thead, Tbody, Tr, Th, Td, Form, Input, Button
from starlette.responses import RedirectResponse

from app import rt
from utils.i18n import get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, fmt_uzs, current_role, current_subrole
from app_routes.admin import log_action

try:
    from db import fetch_all, fetch_one, execute
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False

CAN_DUN = {"collections", "super"}
CAN_WRITEOFF = {"finance", "compliance", "super"}
PD_BY_GRADE = {"A": 0.01, "B": 0.03, "C": 0.06, "D": 0.12}
STAGES = ["none", "reminder 1", "reminder 2", "escalated", "legal", "written off"]


def _ensure():
    if not _HAS_DB:
        return
    execute("""CREATE TABLE IF NOT EXISTS factorio.collections_actions (
        id BIGSERIAL PRIMARY KEY, invoice_number TEXT NOT NULL, stage INT NOT NULL DEFAULT 0,
        action_type TEXT NOT NULL DEFAULT 'dunning', note TEXT NOT NULL DEFAULT '',
        actor TEXT NOT NULL DEFAULT '', created_at TIMESTAMPTZ NOT NULL DEFAULT now())""")


def _overdue():
    if not _HAS_DB:
        return []
    return fetch_all("""
        SELECT i.invoice_number, i.debtor_name, i.amount, i.due_date, i.risk_grade,
               (CURRENT_DATE - i.due_date) AS days_over
        FROM factorio.invoices i
        WHERE i.status='funding' AND i.due_date < CURRENT_DATE
        ORDER BY i.due_date LIMIT 40""")


def _stage_of(num: str) -> int:
    if not _HAS_DB:
        return 0
    r = fetch_one("SELECT MAX(stage) s FROM factorio.collections_actions WHERE invoice_number=%(n)s", {"n": num})
    return int((r or {}).get("s") or 0)


def seed_collections() -> int:
    _ensure()
    if not _HAS_DB:
        return 0
    if (fetch_one("SELECT COUNT(*) n FROM factorio.collections_actions") or {}).get("n"):
        return 0
    n = 0
    for idx, r in enumerate(_overdue()):
        stage = 1 + (idx % 2)  # start most at reminder 1 or 2
        execute("INSERT INTO factorio.collections_actions (invoice_number,stage,action_type,note,actor) "
                "VALUES (%(n)s,%(s)s,'dunning',%(nt)s,'engine')",
                {"n": r["invoice_number"], "s": stage, "nt": f"Auto {STAGES[stage]}"})
        n += 1
    return n


_TH = "text-left text-[11px] font-mono tracking-widest uppercase text-ink-dim py-3 px-4"
_TD = "py-3 px-4 text-sm text-ink"
_TDR = _TD + " text-right tabular-nums"


def _guard(req):
    if current_role(req) != "admin":
        return RedirectResponse("/app", status_code=303)
    return None


@rt("/app/admin/collections")
def collections(req):
    g = _guard(req)
    if g:
        return g
    try:
        seed_collections()
    except Exception:
        pass
    sub = current_subrole(req)
    can_dun = sub in CAN_DUN
    can_wo = sub in CAN_WRITEOFF
    provision = 0.0
    rows = []
    for r in _overdue():
        num = r["invoice_number"]; amt = float(r["amount"] or 0)
        stage = _stage_of(num)
        pd = PD_BY_GRADE.get(r["risk_grade"], 0.05)
        prov = amt * pd
        provision += prov
        acts = []
        if can_dun and stage < 4:
            from utils.access import context_for
            acts.append(Form(Input(type="hidden", name="inv", value=num),
                             Input(type="hidden", name="do", value="escalate"),
                             Input(type="hidden", name="csrf", value=context_for(req).csrf_token),
                             Button("Escalate", type="submit",
                                    cls="text-xs px-2 py-1 rounded-full bg-accent text-bg mr-1"),
                             action="/app/admin/collections/act", method="post", cls="inline"))
        if can_wo and stage >= 3 and stage < 5:
            from utils.access import context_for
            acts.append(Form(Input(type="hidden", name="inv", value=num),
                             Input(type="hidden", name="do", value="writeoff"),
                             Input(type="hidden", name="csrf", value=context_for(req).csrf_token),
                             Button("Write-off", type="submit",
                                    cls="text-xs px-2 py-1 rounded-full border border-red-300 text-red-700"),
                             action="/app/admin/collections/act", method="post", cls="inline"))
        rows.append(Tr(
            Td(num, cls=_TD), Td(r["debtor_name"], cls=_TD),
            Td(fmt_uzs(amt), cls=_TDR),
            Td(f"{r['days_over']}d", cls=_TDR + " text-red-700"),
            Td(Span(STAGES[min(stage, 5)], cls="text-xs text-ink-muted"), cls="py-3 px-4"),
            Td(fmt_uzs(prov), cls=_TDR + " text-accent"),
            Td(Span(*acts) if acts else Span("—", cls="text-ink-dim text-xs"), cls="py-3 px-4 text-right"),
            cls="border-b border-line"))
    note = P(("Collections may escalate dunning; Finance / Compliance approve write-offs."
              if (can_dun or can_wo) else
              "Collections actions require Collections / Finance / Compliance / Super (segregation of duties)."),
             cls="text-sm mt-4 " + ("text-ink-muted" if (can_dun or can_wo) else "text-red-700"))
    return app_page("Collections",
                    Section_(Eyebrow("Back office · Collections"),
                             Heading(1, "Collections & credit management", cls="mt-4"),
                             P(f"Dunning workflow over overdue invoices, with a bad-debt provision of "
                               f"{fmt_uzs(provision)} across the overdue book.",
                               cls="mt-3 text-ink-muted max-w-3xl"), cls="border-t border-line"),
                    Section_(Div(Table(
                        Thead(Tr(*[Th(h, cls=_TH) for h in
                                   ["Invoice", "Debtor", "Amount", "Overdue", "Dunning stage", "Provision", "Action"]],
                                 cls="border-b border-line")),
                        Tbody(*rows), cls="w-full"),
                        cls="rounded-2xl bg-bg-elevated border border-line overflow-hidden overflow-x-auto"),
                        note, cls="border-t border-line"),
                    current_path="/app/admin/collections", lang=get_lang(req),
                    role="admin", subrole=current_subrole(req))


@rt("/app/admin/collections/act", methods=["POST"])
def collections_act(req, inv: str = "", do: str = "", csrf: str = ""):
    import hmac
    if not csrf or not hmac.compare_digest(str(req.session.get("csrf_token") or ""), csrf):
        return RedirectResponse("/app", status_code=303)
    g = _guard(req)
    if g:
        return g
    sub = current_subrole(req)
    if not _HAS_DB:
        return RedirectResponse("/app/admin/collections", status_code=303)
    if do == "escalate" and sub in CAN_DUN:
        stage = min(4, _stage_of(inv) + 1)
        execute("INSERT INTO factorio.collections_actions (invoice_number,stage,action_type,note,actor) "
                "VALUES (%(n)s,%(s)s,'dunning',%(nt)s,%(a)s)",
                {"n": inv, "s": stage, "nt": STAGES[stage], "a": f"admin:{sub}"})
        log_action("admin", sub, "dunning.escalate", inv, STAGES[stage])
    elif do == "writeoff" and sub in CAN_WRITEOFF:
        execute("INSERT INTO factorio.collections_actions (invoice_number,stage,action_type,note,actor) "
                "VALUES (%(n)s,5,'writeoff','Written off',%(a)s)", {"n": inv, "a": f"admin:{sub}"})
        execute("UPDATE factorio.invoices SET status='defaulted', updated_at=now() WHERE invoice_number=%(n)s", {"n": inv})
        log_action("admin", sub, "collections.writeoff", inv, "bad-debt write-off")
    return RedirectResponse("/app/admin/collections", status_code=303)
