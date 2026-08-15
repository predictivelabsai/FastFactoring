"""Credit-scoring engine — production back-office module (area 5).

A transparent, reproducible multi-signal debtor score that fuses **observed**
behaviour (payment history and default record from the settled/defaulted book,
concentration, sector risk) with **external** signals (credit bureau, open-banking
cash-flow) — the latter deterministically simulated pending the real integrations,
and clearly labelled as such. Each debtor gets a score (0–100), a grade (A–D),
an indicative advance rate and price, and plain-language **adverse-action reasons**.

The differentiator is **model back-testing**: `calibration()` compares each
grade's **expected** default probability with the **actual** default rate observed
in the book — the legacy marketplace's "credit-score accuracy" metric.

Scoped to Admin + Credit / Compliance / Executive / Super (Credit owns scoring;
Finance releases funds — segregation of duties).
"""

from __future__ import annotations

import hashlib
import json

from fasthtml.common import Div, P, Span, A, Table, Thead, Tbody, Tr, Th, Td, NotStr
from starlette.responses import RedirectResponse

from app import rt
from utils.i18n import get_lang
from landing.components import Eyebrow, Heading, Section_
from app_routes._shared import app_page, current_role, current_subrole

try:
    from db import fetch_all, fetch_one, execute
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False

CAN_VIEW = {"credit", "compliance", "exec", "super"}

PD_BY_GRADE = {"A": 0.01, "B": 0.03, "C": 0.06, "D": 0.12}
ADVANCE_BY_GRADE = {"A": 90, "B": 85, "C": 80, "D": 70}
PRICE_BPS_BY_GRADE = {"A": 250, "B": 350, "C": 500, "D": 750}
# Sector signal (higher = safer). Riskier sectors score lower.
SECTOR_SIGNAL = {
    "healthcare": 85, "services": 82, "wholesale": 75, "retail": 72,
    "manufacturing": 70, "logistics": 68, "agriculture": 62, "hospitality": 60,
    "construction": 55, "energy": 58, "telecom": 78, "other": 65,
}


def _h(name: str, salt: str, lo: int, hi: int) -> int:
    """Deterministic, stable pseudo-signal in [lo,hi] for a name (placeholder feed)."""
    d = int(hashlib.md5(f"{salt}:{name}".encode()).hexdigest(), 16)
    return lo + d % (hi - lo + 1)


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def _grade(score: float) -> str:
    return "A" if score >= 78 else "B" if score >= 62 else "C" if score >= 45 else "D"


def _ensure():
    if not _HAS_DB:
        return
    execute("""CREATE TABLE IF NOT EXISTS factorio.credit_scores (
        id BIGSERIAL PRIMARY KEY, subject TEXT NOT NULL, score NUMERIC(5,2) NOT NULL,
        grade TEXT NOT NULL, pd_expected NUMERIC(5,4) NOT NULL,
        advance_rate NUMERIC(5,2) NOT NULL, price_bps INT NOT NULL,
        n_invoices INT NOT NULL DEFAULT 0, observed_default NUMERIC(5,4),
        features TEXT NOT NULL DEFAULT '', reasons TEXT NOT NULL DEFAULT '',
        scored_at TIMESTAMPTZ NOT NULL DEFAULT now())""")


