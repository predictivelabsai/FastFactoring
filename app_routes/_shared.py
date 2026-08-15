"""Shared authenticated role, navigation, money, and reporting helpers."""

from __future__ import annotations

from datetime import date

from fasthtml.common import Div, Span, A, Nav, Ul, Li, Select, Option
from starlette.responses import RedirectResponse, Response

from app import rt
from utils.i18n import t, DEFAULT_LANG
from utils.access import ADMIN_EMAIL, audit, context_for, current_context, normalize_role

try:
    from db import fetch_all
    _HAS_DB = True
except Exception:  # pragma: no cover - DB optional in some environments
    _HAS_DB = False


# ── Money ───────────────────────────────────────────────────────────────

from utils.money import fmt_money  # noqa: E402


def fmt_uzs(amount) -> str:
    """Back-compat name — formats a stored (UZS-scale) amount in the display
    currency (USD by default). See utils.money.fmt_money."""
    return fmt_money(amount)


# ── Investor identity (no-password switcher) ────────────────────────────

import re as _re


def display_name(username: str | None) -> str:
    """Friendly display for synthetic usernames: investor1 -> Investor,
    investor2 -> Investor 2."""
    m = _re.match(r"^investor0*(\d+)$", (username or ""), _re.I)
    if m:
        n = m.group(1)
        return "Investor" if n == "1" else f"Investor {n}"
    return username or ""


def list_investors(req=None) -> list[dict]:
    if not _HAS_DB:
        return []
    try:
        ctx = context_for(req) if req is not None else current_context()
        if ctx.effective_role == "investor" and ctx.investor_user_id:
            return fetch_all(
                "SELECT id,username,email FROM factorio.users WHERE role='investor' AND id=%s",
                (ctx.investor_user_id,),
            )
        if ctx.effective_role == "admin":
            return fetch_all(
                "SELECT id,username,email FROM factorio.users WHERE role='investor' ORDER BY id"
            )
        return []
    except Exception:
        return []


def current_investor(req, investors: list[dict] | None = None) -> dict | None:
    """Resolve only the investor authorized by the access profile.

    Native admins may select a record for operational review; non-admin cookies
    are ignored and never change record scope.
    """
    investors = investors if investors is not None else list_investors()
    if not investors:
        return None
    ctx = context_for(req) if req is not None else current_context()
    if ctx.effective_role == "investor" and ctx.investor_user_id:
        return next((item for item in investors if item["id"] == ctx.investor_user_id), None)
    cookie = req.cookies.get("investor") if req is not None else None
    if ctx.effective_role == "admin" and cookie:
        for inv in investors:
            if str(inv["id"]) == str(cookie):
                return inv
    return investors[0] if ctx.effective_role == "admin" else None


@rt("/app/set-investor")
def set_investor(req, investor_id: int = 0):
    if current_role(req) != "admin":
        return Response("Forbidden", status_code=403)
    referer = req.headers.get("referer", "/app")
    resp = RedirectResponse(referer, status_code=303)
    resp.set_cookie("investor", str(investor_id),
                    max_age=365 * 24 * 3600, httponly=False, samesite="lax")
    return resp


# ── Roles / RBAC ─────────────────────────────────────────────────────────

ROLES = ("investor", "supplier", "payer", "admin")
# Segregation of duties is collapsed: Admin is a single full-access role. The old
# admin subroles are gone; current_subrole always returns "super" so any legacy
# CAN_* gate (which all include "super") passes for Admin.
ADMIN_SUBROLES = ("super",)


def current_role(req) -> str:
    """Return the database-backed effective role for this request."""
    return context_for(req).effective_role


def current_subrole(req) -> str:
    # Legacy action gates all accept "super"; only the sole admin receives it.
    return "super" if current_role(req) == "admin" else "ops"


def _valid_csrf(req, token: str) -> bool:
    expected = str((getattr(req, "session", None) or {}).get("csrf_token") or "")
    import secrets
    return bool(expected and token and secrets.compare_digest(expected, token))


@rt("/app/role-preview", methods=["POST"])
def role_preview(req, role: str = "admin", csrf: str = ""):
    ctx = context_for(req)
    role = normalize_role(role)
    if ctx.actual_role != "admin" or not role or not _valid_csrf(req, csrf):
        return Response("Forbidden", status_code=403)
    previous = ctx.effective_role
    if role == "admin":
        req.session.pop("preview_role", None)
    else:
        req.session["preview_role"] = role
    target = context_for(req)
    audit(target, "preview_start" if role != "admin" else "preview_end", role,
          f"actual={target.actual_role};from={previous};effective={target.effective_role};"
          f"supplier={target.supplier_user_id};investor={target.investor_user_id};"
          f"payer={target.payer_registration};synthetic={target.is_synthetic}")
    return RedirectResponse("/app", status_code=303)


@rt("/app/preview-exit", methods=["POST"])
def preview_exit(req, csrf: str = ""):
    return role_preview(req, role="admin", csrf=csrf)


# ── Aging buckets (days past due) ───────────────────────────────────────

