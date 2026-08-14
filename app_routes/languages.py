"""Admin-controlled language availability for public and product surfaces."""

from __future__ import annotations

from fasthtml.common import Button, Div, Form, Input, Label, P, Span
from starlette.responses import RedirectResponse

from app import rt
from app_routes._shared import app_page, current_role
from landing.components import Eyebrow, Heading, Section_
from utils.i18n import (
    DEFAULT_LANG, LANG_META, enabled_languages, get_lang, set_enabled_languages,
)
from utils.money import AVAILABLE_CURRENCIES, display_currency, set_display_currency


def _guard(req):
    if current_role(req) != "admin":
        return RedirectResponse("/app", status_code=303)
    return None


def _language_option(code: str, selected: set[str]):
    meta = LANG_META[code]
    required = code == DEFAULT_LANG
    return Label(
        Input(
            type="checkbox", name="languages", value=code,
            checked=code in selected, disabled=required,
            cls="h-4 w-4 accent-accent",
        ),
        Span(meta["flag"], cls="text-xl"),
        Div(
            P(meta["name"], cls="text-sm font-medium text-ink"),
            P(f"{code.upper()} · {'Always enabled' if required else 'Available to users'}",
              cls="text-xs text-ink-dim"),
        ),
        cls="flex items-center gap-3 rounded-xl border border-line bg-bg-elevated px-4 py-3 cursor-pointer",
    )


@rt("/app/admin/languages", methods=["GET"])
def language_settings(req):
    denied = _guard(req)
    if denied:
        return denied
    lang = get_lang(req)
    active = set(enabled_languages(refresh=True))
    saved = req.query_params.get("saved")
    return app_page(
        "Languages",
        Section_(
            Eyebrow("Administration · Internationalisation"),
            Heading(1, "Languages", cls="mt-4"),
            P("Choose which checked-in languages users may select. English remains the source and fallback.",
              cls="mt-4 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            P("Regional settings updated.", cls="mt-4 text-sm text-accent") if saved else None,
            cls="border-t border-line",
        ),
        Section_(
            Form(
                Input(type="hidden", name="languages", value=DEFAULT_LANG),
                Div(*[_language_option(code, active) for code in LANG_META],
                    cls="grid gap-3 md:grid-cols-2 xl:grid-cols-3"),
                Button("Save language settings", type="submit",
                       cls="mt-6 rounded-full bg-accent px-5 py-3 text-sm font-medium text-bg"),
                method="post", action="/app/admin/languages",
            ),
            P("Russian and Uzbek catalogues are retained but disabled by default.",
              cls="mt-5 text-sm text-ink-dim"),
            cls="border-t border-line",
        ),
        Section_(
            Eyebrow("Display currency"),
            Heading(2, "Choose the application currency", cls="mt-4"),
            P("Stored demo amounts are converted consistently across dashboards, reports, PDFs, and exports.",
              cls="mt-4 text-ink-muted max-w-3xl"),
            Form(
                Div(*[
                    Label(
                        Input(type="radio", name="currency", value=code,
                              checked=code == display_currency(refresh=True),
                              cls="h-4 w-4 accent-accent"),
                        Span({"USD": "$ USD", "EUR": "€ EUR", "GBP": "£ GBP"}[code],
                             cls="text-sm font-medium text-ink"),
                        cls="flex items-center gap-3 rounded-xl border border-line bg-bg-elevated px-4 py-3 cursor-pointer",
                    ) for code in AVAILABLE_CURRENCIES
                ], cls="mt-6 grid gap-3 sm:grid-cols-3"),
                Button("Save display currency", type="submit",
                       cls="mt-6 rounded-full bg-accent px-5 py-3 text-sm font-medium text-bg"),
                method="post", action="/app/admin/currency",
            ),
            cls="border-t border-line",
        ),
        current_path="/app/admin/languages", lang=lang, role="admin",
    )


@rt("/app/admin/languages", methods=["POST"])
async def language_settings_save(req):
    denied = _guard(req)
    if denied:
        return denied
    form = await req.form()
    selected = form.getlist("languages")
    set_enabled_languages(selected)
    try:
        from app_routes.admin import log_action
        log_action("admin", "super", "languages.update", detail=",".join(enabled_languages()))
    except Exception:
        pass
    return RedirectResponse("/app/admin/languages?saved=1", status_code=303)


@rt("/app/admin/currency", methods=["POST"])
async def currency_settings_save(req):
    denied = _guard(req)
    if denied:
        return denied
    form = await req.form()
    set_display_currency(str(form.get("currency") or ""))
    try:
        from app_routes.admin import log_action
        log_action("admin", "super", "currency.update", detail=display_currency())
    except Exception:
        pass
    return RedirectResponse("/app/admin/languages?saved=currency", status_code=303)