def run_scoring() -> int:
    """(Re)compute and store a credit score for every debtor. Idempotent."""
    if not _HAS_DB:
        return 0
    _ensure()
    rows = fetch_all("""
        SELECT i.debtor_name AS name, COUNT(*) n,
               COUNT(*) FILTER (WHERE i.status='settled') n_settled,
               COUNT(*) FILTER (WHERE i.status='defaulted') n_defaulted,
               COALESCE(SUM(i.amount) FILTER (WHERE i.status IN ('funding','funded')),0) exposure,
               MODE() WITHIN GROUP (ORDER BY i.sector) sector,
               AVG(CASE WHEN i.status='settled' AND s.settlement_date IS NOT NULL
                        THEN (s.settlement_date - i.due_date) END) avg_delay
        FROM factorio.invoices i
        LEFT JOIN factorio.invoice_funding f ON f.invoice_id=i.id
        LEFT JOIN factorio.settlements s ON s.funding_id=f.id
        GROUP BY i.debtor_name
    """)
    total_exposure = sum(float(r["exposure"] or 0) for r in rows) or 1.0
    execute("DELETE FROM factorio.credit_scores")
    for r in rows:
        name = r["name"]
        terminal = (r["n_settled"] or 0) + (r["n_defaulted"] or 0)
        obs_default = (r["n_defaulted"] or 0) / terminal if terminal else None
        ad = r["avg_delay"]
        if ad is None:
            avg_delay = 0.0
        elif hasattr(ad, "days"):        # timedelta / interval
            avg_delay = ad.days + ad.seconds / 86400.0
        else:
            avg_delay = float(ad)
        # observed payment signal
        pay = 100.0
        pay -= _clamp(avg_delay, 0, 45)                 # lateness
        if avg_delay < 0:
            pay = min(100.0, pay + 5)                    # pays early
        if obs_default is not None:
            pay -= obs_default * 60.0                    # default history
        pay = _clamp(pay)
        sector_sig = SECTOR_SIGNAL.get(r["sector"], 65)
        bureau_sig = _h(name, "crif", 40, 95)            # placeholder: CRIF bureau
        cashflow_sig = _h(name, "bank", 45, 92)          # placeholder: open-banking cash flow
        share = float(r["exposure"] or 0) / total_exposure
        conc_penalty = _clamp(share * 120, 0, 15)        # concentration drag
        score = (0.35 * pay + 0.15 * sector_sig + 0.25 * bureau_sig
                 + 0.25 * cashflow_sig - conc_penalty)
        score = round(_clamp(score), 1)
        grade = _grade(score)
        feats = {"payment": round(pay), "sector": sector_sig, "bureau": bureau_sig,
                 "cashflow": round(cashflow_sig), "concentration_penalty": round(conc_penalty, 1)}
        # adverse-action reasons: the two weakest signals
        labels = {"payment": "weak payment history", "sector": "elevated sector risk",
                  "bureau": "low bureau score", "cashflow": "thin cash-flow signal"}
        weak = sorted(["payment", "sector", "bureau", "cashflow"], key=lambda k: feats[k])[:2]
        reasons = "; ".join(labels[k] for k in weak) if grade in ("C", "D") else "no material flags"
        execute("""INSERT INTO factorio.credit_scores
            (subject,score,grade,pd_expected,advance_rate,price_bps,n_invoices,observed_default,features,reasons)
            VALUES (%(s)s,%(sc)s,%(g)s,%(pd)s,%(ar)s,%(pb)s,%(n)s,%(od)s,%(f)s,%(r)s)""",
            {"s": name, "sc": score, "g": grade, "pd": PD_BY_GRADE[grade],
             "ar": ADVANCE_BY_GRADE[grade], "pb": PRICE_BPS_BY_GRADE[grade],
             "n": r["n"], "od": obs_default, "f": json.dumps(feats), "r": reasons})
    return len(rows)


def calibration() -> list[dict]:
    """Back-test: expected vs actual default rate, by the grade assigned at funding."""
    if not _HAS_DB:
        return []
    rows = fetch_all("""
        SELECT risk_grade grade,
               COUNT(*) FILTER (WHERE status IN ('settled','defaulted')) n,
               COUNT(*) FILTER (WHERE status='defaulted') defaults
        FROM factorio.invoices GROUP BY risk_grade ORDER BY risk_grade
    """)
    out = []
    for r in rows:
        n = r["n"] or 0
        actual = (r["defaults"] or 0) / n if n else 0.0
        exp = PD_BY_GRADE.get(r["grade"], 0.0)
        out.append({"grade": r["grade"], "n": n, "expected": exp,
                    "actual": actual, "delta": actual - exp})
    return out


def scores_summary() -> str:
    """One-line summary for the copilot."""
    if not _HAS_DB:
        return "No scores."
    if not (fetch_one("SELECT COUNT(*) n FROM factorio.credit_scores") or {}).get("n"):
        try:
            run_scoring()
        except Exception:
            return "No scores."
    rows = fetch_all("SELECT grade, COUNT(*) n FROM factorio.credit_scores GROUP BY grade ORDER BY grade")
    return "Debtor grades — " + ", ".join(f"{r['grade']}: {r['n']}" for r in rows)


# ── UI ────────────────────────────────────────────────────────────────────

_TH = "text-left text-[11px] font-mono tracking-widest uppercase text-ink-dim py-3 px-4"
_TD = "py-3 px-4 text-sm text-ink"
_TDR = _TD + " text-right tabular-nums"


def _guard(req):
    if current_role(req) != "admin":
        return RedirectResponse("/app", status_code=303)
    return None


def _table(headers, rows):
    return Div(Table(
        Thead(Tr(*[Th(h, cls=_TH if i == 0 else _TH.replace("text-left", "text-right"))
                   for i, h in enumerate(headers)], cls="border-b border-line")),
        Tbody(*rows), cls="w-full"),
        cls="rounded-2xl bg-bg-elevated border border-line overflow-hidden overflow-x-auto")


