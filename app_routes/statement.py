"""Account statement: /app/statement — unified, filterable transaction ledger.

Combines investments (cash out) and settlements (principal + interest back in)
for the current investor, with period / amount / counterparty / invoice / type
filters and a CSV export.
"""

from __future__ import annotations

import csv
import io

from fasthtml.common import (
    Div, P, Span, Form, Input, Select, Option, Button, A, NotStr,
    Table, Thead, Tbody, Tr, Th, Td, Label,
)
from starlette.responses import Response

from app import rt
from utils.i18n import t, get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, fmt_uzs, list_investors, current_investor, current_role

try:
    from db import fetch_all
    _HAS_DB = True
except Exception:
    _HAS_DB = False

_TYPE_LABELS = {"investment": "txn_investment", "settlement": "txn_settlement"}


def _parse_filters(req) -> dict:
    q = req.query_params
    def _s(key):
        v = (q.get(key) or "").strip()
        return v or None
    amt = _s("min_amount")
    try:
        amt = float(amt) if amt else None
    except ValueError:
        amt = None
    ttype = _s("txn_type")
    if ttype not in _TYPE_LABELS:
        ttype = None
    return {
        "from": _s("date_from"),
        "to": _s("date_to"),
        "type": ttype,
        "cp": (f"%{_s('counterparty')}%" if _s("counterparty") else None),
        "invno": (f"%{_s('invoice_no')}%" if _s("invoice_no") else None),
        "amt": amt,
        # echo raw values back into the form
        "_raw": {k: (q.get(k) or "") for k in
                 ("date_from", "date_to", "txn_type", "counterparty", "invoice_no", "min_amount")},
    }


def _load_ledger(investor_id: int, fl: dict) -> list[dict]:
    if not _HAS_DB:
        return []
    try:
        return fetch_all("""
            WITH ledger AS (
                SELECT p.payment_date AS txn_date, 'investment' AS txn_type,
                       i.debtor_name AS counterparty, i.invoice_number AS invoice_number,
                       (-p.amount) AS amount
                FROM factorio.payments p
                JOIN factorio.investments inv ON inv.id = p.investment_id
                JOIN factorio.invoice_funding f ON f.id = inv.funding_id
                JOIN factorio.invoices i ON i.id = f.invoice_id
                WHERE p.investor_id = %(iid)s
                UNION ALL
                SELECT s.settlement_date AS txn_date, 'settlement' AS txn_type,
                       i.debtor_name, i.invoice_number,
                       (d.invested_amount + d.amount) AS amount
                FROM factorio.dividends d
                JOIN factorio.invoice_funding f ON f.id = d.funding_id
                JOIN factorio.invoices i ON i.id = f.invoice_id
                LEFT JOIN factorio.settlements s ON s.funding_id = f.id
                WHERE d.investor_id = %(iid)s AND d.is_paid = TRUE
            )
            SELECT * FROM ledger
            WHERE (%(from)s::date IS NULL OR txn_date::date >= %(from)s::date)
              AND (%(to)s::date   IS NULL OR txn_date::date <= %(to)s::date)
              AND (%(type)s::text IS NULL OR txn_type = %(type)s::text)
              AND (%(cp)s::text   IS NULL OR counterparty ILIKE %(cp)s::text)
              AND (%(invno)s::text IS NULL OR invoice_number ILIKE %(invno)s::text)
              AND (%(amt)s::numeric  IS NULL OR abs(amount) >= %(amt)s::numeric)
            ORDER BY txn_date DESC NULLS LAST
        """, {"iid": investor_id, "from": fl["from"], "to": fl["to"],
              "type": fl["type"], "cp": fl["cp"], "invno": fl["invno"], "amt": fl["amt"]})
    except Exception:
        return []


# ── UI ──────────────────────────────────────────────────────────────────

_INPUT = ("w-full bg-bg-elevated border border-line rounded-lg px-3 py-2 text-sm "
          "text-ink focus:outline-none focus:border-accent")
_TH = "text-left text-[11px] font-mono tracking-widest uppercase text-ink-dim py-3 px-4"
_THR = _TH.replace("text-left", "text-right")


def _field(label, control):
    return Div(Label(label, cls="block text-[11px] font-mono uppercase tracking-widest text-ink-dim mb-1"),
               control)


