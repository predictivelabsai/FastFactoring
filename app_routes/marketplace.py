"""Marketplace route: /app/marketplace — browse fundable invoices.

Adds a filter bar (sector / risk grade / max term / min return, via GET query
params) and a debtor-company profile block on the detail page. Uses the shared
`app_page` so the investor sub-nav + switcher appear here too.
"""

from __future__ import annotations

from fasthtml.common import (
    Div, H3, P, Span, A, Article, Form, Input, Select, Option, Button, Label, NotStr,
)
from starlette.responses import RedirectResponse

from app import rt
from utils.i18n import t, get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, list_investors, current_investor, current_role

try:
    from db import connect, fetch_all
    _HAS_DB = True
except Exception:
    _HAS_DB = False

_GRADES = ["A", "B", "C", "D"]
_INPUT = ("w-full bg-bg-elevated border border-line rounded-lg px-3 py-2 text-sm "
          "text-ink focus:outline-none focus:border-accent")


def _parse_filters(req) -> dict:
    q = req.query_params

    def _s(key):
        v = (q.get(key) or "").strip()
        return v or None

    def _n(key):
        v = _s(key)
        try:
            return float(v) if v else None
        except ValueError:
            return None

    grade = _s("risk")
    if grade not in _GRADES:
        grade = None
    return {
        "sector": _s("sector"),
        "risk": grade,
        "max_term": _n("max_term"),
        "min_return": _n("min_return"),
        "_raw": {k: (q.get(k) or "") for k in ("sector", "risk", "max_term", "min_return")},
    }


def _sectors() -> list[str]:
    if not _HAS_DB:
        return []
    try:
        rows = fetch_all(
            "SELECT DISTINCT sector FROM factorio.invoices "
            "WHERE sector IS NOT NULL AND sector <> '' ORDER BY sector"
        )
        return [r["sector"] for r in rows]
    except Exception:
        return []


def _load_marketplace(fl: dict) -> list[dict]:
    if not _HAS_DB:
        return []
    try:
        return fetch_all("""
            SELECT
                f.id AS funding_id,
                i.invoice_number,
                i.debtor_name,
                i.sector,
                i.amount AS invoice_amount,
                i.currency,
                i.due_date,
                i.risk_grade,
                f.funding_goal,
                f.amount_raised,
                f.advance_rate_pct,
                f.fee_pct_per_30d,
                f.estimated_return_pct,
                f.target_hold_days,
                c.name AS seller_company
            FROM factorio.invoice_funding f
            JOIN factorio.invoices i ON i.id = f.invoice_id
            JOIN factorio.companies c ON c.id = i.company_id
            WHERE f.funding_status = 'open' AND f.show_in_marketplace = TRUE
              AND (%(sector)s::text IS NULL OR i.sector = %(sector)s::text)
              AND (%(risk)s::text IS NULL OR i.risk_grade = %(risk)s::text)
              AND (%(max_term)s::int IS NULL OR f.target_hold_days <= %(max_term)s::int)
              AND (%(min_return)s::numeric IS NULL OR f.estimated_return_pct >= %(min_return)s::numeric)
            ORDER BY f.created_at DESC
        """, {"sector": fl["sector"], "risk": fl["risk"],
              "max_term": fl["max_term"], "min_return": fl["min_return"]})
    except Exception:
        return []


def _risk_color(grade: str) -> str:
    return {"A": "text-green-700", "B": "text-accent", "C": "text-yellow-700", "D": "text-red-700"}.get(grade, "text-ink-muted")


def _progress_pct(raised: float, goal: float) -> int:
    if not goal:
        return 0
    return min(100, int((raised / goal) * 100))


def _cur(currency: str, amount: float) -> str:
    # Stored amounts are UZS-scale; display in the app's currency (USD default).
    from utils.money import fmt_money
    return fmt_money(amount)


def _field(label, control):
    return Div(Label(label, cls="block text-[11px] font-mono uppercase tracking-widest text-ink-dim mb-1"),
               control)


