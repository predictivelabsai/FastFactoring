"""Dashboard route: /app — personalized investor overview.

Shows the switched investor's own KPIs (portfolio value, net return, earned to
date, next settlement) and a recent-activity feed first; platform-wide stats
are demoted to a secondary strip.
"""

from __future__ import annotations

from datetime import date

from fasthtml.common import Div, P, Span, A, Article, NotStr

from app import rt
from utils.i18n import t, get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, fmt_uzs, list_investors, current_investor, current_role, display_name
from app_routes.portfolio import _load_positions, _compute, _f

try:
    from db import fetch_one, fetch_all
    _HAS_DB = True
except Exception:
    _HAS_DB = False


def _stat_card(label: str, value: str, sub: str = ""):
    return Article(
        P(label, cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-3"),
        P(value, cls="text-3xl md:text-4xl font-medium tracking-tighter text-ink mb-1"),
        P(sub, cls="text-ink-muted text-sm") if sub else None,
        cls="p-7 rounded-2xl bg-bg-elevated border border-line",
    )


def _platform_stats() -> dict:
    if not _HAS_DB:
        return {}
    try:
        return fetch_one("""
            SELECT
                COALESCE(SUM(f.amount_raised), 0) AS total_funded,
                COUNT(DISTINCT i.id) AS total_invoices,
                COUNT(DISTINCT CASE WHEN i.status = 'funding' THEN i.id END) AS active_invoices,
                COUNT(DISTINCT inv.investor_id) AS total_investors
            FROM factorio.invoices i
            LEFT JOIN factorio.invoice_funding f ON f.invoice_id = i.id
            LEFT JOIN factorio.investments inv ON inv.funding_id = f.id
        """) or {}
    except Exception:
        return {}


def _notifications(investor_id: int) -> list[dict]:
    if not _HAS_DB:
        return []
    try:
        return fetch_all("""
            SELECT title, message, type, created_at, is_read
            FROM factorio.notifications
            WHERE user_id = %(iid)s
            ORDER BY created_at DESC
            LIMIT 8
        """, {"iid": investor_id})
    except Exception:
        return []


def _next_settlement(positions: list[dict]):
    today = date.today()
    upcoming = []
    for p in positions:
        if p["status"] != "confirmed" or not p["due_date"]:
            continue
        due = p["due_date"]
        d = due.date() if hasattr(due, "date") else due
        if d >= today:
            upcoming.append((d, p))
    if not upcoming:
        return None
    upcoming.sort(key=lambda x: x[0])
    d, p = upcoming[0]
    return {"date": d, "debtor": p["debtor_name"],
            "amount": _f(p["expected_return_amount"])}


def _activity_feed(notes: list[dict], lang: str):
    if not notes:
        return P(t("dash_no_activity", lang), cls="text-ink-muted text-sm")
    items = []
    for n in notes:
        when = n["created_at"]
        wstr = str(when.date()) if hasattr(when, "date") else ""
        items.append(Div(
            Div(
                Span(n["title"], cls="text-sm text-ink font-medium"),
                Span(wstr, cls="text-xs text-ink-dim"),
                cls="flex items-center justify-between",
            ),
            P(n["message"], cls="text-sm text-ink-muted mt-0.5") if n["message"] else None,
            cls="py-3 border-b border-line last:border-0",
        ))
    return Div(*items)


@rt("/app/dashboard")
def dashboard(req):
    lang = get_lang(req)
    investors = list_investors(req)
    investor = current_investor(req, investors)
    positions = _load_positions(investor["id"]) if investor else []
    m = _compute(positions)
    nxt = _next_settlement(positions)
    notes = _notifications(investor["id"]) if investor else []
    name = display_name(investor["username"]) if investor else ""

    kpis = Div(
        _stat_card(t("dash_portfolio_value", lang), fmt_uzs(m["account_value"])),
        _stat_card(t("dash_net_return", lang), f"{m['net_annual_return']:.1f}%"),
        _stat_card(t("dash_earned", lang), fmt_uzs(m["realized_returns"])),
        _stat_card(
            t("dash_next_settlement", lang),
            str(nxt["date"]) if nxt else "—",
            nxt["debtor"] if nxt else "",
        ),
        cls="grid md:grid-cols-2 lg:grid-cols-4 gap-4",
    )

    activity = Div(
        Div(
            P(t("dash_activity", lang), cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-3"),
            _activity_feed(notes, lang),
            cls="p-7 rounded-2xl bg-bg-elevated border border-line lg:col-span-2",
        ),
        Div(
            P(t("dash_your_overview", lang), cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-4"),
            A(NotStr(t("dash_browse", lang) + " &rarr;"), href="/app/marketplace",
              cls="block mb-3 px-5 py-3 rounded-full text-sm font-medium bg-accent text-bg hover:bg-ink transition-all text-center"),
            A(NotStr(t("dash_portfolio", lang) + " &rarr;"), href="/app/portfolio",
              cls="block mb-3 px-5 py-3 rounded-full text-sm font-medium border border-line-bright text-ink hover:border-accent hover:text-accent transition-all text-center"),
            A(NotStr(t("nav_statement", lang) + " &rarr;"), href="/app/statement",
              cls="block px-5 py-3 rounded-full text-sm font-medium border border-line-bright text-ink hover:border-accent hover:text-accent transition-all text-center"),
            cls="p-7 rounded-2xl bg-bg-elevated border border-line",
        ),
        cls="grid lg:grid-cols-3 gap-4",
    )

    s = _platform_stats()
    platform = Div(
        P(t("dash_platform", lang), cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-4"),
        Div(
            _stat_card(t("dash_total_funded", lang), fmt_uzs(s.get("total_funded", 0)), t("dash_total_submitted", lang)),
            _stat_card(t("dash_invoices", lang), str(s.get("total_invoices", 0)), t("dash_total_submitted", lang)),
            _stat_card(t("dash_active", lang), str(s.get("active_invoices", 0)), t("dash_seeking", lang)),
            _stat_card(t("dash_investors", lang), str(s.get("total_investors", 0)), t("dash_active_platform", lang)),
            cls="grid md:grid-cols-2 lg:grid-cols-4 gap-4",
        ),
    )

    welcome = t("dash_welcome", lang) + (f", {name}" if name else "") + "."

    return app_page(
        t("dash_eyebrow", lang),
        Section_(
            Eyebrow(t("dash_eyebrow", lang)),
            Heading(1, welcome, cls="mt-4 max-w-4xl"),
            P(t("dash_lede", lang), cls="mt-4 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        Section_(kpis, Div(activity, cls="mt-4"), cls="border-t border-line"),
        Section_(platform, cls="border-t border-line"),
        current_path="/app/dashboard", lang=lang, role=current_role(req), investor=investor, investors=investors,
    )
