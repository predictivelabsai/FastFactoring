"""Open-source FastFactoring landing page following the FastSME product pattern."""

from __future__ import annotations

from urllib.parse import quote, urlencode

from fasthtml.common import *

from utils.i18n import LANG_META, enabled_languages, localize_tree


DEMO_URL = "https://factorio.co.uk/"
REPOSITORY_URL = "https://github.com/predictivelabsai/FastFactoring"
ACCENT = "#7657c8"
FAVICON = "data:image/svg+xml," + quote(
    """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#7657c8"/><path fill="white" d="M9 7h15v5H15v4h8v5h-8v6H9Z"/></svg>""",
    safe="",
)

CAPABILITIES = (
    ("Invoice operations", "Origination, verification, funding, servicing, collections and settlement in one auditable workflow."),
    ("Role-based workspaces", "Purpose-built journeys for suppliers, payers, investors and the platform administrator."),
    ("Deployment control", "Self-host the FastHTML application, connect PostgreSQL and choose the languages and display currency you need."),
)

CSS = """
:root{--accent:#7657c8;--tint:#f5f1ff;--ink:#171426;--muted:#696477;--line:#e9e4f2}
*{box-sizing:border-box}body{margin:0;background:#fff;color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}
.ff-nav{height:68px;display:flex;align-items:center;justify-content:space-between;max-width:1180px;margin:auto;padding:0 24px;border-bottom:1px solid var(--line)}
.ff-brand{display:flex;align-items:center;gap:10px;font-weight:760;color:var(--ink);text-decoration:none}.ff-mark{width:30px;height:30px;border-radius:9px;background:var(--accent);display:grid;place-items:center;color:#fff;font-weight:800}
.ff-nav-actions{display:flex;align-items:center;gap:18px}.ff-nav-link{color:var(--muted);text-decoration:none;font-size:14px;font-weight:650}.ff-nav-link:hover{color:var(--accent)}
.ff-lang{position:relative}.ff-lang summary{list-style:none;cursor:pointer;padding:5px 7px;border:1px solid transparent;border-radius:7px}.ff-lang summary::-webkit-details-marker{display:none}.ff-lang[open] summary,.ff-lang summary:hover{border-color:var(--line)}
.ff-lang-menu{position:absolute;right:0;top:36px;z-index:50;min-width:150px;padding:5px;background:#fff;border:1px solid var(--line);border-radius:10px;box-shadow:0 18px 45px rgba(23,20,38,.14)}.ff-lang-menu a{display:flex;gap:8px;padding:7px 9px;color:var(--muted);font-size:12px;text-decoration:none;border-radius:7px}.ff-lang-menu a:hover,.ff-lang-menu a.active{background:var(--tint);color:var(--ink)}
.ff-button{display:inline-flex;align-items:center;justify-content:center;border-radius:999px;padding:10px 17px;text-decoration:none;font-weight:650;font-size:14px}.ff-button.primary{background:var(--accent);color:#fff}.ff-button.secondary{border:1px solid var(--line);color:var(--ink);background:#fff}
.ff-hero{max-width:1180px;margin:auto;padding:104px 24px 86px}.ff-kicker{color:var(--accent);font-size:12px;font-weight:760;text-transform:uppercase;letter-spacing:.16em}.ff-hero h1{font-size:clamp(44px,7vw,80px);line-height:1.02;letter-spacing:-.055em;max-width:960px;margin:22px 0}.ff-lede{font-size:20px;line-height:1.65;color:var(--muted);max-width:760px}.ff-actions{display:flex;gap:12px;margin-top:32px;flex-wrap:wrap}
.ff-proof{background:var(--tint);border-block:1px solid #e8defd}.ff-grid{max-width:1180px;margin:auto;padding:66px 24px;display:grid;grid-template-columns:repeat(3,1fr);gap:18px}.ff-card{background:rgba(255,255,255,.84);border:1px solid #e6ddfa;border-radius:20px;padding:27px}.ff-num{color:var(--accent);font-size:12px;font-weight:760}.ff-card h2{font-size:20px;margin:24px 0 8px}.ff-card p{color:var(--muted);line-height:1.62;margin:0}
.ff-open{max-width:1180px;margin:auto;padding:82px 24px;display:grid;grid-template-columns:1fr 1fr;gap:72px;align-items:start}.ff-open h2{font-size:38px;letter-spacing:-.035em;margin:12px 0 18px}.ff-open p{color:var(--muted);line-height:1.7}.ff-list{display:grid;gap:12px}.ff-list div{padding:19px;border:1px solid var(--line);border-radius:16px}.ff-list strong{display:block;margin-bottom:6px}.ff-list span{color:var(--muted);font-size:14px;line-height:1.55}
.ff-reference{max-width:1180px;margin:auto;padding:0 24px 82px}.ff-reference-inner{border:1px solid var(--line);border-radius:24px;padding:42px;background:linear-gradient(135deg,var(--tint),#fff)}.ff-reference h2{font-size:32px;letter-spacing:-.03em;margin:10px 0}.ff-reference p{color:var(--muted);line-height:1.65;max-width:720px}.ff-footer{max-width:1180px;margin:auto;padding:30px 24px 48px;border-top:1px solid var(--line);color:var(--muted);font-size:13px;display:flex;justify-content:space-between;gap:20px}
@media(max-width:760px){.ff-nav{height:auto;min-height:62px;padding-block:10px}.ff-nav-actions{gap:8px}.ff-nav-link.optional{display:none}.ff-hero{padding-top:72px}.ff-grid,.ff-open{grid-template-columns:1fr}.ff-open{gap:28px}.ff-reference-inner{padding:28px}.ff-footer{flex-direction:column}}
"""