def _filter_form(fl: dict, sectors: list[str], lang: str):
    raw = fl["_raw"]
    sector_opts = [Option(t("mkt_all", lang), value="", selected=not raw["sector"])]
    for s in sectors:
        sector_opts.append(Option(s.title(), value=s, selected=raw["sector"] == s))
    risk_opts = [Option(t("mkt_all", lang), value="", selected=not raw["risk"])]
    for g in _GRADES:
        risk_opts.append(Option(g, value=g, selected=raw["risk"] == g))
    return Form(
        Div(
            _field(t("mkt_sector", lang), Select(*sector_opts, name="sector", cls=_INPUT)),
            _field(t("mkt_risk", lang), Select(*risk_opts, name="risk", cls=_INPUT)),
            _field(t("mkt_max_term", lang),
                   Input(type="number", name="max_term", min="0", value=raw["max_term"], cls=_INPUT)),
            _field(t("mkt_min_return", lang),
                   Input(type="number", name="min_return", min="0", step="any", value=raw["min_return"], cls=_INPUT)),
            cls="grid grid-cols-2 md:grid-cols-4 gap-3",
        ),
        Div(
            Button(t("mkt_apply", lang), type="submit",
                   cls="inline-flex items-center px-5 py-2 rounded-full text-sm font-medium bg-accent text-bg hover:bg-ink transition-all"),
            A(t("mkt_clear", lang), href="/app/marketplace",
              cls="inline-flex items-center px-5 py-2 rounded-full text-sm font-medium border border-line-bright text-ink hover:border-accent hover:text-accent transition-all"),
            cls="flex items-center gap-3 mt-4",
        ),
        method="get", action="/app/marketplace",
        cls="p-6 rounded-2xl bg-bg-elevated border border-line mb-8",
    )