# (key, lower_inclusive, upper_inclusive) — upper None means open-ended.
AGING_BUCKETS = [
    ("bkt_in_payment", None, 0),     # due in the future / today → still in payment
    ("bkt_late_1_14", 1, 14),
    ("bkt_late_15_30", 15, 30),
    ("bkt_late_31_60", 31, 60),
    ("bkt_late_61_120", 61, 120),
    ("bkt_late_120", 121, None),
]


def aging_bucket_key(days_late: int) -> str:
    """Map days-past-due (negative = not yet due) to an aging-bucket key."""
    if days_late <= 0:
        return "bkt_in_payment"
    for key, lo, hi in AGING_BUCKETS[1:]:
        if hi is None:
            return key
        if lo <= days_late <= hi:
            return key
    return "bkt_late_120"


def days_late(due, today: date | None = None) -> int:
    """Positive when overdue, negative/zero when not yet due."""
    today = today or date.today()
    d = due.date() if hasattr(due, "date") else due
    return (today - d).days


# ── App chrome ──────────────────────────────────────────────────────────

# Role-scoped navigation. (i18n key, href) per role.
_NAV_BY_ROLE = {
    "investor": [
        ("nav_dashboard", "/app"),
        ("mkt_eyebrow", "/app/marketplace"),
        ("port_eyebrow", "/app/portfolio"),
        ("nav_statement", "/app/statement"),
        ("nav_autoinvest", "/app/auto-invest"),
        ("nav_triage", "/app/triage"),
        ("nav_assistant", "/app/assistant"),
    ],
    "supplier": [
        ("nav_seller", "/app/supplier"),
    ],
    "payer": [
        ("nav_payer", "/app/payer"),
    ],
    "admin": [
        ("nav_admin", "/app/admin"),
        ("nav_admin_onboarding", "/app/admin/onboarding"),
        ("nav_admin_risk", "/app/admin/risk"),
        ("nav_admin_funding", "/app/admin/funding"),
        ("nav_admin_reports", "/app/admin/reports"),
        ("nav_admin_audit", "/app/admin/audit"),
    ],
}

# Back-compat alias (dashboard.py imports app_page/current_investor only).
_APP_LINKS = _NAV_BY_ROLE["investor"]


def _sel_cls():
    return ("bg-bg-elevated border border-line-bright rounded-full px-3 py-1.5 "
            "text-sm text-ink focus:outline-none focus:border-accent cursor-pointer")


def _investor_switcher(investor: dict | None, investors: list[dict], lang: str):
    if not investors:
        return Span("", cls="hidden")
    opts = [
        Option(display_name(inv["username"]), value=str(inv["id"]),
               selected=bool(investor and inv["id"] == investor["id"]))
        for inv in investors
    ]
    return Div(
        Span(t("app_viewing_as", lang),
             cls="text-[11px] font-mono uppercase tracking-widest text-ink-dim hidden sm:inline"),
        Select(*opts,
               onchange=("document.cookie='investor='+this.value+"
                         "';path=/;max-age=31536000;samesite=lax';location.reload();"),
               cls=_sel_cls()),
        cls="flex items-center gap-2",
    )


def _role_switcher(role: str, lang: str):
    return Div(
        Span(t("app_role_label", lang),
             cls="text-[11px] font-mono uppercase tracking-widest text-ink-dim hidden sm:inline"),
        Span(t(f"role_{role}", lang), cls="text-sm text-ink font-medium"),
        cls="flex items-center gap-2")


def app_subnav(current_path: str, lang: str,
               investor: dict | None, investors: list[dict],
               role: str = "investor", subrole: str = "ops"):
    links = _NAV_BY_ROLE.get(role, _NAV_BY_ROLE["investor"])
    items = [
        Li(A(t(key, lang), href=href,
             cls="text-sm transition-colors "
                 + ("text-accent font-medium" if current_path == href else "text-ink-muted hover:text-ink")))
        for key, href in links
    ]
    right = _investor_switcher(investor, investors, lang) if role == "investor" \
        else _role_switcher(role, lang)
    return Nav(
        Div(
            Ul(*items, cls="flex items-center gap-5 md:gap-7 flex-wrap"),
            Div(_role_switcher(role, lang) if role == "investor" else Span("", cls="hidden"),
                right, cls="flex items-center gap-3"),
            cls="max-w-7xl mx-auto px-5 md:px-6 flex items-center justify-between gap-4 h-12",
        ),
        cls="sticky top-16 z-40 bg-bg-elevated/90 backdrop-blur border-b border-line",
    )


def app_page(title: str, *content, current_path: str = "/app",
             lang: str = DEFAULT_LANG,
             investor: dict | None = None, investors: list[dict] | None = None,
             role: str = "investor", subrole: str = "ops"):
    """Render product-app content inside the left-nav cockpit shell + copilot."""
    from app_routes.shell import app_shell
    investors = investors if investors is not None else list_investors()
    return app_shell(
        title, *content,
        current_path=current_path, lang=lang,
        investor=investor, investors=investors, role=role, subrole=subrole,
    )
