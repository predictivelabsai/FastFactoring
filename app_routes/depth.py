"""Marketplace depth — reverse-auction & secondary market (step 10b).

Two mechanisms that give the marketplace real depth beyond fixed-price listings:

* **Reverse auction** — investors compete to fund an invoice by bidding the fee
  *down* (and advance rate *up*); the best (lowest-fee) bid wins. Persisted in
  ``auction_bids``.
* **Secondary market** — an investor lists a confirmed position for sale; another
  buys it and ownership transfers. Persisted in the existing ``secondary_market``.

The **autobidder** (rules that auto-place investments) already ships as Auto-Invest
(``factorio.auto_invest``), so this module completes the trio.
"""

from __future__ import annotations

from fasthtml.common import (
    Div, P, Span, A, H3, Form, Input, Button, Label, NotStr,
    Table, Thead, Tbody, Tr, Th, Td,
)
from starlette.responses import RedirectResponse

from app import rt
from utils.i18n import get_lang
from utils.money import fmt_money
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, list_investors, current_investor, current_role

try:
    from db import connect, fetch_all, fetch_one, execute
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False

_INPUT = ("w-full bg-bg-elevated border border-line rounded-lg px-3 py-2 text-sm "
          "text-ink focus:outline-none focus:border-accent")
_TH = "text-left text-[11px] font-mono tracking-widest uppercase text-ink-dim py-3 px-4"
_TD = "py-3 px-4 text-sm text-ink"


def _ensure():
    if not _HAS_DB:
        return
    execute("""CREATE TABLE IF NOT EXISTS factorio.auction_bids (
        id BIGSERIAL PRIMARY KEY,
        funding_id BIGINT NOT NULL REFERENCES factorio.invoice_funding(id) ON DELETE CASCADE,
        investor_id BIGINT NOT NULL REFERENCES factorio.users(id) ON DELETE CASCADE,
        bid_fee_pct NUMERIC(5,2) NOT NULL,
        bid_advance_pct NUMERIC(5,2) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now())""")


def _table(headers, rows):
    return Div(Table(Thead(Tr(*[Th(h, cls=_TH) for h in headers], cls="border-b border-line")),
                     Tbody(*rows), cls="w-full"),
               cls="rounded-2xl bg-bg-elevated border border-line overflow-hidden overflow-x-auto")


def _tabs(active: str):
    def _t(label, href, key):
        return A(label, href=href,
                 cls="px-4 py-2 rounded-full text-sm " +
                     ("bg-accent text-bg" if key == active else "border border-line text-ink-muted hover:text-ink"))
    return Div(_t("Reverse auction", "/app/marketplace/auctions", "auction"),
               _t("Secondary market", "/app/marketplace/secondary", "secondary"),
               cls="flex items-center gap-2 mb-8")


# ── Reverse auction ─────────────────────────────────────────────────────────

