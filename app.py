"""FastFactoring -- open-source FastHTML invoice-financing application.

Single process, two route groups:
  - /                 FastFactoring or Factorio reference landing (by host)
  - /app/*            invoice financing product (app_routes/)
"""

from __future__ import annotations

from fasthtml.common import Beforeware, fast_app, serve
from starlette.responses import PlainTextResponse, RedirectResponse

from utils.config import settings
from utils.i18n import DEFAULT_LANG, enabled_languages, safe_return_path


def _require_app_login(req, sess):
    """Keep every product and admin endpoint behind the shared sign-in flow."""
    if req.url.path.startswith("/app") and not sess.get("uid"):
        return RedirectResponse("/login", status_code=303)

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
from app_routes import shell as _shell_routes  # noqa: E402,F401
