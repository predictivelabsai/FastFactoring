"""Portfolio route: /app/portfolio — investor reporting cockpit.

Provides net-return and account-value hero panels, an investments-by-status
aging table, a debtor payment-habits table, and an enriched positions table
(realized returns + settlement date).
"""

from __future__ import annotations

from datetime import date

from fasthtml.common import Div, P, Span, A, Article, Table, Thead, Tbody, Tr, Th, Td

from app import rt
from utils.i18n import t, get_lang
from landing.components import page, Eyebrow, Heading, Section_
from app_routes._shared import (
    app_page, fmt_uzs, list_investors, current_investor, current_role,
    aging_bucket_key, days_late, AGING_BUCKETS,
)

try:
    from db import fetch_all
    _HAS_DB = True
except Exception:
    _HAS_DB = False


def _load_positions(investor_id: int) -> list[dict]:
    if not _HAS_DB:
        return []
    try:
        return fetch_all("""
            SELECT
                inv.id AS investment_id,
                inv.investment_amount,
                inv.expected_return_amount,
                inv.status,
                inv.investment_date,
                i.invoice_number, i.debtor_name, i.sector,
                i.due_date, i.risk_grade,
                c.name AS seller_company,
                s.settlement_date,
                d.amount AS dividend_amount,
                d.is_paid AS dividend_paid
            FROM factorio.investments inv
            JOIN factorio.invoice_funding f ON f.id = inv.funding_id
            JOIN factorio.invoices i ON i.id = f.invoice_id
            JOIN factorio.companies c ON c.id = i.company_id
            LEFT JOIN factorio.settlements s ON s.funding_id = f.id
            LEFT JOIN factorio.dividends d
                   ON d.funding_id = f.id AND d.investor_id = inv.investor_id
            WHERE inv.investor_id = %(iid)s
            ORDER BY inv.investment_date DESC
        """, {"iid": investor_id})
    except Exception:
        return []


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _delay_days(settlement, due) -> int | None:
    if settlement is None or due is None:
        return None
    s = settlement.date() if hasattr(settlement, "date") else settlement
    d = due.date() if hasattr(due, "date") else due
    return (s - d).days


def _habit_bucket_key(delay: int) -> str:
    if delay < 0:
        return "bkt_paid_earlier"
    if delay == 0:
        return "bkt_paid_on_time"
    return aging_bucket_key(delay)


def _compute(positions: list[dict]) -> dict:
    active = [p for p in positions if p["status"] == "confirmed"]
    settled = [p for p in positions if p["status"] == "settled"]
    defaulted = [p for p in positions if p["status"] == "defaulted"]

    active_invested = sum(_f(p["investment_amount"]) for p in active)
    expected_outstanding = sum(
        _f(p["expected_return_amount"]) - _f(p["investment_amount"]) for p in active)
    interest_received = sum(
        _f(p["dividend_amount"]) for p in settled if p["dividend_paid"])
    writeoffs = sum(_f(p["investment_amount"]) for p in defaulted)
    net_income = interest_received - writeoffs

    # Annualised net return, weighted by principal over realized hold periods.
    realized_principal = sum(_f(p["investment_amount"]) for p in settled)
    weighted_days = 0.0
    for p in settled:
        hold = 1
        if p["settlement_date"] and p["investment_date"]:
            hold = max(1, (p["settlement_date"] - p["investment_date"]).days)
        weighted_days += _f(p["investment_amount"]) * hold
    avg_hold = (weighted_days / realized_principal) if realized_principal else 0
    net_annual_return = 0.0
    if realized_principal and avg_hold:
        net_annual_return = (net_income / realized_principal) * (365.0 / avg_hold) * 100

    return {
        "active_invested": active_invested,
        "expected_outstanding": expected_outstanding,
        "interest_received": interest_received,
        "writeoffs": writeoffs,
        "net_income": net_income,
        "realized_returns": interest_received,
        "account_value": active_invested + interest_received,
        "net_annual_return": net_annual_return,
        "active": active, "settled": settled, "defaulted": defaulted,
    }


# ── UI helpers ──────────────────────────────────────────────────────────

_TH = "text-left text-[11px] font-mono tracking-widest uppercase text-ink-dim py-3 px-4"
_THR = _TH.replace("text-left", "text-right")
_TD = "py-3 px-4 text-sm text-ink"
_TDR = _TD + " text-right"