def _page(req, path, title, *content):
    lang = get_lang(req)
    if current_subrole(req) not in CAN_VIEW:
        content = (P("Credit scoring is restricted to Credit / Compliance / Executive roles "
                     "(segregation of duties).", cls="text-red-700"),)
    return app_page(
        title,
        Section_(Eyebrow("Back office · Credit scoring"),
                 Heading(1, title, cls="mt-4"),
                 P("Multi-signal debtor scoring with model back-testing (actual vs expected default).",
                   cls="mt-3 text-ink-muted max-w-3xl"), cls="border-t border-line"),
        Section_(*content, cls="border-t border-line"),
        current_path=path, lang=lang, role="admin", subrole=current_subrole(req),
    )


def _badge(grade):
    c = {"A": "bg-green-100 text-green-800", "B": "bg-blue-100 text-blue-800",
         "C": "bg-yellow-100 text-yellow-800", "D": "bg-red-100 text-red-800"}.get(grade, "bg-gray-100")
    return Span(grade, cls=f"px-2 py-0.5 rounded-full text-xs font-medium {c}")


@rt("/app/admin/scoring")
def scoring(req):
    g = _guard(req)
    if g:
        return g
    if _HAS_DB and not (fetch_one("SELECT COUNT(*) n FROM factorio.credit_scores") or {}).get("n"):
        try:
            run_scoring()
        except Exception:
            pass
    data = fetch_all("""SELECT subject, score, grade, pd_expected, advance_rate, price_bps,
                               n_invoices, observed_default, reasons
                        FROM factorio.credit_scores ORDER BY score DESC""") if _HAS_DB else []
    rows = []
    for r in data:
        obs = (f"{float(r['observed_default'])*100:.0f}%" if r["observed_default"] is not None else "—")
        rows.append(Tr(
            Td(r["subject"], cls=_TD),
            Td(f"{float(r['score']):.0f}", cls=_TDR + " font-medium"),
            Td(_badge(r["grade"]), cls="py-3 px-4 text-center"),
            Td(f"{float(r['pd_expected'])*100:.0f}%", cls=_TDR),
            Td(obs, cls=_TDR),
            Td(f"{float(r['advance_rate']):.0f}%", cls=_TDR + " text-accent"),
            Td(f"{r['price_bps']} bps", cls=_TDR),
            Td(r["reasons"], cls=_TD + " text-ink-muted"),
            cls="border-b border-line"))
    return _page(req, "/app/admin/scoring", "Credit scoring",
                 P("Score fuses observed payment/default history, concentration and sector risk with "
                   "bureau + open-banking signals (the external feeds are simulated pending integration). "
                   "Model produces the grade, advance and price; a human approves.",
                   cls="text-ink-muted text-sm mb-4 max-w-3xl"),
                 _table(["Debtor", "Score", "Grade", "Exp. PD", "Actual default", "Advance", "Price", "Adverse-action reasons"], rows),
                 P(A("Model calibration (back-testing) →", href="/app/admin/scoring/calibration", cls="text-accent"),
                   cls="mt-4 text-sm"))


@rt("/app/admin/scoring/calibration")
def scoring_calibration(req):
    g = _guard(req)
    if g:
        return g
    cal = calibration()
    rows = []
    worst = 0.0
    for c in cal:
        worst = max(worst, abs(c["delta"]))
        drift = c["delta"] * 100
        rows.append(Tr(
            Td(_badge(c["grade"]), cls="py-3 px-4"),
            Td(str(c["n"]), cls=_TDR),
            Td(f"{c['expected']*100:.0f}%", cls=_TDR),
            Td(f"{c['actual']*100:.1f}%", cls=_TDR),
            Td((("+" if drift >= 0 else "") + f"{drift:.1f} pp"),
               cls=_TDR + (" text-red-700" if drift > 2 else " text-accent")),
            cls="border-b border-line"))
    verdict = ("✓ well calibrated" if worst <= 0.02 else
               "acceptable" if worst <= 0.05 else "⚠ recalibrate")
    return _page(req, "/app/admin/scoring", "Model calibration",
                 P(NotStr("Back-test of the risk grade assigned at funding against the "
                          "<b>actual</b> default rate in the settled book — the model-accuracy metric. "
                          f"Worst grade drift: <b>{worst*100:.1f} pp</b> ({verdict})."),
                   cls="text-ink-muted text-sm mb-4 max-w-3xl"),
                 _table(["Grade", "Terminal invoices", "Expected PD", "Actual default", "Drift"], rows))
