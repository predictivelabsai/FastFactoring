"""Landing-page components for Factorio's configurable multilingual surface."""

from __future__ import annotations

from urllib.parse import quote, urlencode

from fasthtml.common import (
    Html, Head, Body, Meta, Title, Link, Script, NotStr,
    Nav, Main, Footer, Section, Article, Div, Span, A, Img,
    H1, H2, H3, H4, P, Ul, Li, Button, Form, Input, Textarea, Label,
    Select, Option,
)

from utils.i18n import (
    DEFAULT_LANG, LANG_META, enabled_languages, localize_tree, t,
)

SITE_NAME = "Factorio"
CONTACT_EMAIL = "hello@factorio.co.uk"
FAVICON = "data:image/svg+xml," + quote(
    """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#1F5D43"/><path fill="white" d="M8 7h16v5H14v4h9v5h-9v6H8Z"/></svg>""",
    safe="",
)

SECTOR_ICONS = {
    "manufacturing": "&#9881;",
    "wholesale": "&#128230;",
    "construction": "&#127959;",
    "logistics": "&#128666;",
    "hospitality": "&#127976;",
    "retail": "&#128717;",
    "healthcare": "&#127973;",
    "services": "&#128188;",
    "agriculture": "&#127806;",
    "energy": "&#9889;",
}
SECTOR_KEYS = ["manufacturing", "wholesale", "construction", "logistics",
               "hospitality", "retail", "healthcare", "services",
               "agriculture", "energy"]

TAILWIND_CONFIG = """
tailwind.config = {
  theme: {
    extend: {
      colors: {
        bg:     { DEFAULT: '#F7F6F1', elevated: '#FFFFFF', raised: '#EFEDE4' },
        ink:    { DEFAULT: '#14231B', muted: '#415046', dim: '#7A867E' },
        line:   { DEFAULT: '#E3DFD2', bright: '#CFC8B4' },
        accent: { DEFAULT: '#1F5D43', dim: '#CFE5DA', deep: '#0F3226' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      letterSpacing: { tightest: '-0.04em', tighter: '-0.025em' },
    },
  },
};
"""


def Eyebrow(text: str, *, cls: str = ""):
    return Span(text, cls=f"font-mono text-[11px] tracking-[0.18em] uppercase text-accent {cls}".strip())


def Heading(level: int, text, *, cls: str = ""):
    tag = {1: H1, 2: H2, 3: H3, 4: H4}[level]
    base = {
        1: "text-4xl sm:text-5xl md:text-7xl font-medium tracking-tightest text-ink leading-[1.05] md:leading-[1.02]",
        2: "text-2xl sm:text-3xl md:text-5xl font-medium tracking-tighter text-ink leading-[1.12] md:leading-[1.08]",
        3: "text-lg sm:text-xl md:text-2xl font-medium tracking-tight text-ink",
        4: "text-base md:text-lg font-medium text-ink",
    }[level]
    return tag(text if not isinstance(text, tuple) else Span(*text), cls=f"{base} {cls}".strip())


def Body_(text, *, cls: str = "", muted: bool = True):
    tone = "text-ink-muted" if muted else "text-ink"
    return P(text, cls=f"text-base md:text-lg leading-relaxed {tone} {cls}".strip())


def Button_(text: str, *, href: str = "#", primary: bool = True, cls: str = ""):
    base = "inline-flex items-center gap-2 px-5 py-3 rounded-full text-sm font-medium transition-all duration-200"
    if primary:
        style = "bg-accent text-bg hover:bg-ink shadow-[0_0_0_1px_#1F5D43] hover:shadow-[0_0_0_1px_#14231B]"
    else:
        style = "bg-transparent text-ink border border-line-bright hover:border-accent hover:text-accent"
    return A(text, Span(NotStr("&rarr;"), cls="text-base"), href=href, cls=f"{base} {style} {cls}".strip())


def Pill(text: str, *, cls: str = ""):
    return Span(
        text,
        cls=f"inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono tracking-wider uppercase text-ink-muted bg-bg-elevated border border-line {cls}".strip(),
    )