def _filter_form(fl: dict, lang: str):
    raw = fl["_raw"]
    type_opts = [Option(t("stmt_all_types", lang), value="", selected=not raw["txn_type"])]
    for val, key in _TYPE_LABELS.items():
        type_opts.append(Option(t(key, lang), value=val, selected=raw["txn_type"] == val))
    return Form(
        Div(
            _field(t("stmt_from", lang), Input(type="date", name="date_from", value=raw["date_from"], cls=_INPUT)),
            _field(t("stmt_to", lang), Input(type="date", name="date_to", value=raw["date_to"], cls=_INPUT)),
            _field(t("stmt_type", lang), Select(*type_opts, name="txn_type", cls=_INPUT)),
            _field(t("stmt_counterparty", lang), Input(type="text", name="counterparty", value=raw["counterparty"], cls=_INPUT)),
            _field(t("stmt_invoice_no", lang), Input(type="text", name="invoice_no", value=raw["invoice_no"], cls=_INPUT)),
            _field(t("stmt_amount", lang), Input(type="number", name="min_amount", value=raw["min_amount"], step="any", cls=_INPUT)),
            cls="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3",
        ),
        Div(
            Button(t("stmt_filter", lang), type="submit",
                   cls="inline-flex items-center px-5 py-2 rounded-full text-sm font-medium bg-accent text-bg hover:bg-ink transition-all"),
            A(t("stmt_export", lang), href=_export_href(raw),
              cls="inline-flex items-center px-5 py-2 rounded-full text-sm font-medium border border-line-bright text-ink hover:border-accent hover:text-accent transition-all"),
            cls="flex items-center gap-3 mt-4",
        ),
        method="get", action="/app/statement",
        cls="p-6 rounded-2xl bg-bg-elevated border border-line mb-8",
    )


def _export_href(raw: dict) -> str:
    from urllib.parse import urlencode
    params = {k: v for k, v in raw.items() if v}
    qs = urlencode(params)
    return "/app/statement/export" + (f"?{qs}" if qs else "")


def _amount_cell(amount: float):
    pos = amount >= 0
    txt = ("+" if pos else "−") + fmt_uzs(abs(amount)).replace("UZS ", "UZS ")
    return Td(txt, cls="py-3 px-4 text-sm text-right tabular-nums " + ("text-accent" if pos else "text-ink"))


def _ledger_table(rows: list[dict], lang: str):
    if not rows:
        return Div(P(t("stmt_empty", lang), cls="text-ink-muted text-lg"), cls="py-12 text-center")
    body = []
    for r in rows:
        d = r["txn_date"]
        dstr = str(d.date()) if hasattr(d, "date") else (str(d) if d else "—")
        body.append(Tr(
            Td(dstr, cls="py-3 px-4 text-sm text-ink-muted"),
            Td(t(_TYPE_LABELS[r["txn_type"]], lang), cls="py-3 px-4 text-sm text-ink"),
            Td(r["counterparty"], cls="py-3 px-4 text-sm text-ink"),
            Td(r["invoice_number"], cls="py-3 px-4 text-sm text-ink-muted"),
            _amount_cell(float(r["amount"] or 0)),
            cls="border-b border-line hover:bg-bg-raised/50",
        ))
    return Div(Table(
        Thead(Tr(
            Th(t("stmt_date", lang), cls=_TH),
            Th(t("stmt_type", lang), cls=_TH),
            Th(t("stmt_counterparty", lang), cls=_TH),
            Th(t("stmt_invoice_no", lang), cls=_TH),
            Th(t("stmt_amount", lang), cls=_THR),
            cls="border-b border-line",
        )),
        Tbody(*body),
        cls="w-full",
    ), cls="rounded-2xl bg-bg-elevated border border-line overflow-hidden")


@rt("/app/statement")
def statement(req):
    lang = get_lang(req)
    investors = list_investors()
    investor = current_investor(req, investors)
    fl = _parse_filters(req)
    rows = _load_ledger(investor["id"], fl) if investor else []

    return app_page(
        t("stmt_eyebrow", lang),
        Section_(Eyebrow(t("stmt_eyebrow", lang)),
                 Heading(1, t("stmt_h1", lang), cls="mt-4 max-w-4xl"), cls="border-t border-line"),
        Section_(_filter_form(fl, lang), _ledger_table(rows, lang), cls="border-t border-line"),
        current_path="/app/statement", lang=lang, role=current_role(req), investor=investor, investors=investors,
    )


@rt("/app/statement/export")
def statement_export(req):
    investors = list_investors()
    investor = current_investor(req, investors)
    fl = _parse_filters(req)
    rows = _load_ledger(investor["id"], fl) if investor else []

    buf = io.StringIO()
    w = csv.writer(buf)
    from utils.money import convert_amount, display_currency
    currency = display_currency()
    w.writerow(["date", "type", "counterparty", "invoice_number",
                f"amount_{currency.lower()}"])
    for r in rows:
        d = r["txn_date"]
        dstr = str(d.date()) if hasattr(d, "date") else (str(d) if d else "")
        amount, _ = convert_amount(r["amount"], currency)
        w.writerow([dstr, r["txn_type"], r["counterparty"], r["invoice_number"],
                    f"{amount:.2f}"])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=factorio-statement.csv"},
    )
