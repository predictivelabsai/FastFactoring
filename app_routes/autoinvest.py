"""Auto-invest route: risk-aware, explainable allocation proposals per investor."""

from __future__ import annotations

from fasthtml.common import (
    Div, P, Span, Form, Input, Select, Option, Button, Label, NotStr,
    Table, Thead, Tbody, Tr, Th, Td, A,
)
from starlette.responses import RedirectResponse

from app import rt
from utils.i18n import t, get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, list_investors, current_investor, current_role
from utils.money import fmt_money

try:
    from db import fetch_all, fetch_one, execute
    _HAS_DB = True
except Exception:
    _HAS_DB = False

_GRADES = ["A", "B", "C", "D"]
_INPUT = ("w-full bg-bg-elevated border border-line rounded-lg px-3 py-2 text-sm "
          "text-ink focus:outline-none focus:border-accent")


def _load_rule(investor_id: int) -> dict:
    defaults = {"max_amount_per_invoice": 500, "min_risk_grade": "B",
                "preferred_sectors": "", "risk_profile": "balanced",
                "max_debtor_pct": 25, "max_term_days": 90,
                "min_return_pct": 0, "is_active": True, "_exists": False}
    if not _HAS_DB:
        return defaults
    try:
        row = fetch_one("""
            SELECT max_amount_per_invoice, min_risk_grade, preferred_sectors,
                   risk_profile, max_debtor_pct, max_term_days, min_return_pct, is_active
            FROM factorio.auto_invest
            WHERE investor_id = %(iid)s
            ORDER BY id DESC LIMIT 1
        """, {"iid": investor_id})
        if row:
            row["_exists"] = True
            return row
    except Exception:
        pass
    return defaults


def _save_rule(investor_id: int, *, max_amount, min_grade, sectors, risk_profile,
               max_debtor_pct, max_term_days, min_return_pct, is_active):
    if not _HAS_DB:
        return
    try:
        execute("DELETE FROM factorio.auto_invest WHERE investor_id = %(iid)s",
                {"iid": investor_id})
        execute("""
            INSERT INTO factorio.auto_invest
                (investor_id, max_amount_per_invoice, min_risk_grade,
                 preferred_sectors, risk_profile, max_debtor_pct, max_term_days,
                 min_return_pct, is_active)
            VALUES (%(iid)s, %(amt)s, %(grade)s, %(sectors)s, %(profile)s,
                    %(debtor)s, %(term)s, %(ret)s, %(active)s)
        """, {"iid": investor_id, "amt": max_amount, "grade": min_grade,
              "sectors": sectors, "profile": risk_profile,
              "debtor": max_debtor_pct, "term": max_term_days,
              "ret": min_return_pct, "active": is_active})
    except Exception:
        pass


def _field(label, control, hint=None):
    return Div(
        Label(label, cls="block text-[11px] font-mono uppercase tracking-widest text-ink-dim mb-1"),
        control,
        P(hint, cls="text-xs text-ink-dim mt-1") if hint else None,
    )


def _status_pill(active: bool, lang: str):
    if active:
        return Span(t("ai_active", lang),
                    cls="px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800")
    return Span(t("ai_inactive", lang),
                cls="px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700")


