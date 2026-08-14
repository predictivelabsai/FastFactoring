# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## What this is

FastFactoring is an open-source invoice-financing platform. Factorio is its hosted,
standalone reference implementation. One FastHTML process hosts the public pages and
HTMX-driven product app backed by PostgreSQL (`factorio` schema).

## Commands

All commands assume `source .venv/bin/activate` (or use `.venv/bin/python` directly).

```bash
# Setup
cp .env.example .env                             # fill DB_URL or DATABASE_URL_PROD
pip install -r requirements.txt
python -m db.migrate                             # idempotent; creates factorio schema + tables
python -m db.migrate --drop                      # DESTRUCTIVE — drops schema and recreates

# Seed synthetic data (deterministic for a given seed)
python -m synthetic.generate --seed 42           # full seed
python -m synthetic.generate --seed 42 --fresh   # truncate then re-seed
python -m synthetic.generate --limit 5           # small subset for fast iteration

# Run
PORT=5055 python main.py                         # :5055 is the default

# Docker
docker compose up --build                        # local bring-up
```

## Architecture

### Entrypoint & route registration

`main.py` only calls `serve(port=settings().port)`; all wiring is in `app.py`. `app.py` builds the `fast_app(...)` instance, then imports each route module **for its side effect** — the `@rt(...)` decorators register against the shared app at import time. A new route module does nothing until it is imported at the bottom of `app.py`.

### Routes (one FastHTML `app.py` mounts everything)

- `/` → FastFactoring on local/preview hosts and Factorio on `factorio.co.uk`; `/fastfactoring` always renders the open-source product page
- `/for-sellers` + `/for-investors` + `/how-it-works` + `/pricing` + `/contact` → Factorio reference-product pages in `landing/routes.py`
- `/app` → dashboard with platform stats. `app_routes/dashboard.py`
- `/app/marketplace` + `/app/marketplace/<funding_id>` → browse + detail for fundable invoices. `app_routes/marketplace.py`
- `/app/portfolio` → investor positions and returns table. `app_routes/portfolio.py`
- `/set-lang?lang=` → sets the `lang` cookie and redirects back (i18n switcher)

### Internationalisation

English is the source and fallback. Eleven checked-in JSON catalogues under `utils/locales/` provide the FastSME cohort: et, de, fr, sv, lv, no, da, pl, nl, fi and lt. Russian and Uzbek translations remain available but are disabled by default. Admins control enabled languages at `/app/admin/languages`.

- In a route: `lang = get_lang(req)` (session, cookie, then browser negotiation), then `t("some_key", lang)`.
- Pass `lang` through to `page(title, *content, current_path=..., lang=lang)` so the nav/footer render in the right language.
- Run `python -m scripts.update_i18n` after copy changes. Use `--translate` only as an explicit maintenance operation; production never calls a translator.

### Configuration

`utils/config.py` exposes cached `settings()`. Production prefers `DATABASE_URL_PROD`, falling back to `DB_URL`. Google OIDC uses `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI`. Always read config through `settings()`.

### Data model (`db/schema.sql`)

All tables live in `factorio.*`:
`users, companies, invoices, invoice_funding, investments, invoice_updates, notifications, settlements, dividends, payments, secondary_market, auto_invest, faq`.

Adapted from litfunder-backend: LegalCase → invoices, CaseFunding → invoice_funding, CaseInvestment → investments, etc.

### Front-end

- Tailwind CSS via CDN + Inter / JetBrains Mono fonts
- Design: parchment background (#F7F6F1), deep-green accent (#1F5D43)
- Component primitives in `landing/components.py`: `page()`, `Hero()`, `Section_()`, `Eyebrow()`, `Heading()`, `Button_()`, `Pill()`, `CTASection()`, etc. `page()` is the shell every full page returns (wraps content in nav + footer + Tailwind config).
- `static/site.css` — minimal custom CSS (hero grid, selection color)
- No React/Vue/Svelte — pure server-rendered FastHTML + HTMX
- `fasthtml-ctx.txt` (repo root) is a bundled FastHTML reference — consult it for framework API/idioms instead of guessing.

### Media / docs generation (`scripts/`)

`scripts/capture_screenshots.py` (Playwright) refreshes `screenshots/`, `scripts/make_gif.py` builds the reference-product GIF, and `scripts/make_pdf.py` builds the product-tour PDF. These drive a running server and are only needed when regenerating marketing/docs assets.

### Synthetic data (`synthetic/generate.py`)

- Deterministic given `--seed` (uses `random.Random(seed)` + `Faker.seed(seed)`)
- Seeds: 32 users (admin/seller/investor), 15 companies, 30 invoices with funding + investments, 6 FAQs
- Idempotent via `ON CONFLICT ... DO UPDATE`

## Conventions

- Schemas always fully qualified (`factorio.*`) — never rely on `search_path`
- HTML entities must use `NotStr()` wrapper (FastHTML escapes strings by default)
- Synthetic data is deterministic given `--seed`
- Stored synthetic amounts are UZS-scale; admins select USD, EUR, or GBP display currency. All monetary UI must use `utils.money.fmt_money()`.
- RBAC roles are exactly investor, supplier, payer and admin. Only `kaljuvee@gmail.com` may hold admin.
- When adding new routes, import them at the bottom of `app.py` for side-effect registration