def _lang_switcher(current_lang: str, current_path: str = "/"):
    """Flag dropdown (kanvas/pehero pattern): a button showing the current flag,
    opening a menu of flag + native-name options. Defaults to English (GB flag)."""
    current = LANG_META.get(current_lang, LANG_META["en"])
    options = []
    for code in enabled_languages():
        meta = LANG_META[code]
        active_cls = " font-semibold text-ink" if code == current_lang else ""
        options.append(
            A(Span(meta["flag"], cls="mr-2"), Span(meta["name"], cls="text-xs"),
              href=f"/set-lang?{urlencode({'lang': code, 'next': current_path})}",
              lang=code,
              cls=("flex items-center gap-1 px-3 py-1.5 text-sm text-ink-muted "
                   "hover:bg-bg-raised hover:text-ink transition-colors no-underline" + active_cls))
        )
    return Div(
        Button(current["flag"], type="button",
               onclick="this.nextElementSibling.classList.toggle('hidden')",
               cls="text-base leading-none px-1.5 py-1 border border-transparent rounded "
                   "hover:border-line transition-colors cursor-pointer bg-transparent"),
        Div(*options,
            cls="hidden absolute right-0 top-full mt-1 bg-bg-elevated border border-line "
                "rounded-lg shadow-lg z-50 py-1 min-w-[150px] flex flex-col"),
        cls="relative",
    )


def _navbar(current_path: str = "/", lang: str = DEFAULT_LANG):
    nav_keys = [
        ("nav_for_sellers", "/for-sellers"),
        ("nav_for_investors", "/for-investors"),
        ("nav_how_it_works", "/how-it-works"),
        ("nav_pricing", "/pricing"),
        ("nav_contact", "/contact"),
    ]
    items = [
        Li(A(t(key, lang), href=href,
             cls=f"text-sm text-ink-muted hover:text-ink transition-colors {'text-ink font-medium' if current_path == href else ''}"))
        for key, href in nav_keys
    ]
    items.append(
        Li(A("Demo", href="https://factorio.co.uk/",
             cls="text-sm text-ink-muted hover:text-ink transition-colors"))
    )
    return Nav(
        Div(
            A(
                Span(NotStr("&#9670;"), cls="text-accent mr-2"),
                Span(SITE_NAME, cls="font-medium tracking-tight"),
                href="/",
                cls="flex items-center text-ink text-base hover:text-accent transition-colors",
            ),
            Ul(*items, cls="hidden lg:flex items-center gap-7"),
            Div(
                _lang_switcher(lang, current_path),
                A(t("nav_get_quote", lang), href="/contact",
                  cls="hidden lg:inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium text-ink border border-line-bright hover:border-accent hover:text-accent transition-colors"),
                A(t("nav_login", lang), href="/login",
                  cls="inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium bg-accent text-bg hover:bg-ink transition-colors"),
                cls="flex items-center gap-3",
            ),
            cls="max-w-7xl mx-auto px-5 md:px-6 flex items-center justify-between h-16 gap-4",
        ),
        cls="sticky top-0 z-50 backdrop-blur-md bg-bg/80 border-b border-line",
    )