@rt("/app/marketplace/auctions")
def auctions(req):
    lang = get_lang(req)
    try:
        _ensure()
    except Exception:
        pass
    investors = list_investors()
    investor = current_investor(req, investors)
    rows = fetch_all("""
        SELECT f.id AS funding_id, i.debtor_name, i.sector, i.amount AS invoice_amount,
               f.advance_rate_pct, f.fee_pct_per_30d, f.estimated_return_pct,
               c.name AS seller_company,
               (SELECT MIN(bid_fee_pct) FROM factorio.auction_bids b WHERE b.funding_id=f.id) AS best_fee,
               (SELECT MAX(bid_advance_pct) FROM factorio.auction_bids b WHERE b.funding_id=f.id) AS best_advance,
               (SELECT COUNT(*) FROM factorio.auction_bids b WHERE b.funding_id=f.id) AS n_bids
        FROM factorio.invoice_funding f
        JOIN factorio.invoices i ON i.id=f.invoice_id
        JOIN factorio.companies c ON c.id=i.company_id
        WHERE f.funding_status='open' AND f.show_in_marketplace=TRUE
        ORDER BY f.created_at DESC LIMIT 12
    """) if _HAS_DB else []

    cards = []
    for r in rows:
        best_fee = r["best_fee"] if r["best_fee"] is not None else r["fee_pct_per_30d"]
        best_adv = r["best_advance"] if r["best_advance"] is not None else r["advance_rate_pct"]
        cards.append(Div(
            Div(Span((r["sector"] or "").title(), cls="font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
                Span(f"{r['n_bids']} bids", cls="text-[11px] text-ink-muted"),
                cls="flex items-center justify-between mb-2"),
            H3(r["debtor_name"], cls="text-ink text-lg font-medium"),
            P(f"Seller: {r['seller_company']} · {fmt_money(float(r['invoice_amount']))}",
              cls="text-ink-muted text-sm mb-3"),
            Div(Div(P("Best fee /30d", cls="text-[10px] font-mono uppercase text-ink-dim"),
                    P(f"{float(best_fee):.2f}%", cls="text-accent font-medium")),
                Div(P("Best advance", cls="text-[10px] font-mono uppercase text-ink-dim"),
                    P(f"{float(best_adv):.0f}%", cls="text-ink font-medium")),
                cls="grid grid-cols-2 gap-3 mb-4"),
            Form(
                Div(Label("Your fee %/30d", cls="text-[10px] font-mono uppercase text-ink-dim"),
                    Input(type="number", name="bid_fee_pct", step="0.01", min="0",
                          value=f"{float(best_fee):.2f}", required=True, cls=_INPUT)),
                Div(Label("Your advance %", cls="text-[10px] font-mono uppercase text-ink-dim mt-2 block"),
                    Input(type="number", name="bid_advance_pct", step="1", min="0", max="100",
                          value=f"{float(best_adv):.0f}", required=True, cls=_INPUT)),
                Input(type="hidden", name="funding_id", value=str(r["funding_id"])),
                Button("Place bid", type="submit",
                       cls="w-full mt-3 px-4 py-2 rounded-full text-sm font-medium bg-accent text-bg hover:bg-ink transition-all"),
                method="post", action="/app/marketplace/auctions/bid"),
            cls="p-6 rounded-2xl bg-bg-elevated border border-line"))

    empty = P("No open auctions.", cls="text-ink-muted") if not cards else None
    return app_page(
        "Reverse auction",
        Section_(Eyebrow("Marketplace · Depth"),
                 Heading(1, "Reverse auction", cls="mt-4"),
                 P("Bid the fee down and the advance up — the best bid wins the invoice. "
                   "A live price-discovery layer on top of fixed-price listings.",
                   cls="mt-3 text-ink-muted max-w-3xl"), cls="border-t border-line"),
        Section_(_tabs("auction"),
                 Div(*cards, cls="grid sm:grid-cols-2 lg:grid-cols-3 gap-4") if cards else empty,
                 cls="border-t border-line"),
        current_path="/app/marketplace/auctions", lang=lang, role=current_role(req), investor=investor, investors=investors,
    )


@rt("/app/marketplace/auctions/bid", methods=["POST"])
async def auctions_bid(req, funding_id: int = 0, bid_fee_pct: float = 0.0, bid_advance_pct: float = 0.0):
    investors = list_investors()
    investor = current_investor(req, investors)
    if _HAS_DB and investor and funding_id and 0 <= bid_fee_pct <= 100 and 0 <= bid_advance_pct <= 100:
        try:
            _ensure()
            with connect() as conn, conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT id FROM factorio.invoice_funding
                             WHERE id=%s AND funding_status='open'
                               AND show_in_marketplace=TRUE
                             FOR UPDATE""",
                        (funding_id,),
                    )
                    if cur.fetchone():
                        cur.execute(
                            """INSERT INTO factorio.auction_bids
                                      (funding_id,investor_id,bid_fee_pct,bid_advance_pct)
                               VALUES (%s,%s,%s,%s)""",
                            (funding_id, investor["id"], bid_fee_pct, bid_advance_pct),
                        )
        except Exception:
            pass
    return RedirectResponse("/app/marketplace/auctions", status_code=303)


# ── Secondary market ────────────────────────────────────────────────────────

@rt("/app/marketplace/secondary")
def secondary(req):
    lang = get_lang(req)
    investors = list_investors()
    investor = current_investor(req, investors)

    listed = fetch_all("""
        SELECT s.id, s.listing_price, s.investor_id AS seller_id, u.username AS seller,
               inv.investment_amount, inv.expected_return_amount,
               i.debtor_name, i.sector, f.estimated_return_pct
        FROM factorio.secondary_market s
        JOIN factorio.investments inv ON inv.id=s.investment_id
        JOIN factorio.invoice_funding f ON f.id=inv.funding_id
        JOIN factorio.invoices i ON i.id=f.invoice_id
        JOIN factorio.users u ON u.id=s.investor_id
        WHERE s.status='listed' ORDER BY s.created_at DESC
    """) if _HAS_DB else []

    my_positions = fetch_all("""
        SELECT inv.id, inv.investment_amount, inv.expected_return_amount,
               i.debtor_name, f.estimated_return_pct
        FROM factorio.investments inv
        JOIN factorio.invoice_funding f ON f.id=inv.funding_id
        JOIN factorio.invoices i ON i.id=f.invoice_id
        WHERE inv.investor_id=%(iid)s AND inv.status IN ('confirmed','pending')
          AND inv.id NOT IN (SELECT investment_id FROM factorio.secondary_market WHERE status='listed')
        ORDER BY inv.investment_amount DESC LIMIT 8
    """, {"iid": investor["id"]}) if (_HAS_DB and investor) else []

    listed_rows = [Tr(
        Td(r["debtor_name"], cls=_TD),
        Td((r["sector"] or "").title(), cls=_TD + " text-ink-muted"),
        Td(fmt_money(float(r["investment_amount"])), cls=_TD),
        Td(f"{float(r['estimated_return_pct']):.1f}%", cls=_TD + " text-accent"),
        Td(r["seller"], cls=_TD + " text-ink-muted"),
        Td(fmt_money(float(r["listing_price"])), cls=_TD + " font-medium"),
        Td(Form(Input(type="hidden", name="listing_id", value=r["id"]),
                Input(type="hidden", name="csrf", value=__import__("utils.access", fromlist=["context_for"]).context_for(req).csrf_token),
                Button("Buy", type="submit", cls="text-xs px-3 py-1 rounded-full " +
                       ("bg-accent text-bg" if r["seller_id"] != (investor or {}).get("id") else "border border-line text-ink-dim pointer-events-none")),
                action="/app/marketplace/secondary/buy", method="post"),
           cls="py-3 px-4"),
        cls="border-b border-line") for r in listed]
    listed_tbl = _table(["Debtor", "Sector", "Face value", "Est. return", "Seller", "Ask", ""], listed_rows) \
        if listed_rows else P("No positions listed for sale.", cls="text-ink-muted")

    pos_rows = []
    for p in my_positions:
        pos_rows.append(Tr(
            Td(p["debtor_name"], cls=_TD),
            Td(fmt_money(float(p["investment_amount"])), cls=_TD),
            Td(f"{float(p['estimated_return_pct']):.1f}%", cls=_TD + " text-accent"),
            Td(Form(
                Input(type="number", name="price", step="0.01", min="0",
                      value=f"{float(p['investment_amount']):.0f}", required=True,
                      cls="w-28 bg-bg-elevated border border-line rounded-lg px-2 py-1 text-sm text-ink"),
                Input(type="hidden", name="investment_id", value=str(p["id"])),
                Button("List", type="submit",
                       cls="ml-2 text-xs px-3 py-1 rounded-full bg-accent text-bg"),
                method="post", action="/app/marketplace/secondary/list",
                cls="flex items-center"),
               cls="py-3 px-4"),
            cls="border-b border-line"))
    pos_tbl = _table(["Debtor", "Face value", "Est. return", "List for sale"], pos_rows) \
        if pos_rows else P("You hold no positions available to list.", cls="text-ink-muted")

    return app_page(
        "Secondary market",
        Section_(Eyebrow("Marketplace · Depth"),
                 Heading(1, "Secondary market", cls="mt-4"),
                 P("Exit early — list a confirmed position for another investor to buy. Ownership "
                   "transfers on purchase.", cls="mt-3 text-ink-muted max-w-3xl"), cls="border-t border-line"),
        Section_(_tabs("secondary"),
                 Div(P("Positions for sale", cls="text-sm font-medium text-ink mb-3"), listed_tbl, cls="mb-10"),
                 Div(P(f"Your positions ({investor['username'] if investor else '—'})",
                       cls="text-sm font-medium text-ink mb-3"), pos_tbl),
                 cls="border-t border-line"),
        current_path="/app/marketplace/secondary", lang=lang, role=current_role(req), investor=investor, investors=investors,
    )


@rt("/app/marketplace/secondary/list", methods=["POST"])
async def secondary_list(req, investment_id: int = 0, price: float = 0.0):
    investors = list_investors()
    investor = current_investor(req, investors)
    if _HAS_DB and investor and investment_id and price > 0:
        try:
            own = fetch_one("SELECT 1 FROM factorio.investments WHERE id=%(i)s AND investor_id=%(v)s",
                            {"i": investment_id, "v": investor["id"]})
            if own:
                execute("""INSERT INTO factorio.secondary_market (investor_id,investment_id,listing_price,status)
                           VALUES (%(v)s,%(i)s,%(p)s,'listed')""",
                        {"v": investor["id"], "i": investment_id, "p": price})
        except Exception:
            pass
    return RedirectResponse("/app/marketplace/secondary", status_code=303)


@rt("/app/marketplace/secondary/buy", methods=["POST"])
def secondary_buy(req, listing_id: int = 0, csrf: str = ""):
    import hmac
    if not csrf or not hmac.compare_digest(str(req.session.get("csrf_token") or ""), csrf):
        return RedirectResponse("/app", status_code=303)
    investors = list_investors()
    investor = current_investor(req, investors)
    if _HAS_DB and investor and listing_id:
        try:
            with connect() as conn, conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT investor_id,investment_id FROM factorio.secondary_market
                             WHERE id=%s AND status='listed' FOR UPDATE""",
                        (listing_id,),
                    )
                    listing = cur.fetchone()
                    if listing and listing[0] != investor["id"]:
                        cur.execute(
                            "UPDATE factorio.secondary_market SET status='sold' WHERE id=%s AND status='listed'",
                            (listing_id,),
                        )
                        if cur.rowcount != 1:
                            raise RuntimeError("secondary listing was already claimed")
                        cur.execute(
                            """UPDATE factorio.investments SET investor_id=%s,updated_at=now()
                                 WHERE id=%s AND investor_id=%s""",
                            (investor["id"], listing[1], listing[0]),
                        )
                        if cur.rowcount != 1:
                            raise RuntimeError("secondary investment owner changed")
        except Exception:
            pass
    return RedirectResponse("/app/marketplace/secondary", status_code=303)