def _invoice_card(row: dict, lang: str):
    pct = _progress_pct(float(row["amount_raised"]), float(row["funding_goal"]))
    cur = row["currency"]
    return Article(
        Div(
            Span(row["sector"].title(), cls="font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
            Span(row["risk_grade"], cls=f"font-mono text-sm font-medium {_risk_color(row['risk_grade'])}"),
            cls="flex items-center justify-between mb-4",
        ),
        H3(row["debtor_name"], cls="text-ink text-lg font-medium mb-1"),
        P(f"{t('mkt_seller', lang)}: {row['seller_company']}", cls="text-ink-muted text-sm mb-4"),
        Div(
            Div(
                Span(_cur(cur, float(row["invoice_amount"])), cls="text-ink font-medium"),
                Span(f" {t('mkt_invoice', lang)}", cls="text-ink-muted text-sm"),
                cls="mb-2",
            ),
            Div(
                Div(cls="h-2 rounded-full bg-accent", style=f"width: {pct}%"),
                cls="h-2 rounded-full bg-line overflow-hidden mb-2",
            ),
            Div(
                Span(f"{pct}% {t('mkt_funded', lang)}", cls="text-ink-muted text-xs"),
                Span(f"{row['target_hold_days']}d {t('mkt_term', lang)}", cls="text-ink-muted text-xs"),
                cls="flex justify-between",
            ),
            cls="mb-4",
        ),
        Div(
            Div(
                P(t("mkt_advance", lang), cls="text-[10px] font-mono uppercase text-ink-dim"),
                P(f"{float(row['advance_rate_pct']):.0f}%", cls="text-ink font-medium"),
            ),
            Div(
                P(t("mkt_fee", lang), cls="text-[10px] font-mono uppercase text-ink-dim"),
                P(f"{float(row['fee_pct_per_30d']):.1f}%", cls="text-ink font-medium"),
            ),
            Div(
                P(t("mkt_est_return", lang), cls="text-[10px] font-mono uppercase text-ink-dim"),
                P(f"{float(row['estimated_return_pct']):.1f}%", cls="text-accent font-medium"),
            ),
            cls="grid grid-cols-3 gap-3 mb-5",
        ),
        A(NotStr(t("mkt_invest", lang) + " &rarr;"), href=f"/app/marketplace/{row['funding_id']}",
          cls="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium bg-accent text-bg hover:bg-ink transition-all"),
        cls="p-6 rounded-2xl bg-bg-elevated border border-line hover:border-accent/50 transition-colors",
    )


@rt("/app/marketplace")
def marketplace(req):
    lang = get_lang(req)
    investors = list_investors(req)
    investor = current_investor(req, investors)
    fl = _parse_filters(req)
    listings = _load_marketplace(fl)

    empty = Div(
        P(t("mkt_empty", lang), cls="text-ink-muted text-lg"),
        cls="py-12 text-center",
    ) if not listings else None

    grid = Div(
        *[_invoice_card(r, lang) for r in listings],
        cls="grid sm:grid-cols-2 lg:grid-cols-3 gap-4",
    ) if listings else None

    return app_page(
        t("mkt_eyebrow", lang),
        Section_(
            Eyebrow(t("mkt_eyebrow", lang)),
            Heading(1, t("mkt_h1", lang), cls="mt-4 max-w-4xl"),
            P(f"{len(listings)} {t('mkt_count', lang)}.",
              cls="mt-4 text-ink-muted text-lg"),
            cls="border-t border-line",
        ),
        Section_(_filter_form(fl, _sectors(), lang), grid or empty, cls="border-t border-line"),
        current_path="/app/marketplace", lang=lang, role=current_role(req), investor=investor, investors=investors,
    )


@rt("/app/marketplace/{funding_id:int}")
def marketplace_detail(req, funding_id: int):
    lang = get_lang(req)
    investors = list_investors(req)
    investor = current_investor(req, investors)
    if not _HAS_DB:
        return app_page("Not found", Section_(P("Database not configured.")),
                        current_path="/app/marketplace", lang=lang,
                        role=current_role(req), investor=investor, investors=investors)

    try:
        row = fetch_all("""
            SELECT
                f.*, i.invoice_number, i.debtor_name, i.debtor_registration,
                i.description, i.sector, i.amount AS invoice_amount, i.currency,
                i.issue_date, i.due_date, i.payment_terms_days, i.risk_grade,
                c.name AS seller_company, c.registration_number AS seller_reg,
                c.sector AS seller_sector, c.country AS seller_country,
                c.annual_turnover AS seller_turnover
            FROM factorio.invoice_funding f
            JOIN factorio.invoices i ON i.id = f.invoice_id
            JOIN factorio.companies c ON c.id = i.company_id
            WHERE f.id = %s
              AND f.funding_status = 'open'
              AND f.show_in_marketplace = TRUE
        """, (funding_id,))
    except Exception:
        row = []

    if not row:
        return app_page("Not found", Section_(
            Heading(1, "Invoice not found.", cls="mt-4"),
        ), current_path="/app/marketplace", lang=lang, role=current_role(req), investor=investor, investors=investors)

    r = row[0]
    pct = _progress_pct(float(r["amount_raised"]), float(r["funding_goal"]))
    cur = r["currency"]

    def _detail(label, value):
        return Div(
            P(label, cls="text-[10px] font-mono uppercase tracking-widest text-ink-dim mb-1"),
            P(str(value), cls="text-ink font-medium"),
        )

    debtor_profile = Div(
        P(t("mkt_debtor_profile", lang), cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-4"),
        Div(
            _detail(t("mkt_seller", lang), r["seller_company"]),
            _detail(t("mkt_registration", lang), r["seller_reg"] or "—"),
            _detail(t("mkt_sector", lang), (r["seller_sector"] or "—").title()),
            _detail(t("mkt_country", lang), r["seller_country"] or "—"),
            _detail(t("mkt_turnover", lang),
                    _cur(cur, float(r["seller_turnover"])) if r["seller_turnover"] else "—"),
            cls="grid grid-cols-2 gap-4",
        ),
        cls="p-6 rounded-2xl bg-bg-elevated border border-line",
    )
    invest_form = None
    if investor:
        from utils.access import context_for
        ctx = context_for(req)
        remaining = max(0, float(r["funding_goal"]) - float(r["amount_raised"]))
        if remaining > 0:
            invest_form = Form(
                Label("Investment amount", cls="text-sm text-ink-muted"),
                Input(type="number", name="amount", min="1", max=str(remaining),
                      value=str(min(remaining, max(50, float(r["minimum_investment"] or 50)))),
                      step="0.01", required=True, cls=_INPUT),
                Input(type="hidden", name="funding_id", value=funding_id),
                Input(type="hidden", name="csrf", value=ctx.csrf_token),
                Button("Invest", type="submit",
                       cls="mt-3 px-5 py-2 rounded-full bg-accent text-white"),
                action="/app/marketplace/invest", method="post",
                cls="mt-6 max-w-sm")

    return app_page(
        f"{r['debtor_name']}",
        Section_(
            A(NotStr("&larr; " + t("mkt_back", lang)), href="/app/marketplace", cls="text-ink-dim text-xs hover:text-accent mb-6 inline-block"),
            Div(
                Span(r["risk_grade"], cls=f"text-2xl font-medium {_risk_color(r['risk_grade'])} mr-3"),
                Span(r["sector"].title(), cls="font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
                cls="flex items-center mb-4",
            ),
            Heading(1, r["debtor_name"], cls="max-w-4xl"),
            P(f"Invoice #{r['invoice_number']} · {t('mkt_seller', lang)}: {r['seller_company']} ({r['seller_country']})",
              cls="mt-3 text-ink-muted text-lg"),
            cls="border-t border-line",
        ),
        Section_(
            Div(
                Div(
                    Div(
                        Div(cls="h-3 rounded-full bg-accent", style=f"width: {pct}%"),
                        cls="h-3 rounded-full bg-line overflow-hidden mb-3",
                    ),
                    Div(
                        Span(f"{_cur(cur, float(r['amount_raised']))} raised", cls="text-ink font-medium"),
                        Span(f"of {_cur(cur, float(r['funding_goal']))} goal", cls="text-ink-muted text-sm ml-2"),
                        cls="mb-8",
                    ),
                    Div(
                        _detail(t("mkt_invoice", lang).title(), _cur(cur, float(r["invoice_amount"]))),
                        _detail(t("mkt_advance", lang), f"{float(r['advance_rate_pct']):.0f}%"),
                        _detail(t("mkt_fee", lang), f"{float(r['fee_pct_per_30d']):.1f}%"),
                        _detail(t("mkt_est_return", lang), f"{float(r['estimated_return_pct']):.1f}%"),
                        cls="grid grid-cols-2 md:grid-cols-4 gap-6",
                    ),
                    invest_form,
                    cls="md:col-span-2",
                ),
                debtor_profile,
                cls="grid md:grid-cols-3 gap-8",
            ),
            cls="border-t border-line",
        ),
        current_path="/app/marketplace", lang=lang, role=current_role(req), investor=investor, investors=investors,
    )


@rt("/app/marketplace/invest", methods=["POST"])
def marketplace_invest(req, funding_id: int = 0, amount: float = 0, csrf: str = ""):
    import hmac
    from utils.access import audit, context_for
    ctx = context_for(req)
    investor = current_investor(req, list_investors(req))
    expected = str(req.session.get("csrf_token") or "")
    if (ctx.effective_role != "investor" or not investor or amount <= 0 or
            not expected or not hmac.compare_digest(expected, csrf)):
        return RedirectResponse("/app", status_code=303)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT f.funding_goal,f.amount_raised,f.estimated_return_pct,
                                  i.is_synthetic
                             FROM factorio.invoice_funding f
                             JOIN factorio.invoices i ON i.id=f.invoice_id
                            WHERE f.id=%s AND f.funding_status='open'
                              AND f.show_in_marketplace=TRUE
                            FOR UPDATE""", (funding_id,))
            row = cur.fetchone()
            if not row or (ctx.is_synthetic and not row[3]):
                conn.rollback()
                audit(ctx, "investment_denied", str(funding_id), "target_not_synthetic_visible_or_open")
                return RedirectResponse("/app/marketplace", status_code=303)
            remaining = float(row[0]) - float(row[1])
            placed = min(float(amount), remaining)
            if placed <= 0:
                conn.rollback()
                return RedirectResponse(f"/app/marketplace/{funding_id}", status_code=303)
            expected_return = placed * float(row[2]) / 100
            ownership = placed / float(row[0]) * 100 if row[0] else 0
            cur.execute("""INSERT INTO factorio.investments(
                              funding_id,investor_id,investment_amount,ownership_pct,
                              expected_return_amount,status)
                           VALUES (%s,%s,%s,%s,%s,'confirmed')
                           ON CONFLICT(funding_id,investor_id) DO UPDATE SET
                             investment_amount=factorio.investments.investment_amount+EXCLUDED.investment_amount,
                             ownership_pct=factorio.investments.ownership_pct+EXCLUDED.ownership_pct,
                             expected_return_amount=factorio.investments.expected_return_amount+EXCLUDED.expected_return_amount,
                             status='confirmed',updated_at=now()""",
                        (funding_id, investor["id"], placed, ownership, expected_return))
            cur.execute("""UPDATE factorio.invoice_funding SET amount_raised=amount_raised+%s,
                              funding_status=CASE WHEN amount_raised+%s>=funding_goal THEN 'funded' ELSE funding_status END
                            WHERE id=%s""", (placed, placed, funding_id))
        conn.commit()
    audit(ctx, "investment_created", str(funding_id),
          f"amount={placed};preview={ctx.preview};investor={investor['id']}")
    return RedirectResponse("/app/portfolio", status_code=303)
