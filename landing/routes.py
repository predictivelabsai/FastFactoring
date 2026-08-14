"""Marketing routes: /, /for-sellers, /for-investors, /how-it-works, /pricing, /contact."""

from __future__ import annotations

from fasthtml.common import (
    Div, H1, H2, H3, H4, P, Ul, Li, Section, Article, Span, A, Form, Input, Textarea, Label, Button, NotStr,
)

from app import rt
from utils.i18n import t, get_lang
from landing.components import (
    page, Hero, ProductPreview, HowItWorks, SectorCards, SectorExplorer, BenefitsStrip, CTASection,
    Eyebrow, Heading, Body_, Button_, Pill, Section_, SITE_NAME,
)
from landing.fastfactoring import landing_page as fastfactoring_landing


def _factorio_home(lang: str):
    return page(
        t("hero_eyebrow", lang),
        Hero(lang=lang),
        ProductPreview(lang=lang),
        HowItWorks(lang=lang),
        SectorCards(lang=lang),
        SectorExplorer(lang=lang),
        BenefitsStrip(lang=lang),
        CTASection(lang=lang),
        current_path="/",
        lang=lang,
    )


@rt("/")
def home(req):
    lang = get_lang(req)
    host = req.headers.get("host", "").split(":", 1)[0].lower()
    # The production reference implementation remains Factorio-branded. Local,
    # preview, and future FastFactoring hosts present the open-source product.
    if host in {"factorio.co.uk", "www.factorio.co.uk"}:
        return _factorio_home(lang)
    return fastfactoring_landing(lang)


@rt("/fastfactoring")
def fastfactoring(req):
    return fastfactoring_landing(get_lang(req))


@rt("/factorio")
def factorio_reference(req):
    """Stable local route for reference-product capture and review."""
    return _factorio_home(get_lang(req))


