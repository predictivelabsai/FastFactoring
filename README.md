# FastFactoring

**FastFactoring** is an open-source invoice-financing platform built with FastHTML,
HTMX, and PostgreSQL. It gives product teams an auditable foundation for supplier
onboarding, invoice verification, funding, servicing, collections, settlement, and
role-specific operations without a proprietary JavaScript application stack.

**Factorio** is the standalone reference product shipped from this repository. The
live demo at [factorio.co.uk](https://factorio.co.uk) remains Factorio-branded and
uses the same supplier, payer, investor, and administrator sign-in flow.

One FastHTML process serves both a marketing landing site and an HTMX-driven product
app (dashboard, marketplace, portfolio, statement, auto-invest), backed by PostgreSQL.
The UI supports the 12-language FastSME locale cohort. Administrators choose which
checked-in languages are available; retained Russian and Uzbek catalogues are disabled
by default.

The investor experience includes a reporting cockpit, a filterable account statement
with CSV export, and configurable automated investment rules.

---

## Features

**Public sites** — a FastSME-style open-source FastFactoring page plus the Factorio
reference-product landing, seller, investor, workflow, pricing, and contact pages.

**Investor product app** (`/app/*`):

| Route | What it does |
|-------|--------------|
| `/app` | Personalized dashboard — per-investor KPIs (portfolio value, net annual return, earned-to-date, next settlement), recent-activity feed, demoted platform stats |
| `/app/marketplace` | Browse fundable invoices with filters (sector / risk grade / max term / min return); detail page with debtor-company profile |
| `/app/portfolio` | Reporting cockpit — net-annual-return & account-value panels, an investments aging table (by days-to/past-due), a debtor payment-habits table, and an enriched positions table |
| `/app/statement` | Unified, filterable transaction ledger (investments out, settlements in) + CSV export |
| `/app/auto-invest` | Per-investor automated bidding rules (min risk grade, max amount/invoice, preferred sectors, on/off) |

**Authentication and RBAC** — session-based local and Google sign-in map users to exactly
four roles: investor, supplier, payer, or admin. `kaljuvee@gmail.com` is the sole admin;
the three non-admin roles retain one-click synthetic demo sessions.

**i18n** — English is the source/fallback and checked-in JSON catalogues cover Estonian,
German, French, Swedish, Latvian, Norwegian, Danish, Polish, Dutch, Finnish, and
Lithuanian. Browser negotiation and the language selector persist the choice.

---

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env                       # set DB_URL or DATABASE_URL_PROD
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
| `DATABASE_URL_PROD` | Preferred production PostgreSQL connection | — |
| `DB_URL` | Local/fallback PostgreSQL connection | — |
| `APP_SECRET` | session/signing secret | `change-me` |
| `ADMIN_PASSWORD` | Temporary local password for the sole admin | disabled |
| `GOOGLE_*` | Google OpenID Connect client, callback, and optional allowlists | disabled |
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
                  └─ import landing.routes       # FastFactoring + Factorio pages
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
| `utils/` | Configuration, authentication helpers, money formatting, and i18n runtime/catalogues |
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
There are no standalone JavaScript/TypeScript source files; roughly 106 lines of inline
progressive enhancement support the cockpit drawer, streaming chat, and PDF pane. The
repository application source is therefore well over 99% Python/FastHTML by line count.

### Conventions

- Schemas always fully qualified (`factorio.*`).
- All money flows through one formatter; admins select USD, EUR, or GBP globally.
- Run `python -m scripts.update_i18n` after UI-copy changes; every enabled locale must
  exactly cover the English source inventory.
- New routes must be imported at the bottom of `app.py` for side-effect registration.
- Nullable SQL filter params are cast (e.g. `%(x)s::date IS NULL OR …`) so Postgres can
  infer their type — an uncast `$n IS NULL` raises `AmbiguousParameter`.

See [CLAUDE.md](CLAUDE.md) for the full conventions reference.

---

## Reference Deployment (Coolify CI/CD)

The Factorio reference product is deployed on a self-hosted [Coolify](https://coolify.io)
instance from this public GitHub repository. Production runs at
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

1. **New Resource → Public Repository** → `https://github.com/predictivelabsai/FastFactoring`,
   branch `main`, Build Pack **Dockerfile**, Ports Exposes **5055**.
2. **Environment Variables**: `DB_URL`, `APP_SECRET`, `APP_ENV=production`, `PORT=5055`.
3. **Auto-deploy webhook** — add the repo webhook so pushes trigger a deploy:

   ```bash
   # Coolify → app → Webhooks gives the GitHub URL + secret
   gh api repos/predictivelabsai/FastFactoring/hooks -X POST --input - <<'JSON'
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
