# Factorio

**Invoice financing (factoring) platform.** Factorio connects businesses that need
cash flow now with investors seeking short-term, asset-backed returns: sellers upload
unpaid invoices, investors fund them on a marketplace, and returns settle when the
invoice is paid.

One FastHTML process serves both a marketing landing site and an HTMX-driven product
app (dashboard, marketplace, portfolio, statement, auto-invest), backed by PostgreSQL.
The entire UI is trilingual (English / Uzbek / Russian).

The investor experience is modelled on [investly.co](https://investly.co): a reporting
cockpit, a filterable account statement with CSV export, and an auto-invest (autobidder)
configuration.

---

## Features

**Marketing site** — landing, for-sellers, for-investors, how-it-works, pricing, contact.

**Investor product app** (`/app/*`):

| Route | What it does |
|-------|--------------|
| `/app` | Personalized dashboard — per-investor KPIs (portfolio value, net annual return, earned-to-date, next settlement), recent-activity feed, demoted platform stats |
| `/app/marketplace` | Browse fundable invoices with filters (sector / risk grade / max term / min return); detail page with debtor-company profile |
| `/app/portfolio` | Reporting cockpit — net-annual-return & account-value panels, an investments aging table (by days-to/past-due), a debtor payment-habits table, and an enriched positions table |
| `/app/statement` | Unified, filterable transaction ledger (investments out, settlements in) + CSV export |
| `/app/auto-invest` | Per-investor automated bidding rules (min risk grade, max amount/invoice, preferred sectors, on/off) |

**Investor switcher** — the app uses a no-password, cookie-based investor switcher
(impersonate any seeded investor) for demo purposes; there is no auth layer.

**i18n** — every user-facing string is keyed in `utils/i18n.py` with `en` / `uz` / `ru`
translations; the language is held in a `lang` cookie and toggled via `/set-lang`.

---

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env                       # set DB_URL (PostgreSQL)
python -m db.migrate                       # create the `factorio` schema + tables
python -m synthetic.generate --seed 42     # seed deterministic demo data
#   --fresh   truncate then re-seed
#   --limit N small subset for fast iteration

PORT=5055 python main.py                   # http://localhost:5055
```

`db.migrate --drop` drops and recreates the schema (**destructive**).

### Configuration

All config is read through `utils/config.py` `settings()` (pydantic-settings, loads `.env`):

| Var | Meaning | Default |
|-----|---------|---------|
| `DB_URL` | PostgreSQL connection string | — (required) |
| `APP_SECRET` | session/signing secret | `change-me` |
| `APP_ENV` | `dev` / `production` | `dev` |
| `PORT` | HTTP port | `5055` |
| `XAI_API_KEY` | xAI API key for invoice extraction and assistants | — |
| `XAI_MODEL` | Grok model used for extraction/chat | `grok-4.3` |
| `XAI_BASE_URL` | xAI OpenAI-compatible API base URL | `https://api.x.ai/v1` |

---

## Architecture

### Request flow

`main.py` only calls `serve(port=settings().port)`. **All wiring lives in `app.py`**: it
builds the `fast_app(...)` instance, then imports each route module *for its side effect* —
the `@rt(...)` decorators register against the shared app at import time. **A new route
module does nothing until it is imported at the bottom of `app.py`.**

```
main.py ─► app.py ─► fast_app(...)              # the shared app + `rt` decorator
                  └─ import landing.routes       # marketing pages
                  └─ import app_routes.dashboard / marketplace / portfolio /
                            statement / autoinvest / _shared   # product app
```

### Layout

| Path | Purpose |
|------|---------|
| `app.py` / `main.py` | FastHTML app + entrypoint (all routes register here) |
| `landing/` | Marketing routes + shared UI primitives (`page()`, `Section_()`, `Hero()`, `Button_()`, …) |
| `app_routes/` | Product app routes; `_shared.py` holds `app_page()`, the investor switcher, the UZS formatter and aging-bucket helpers |
| `db/` | `schema.sql` (all tables in the **`factorio`** schema), `__init__.py` (psycopg pool: `fetch_all` / `fetch_one` / `execute`), `migrate.py` |
| `synthetic/` | Deterministic synthetic-data generator (`random.Random(seed)` + `Faker.seed`) |
| `utils/` | `config.py` (`settings()`) and `i18n.py` (`t()`, `get_lang()`, en/uz/ru) |
| `scripts/` | Screenshot / GIF / PDF media generation (Playwright) |

### Data model (`db/schema.sql`)

All tables are fully qualified under the **`factorio`** schema (never relying on
`search_path`):

```
users · companies · invoices · invoice_funding · investments · invoice_updates
notifications · settlements · dividends · payments · secondary_market · auto_invest · faq
```

The shared PostgreSQL host runs **one schema per app**; Factorio owns the `factorio`
schema. Adapted from the litfunder-backend model (LegalCase → invoices,
CaseFunding → invoice_funding, CaseInvestment → investments).

### Front-end

Tailwind via CDN + Inter / JetBrains Mono fonts. Parchment background (`#F7F6F1`),
deep-green accent (`#1F5D43`). Pure server-rendered FastHTML + HTMX — no React/Vue/Svelte.
HTML entities are wrapped in `NotStr()` (FastHTML escapes strings by default).

### Conventions

- Schemas always fully qualified (`factorio.*`).
- All money flows through one formatter (`fmt_uzs()` in `app_routes/_shared.py`); the app
  is UZS in practice (`marketplace.py` keeps a multi-symbol map for invoice currencies).
- User-facing copy goes through `t(key, lang)` with all three languages defined — never
  hardcode display strings.
- New routes must be imported at the bottom of `app.py` for side-effect registration.
- Nullable SQL filter params are cast (e.g. `%(x)s::date IS NULL OR …`) so Postgres can
  infer their type — an uncast `$n IS NULL` raises `AmbiguousParameter`.

See [CLAUDE.md](CLAUDE.md) for the full conventions reference.

---

## Deployment (Coolify CI/CD)

Factorio is deployed on a self-hosted [Coolify](https://coolify.io) instance as a
Dockerfile-based application sourced from the public GitHub repo. Production runs at
**[factorio.co.uk](https://factorio.co.uk)**.

### Manual invoice-extraction test

1. Open [Sign in](https://factorio.co.uk/login) and choose **Supplier**.
2. The default [Factorio AI](https://factorio.co.uk/app) chat asks for an invoice.
3. Click the paperclip and upload a synthetic PDF from `data/synthetic-invoices/`.
4. Check the inline offer: invoice value, percentage and amount paid today, term,
   and the smaller monthly financing-cost disclosure.
5. Accept the offer, then open [My applications](https://factorio.co.uk/app/supplier)
   and download the generated one-page synthetic financing contract.
6. Re-uploading the same sample should show a duplicate invoice-number error.

Bank-statement upload and Open Banking connection are optional follow-up actions
shown beneath the offer; neither is required to see indicative terms.

Digital PDFs use local text-to-Markdown extraction. To exercise the scanned fallback,
print a sample PDF to an image-only PDF (or upload a PNG/JPEG screenshot); only that
path invokes xAI image understanding.

**Pipeline:** push to `main` → GitHub webhook → Coolify pulls the commit, rebuilds the
Docker image, and redeploys. No manual step.

### Container

`Dockerfile` (python:3.12-slim) installs `requirements.txt`, then `docker-entrypoint.sh`
runs `python -m db.migrate` (idempotent) before `python main.py`. Set `SKIP_MIGRATE=1`
to skip the migration on boot. The app listens on `PORT` (5055).

```bash
docker compose up --build        # local bring-up
```

### Coolify setup (one-time)

1. **New Resource → Public Repository** → `https://github.com/predictivelabsai/factorio`,
   branch `main`, Build Pack **Dockerfile**, Ports Exposes **5055**.
2. **Environment Variables**: `DB_URL`, `APP_SECRET`, `APP_ENV=production`, `PORT=5055`.
3. **Auto-deploy webhook** — add the repo webhook so pushes trigger a deploy:

   ```bash
   # Coolify → app → Webhooks gives the GitHub URL + secret
   gh api repos/predictivelabsai/factorio/hooks -X POST --input - <<'JSON'
   {
     "name": "web", "active": true, "events": ["push"],
     "config": {
       "url": "https://<coolify-host>/webhooks/source/github/events/manual",
       "content_type": "json",
       "secret": "<coolify-webhook-secret>"
     }
   }
   JSON
   ```

4. **Deploy** once from the Coolify UI; subsequent pushes deploy automatically.

### Database

The migration / seed are run against the shared PostgreSQL host (they create and populate
the `factorio` schema). They are safe to run from any box that can reach `DB_URL`:

```bash
python -m db.migrate
python -m synthetic.generate --seed 42 --fresh
```

---

## Tech

FastHTML + HTMX (server-rendered, no JS framework) · PostgreSQL (psycopg 3) ·
Tailwind (CDN) · pydantic-settings · Faker · Docker / Coolify.
