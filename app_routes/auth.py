"""Real authentication — production (step 8).

Session-based login with PBKDF2-hashed passwords over an ``app_users`` table.
Layered so the demo is not broken: if a user is **logged in**, the session's
role/subrole win; otherwise the app falls back to the cookie role-switcher used
for demos. MFA/SSO are stubbed (documented as the next hardening step).

Passwords use stdlib ``hashlib.pbkdf2_hmac`` — no extra dependency.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Div, Span, A, Form, Input, Button, P, H1, Label,
)
from starlette.responses import RedirectResponse

from app import rt
from landing.components import TAILWIND_CONFIG, SITE_NAME

try:
    from db import fetch_all, fetch_one, execute
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False

# Demo users seeded on first use (password "demo1234" for all).
DEMO_USERS = [
    ("admin@factorio.co.uk", "Super Admin", "admin", "super"),
    ("finance@factorio.co.uk", "Finance Officer", "admin", "finance"),
    ("credit@factorio.co.uk", "Credit Analyst", "admin", "credit"),
    ("compliance@factorio.co.uk", "Compliance Officer", "admin", "compliance"),
    ("collections@factorio.co.uk", "Collections Agent", "admin", "collections"),
    ("investor@factorio.co.uk", "Investor", "investor", "ops"),
    ("supplier@factorio.co.uk", "Supplier", "supplier", "ops"),
    ("payer@factorio.co.uk", "Payer", "payer", "ops"),
]
DEMO_PASSWORD = "demo1234"

# The one-click demo accounts offered as a choice on the login page, mapped to
# Factorio's own user/role model. (email, name, role, subrole)
DEMO_SESSION = {
    "investor": ("investor@factorio.co.uk", "Investor", "investor", "ops"),
    "supplier": ("supplier@factorio.co.uk", "Supplier", "supplier", "ops"),
    "payer":    ("payer@factorio.co.uk",    "Payer",    "payer",    "ops"),
    "admin":    ("admin@factorio.co.uk",    "Super Admin", "admin", "super"),
}
# Display order + one-line descriptions for the login-page choice card.
DEMO_CHOICES = [
    ("investor", "Investor", "Fund invoices, track a portfolio"),
    ("supplier", "Supplier", "Sell invoices for cash today"),
    ("payer",    "Payer",    "Confirm invoices you owe"),
    ("admin",    "Admin",    "Back office — full access"),
]

# Small shield-check glyph for the demo-accounts card header.
_SHIELD_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01'
    'C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0'
    'C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>'
)


def _hash(pw: str, salt: bytes | None = None):
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 100_000)
    return base64.b64encode(salt).decode(), base64.b64encode(dk).decode()


def _verify(pw: str, salt_b64: str, hash_b64: str) -> bool:
    try:
        salt = base64.b64decode(salt_b64)
        _, calc = _hash(pw, salt)
        return hmac.compare_digest(calc, hash_b64)
    except Exception:
        return False


def _ensure():
    if not _HAS_DB:
        return
    execute("""CREATE TABLE IF NOT EXISTS factorio.app_users (
        email TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '',
        salt TEXT NOT NULL, pw_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'investor', subrole TEXT NOT NULL DEFAULT 'ops',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now())""")


def seed_users() -> int:
    _ensure()
    if not _HAS_DB:
        return 0
    n = 0
    for email, name, role, subrole in DEMO_USERS:
        if fetch_one("SELECT 1 FROM factorio.app_users WHERE email=%(e)s", {"e": email}):
            continue
        salt, h = _hash(DEMO_PASSWORD)
        execute("INSERT INTO factorio.app_users (email,name,salt,pw_hash,role,subrole) "
                "VALUES (%(e)s,%(n)s,%(s)s,%(h)s,%(r)s,%(sr)s)",
                {"e": email, "n": name, "s": salt, "h": h, "r": role, "sr": subrole})
        n += 1
    return n


def current_user(req):
    """Return the logged-in user dict from the session, or None."""
    s = getattr(req, "session", None)
    if s and s.get("uid"):
        return {"email": s.get("uid"), "name": s.get("name", ""),
                "role": s.get("role"), "subrole": s.get("subrole", "ops")}
    return None


# ── Login / logout ─────────────────────────────────────────────────────────

def _demo_row(who: str, email: str, label: str, desc: str):
    return A(
        Div(
            P(label, cls="text-ink font-medium text-sm"),
            P(email, cls="text-ink-dim text-xs mt-0.5"),
            P(desc, cls="text-ink-muted text-xs mt-0.5"),
        ),
        Span(NotStr("Use this account &rarr;"),
             cls="text-accent text-xs font-medium whitespace-nowrap ml-3 shrink-0"),
        href=f"/login/demo?who={who}",
        cls="flex items-center justify-between px-4 py-3 rounded-xl border border-line "
            "bg-bg-elevated hover:border-accent transition-colors no-underline",
    )


def _login_page(error: str = "", email: str = ""):
    field = "w-full mt-1 px-4 py-2.5 rounded-xl border border-line-bright bg-bg-elevated text-ink focus:outline-none focus:border-accent"

    brand = Div(
        A(Span(NotStr("&#9670;"), cls="text-bg mr-2 text-2xl"),
          Span(SITE_NAME, cls="font-semibold text-xl text-bg"),
          href="/", cls="flex items-center no-underline"),
        Div(
            H1("Invoice financing, end to end",
               cls="text-3xl font-semibold text-bg leading-tight mb-4"),
            P("Suppliers turn unpaid invoices into cash today; investors earn short-term, "
              "asset-backed returns — one platform with a full back office.",
              cls="text-bg/80 text-base leading-relaxed max-w-md"),
        ),
        P("Demo environment · synthetic data", cls="text-bg/60 text-sm"),
        cls="hidden md:flex md:w-1/2 bg-accent flex-col justify-between p-12",
    )

    demo_card = Div(
        Div(Span(NotStr(_SHIELD_SVG), cls="text-accent flex"),
            Span("Demo accounts", cls="text-ink font-medium text-sm"),
            cls="flex items-center gap-2 mb-3"),
        Div(*[_demo_row(who, DEMO_SESSION[who][0], label, desc)
              for who, label, desc in DEMO_CHOICES], cls="flex flex-col gap-2"),
        P(NotStr("One-click sign-in — no password needed. Or use the form above "
                 "(password <b>demo1234</b>)."),
          cls="text-ink-dim text-xs mt-3 leading-relaxed"),
        cls="mt-8 p-5 rounded-2xl border border-line bg-bg-raised/40",
    )

    form_panel = Div(
        Div(
            H1(f"Sign in to {SITE_NAME}", cls="text-2xl font-medium text-ink mb-1"),
            P("Back-office & investor portal", cls="text-ink-muted text-sm mb-6"),
            (P(error, cls="text-red-700 text-sm mb-4 px-4 py-2 rounded-lg bg-red-50 border border-red-200")
             if error else None),
            Form(
                Label("Email", cls="text-sm text-ink-muted"),
                Input(name="email", type="email", value=email, required=True, cls=field),
                Label("Password", cls="text-sm text-ink-muted mt-4 block"),
                Input(name="password", type="password", required=True, cls=field),
                Button("Sign in", type="submit",
                       cls="w-full mt-6 px-5 py-2.5 rounded-full bg-accent text-bg font-medium hover:bg-ink transition-colors"),
                method="post", action="/login"),
            demo_card,
            cls="w-full max-w-sm"),
        cls="flex-1 flex items-center justify-center p-6 bg-bg",
    )

    return Html(
        Head(Meta(charset="utf-8"), Meta(name="viewport", content="width=device-width, initial-scale=1"),
             Title(f"Sign in · {SITE_NAME}"),
             Link(rel="icon", type="image/svg+xml", href="/static/favicon.svg"),
             Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"),
             Script(src="https://cdn.tailwindcss.com"), Script(NotStr(TAILWIND_CONFIG)),
             Link(rel="stylesheet", href="/static/site.css")),
        Body(Div(brand, form_panel, cls="min-h-screen flex"),
             cls="bg-bg text-ink font-sans antialiased"))


@rt("/login", methods=["GET"])
def login_get(req):
    if current_user(req):
        return RedirectResponse("/app", status_code=303)
    return _login_page()


@rt("/login", methods=["POST"])
def login_post(req, email: str = "", password: str = ""):
    seed_users()
    email = (email or "").strip().lower()
    u = fetch_one("SELECT * FROM factorio.app_users WHERE email=%(e)s", {"e": email}) if _HAS_DB else None
    if not u or not _verify(password, u["salt"], u["pw_hash"]):
        return _login_page("Invalid email or password.", email)
    s = req.session
    s["uid"] = u["email"]; s["name"] = u["name"]; s["role"] = u["role"]; s["subrole"] = u["subrole"]
    dest = "/app"
    return RedirectResponse(dest, status_code=303)


@rt("/login/demo", methods=["GET"])
def login_demo(req, who: str = ""):
    """One-click demo sign-in — sets the session directly for a whitelisted
    demo role (no password, no DB write). Mirrors the login_post redirect."""
    choice = DEMO_SESSION.get(who)
    if not choice:
        return RedirectResponse("/login", status_code=303)
    email, name, role, subrole = choice
    s = req.session
    s["uid"] = email; s["name"] = name; s["role"] = role; s["subrole"] = subrole
    dest = "/app"
    return RedirectResponse(dest, status_code=303)


@rt("/logout")
def logout(req):
    try:
        req.session.clear()
    except Exception:
        pass
    return RedirectResponse("/", status_code=303)
