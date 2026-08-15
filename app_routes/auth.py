"""Unified local/Google authentication and four-role account onboarding."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from urllib.parse import quote_plus

from fasthtml.common import (
    A, Body, Button, Div, Form, H1, Head, Html, Input, Label, Link, Meta,
    NotStr, Option, P, Script, Select, Span, Title,
)
from starlette.responses import RedirectResponse, Response

from app import rt
from landing.components import SITE_NAME, TAILWIND_CONFIG
from utils import accounts, google_auth
from utils.access import ADMIN_EMAIL, PUBLIC_ROLES, ROLES, context_for
from utils.config import settings
from utils.i18n import get_lang, localize_tree

try:
    from db import execute, fetch_one
    _HAS_DB = True
except Exception:  # pragma: no cover
    _HAS_DB = False


DEMO_PASSWORD = "demo1234"
DEMO_SESSION = {
    "investor": ("investor1@factorio.co.uk", "Investor", "investor"),
    "supplier": ("seller1@factorio.co.uk", "Supplier", "supplier"),
    "payer": ("payer@factorio.co.uk", "Payer", "payer"),
}
DEMO_CHOICES = (
    ("investor", "Investor", "Fund invoices and track a portfolio"),
    ("supplier", "Supplier", "Submit invoices and follow applications"),
    ("payer", "Payer", "Review and confirm obligations"),
)


def _hash(password: str, salt: bytes | None = None):
    """Compatibility wrapper; new passwords use scrypt."""
    if salt is None:
        return "", accounts.hash_password(password)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return base64.b64encode(salt).decode(), base64.b64encode(digest).decode()


def _verify(password: str, salt_b64: str, encoded: str) -> bool:
    if (encoded or "").startswith("scrypt$"):
        return accounts.verify_password(password, encoded)
    try:
        salt = base64.b64decode(salt_b64)
        _, calculated = _hash(password, salt)
        return hmac.compare_digest(calculated, encoded)
    except Exception:
        return False


def _ensure() -> None:
    if not _HAS_DB:
        return
    # Production migrations create these objects. This keeps older local
    # databases usable without weakening the schema contract.
    execute("""CREATE TABLE IF NOT EXISTS factorio.app_users (
        email TEXT PRIMARY KEY,name TEXT NOT NULL DEFAULT '',salt TEXT NOT NULL,
        pw_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'investor',
        subrole TEXT NOT NULL DEFAULT 'ops',created_at TIMESTAMPTZ NOT NULL DEFAULT now())""")


def seed_users() -> int:
    """Create only an explicitly configured local administrator credential."""
    if not _HAS_DB or not settings().admin_password:
        return 0
    _ensure()
    password_hash = accounts.hash_password(settings().admin_password)
    execute(
        """INSERT INTO factorio.app_users(
               email,name,salt,pw_hash,role,subrole,is_verified,google_linked,status,updated_at)
           VALUES (%(email)s,'Julian Kaljuvee','',%(hash)s,'admin','super',TRUE,FALSE,'active',now())
           ON CONFLICT(email) DO UPDATE SET salt='',pw_hash=EXCLUDED.pw_hash,
               role='admin',subrole='super',is_verified=TRUE,status='active',updated_at=now()""",
        {"email": ADMIN_EMAIL, "hash": password_hash},
    )
    execute(
        """INSERT INTO factorio.access_profiles(email,role)
           VALUES (%(email)s,'admin') ON CONFLICT(email) DO UPDATE SET role='admin',updated_at=now()""",
        {"email": ADMIN_EMAIL},
    )
    return 1


def current_user(req):
    ctx = context_for(req)
    if not ctx.authenticated:
        return None
    return {"email": ctx.email, "name": ctx.name, "role": ctx.actual_role}


def is_admin(req) -> bool:
    ctx = context_for(req)
    return ctx.authenticated and ctx.actual_role == "admin"


def _csrf(req) -> str:
    token = str(req.session.get("csrf_token") or "")
    if not token:
        token = secrets.token_urlsafe(32)
        req.session["csrf_token"] = token
    return token


def _valid_csrf(req, supplied: str) -> bool:
    expected = str(req.session.get("csrf_token") or "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def _establish(req, account: dict) -> None:
    language = req.session.get("lang")
    req.session.clear()
    if language:
        req.session["lang"] = language
    req.session["uid"] = str(account["email"]).lower()
    req.session["name"] = str(account.get("name") or account["email"])
    req.session["csrf_token"] = secrets.token_urlsafe(32)
    req.session["session_version"] = int(account.get("session_version") or 1)


def _is_factorio_host(req) -> bool:
    host = (req.headers.get("x-forwarded-host") or req.headers.get("host") or "")
    return host.split(",", 1)[0].split(":", 1)[0].lower() in {"factorio.co.uk", "www.factorio.co.uk"}


def _field(label: str, name: str, *, type: str = "text", value: str = "", **kwargs):
    cls = ("w-full mt-1 px-4 py-2.5 rounded-xl border border-line-bright "
           "bg-bg-elevated text-ink focus:outline-none focus:border-accent")
    return Div(Label(label, cls="text-sm text-ink-muted"),
               Input(name=name, type=type, value=value, cls=cls, **kwargs), cls="mb-4")


def _demo_card():
    return Div(
        P("Synthetic demo accounts", cls="text-ink font-medium text-sm mb-3"),
        *[A(Div(P(label, cls="text-ink font-medium text-sm"),
                    P(description, cls="text-ink-muted text-xs")),
              Span("Use →", cls="text-accent text-xs"),
              href=f"/login/demo?who={role}",
              cls="flex justify-between items-center p-3 mb-2 rounded-xl border border-line no-underline")
          for role, label, description in DEMO_CHOICES],
        cls="mt-7 p-5 rounded-2xl border border-line bg-bg-raised/40",
    )


def _auth_page(req, *, mode: str = "login", error: str = "", message: str = "",
               email: str = "", invite: str = ""):
    lang, csrf = get_lang(req), _csrf(req)
    invited_role = accounts.invite_role(invite)
    roles = [("supplier", "Supplier"), ("investor", "Investor"), ("payer", "Payer")]
    login_form = Form(
        _field("Email", "email", type="email", value=email, required=True, autocomplete="email"),
        _field("Password", "password", type="password", required=True, autocomplete="current-password"),
        Input(type="hidden", name="csrf", value=csrf),
        Button("Sign in", type="submit", cls="w-full px-5 py-2.5 rounded-full bg-accent text-bg font-medium"),
        method="post", action="/login",
    )
    register_form = Form(
        _field("Name", "name", required=True, autocomplete="name"),
        _field("Email", "email", type="email", value=email, required=True, autocomplete="email"),
        _field("Password (minimum 10 characters)", "password", type="password",
               required=True, minlength="10", autocomplete="new-password"),
        Div(Label("Role", cls="text-sm text-ink-muted"),
            Select(*[Option(label, value=role, selected=(invited_role or "supplier") == role)
                     for role, label in roles], name="role", disabled=bool(invited_role),
                   cls="w-full mt-1 px-4 py-2.5 rounded-xl border border-line-bright bg-bg-elevated mb-4")),
        Input(type="hidden", name="role", value=invited_role) if invited_role else None,
        Input(type="hidden", name="invite", value=invite),
        Input(type="hidden", name="csrf", value=csrf),
        Button("Create account", type="submit", cls="w-full px-5 py-2.5 rounded-full bg-accent text-bg font-medium"),
        method="post", action="/register",
    )
    forgot_form = Form(
        _field("Email", "email", type="email", value=email, required=True, autocomplete="email"),
        Input(type="hidden", name="csrf", value=csrf),
        Button("Send reset link", type="submit", cls="w-full px-5 py-2.5 rounded-full bg-accent text-bg font-medium"),
        method="post", action="/forgot-password",
    )
    form = register_form if mode == "register" else forgot_form if mode == "forgot" else login_form
    title = "Create your account" if mode == "register" else "Reset your password" if mode == "forgot" else f"Sign in to {SITE_NAME}"
    tabs = Div(
        A("Sign in", href="/login", cls="text-accent" if mode == "login" else "text-ink-muted"),
        A("Register", href=f"/register{'?invite='+invite if invite else ''}", cls="text-accent" if mode == "register" else "text-ink-muted"),
        cls="flex gap-5 text-sm mb-6",
    )
    panel = Div(
        H1(title, cls="text-2xl font-medium text-ink mb-2"), tabs,
        P(error, cls="text-red-700 text-sm mb-4") if error else None,
        P(message, cls="text-green-700 text-sm mb-4") if message else None,
        A("Continue with Google", href="/auth/google",
          cls="block w-full mb-5 px-5 py-2.5 rounded-full border border-line-bright text-center text-ink text-sm font-medium no-underline"),
        form,
        A("Forgot password?", href="/forgot-password", cls="block text-center text-sm text-accent mt-4") if mode == "login" else None,
        _demo_card() if mode == "login" and _is_factorio_host(req) else None,
        cls="w-full max-w-md p-6",
    )
    return localize_tree(Html(
        Head(Meta(charset="utf-8"), Meta(name="viewport", content="width=device-width,initial-scale=1"),
             Title(f"{title} · {SITE_NAME}"), Link(rel="icon", href="/static/favicon.svg"),
             Script(src="https://cdn.tailwindcss.com"), Script(NotStr(TAILWIND_CONFIG)),
             Link(rel="stylesheet", href="/static/site.css")),
        Body(Div(panel, cls="min-h-screen grid place-items-center bg-bg"), cls="font-sans"),
        lang=lang,
    ), lang)


@rt("/login", methods=["GET"])
def login_get(req, error: str = "", message: str = ""):
    if current_user(req):
        return RedirectResponse("/app", status_code=303)
    return _auth_page(req, error=error, message=message)


@rt("/login", methods=["POST"])
def login_post(req, email: str = "", password: str = "", csrf: str = ""):
    if not _valid_csrf(req, csrf):
        return Response("Invalid form token.", status_code=403)
    if str(email).strip().lower() == ADMIN_EMAIL:
        seed_users()
    account = accounts.authenticate(email, password)
    if not account:
        return _auth_page(req, error="Invalid email, password, or unverified account.", email=email)
    _establish(req, account)
    return RedirectResponse("/app", status_code=303)


@rt("/register", methods=["GET"])
def register_get(req, invite: str = ""):
    return _auth_page(req, mode="register", invite=invite)


@rt("/register", methods=["POST"])
def register_post(req, name: str = "", email: str = "", password: str = "",
                  role: str = "supplier", invite: str = "", csrf: str = ""):
    if not _valid_csrf(req, csrf):
        return Response("Invalid form token.", status_code=403)
    ok, message = accounts.register(email, password, name, role, invite)
    if not ok:
        return _auth_page(req, mode="register", error=message, email=email, invite=invite)
    return _auth_page(req, message=message, email=email)


@rt("/forgot-password", methods=["GET"])
def forgot_get(req):
    return _auth_page(req, mode="forgot")


@rt("/forgot-password", methods=["POST"])
def forgot_post(req, email: str = "", csrf: str = ""):
    if not _valid_csrf(req, csrf):
        return Response("Invalid form token.", status_code=403)
    accounts.forgot(email)
    return _auth_page(req, mode="forgot", message="If an account exists, a reset link has been sent.")


@rt("/auth/local/verify/{token}")
def verify_local(req, token: str):
    account = accounts.verify_account(token)
    if not account:
        return RedirectResponse("/login?error=" + quote_plus("Invalid or expired verification link."), status_code=303)
    _establish(req, account)
    return RedirectResponse("/app", status_code=303)


def _reset_page(req, token: str, error: str = ""):
    csrf = _csrf(req)
    return Html(Head(Title("Reset password"), Meta(name="viewport", content="width=device-width,initial-scale=1")),
                Body(Div(H1("Choose a new password"), P(error) if error else None,
                         Form(Input(type="hidden", name="token", value=token),
                              Input(type="hidden", name="csrf", value=csrf),
                              Input(type="password", name="password", minlength="10", required=True),
                              Button("Reset password", type="submit"), method="post", action="/auth/local/reset"))))


@rt("/auth/local/reset/{token}")
def reset_get(req, token: str):
    return _reset_page(req, token)


@rt("/auth/local/reset", methods=["POST"])
def reset_post(req, token: str = "", password: str = "", csrf: str = ""):
    if not _valid_csrf(req, csrf):
        return Response("Invalid form token.", status_code=403)
    if not accounts.reset_password(token, password):
        return _reset_page(req, token, "Invalid or expired link, or password too short.")
    return RedirectResponse("/login?message=" + quote_plus("Password reset. You can sign in now."), status_code=303)


@rt("/choose-role", methods=["GET"])
def choose_role_get(req, error: str = ""):
    if not req.session.get("uid"):
        return RedirectResponse("/login", status_code=303)
    account = fetch_one(
        "SELECT status,google_linked FROM factorio.app_users WHERE email=%(email)s",
        {"email": str(req.session.get("uid") or "").lower()},
    ) if _HAS_DB else None
    if not account or account.get("status") != "pending" or not account.get("google_linked"):
        return RedirectResponse("/app" if account and account.get("status") == "active" else "/login",
                                status_code=303)
    csrf = _csrf(req)
    return Html(Head(Title("Choose your workspace"), Meta(name="viewport", content="width=device-width,initial-scale=1")),
                Body(Div(H1("Choose your workspace"), P(error) if error else None,
                         P("You can create a Supplier, Investor, or Payer account. Admin access cannot be self-assigned."),
                         Form(Select(Option("Supplier", value="supplier"), Option("Investor", value="investor"),
                                     Option("Payer", value="payer"), name="role"),
                              Input(type="hidden", name="csrf", value=csrf),
                              Button("Continue", type="submit"), method="post", action="/choose-role"))))


@rt("/choose-role", methods=["POST"])
def choose_role_post(req, role: str = "supplier", csrf: str = ""):
    if not _valid_csrf(req, csrf):
        return Response("Invalid form token.", status_code=403)
    email = str(req.session.get("uid") or "").lower()
    if not accounts.choose_role(email, role):
        return choose_role_get(req, "Choose Supplier, Investor, or Payer.")
    req.session["session_version"] = int(req.session.get("session_version") or 1) + 1
    return RedirectResponse("/app", status_code=303)


@rt("/login/demo")
def login_demo(req, who: str = ""):
    if not _is_factorio_host(req) or who not in DEMO_SESSION:
        return RedirectResponse("/login", status_code=303)
    email, name, role = DEMO_SESSION[who]
    account = accounts.demo_account(email, name, role)
    if not account:
        return RedirectResponse("/login", status_code=303)
    _establish(req, account)
    return RedirectResponse("/app", status_code=303)


@rt("/auth/google")
def google_start(req):
    if not google_auth.enabled():
        return RedirectResponse("/login?error=" + quote_plus("Google sign-in is not configured."), status_code=303)
    state = google_auth.new_state()
    req.session["google_oauth_state"] = state
    return RedirectResponse(google_auth.authorize_url(req, state), status_code=303)


@rt("/auth/google/callback")
def google_callback(req, code: str = "", state: str = "", error: str = ""):
    expected = str(req.session.pop("google_oauth_state", ""))
    if error or not code or not state or not expected or not hmac.compare_digest(state, expected):
        return RedirectResponse("/login?error=" + quote_plus("Google sign-in failed."), status_code=303)
    identity = google_auth.exchange(req, code)
    if not identity:
        return RedirectResponse("/login?error=" + quote_plus("Google account could not be verified."), status_code=303)
    account = accounts.google_account(identity["email"], identity["name"])
    if not account:
        return RedirectResponse("/login?error=" + quote_plus("Google account could not be created."), status_code=303)
    _establish(req, account)
    return RedirectResponse("/app" if account.get("status") == "active" and account.get("role") else "/choose-role", status_code=303)


@rt("/logout")
def logout(req):
    req.session.clear()
    return RedirectResponse("/", status_code=303)