@rt("/for-sellers")
def for_sellers(req):
    lang = get_lang(req)
    benefits = [
        (t("sellers_b1_title", lang), t("sellers_b1_body", lang)),
        (t("sellers_b2_title", lang), t("sellers_b2_body", lang)),
        (t("sellers_b3_title", lang), t("sellers_b3_body", lang)),
        (t("sellers_b4_title", lang), t("sellers_b4_body", lang)),
    ]
    criteria = [
        t("sellers_e1", lang), t("sellers_e2", lang),
        t("sellers_e3", lang), t("sellers_e4", lang),
    ]
    return page(
        t("sellers_eyebrow", lang),
        Section_(
            Eyebrow(t("sellers_eyebrow", lang)),
            Heading(1, t("sellers_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("sellers_lede", lang), cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        Section_(
            Heading(2, t("sellers_benefits_h2", lang), cls="mb-10 max-w-3xl"),
            Div(
                *[Article(
                    H3(title, cls="text-ink text-xl font-medium mb-3"),
                    P(body, cls="text-ink-muted text-sm leading-relaxed"),
                    cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
                ) for (title, body) in benefits],
                cls="grid md:grid-cols-2 gap-4",
            ),
            cls="border-t border-line",
        ),
        Section_(
            Heading(2, t("sellers_eligibility_h2", lang), cls="mb-10 max-w-3xl"),
            Div(
                Ul(
                    *[Li(
                        Span(NotStr("&#10003; "), cls="text-accent mr-2"),
                        Span(c, cls="text-ink text-sm"),
                        cls="mb-3 flex items-baseline",
                    ) for c in criteria],
                    cls="space-y-1",
                ),
                cls="max-w-xl",
            ),
            Div(Button_(t("cta_button", lang), href="/contact", primary=True), cls="mt-8"),
            cls="border-t border-line",
        ),
        CTASection(lang=lang, headline=t("sellers_cta_h", lang), body=t("sellers_cta_b", lang)),
        current_path="/for-sellers",
        lang=lang,
    )


@rt("/for-investors")
def for_investors(req):
    lang = get_lang(req)
    features = [
        (t("investors_f1_title", lang), t("investors_f1_body", lang)),
        (t("investors_f2_title", lang), t("investors_f2_body", lang)),
        (t("investors_f3_title", lang), t("investors_f3_body", lang)),
        (t("investors_f4_title", lang), t("investors_f4_body", lang)),
    ]
    how_steps = [
        ("01", t("investors_h_s1_title", lang), t("investors_h_s1_body", lang)),
        ("02", t("investors_h_s2_title", lang), t("investors_h_s2_body", lang)),
        ("03", t("investors_h_s3_title", lang), t("investors_h_s3_body", lang)),
        ("04", t("investors_h_s4_title", lang), t("investors_h_s4_body", lang)),
    ]
    return page(
        t("investors_eyebrow", lang),
        Section_(
            Eyebrow(t("investors_eyebrow", lang)),
            Heading(1, t("investors_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("investors_lede", lang), cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        Section_(
            Heading(2, t("investors_why_h2", lang), cls="mb-10 max-w-3xl"),
            Div(
                *[Article(
                    H3(title, cls="text-ink text-xl font-medium mb-3"),
                    P(body, cls="text-ink-muted text-sm leading-relaxed"),
                    cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
                ) for (title, body) in features],
                cls="grid md:grid-cols-2 gap-4",
            ),
            cls="border-t border-line",
        ),
        Section_(
            Heading(2, t("investors_how_h2", lang), cls="mb-10 max-w-3xl"),
            Div(
                *[Article(
                    P(num, cls="font-mono text-[11px] tracking-widest uppercase text-ink-dim mb-3"),
                    H3(title, cls="text-ink text-xl font-medium mb-3"),
                    P(body, cls="text-ink-muted text-sm leading-relaxed"),
                    cls="p-7 rounded-2xl bg-bg-elevated border border-line h-full",
                ) for (num, title, body) in how_steps],
                cls="grid md:grid-cols-2 lg:grid-cols-4 gap-4",
            ),
            cls="border-t border-line",
        ),
        CTASection(lang=lang, headline=t("investors_cta_h", lang),
                   body=t("investors_cta_b", lang), cta_label=t("investors_cta_btn", lang)),
        current_path="/for-investors",
        lang=lang,
    )


@rt("/how-it-works")
def how_it_works(req):
    lang = get_lang(req)
    return page(
        t("nav_how_it_works", lang),
        Section_(
            Eyebrow(t("how_eyebrow", lang)),
            Heading(1, t("hiw_h1", lang), cls="mt-4 max-w-4xl"),
            cls="border-t border-line",
        ),
        *[Section_(
            Div(
                Span(num, cls="font-mono text-[11px] tracking-widest uppercase text-ink-dim"),
                Heading(2, t(title_key, lang), cls="mt-3 max-w-3xl"),
                P(t(body_key, lang), cls="mt-5 text-ink-muted text-lg max-w-3xl leading-relaxed"),
                cls="mb-8",
            ),
            cls="border-t border-line",
        ) for (num, title_key, body_key) in [
            ("01", "how_s1_title", "how_s1_body"),
            ("02", "how_s2_title", "how_s2_body"),
            ("03", "how_s3_title", "how_s3_body"),
            ("04", "how_s4_title", "how_s4_body"),
        ]],
        CTASection(lang=lang),
        current_path="/how-it-works",
        lang=lang,
    )


@rt("/pricing")
def pricing(req):
    lang = get_lang(req)
    tiers = [
        {
            "name": t("benefit_sellers_label", lang),
            "price": "1.5–3%",
            "sub": {"en": "fee per 30 days", "uz": "30 kunlik komissiya", "ru": "комиссия за 30 дней"}.get(lang, "fee per 30 days"),
            "blurb": {"en": "Based on invoice size, debtor credit quality, and payment terms. No setup fee, no monthly minimums.",
                      "uz": "Hisob-faktura hajmi, qarzdor kredit sifati va to'lov shartlariga asoslanadi. Boshlang'ich to'lov yo'q, oylik minimal yo'q.",
                      "ru": "На основе суммы счёта, кредитного качества дебитора и сроков оплаты. Без стартовых платежей, без ежемесячных минимумов."}.get(lang),
            "features": {
                "en": ["Advance rate up to 90%", "Funding in 1–3 business days", "No long-term contracts", "No hidden fees", "Dedicated account manager"],
                "uz": ["90% gacha avans stavkasi", "1–3 ish kunida moliyalashtirish", "Uzoq muddatli shartnomalar yo'q", "Yashirin to'lovlar yo'q", "Shaxsiy hisob menejeri"],
                "ru": ["Ставка аванса до 90%", "Финансирование за 1–3 рабочих дня", "Без долгосрочных контрактов", "Без скрытых комиссий", "Персональный менеджер"],
            }.get(lang, []),
            "cta": (t("cta_button", lang), "/contact"),
            "primary": False,
        },
        {
            "name": t("benefit_investors_label", lang),
            "price": "8–12%",
            "sub": {"en": "target annualised return", "uz": "maqsadli yillik daromad", "ru": "целевая годовая доходность"}.get(lang),
            "blurb": {"en": "Returns depend on invoice duration, risk grade, and fee structure. Transparent pricing on every listing.",
                      "uz": "Daromadlar hisob-faktura muddati, xavf darajasi va komissiya tuzilmasiga bog'liq. Har bir e'londa shaffof narxlash.",
                      "ru": "Доходность зависит от срока счёта, уровня риска и структуры комиссий. Прозрачное ценообразование в каждом листинге."}.get(lang),
            "features": {
                "en": ["Minimum $50 per invoice", "Risk grades A–D", "Auto-invest available", "Secondary market (coming soon)", "Real-time portfolio tracking"],
                "uz": ["Har bir hisob-faktura uchun minimal $50", "A–D xavf darajalari", "Avtoinvestitsiya mavjud", "Ikkilamchi bozor (tez kunda)", "Real vaqtda portfel kuzatuvi"],
                "ru": ["Минимум $50 за счёт", "Рейтинги риска A–D", "Автоинвестирование", "Вторичный рынок (скоро)", "Отслеживание портфеля в реальном времени"],
            }.get(lang, []),
            "cta": (t("hero_cta_invest", lang), "/app/marketplace"),
            "primary": True,
        },
        {
            "name": "Enterprise",
            "price": {"en": "Custom", "uz": "Maxsus", "ru": "Индивидуально"}.get(lang),
            "sub": {"en": "volume pricing", "uz": "hajmli narxlash", "ru": "объёмные цены"}.get(lang),
            "blurb": {"en": "For businesses with $80,000+ monthly invoice volume. Dedicated terms, API access, and priority verification.",
                      "uz": "Oylik $80,000+ hisob-faktura hajmiga ega korxonalar uchun. Maxsus shartlar, API kirish va ustuvor tekshirish.",
                      "ru": "Для бизнеса с ежемесячным объёмом счетов $80 000+. Индивидуальные условия, доступ к API и приоритетная верификация."}.get(lang),
            "features": {
                "en": ["Custom advance rates", "Same-day funding", "API integration", "Bulk invoice upload", "Priority support"],
                "uz": ["Maxsus avans stavkalari", "Bir kunlik moliyalashtirish", "API integratsiyasi", "Ommaviy hisob-faktura yuklash", "Ustuvor qo'llab-quvvatlash"],
                "ru": ["Индивидуальные ставки аванса", "Финансирование в тот же день", "Интеграция через API", "Массовая загрузка счетов", "Приоритетная поддержка"],
            }.get(lang, []),
            "cta": (t("nav_contact", lang), "/contact"),
            "primary": False,
        },
    ]
    return page(
        t("pricing_eyebrow", lang),
        Section_(
            Eyebrow(t("pricing_eyebrow", lang)),
            Heading(1, t("pricing_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("pricing_lede", lang), cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        Section_(
            Div(
                *[Article(
                    P(tier["name"], cls="text-[11px] font-mono tracking-widest uppercase text-ink-dim mb-3"),
                    Div(
                        Span(tier["price"], cls="text-4xl md:text-5xl font-medium tracking-tighter text-ink"),
                        Span(f" {tier['sub']}", cls="text-ink-muted text-sm ml-2"),
                        cls="mb-4",
                    ),
                    P(tier["blurb"], cls="text-ink-muted leading-relaxed mb-6"),
                    Ul(
                        *[Li(
                            Span(NotStr("&#10003; "), cls="text-accent mr-2"),
                            Span(f, cls="text-ink text-sm"),
                            cls="mb-2 flex items-baseline",
                        ) for f in tier["features"]],
                        cls="mb-8 space-y-1",
                    ),
                    Button_(tier["cta"][0], href=tier["cta"][1], primary=tier["primary"]),
                    cls=("p-8 rounded-2xl bg-bg-elevated h-full flex flex-col " +
                         ("border border-accent/60" if tier["primary"] else "border border-line")),
                ) for tier in tiers],
                cls="grid md:grid-cols-3 gap-4",
            ),
            cls="border-t border-line",
        ),
        CTASection(lang=lang),
        current_path="/pricing",
        lang=lang,
    )


@rt("/contact")
def contact(req):
    lang = get_lang(req)
    form = Form(
        Div(
            Label(t("contact_name", lang), cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Input(name="name", type="text", required=True,
                  cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-5",
        ),
        Div(
            Label(t("contact_email", lang), cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Input(name="email", type="email", required=True,
                  cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-5",
        ),
        Div(
            Label(t("contact_company", lang), cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Input(name="company", type="text",
                  cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-5",
        ),
        Div(
            Label(t("contact_message", lang), cls="block text-xs font-mono tracking-widest uppercase text-ink-dim mb-2"),
            Textarea(name="message", rows="5", required=True,
                     cls="w-full px-4 py-3 rounded-xl bg-bg-elevated border border-line text-ink focus:border-accent focus:outline-none"),
            cls="mb-8",
        ),
        Button(NotStr(t("contact_submit", lang) + " &rarr;"), type="submit",
               cls="inline-flex items-center gap-2 px-5 py-3 rounded-full text-sm font-medium bg-accent text-bg hover:bg-ink transition-all"),
        method="post", action="/contact",
    )
    return page(
        t("contact_eyebrow", lang),
        Section_(
            Eyebrow(t("contact_eyebrow", lang)),
            Heading(1, t("contact_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("contact_lede", lang), cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            Div(form, cls="mt-12 max-w-xl"),
            cls="border-t border-line",
        ),
        current_path="/contact",
        lang=lang,
    )


@rt("/contact", methods=["POST"])
def contact_post(req, name: str = "", email: str = "", company: str = "", message: str = ""):
    lang = get_lang(req)
    import logging
    logging.getLogger(__name__).info("contact form: %s (%s) %s chars", name, email, len(message or ""))
    return page(
        t("contact_thanks_h1", lang),
        Section_(
            Eyebrow(t("contact_eyebrow", lang)),
            Heading(1, t("contact_thanks_h1", lang), cls="mt-4 max-w-4xl"),
            P(t("contact_thanks_body", lang), cls="mt-6 text-ink-muted text-lg max-w-3xl leading-relaxed"),
            cls="border-t border-line",
        ),
        current_path="/contact",
        lang=lang,
    )