def _form(rule: dict, lang: str, saved: bool):
    grade_opts = [
        Option(g, value=g, selected=(rule["min_risk_grade"] == g)) for g in _GRADES
    ]
    active = bool(rule["is_active"])
    profile_opts = [
        Option(label, value=value, selected=rule["risk_profile"] == value)
        for value, label in (
            ("conservative", "Conservative · A-grade, shorter term"),
            ("balanced", "Balanced · A/B-grade, diversified"),
            ("growth", "Growth · A/B/C-grade, higher return"),
        )
    ]
    return Form(
        Div(
            P(t("ai_status", lang), cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim"),
            _status_pill(active, lang),
            cls="flex items-center justify-between mb-6",
        ),
        Div(
            _field("Risk preference",
                   Select(*profile_opts, name="risk_profile", cls=_INPUT),
                   "Investor AI uses this to weight grade, return, term and diversification."),
            _field(t("ai_min_grade", lang),
                   Select(*grade_opts, name="min_risk_grade", cls=_INPUT)),
            _field(t("ai_max_amount", lang),
                   Input(type="number", name="max_amount_per_invoice", min="0", step="any",
                         value=str(rule["max_amount_per_invoice"] or ""), cls=_INPUT)),
            _field("Maximum debtor concentration (%)",
                   Input(type="number", name="max_debtor_pct", min="5", max="100", step="1",
                         value=str(rule["max_debtor_pct"]), cls=_INPUT)),
            _field("Maximum invoice term (days)",
                   Input(type="number", name="max_term_days", min="1", max="365", step="1",
                         value=str(rule["max_term_days"]), cls=_INPUT)),
            _field("Minimum estimated return (%)",
                   Input(type="number", name="min_return_pct", min="0", max="100", step="0.1",
                         value=str(rule["min_return_pct"]), cls=_INPUT)),
            cls="grid md:grid-cols-2 gap-4 mb-4",
        ),
        _field(t("ai_sectors", lang),
               Input(type="text", name="preferred_sectors",
                     value=rule["preferred_sectors"] or "", cls=_INPUT),
               hint=t("ai_sectors_hint", lang)),
        Label(
            Input(type="checkbox", name="is_active", value="1", checked=active,
                  cls="mr-2 align-middle accent-accent"),
            Span(t("ai_enable", lang), cls="text-sm text-ink align-middle"),
            cls="flex items-center mt-5 cursor-pointer",
        ),
        Div(
            Button(t("ai_save", lang), type="submit",
                   cls="inline-flex items-center px-5 py-2 rounded-full text-sm font-medium bg-accent text-bg hover:bg-ink transition-all"),
            Span(t("ai_saved", lang), cls="text-sm text-accent ml-3") if saved else None,
            cls="flex items-center mt-6",
        ),
        method="post", action="/app/auto-invest",
        cls="p-7 rounded-2xl bg-bg-elevated border border-line max-w-2xl",
    )


def _allocation_plan(investor_id: int, rule: dict) -> list[dict]:
    """Rank open invoices using transparent risk-preference and concentration rules."""
    if not _HAS_DB:
        return []
    try:
        candidates = fetch_all("""
            SELECT f.id funding_id, i.invoice_number, i.debtor_name, i.sector,
                   i.risk_grade, f.target_hold_days, f.estimated_return_pct,
                   GREATEST(f.funding_goal-f.amount_raised,0) available
            FROM factorio.invoice_funding f
            JOIN factorio.invoices i ON i.id=f.invoice_id
            WHERE f.funding_status='open' AND f.show_in_marketplace=TRUE
            ORDER BY f.created_at DESC
        """)
        positions = fetch_all("""
            SELECT i.debtor_name, i.sector, inv.investment_amount
            FROM factorio.investments inv
            JOIN factorio.invoice_funding f ON f.id=inv.funding_id
            JOIN factorio.invoices i ON i.id=f.invoice_id
            WHERE inv.investor_id=%s AND inv.status='confirmed'
        """, (investor_id,))
    except Exception:
        return []
    total = sum(float(row["investment_amount"] or 0) for row in positions)
    debtor_exp = {}
    sector_exp = {}
    for row in positions:
        amount = float(row["investment_amount"] or 0)
        debtor_exp[row["debtor_name"]] = debtor_exp.get(row["debtor_name"], 0) + amount
        sector_exp[row["sector"]] = sector_exp.get(row["sector"], 0) + amount
    profile = rule.get("risk_profile") or "balanced"
    allowed = {"conservative": "A", "balanced": "B", "growth": "C"}[profile]
    selected_grade = rule.get("min_risk_grade") or allowed
    max_grade_index = min(_GRADES.index(allowed), _GRADES.index(selected_grade))
    preferred = {s.strip().lower() for s in str(rule.get("preferred_sectors") or "").split(",") if s.strip()}
    results = []
    for row in candidates:
        grade = row["risk_grade"]
        term = int(row["target_hold_days"] or 0)
        est_return = float(row["estimated_return_pct"] or 0)
        available = float(row["available"] or 0)
        if grade not in _GRADES or _GRADES.index(grade) > max_grade_index:
            continue
        if term > int(rule.get("max_term_days") or 90):
            continue
        if est_return < float(rule.get("min_return_pct") or 0):
            continue
        current_debtor_pct = debtor_exp.get(row["debtor_name"], 0) / total * 100 if total else 0
        if current_debtor_pct >= float(rule.get("max_debtor_pct") or 25):
            continue
        grade_score = {
            "conservative": {"A": 50},
            "balanced": {"A": 34, "B": 44},
            "growth": {"A": 24, "B": 38, "C": 48},
        }[profile].get(grade, 0)
        term_score = max(0, 20 - term / max(1, int(rule.get("max_term_days") or 90)) * 20)
        return_score = min(25, est_return * 3)
        preference_score = 10 if preferred and str(row["sector"]).lower() in preferred else 0
        concentration_penalty = (
            debtor_exp.get(row["debtor_name"], 0) + sector_exp.get(row["sector"], 0)
        ) / total * 20 if total else 0
        score = grade_score + term_score + return_score + preference_score - concentration_penalty
        allocation = min(float(rule.get("max_amount_per_invoice") or 0), available)
        if allocation <= 0:
            continue
        results.append({**row, "score": score, "allocation": allocation,
                        "reason": (f"{profile.title()} fit: grade {grade}, {term}d term, "
                                   f"{est_return:.1f}% estimated return; debtor currently "
                                   f"{current_debtor_pct:.0f}% of active portfolio.")})
    return sorted(results, key=lambda row: row["score"], reverse=True)[:5]


def allocation_context(investor_id: int) -> str:
    """Plain-text preferences and proposals for grounding Investor AI."""
    rule = _load_rule(investor_id)
    plan = _allocation_plan(investor_id, rule)
    lines = [
        "Auto-invest preferences:",
        f"- Status: {'active' if rule.get('is_active') else 'inactive'}",
        f"- Risk preference: {rule.get('risk_profile', 'balanced')}",
        f"- Minimum risk grade: {rule.get('min_risk_grade', 'B')}",
        f"- Maximum per invoice: {fmt_money(rule.get('max_amount_per_invoice'))}",
        f"- Maximum debtor concentration: {float(rule.get('max_debtor_pct') or 25):.0f}%",
        f"- Maximum term: {int(rule.get('max_term_days') or 90)} days",
        f"- Minimum estimated return: {float(rule.get('min_return_pct') or 0):.1f}%",
        f"- Preferred sectors: {rule.get('preferred_sectors') or 'none'}",
        "",
        "Current allocation proposals (proposal only; no investment has been placed):",
    ]
    if not plan:
        lines.append("- No open invoice currently meets every saved limit.")
    for row in plan:
        lines.append(
            f"- {row['invoice_number']} | {row['debtor_name']} | grade {row['risk_grade']} | "
            f"{int(row['target_hold_days'])} days | "
            f"{float(row['estimated_return_pct']):.1f}% estimated return | "
            f"proposed {fmt_money(row['allocation'])} | {row['reason']}"
        )
    return "\n".join(lines)


def _plan_table(plan: list[dict]):
    if not plan:
        return P("No open invoices currently satisfy this risk profile and its limits.",
                 cls="text-sm text-ink-muted")
    rows = [
        Tr(Td(row["invoice_number"], cls="py-3 px-4 text-sm"),
           Td(row["debtor_name"], cls="py-3 px-4 text-sm"),
           Td(row["risk_grade"], cls="py-3 px-4 text-sm"),
           Td(f"{int(row['target_hold_days'])} days", cls="py-3 px-4 text-sm"),
           Td(f"{float(row['estimated_return_pct']):.1f}%", cls="py-3 px-4 text-sm"),
           Td(fmt_money(row["allocation"]), cls="py-3 px-4 text-sm text-right font-medium"),
           Td(row["reason"], cls="py-3 px-4 text-xs text-ink-muted"),
           cls="border-b border-line")
        for row in plan
    ]
    return Div(
        Table(Thead(Tr(*[Th(label, cls="text-left text-[10px] font-mono uppercase "
                                         "tracking-widest text-ink-dim py-3 px-4")
                         for label in ("Invoice", "Debtor", "Grade", "Term", "Return",
                                       "Proposed", "Why")])),
              Tbody(*rows), cls="w-full"),
        cls="rounded-2xl bg-bg-elevated border border-line overflow-x-auto")


@rt("/app/auto-invest", methods=["GET"])
def auto_invest(req):
    if current_role(req) != "investor":
        return RedirectResponse("/app", status_code=303)
    lang = get_lang(req)
    investors = list_investors()
    investor = current_investor(req, investors)
    rule = _load_rule(investor["id"]) if investor else _load_rule(0)
    saved = req.query_params.get("saved") == "1"
    plan = _allocation_plan(investor["id"], rule) if investor else []

    return app_page(
        t("ai_eyebrow", lang),
        Section_(
            Eyebrow(t("ai_eyebrow", lang)),
            Heading(1, t("ai_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("ai_lede", lang), cls="mt-4 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        Section_(Div(_form(rule, lang, saved),
                     Div(P("Investor AI allocation plan",
                           cls="text-[11px] font-mono uppercase tracking-widest text-ink-dim mb-3"),
                         P("Explainable proposals based on your saved risk preference. "
                           "No investment is placed from this preview.",
                           cls="text-sm text-ink-muted mb-4"),
                         _plan_table(plan),
                         A("Ask Investor AI about this plan →", href="/app",
                           cls="inline-block mt-4 text-sm text-accent"),
                         cls="min-w-0"),
                     cls="grid xl:grid-cols-[minmax(360px,560px)_1fr] gap-6 items-start"),
                 cls="border-t border-line"),
        current_path="/app/auto-invest", lang=lang, role=current_role(req), investor=investor, investors=investors,
    )


@rt("/app/auto-invest", methods=["POST"])
async def auto_invest_save(req):
    if current_role(req) != "investor":
        return RedirectResponse("/app", status_code=303)
    investors = list_investors()
    investor = current_investor(req, investors)
    form = await req.form()
    if investor:
        try:
            amt = float(form.get("max_amount_per_invoice") or 0)
        except (TypeError, ValueError):
            amt = 0
        grade = form.get("min_risk_grade") or "B"
        if grade not in _GRADES:
            grade = "B"
        profile = str(form.get("risk_profile") or "balanced")
        if profile not in {"conservative", "balanced", "growth"}:
            profile = "balanced"
        def _number(name, default):
            try:
                return float(form.get(name) or default)
            except (TypeError, ValueError):
                return float(default)
        _save_rule(
            investor["id"],
            max_amount=amt,
            min_grade=grade,
            sectors=(form.get("preferred_sectors") or "").strip(),
            risk_profile=profile,
            max_debtor_pct=max(5, min(100, _number("max_debtor_pct", 25))),
            max_term_days=int(max(1, min(365, _number("max_term_days", 90)))),
            min_return_pct=max(0, min(100, _number("min_return_pct", 0))),
            is_active=bool(form.get("is_active")),
        )
    return RedirectResponse("/app/auto-invest?saved=1", status_code=303)