def _metric_panel(title: str, headline: str, rows: list[tuple]):
    body = []
    for label, value, *emph in rows:
        strong = emph and emph[0]
        body.append(Div(
            Span(label, cls="text-sm " + ("text-ink font-medium" if strong else "text-ink-muted")),
            Span(value, cls="text-sm tabular-nums " + ("text-ink font-medium" if strong else "text-ink")),
            cls="flex items-center justify-between py-2 " + ("border-t border-line" if strong else ""),
        ))
    return Article(
        P(title, cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-2"),
        P(headline, cls="text-4xl font-medium tracking-tighter text-ink mb-4"),
        Div(*body),
        cls="p-7 rounded-2xl bg-bg-elevated border border-line",
    )


def _status_badge(status: str):
    colors = {
        "pending": "bg-yellow-100 text-yellow-800",
        "confirmed": "bg-green-100 text-green-800",
        "settled": "bg-blue-100 text-blue-800",
        "defaulted": "bg-red-100 text-red-800",
    }
    return Span(status.title(),
                cls=f"px-2 py-0.5 rounded-full text-xs font-medium {colors.get(status, 'bg-gray-100 text-gray-800')}")


def _aging_table(active: list[dict], lang: str):
    today = date.today()
    buckets = {key: {"n": 0, "principal": 0.0, "interest": 0.0}
               for key, _, _ in AGING_BUCKETS}
    for p in active:
        key = aging_bucket_key(days_late(p["due_date"], today))
        b = buckets[key]
        b["n"] += 1
        b["principal"] += _f(p["investment_amount"])
        b["interest"] += _f(p["expected_return_amount"]) - _f(p["investment_amount"])

    rows = []
    for key, _, _ in AGING_BUCKETS:
        b = buckets[key]
        rows.append(Tr(
            Td(t(key, lang), cls=_TD),
            Td(str(b["n"]), cls=_TDR),
            Td(fmt_uzs(b["principal"]), cls=_TDR),
            Td(fmt_uzs(b["interest"]), cls=_TDR + " text-accent"),
            cls="border-b border-line",
        ))
    return Div(
        P(t("port_aging_title", lang), cls="text-sm font-medium text-ink mb-3"),
        Div(Table(
            Thead(Tr(
                Th(t("port_status", lang), cls=_TH),
                Th(t("port_col_invoices", lang), cls=_THR),
                Th(t("port_exp_principal", lang), cls=_THR),
                Th(t("port_exp_interest", lang), cls=_THR),
                cls="border-b border-line",
            )),
            Tbody(*rows),
            cls="w-full",
        ), cls="rounded-2xl bg-bg-elevated border border-line overflow-hidden"),
    )


def _habits_table(settled: list[dict], defaulted: list[dict], lang: str):
    order = ["bkt_paid_earlier", "bkt_paid_on_time", "bkt_late_1_14",
             "bkt_late_15_30", "bkt_late_31_60", "bkt_late_61_120", "bkt_late_120"]
    buckets = {key: {"n": 0, "amount": 0.0} for key in order}
    for p in settled:
        delay = _delay_days(p["settlement_date"], p["due_date"])
        if delay is None:
            continue
        b = buckets[_habit_bucket_key(delay)]
        b["n"] += 1
        b["amount"] += _f(p["investment_amount"])

    writeoff = {"n": len(defaulted), "amount": sum(_f(p["investment_amount"]) for p in defaulted)}
    total_n = sum(b["n"] for b in buckets.values()) + writeoff["n"]

    def _row(label, n, amount):
        pct = (n / total_n * 100) if total_n else 0
        return Tr(
            Td(label, cls=_TD),
            Td(str(n), cls=_TDR),
            Td(f"{pct:.0f}%", cls=_TDR + " text-ink-muted"),
            Td(fmt_uzs(amount), cls=_TDR),
            cls="border-b border-line",
        )

    rows = [_row(t(key, lang), buckets[key]["n"], buckets[key]["amount"]) for key in order]
    rows.append(_row(t("port_writeoffs", lang), writeoff["n"], writeoff["amount"]))
    return Div(
        P(t("port_habits_title", lang), cls="text-sm font-medium text-ink mb-3"),
        Div(Table(
            Thead(Tr(
                Th(t("port_status", lang), cls=_TH),
                Th(t("port_col_invoices", lang), cls=_THR),
                Th(t("port_col_percentage", lang), cls=_THR),
                Th(t("port_col_amount", lang), cls=_THR),
                cls="border-b border-line",
            )),
            Tbody(*rows),
            cls="w-full",
        ), cls="rounded-2xl bg-bg-elevated border border-line overflow-hidden"),
    )


def _positions_table(positions: list[dict], lang: str):
    rows = []
    for p in positions:
        realized = fmt_uzs(p["dividend_amount"]) if p["dividend_paid"] else "—"
        settled_on = str(p["settlement_date"].date()) if p["settlement_date"] else "—"
        rows.append(Tr(
            Td(p["invoice_number"], cls=_TD),
            Td(p["debtor_name"], cls=_TD),
            Td(fmt_uzs(p["investment_amount"]), cls=_TDR),
            Td(fmt_uzs(p["expected_return_amount"]), cls=_TDR + " text-accent"),
            Td(realized, cls=_TDR),
            Td(settled_on, cls=_TD + " text-ink-muted"),
            Td(p["risk_grade"], cls="py-3 px-4 text-sm text-center font-medium"),
            Td(_status_badge(p["status"]), cls="py-3 px-4 text-center"),
            cls="border-b border-line hover:bg-bg-raised/50",
        ))
    return Div(
        P(t("port_positions_title", lang), cls="text-sm font-medium text-ink mb-3"),
        Div(Table(
            Thead(Tr(
                Th(t("port_invoice", lang), cls=_TH),
                Th(t("port_debtor", lang), cls=_TH),
                Th(t("port_invested", lang), cls=_THR),
                Th(t("port_expected_col", lang), cls=_THR),
                Th(t("port_realized_col", lang), cls=_THR),
                Th(t("port_settled_col", lang), cls=_TH),
                Th(t("port_grade", lang), cls=_TH.replace("text-left", "text-center")),
                Th(t("port_status", lang), cls=_TH.replace("text-left", "text-center")),
                cls="border-b border-line",
            )),
            Tbody(*rows),
            cls="w-full",
        ), cls="rounded-2xl bg-bg-elevated border border-line overflow-hidden"),
    )


@rt("/app/portfolio")
def portfolio(req):
    lang = get_lang(req)
    investors = list_investors(req)
    investor = current_investor(req, investors)
    positions = _load_positions(investor["id"]) if investor else []
    m = _compute(positions)

    hero = Div(
        _metric_panel(
            t("port_net_return", lang),
            f"{m['net_annual_return']:.1f}%",
            [
                (t("port_interest_received", lang), fmt_uzs(m["interest_received"])),
                (t("port_writeoffs", lang), "−" + fmt_uzs(m["writeoffs"])),
                (t("port_net_income", lang), fmt_uzs(m["net_income"]), True),
            ],
        ),
        _metric_panel(
            t("port_account_value", lang),
            fmt_uzs(m["account_value"]),
            [
                (t("port_invested_active", lang), fmt_uzs(m["active_invested"])),
                (t("port_expected_outstanding", lang), fmt_uzs(m["expected_outstanding"])),
                (t("port_realized", lang), fmt_uzs(m["realized_returns"]), True),
            ],
        ),
        cls="grid md:grid-cols-2 gap-4 mb-10",
    )

    if not positions:
        empty = Div(
            P(t("port_empty", lang), cls="text-ink-muted text-lg"),
            P(A(t("footer_marketplace", lang), href="/app/marketplace", cls="text-accent underline"),
              cls="text-ink-muted mt-2"),
            cls="py-12 text-center",
        )
        return app_page(
            t("port_eyebrow", lang),
            Section_(Eyebrow(t("port_eyebrow", lang)),
                     Heading(1, t("port_h1", lang), cls="mt-4 max-w-4xl"), cls="border-t border-line"),
            Section_(hero, empty, cls="border-t border-line"),
            current_path="/app/portfolio", lang=lang, role=current_role(req), investor=investor, investors=investors,
        )

    return app_page(
        t("port_eyebrow", lang),
        Section_(Eyebrow(t("port_eyebrow", lang)),
                 Heading(1, t("port_h1", lang), cls="mt-4 max-w-4xl"), cls="border-t border-line"),
        Section_(
            hero,
            Div(_aging_table(m["active"], lang),
                _habits_table(m["settled"], m["defaulted"], lang),
                cls="grid lg:grid-cols-2 gap-4 mb-10"),
            _positions_table(positions, lang),
            cls="border-t border-line",
        ),
        current_path="/app/portfolio", lang=lang, role=current_role(req), investor=investor, investors=investors,
    )