def _footer(lang: str = DEFAULT_LANG):
    return Footer(
        Div(
            Div(
                Div(
                    A(Span(NotStr("&#9670;"), cls="text-accent mr-2"), Span(SITE_NAME, cls="font-medium text-ink"),
                      href="/", cls="flex items-center text-lg mb-4"),
                    P(t("footer_tagline", lang), cls="text-ink-muted text-sm max-w-xs mb-5"),
                    P(t("footer_built_by", lang), cls="text-ink-dim text-xs leading-relaxed max-w-xs"),
                    A("Open-source FastFactoring project →", href="/fastfactoring",
                      cls="inline-block mt-4 text-accent text-xs hover:text-ink"),
                ),
                Div(
                    H4(t("footer_product", lang), cls="text-xs font-mono tracking-[0.18em] uppercase text-ink-muted mb-5"),
                    Ul(
                        Li(A(t("nav_for_sellers", lang), href="/for-sellers", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                        Li(A(t("nav_for_investors", lang), href="/for-investors", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                        Li(A(t("nav_how_it_works", lang), href="/how-it-works", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                        Li(A(t("nav_pricing", lang), href="/pricing", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                        Li(A(t("footer_marketplace", lang), href="/app/marketplace", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                    ),
                ),
                Div(
                    H4(t("footer_company", lang), cls="text-xs font-mono tracking-[0.18em] uppercase text-ink-muted mb-5"),
                    Ul(
                        Li(A(t("nav_contact", lang), href="/contact", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                        Li(A(t("footer_terms", lang), href="#", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                        Li(A(t("footer_privacy", lang), href="#", cls="text-sm text-ink hover:text-accent"), cls="mb-2"),
                    ),
                ),
                cls="grid grid-cols-2 md:grid-cols-3 gap-10",
            ),
            Div(
                Div(f"© {__import__('datetime').datetime.now().year} Factorio.",
                    cls="text-ink-dim text-xs"),
                A(CONTACT_EMAIL, href=f"mailto:{CONTACT_EMAIL}",
                  cls="text-ink-dim text-xs hover:text-accent"),
                cls="mt-10 md:mt-14 pt-6 border-t border-line flex items-start md:items-center justify-between flex-wrap gap-4",
            ),
            cls="max-w-7xl mx-auto px-5 md:px-6",
        ),
        cls="py-12 md:py-16 border-t border-line bg-bg-elevated",
    )


def page(title: str, *content, current_path: str = "/", lang: str = DEFAULT_LANG, head_extra=None):
    tagline = t("footer_tagline", lang)
    head_children = [
        Meta(charset="utf-8"),
        Meta(name="viewport", content="width=device-width, initial-scale=1"),
        Meta(name="description", content=f"{SITE_NAME} — {tagline}"),
        Title(f"{title} · {SITE_NAME}"),
        Link(rel="icon", type="image/svg+xml", href="/static/favicon.svg"),
        Link(rel="preconnect", href="https://fonts.googleapis.com"),
        Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
        Link(
            rel="stylesheet",
            href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap",
        ),
        Script(src="https://cdn.tailwindcss.com"),
        Script(NotStr(TAILWIND_CONFIG)),
        Script(src="https://unpkg.com/htmx.org@2.0.3"),
        Link(rel="stylesheet", href="/static/site.css"),
    ]
    if head_extra:
        head_children.extend(head_extra if isinstance(head_extra, list) else [head_extra])

    return localize_tree(Html(
        Head(*head_children),
        Body(
            _navbar(current_path, lang=lang),
            Main(*content, cls="min-h-screen"),
            _footer(lang=lang),
            cls="bg-bg text-ink font-sans antialiased",
        ),
        lang=lang,
    ), lang)


# ---- Higher-level blocks ------------------------------------------------

def Section_(*content, cls: str = ""):
    return Section(Div(*content, cls="max-w-7xl mx-auto px-5 md:px-6"), cls=f"py-14 md:py-20 lg:py-24 {cls}".strip())


def _StatCell(value: str, caption: str):
    return Div(
        Span(value, cls="text-2xl md:text-3xl font-medium tracking-tighter text-ink"),
        P(caption, cls="text-ink-muted text-xs md:text-sm mt-1"),
    )


def Hero(lang: str = DEFAULT_LANG):
    headline = (
        Span(t("hero_turn", lang)),
        Span(t("hero_unpaid", lang), cls="text-accent"),
        Span(t("hero_into", lang)),
        Span(t("hero_working", lang), cls="text-accent"),
        Span(t("hero_for_biz", lang)),
    )
    return Section(
        Div(
            Div(
                Eyebrow(t("hero_eyebrow", lang)),
                H1(*headline,
                   cls="mt-5 md:mt-6 text-[40px] sm:text-5xl md:text-7xl lg:text-[84px] font-medium tracking-tightest text-ink leading-[1.05] md:leading-[1.02] max-w-5xl"),
                P(t("hero_lede", lang), cls="mt-6 md:mt-8 text-base md:text-xl text-ink-muted max-w-2xl leading-relaxed"),
                Div(
                    Button_(t("hero_cta_finance", lang), href="/for-sellers", primary=True),
                    Button_(t("hero_cta_invest", lang), href="/for-investors", primary=False),
                    cls="mt-8 md:mt-10 flex items-center gap-3 flex-wrap",
                ),
                cls="relative z-30 max-w-7xl mx-auto px-5 md:px-6 py-24 md:py-0",
            ),
            cls="relative min-h-[80vh] md:min-h-[86vh] flex items-center overflow-hidden bg-bg",
        ),
        Div(
            Div(
                _StatCell("85%", t("stat_advance", lang)),
                _StatCell("1–3 " + ("kun" if lang == "uz" else "дня" if lang == "ru" else "days"),
                          t("stat_days", lang)),
                _StatCell("10", t("stat_sectors", lang)),
                _StatCell(str(len(enabled_languages())), t("stat_total", lang)),
                cls="max-w-7xl mx-auto px-5 md:px-6 py-5 md:py-6 grid grid-cols-2 md:grid-cols-4 gap-6",
            ),
            cls="border-y border-line bg-bg-elevated/60",
        ),
    )


def ProductPreview(lang: str = DEFAULT_LANG):
    """Animated product tour (home-page hero GIF), built from the same role
    screenshots as the user guide (scripts/make_gif.py --home)."""
    return Section(
        Div(
            Div(
                Eyebrow(t("preview_eyebrow", lang)),
                Heading(2, t("preview_title", lang),
                        cls="mt-4 max-w-3xl mx-auto text-center"),
                P(t("preview_sub", lang),
                  cls="mt-4 text-ink-muted text-base md:text-lg max-w-2xl mx-auto text-center"),
                cls="text-center",
            ),
            Div(
                Img(src="/docs/fastfactoring-reference-home.gif",
                    alt="Factorio product tour",
                    loading="lazy",
                    cls="w-full h-auto block"),
                cls="mt-10 md:mt-12 max-w-5xl mx-auto rounded-2xl overflow-hidden "
                    "border border-line shadow-2xl shadow-ink/5 bg-bg-elevated",
            ),
            cls="max-w-7xl mx-auto px-5 md:px-6 py-20 md:py-28",
        ),
        cls="bg-bg border-t border-line",
    )


def HowItWorks(lang: str = DEFAULT_LANG):
    steps = [
        ("01", t("how_s1_title", lang), t("how_s1_body", lang)),
        ("02", t("how_s2_title", lang), t("how_s2_body", lang)),
        ("03", t("how_s3_title", lang), t("how_s3_body", lang)),
        ("04", t("how_s4_title", lang), t("how_s4_body", lang)),
    ]
    return Section_(
        Div(
            Eyebrow(t("how_eyebrow", lang)),
            Heading(2, t("how_heading", lang), cls="mt-3 max-w-3xl mb-10"),
            cls="mb-6",
        ),
        Div(
            *[Article(
                P(num, cls="font-mono text-[11px] tracking-widest uppercase text-ink-dim mb-3"),
                H3(title, cls="text-ink text-xl font-medium mb-3"),
                P(body, cls="text-ink-muted text-sm leading-relaxed"),
                cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
            ) for (num, title, body) in steps],
            cls="grid md:grid-cols-2 lg:grid-cols-4 gap-4",
        ),
        cls="border-t border-line",
    )


def SectorCards(lang: str = DEFAULT_LANG):
    return Section_(
        Div(
            Eyebrow(t("sectors_eyebrow", lang)),
            Heading(2, t("sectors_heading", lang), cls="mt-3 max-w-3xl mb-10"),
            cls="mb-6",
        ),
        Div(
            *[Article(
                Div(Span(NotStr(SECTOR_ICONS[k]), cls="text-accent text-2xl"), cls="mb-5"),
                H3(t(f"sector_{k}", lang), cls="text-ink text-xl font-medium mb-2"),
                P(t(f"sector_{k}_blurb", lang), cls="text-ink-muted text-sm leading-relaxed"),
                cls="p-7 rounded-2xl bg-bg-elevated border border-line hover:border-accent/50 transition-colors h-full",
            ) for k in SECTOR_KEYS],
            cls="grid sm:grid-cols-2 lg:grid-cols-5 gap-4",
        ),
        cls="border-t border-line",
    )


def SectorExplorer(lang: str = DEFAULT_LANG):
    """Home-page industry dropdown: pick a sector, see a sample use case."""
    opts = [
        Option(t(f"sector_{k}", lang), value=k, selected=(i == 0))
        for i, k in enumerate(SECTOR_KEYS)
    ]
    panels = [
        Div(
            Div(Span(NotStr(SECTOR_ICONS[k]), cls="text-accent text-2xl"),
                H3(t(f"sector_{k}", lang), cls="text-ink text-xl font-medium"),
                cls="flex items-center gap-3 mb-3"),
            P(t(f"sector_{k}_usecase", lang), cls="text-ink-muted leading-relaxed"),
            id=f"uc-{k}",
            cls="p-7 rounded-2xl bg-bg-elevated border border-line" + ("" if i == 0 else " hidden"),
        )
        for i, k in enumerate(SECTOR_KEYS)
    ]
    select = Select(
        *opts,
        onchange=("document.querySelectorAll('[id^=uc-]').forEach(function(e){e.classList.add('hidden')});"
                  "document.getElementById('uc-'+this.value).classList.remove('hidden');"),
        cls="w-full sm:w-auto bg-bg-elevated border border-line-bright rounded-full px-5 py-3 "
            "text-sm text-ink focus:outline-none focus:border-accent cursor-pointer",
        aria_label=t("sector_explorer_label", lang),
    )
    return Section_(
        Eyebrow(t("sector_explorer_eyebrow", lang)),
        Heading(2, t("sector_explorer_heading", lang), cls="mt-3 max-w-3xl mb-6"),
        Div(Span(t("sector_explorer_label", lang),
                 cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mr-3 hidden sm:inline"),
            select, cls="mb-5 flex items-center flex-wrap gap-3"),
        Div(*panels),
        cls="border-t border-line",
    )


def BenefitsStrip(lang: str = DEFAULT_LANG):
    benefits = [
        (t("benefit_sellers_label", lang), t("benefit_sellers_metric", lang), t("benefit_sellers_caption", lang)),
        (t("benefit_investors_label", lang), t("benefit_investors_metric", lang), t("benefit_investors_caption", lang)),
    ]
    return Section_(
        Eyebrow(t("benefits_eyebrow", lang)),
        Heading(2, t("benefits_heading", lang), cls="mt-3 max-w-3xl mb-10"),
        Div(
            *[Article(
                P(label, cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-3"),
                P(metric, cls="text-3xl md:text-4xl font-medium tracking-tighter text-ink mb-3"),
                P(caption, cls="text-ink-muted text-sm leading-relaxed"),
                cls="p-7 rounded-2xl bg-bg-elevated border border-line",
            ) for (label, metric, caption) in benefits],
            cls="grid md:grid-cols-2 gap-4",
        ),
        cls="border-t border-line",
    )


def CTASection(*, lang: str = DEFAULT_LANG,
               headline: str | None = None, body: str | None = None,
               cta_label: str | None = None, cta_href: str = "/contact"):
    headline = headline or t("cta_headline", lang)
    body = body or t("cta_body", lang)
    cta_label = cta_label or t("cta_button", lang)
    browse_label = t("cta_browse", lang)
    return Section(
        Div(
            Div(
                Eyebrow(t("cta_eyebrow", lang)),
                Heading(2, headline, cls="mt-3 max-w-3xl"),
                P(body, cls="mt-5 text-ink-muted text-lg max-w-2xl leading-relaxed"),
                Div(
                    Button_(cta_label, href=cta_href, primary=True),
                    Button_(browse_label, href="/app/marketplace", primary=False),
                    cls="mt-8 flex items-center gap-3 flex-wrap",
                ),
                cls="max-w-7xl mx-auto px-5 md:px-6 py-20 md:py-28 relative z-10",
            ),
            Div(cls="absolute inset-0 bg-gradient-to-br from-accent/5 via-transparent to-transparent pointer-events-none"),
            cls="relative border-y border-line bg-bg-elevated/60 overflow-hidden",
        ),
    )