def _language_switcher(lang: str, current: str):
    current_meta = LANG_META.get(lang, LANG_META["en"])
    return Details(
        Summary(current_meta["flag"], aria_label="Choose language"),
        Div(*[
            A(Span(meta["flag"]), Span(meta["name"]),
              href=f"/set-lang?{urlencode({'lang': code, 'next': current})}",
              lang=code, cls="active" if code == lang else "")
            for code in enabled_languages()
            for meta in (LANG_META[code],)
        ], cls="ff-lang-menu"),
        cls="ff-lang",
    )


def landing_page(lang: str = "en"):
    """Render the FastSME-style open-source product page.

    The separately branded Factorio deployment remains the reference demo.
    """
    description = "Open-source invoice factoring infrastructure built with FastHTML, HTMX and PostgreSQL."
    return localize_tree(Html(
        Head(
            Title("FastFactoring · Open-source invoice financing"),
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Meta(name="description", content=description),
            Link(rel="icon", type="image/svg+xml", href=FAVICON),
            Link(rel="preconnect", href="https://fonts.googleapis.com"),
            Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"),
            Style(CSS),
        ),
        Body(
            Nav(
                A(Span("F", cls="ff-mark"), Span("FastFactoring"), href="/", cls="ff-brand"),
                Div(
                    A("Overview", href="#overview", cls="ff-nav-link optional"),
                    A("Open source", href="#open-source", cls="ff-nav-link optional"),
                    A("Demo", href=DEMO_URL, cls="ff-nav-link"),
                    _language_switcher(lang, "/fastfactoring"),
                    A("View on GitHub", href=REPOSITORY_URL, cls="ff-button secondary"),
                    A("Sign in", href="/login", cls="ff-button primary"),
                    cls="ff-nav-actions",
                ),
                cls="ff-nav",
            ),
            Main(
                Section(
                    Span("Invoice finance infrastructure", cls="ff-kicker"),
                    H1("Ship a modern factoring platform without starting from zero."),
                    P(description, cls="ff-lede"),
                    Div(
                        A("Explore the live demo →", href=DEMO_URL, cls="ff-button primary"),
                        A("Read the source →", href=REPOSITORY_URL, cls="ff-button secondary"),
                        cls="ff-actions",
                    ),
                    id="overview", cls="ff-hero",
                ),
                Section(
                    Div(*[
                        Article(Span(f"0{index}", cls="ff-num"), H2(title), P(body), cls="ff-card")
                        for index, (title, body) in enumerate(CAPABILITIES, 1)
                    ], cls="ff-grid"),
                    cls="ff-proof",
                ),
                Section(
                    Div(
                        Span("Open by design", cls="ff-kicker"),
                        H2("Own the workflow, data and deployment."),
                        P("FastFactoring is a transparent foundation for teams building invoice-finance products. Fork it, audit it and adapt the business rules without adopting a proprietary front-end stack."),
                        A("Contribute on GitHub →", href=REPOSITORY_URL, cls="ff-button primary"),
                    ),
                    Div(
                        Div(Strong("FastHTML first"), Span("Server-rendered Python components with HTMX interactions and minimal client-side JavaScript.")),
                        Div(Strong("Portable operations"), Span("PostgreSQL migrations, deterministic synthetic fixtures and container deployment are included.")),
                        Div(Strong("International by default"), Span("Checked-in translations, browser negotiation and administrator-controlled language and currency settings.")),
                        cls="ff-list",
                    ),
                    id="open-source", cls="ff-open",
                ),
                Section(
                    Div(
                        Span("Reference implementation", cls="ff-kicker"),
                        H2("See FastFactoring running as Factorio."),
                        P("Factorio is the standalone, production-shaped product we ship from this codebase. Its public landing page leads into the same supplier, payer, investor and administrator sign-in flow."),
                        A("Open the Factorio demo →", href=DEMO_URL, cls="ff-button primary"),
                        cls="ff-reference-inner",
                    ),
                    cls="ff-reference",
                ),
            ),
            Footer(
                Span("FastFactoring is part of the open-source FastSME suite."),
                Div(A("All FastSME products", href="https://fastsme.com/products", style="color:var(--accent);margin-right:18px"),
                    A("Factorio demo", href=DEMO_URL, style="color:var(--accent)")),
                cls="ff-footer",
            ),
        ),
        lang=lang,
    ), lang)
