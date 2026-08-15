"""FastFactoring -- open-source FastHTML invoice-financing application.

Single process, two route groups:
  - /                 FastFactoring or Factorio reference landing (by host)
  - /app/*            invoice financing product (app_routes/)
"""

from __future__ import annotations

import hmac
from urllib.parse import urlsplit

from fasthtml.common import Beforeware, fast_app, serve
from starlette.responses import PlainTextResponse, RedirectResponse, Response

from utils.config import settings
from utils.access import audit, context_for, path_allowed, preview_request_allowed
from utils.i18n import DEFAULT_LANG, enabled_languages, safe_return_path


def _require_app_login(req, sess):
    """Load DB-backed authority and fail closed before every product route."""
    ctx = context_for(req)
    if not req.url.path.startswith("/app"):
        return None
    if not ctx.authenticated:
        if sess.get("uid") and ctx.status == "pending":
            return RedirectResponse("/choose-role", status_code=303)
        sess.clear()
        return RedirectResponse("/login", status_code=303)
    if not path_allowed(ctx, req.url.path):
        audit(ctx, "access_denied", req.url.path,
              f"actual={ctx.actual_role};effective={ctx.effective_role}")
        return Response("This page is not available for your role.", status_code=403)
    if not preview_request_allowed(ctx, req.url.path, req.method):
        audit(ctx, "preview_write_denied", req.url.path,
              f"actual={ctx.actual_role};effective={ctx.effective_role}")
        return Response("This action is disabled in role preview.", status_code=403)
    if req.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        supplied = req.headers.get("x-csrf-token", "")
        expected = str(sess.get("csrf_token") or "")
        host = (req.headers.get("x-forwarded-host") or req.headers.get("host") or "").split(",", 1)[0]
        source = req.headers.get("origin") or req.headers.get("referer") or ""
        source_host = urlsplit(source).netloc
        same_origin = bool(host and source_host and host.lower() == source_host.lower())
        token_ok = bool(expected and supplied and hmac.compare_digest(expected, supplied))
        if not (token_ok or same_origin):
            audit(ctx, "csrf_denied", req.url.path, req.method)
            return Response("Invalid request origin.", status_code=403)

app, rt = fast_app(
    live=False,
    static_path=".",
    pico=False,
    before=Beforeware(_require_app_login),
    secret_key=settings().app_secret,
    sess_https_only=settings().app_env == "production",
    htmx=True,
)


@rt("/healthz")
def healthz():
    """Process health probe; deliberately independent of external services."""
    return PlainTextResponse("ok")


@rt("/set-lang")
def set_lang(req, lang: str = DEFAULT_LANG, next: str = "/"):
    allowed = enabled_languages()
    lang = lang if lang in allowed else DEFAULT_LANG
    try:
        req.session["lang"] = lang
    except Exception:
        pass
    resp = RedirectResponse(safe_return_path(next), status_code=303)
    resp.set_cookie("lang", lang, max_age=365 * 24 * 3600,
                    httponly=True, secure=settings().app_env == "production",
                    samesite="lax")
    return resp


from landing import routes as _landing_routes  # noqa: E402,F401
from app_routes import _shared as _app_shared  # noqa: E402,F401
from app_routes import dashboard as _dashboard_routes  # noqa: E402,F401
from app_routes import marketplace as _marketplace_routes  # noqa: E402,F401
from app_routes import portfolio as _portfolio_routes  # noqa: E402,F401
from app_routes import statement as _statement_routes  # noqa: E402,F401
from app_routes import autoinvest as _autoinvest_routes  # noqa: E402,F401
from app_routes import assistant as _assistant_routes  # noqa: E402,F401
from app_routes import admin as _admin_routes  # noqa: E402,F401
from app_routes import onboarding as _onboarding_routes  # noqa: E402,F401
from app_routes import processing as _processing_routes  # noqa: E402,F401
from app_routes import collections as _collections_routes  # noqa: E402,F401
from app_routes import compliance as _compliance_routes  # noqa: E402,F401
from app_routes import auth as _auth_routes  # noqa: E402,F401
from app_routes import modules as _modules_routes  # noqa: E402,F401
from app_routes import accounting as _accounting_routes  # noqa: E402,F401
from app_routes import scoring as _scoring_routes  # noqa: E402,F401
from app_routes import integrations as _integrations_routes  # noqa: E402,F401
from app_routes import origination as _origination_routes  # noqa: E402,F401
from app_routes import depth as _depth_routes  # noqa: E402,F401
from app_routes import pdf_viewer as _pdf_viewer_routes  # noqa: E402,F401
from app_routes import agents as _agents_routes  # noqa: E402,F401
from app_routes import languages as _language_routes  # noqa: E402,F401
from app_routes import team as _team_routes  # noqa: E402,F401
from app_routes import shell as _shell_routes  # noqa: E402,F401
