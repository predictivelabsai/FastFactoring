# Repository Guidelines

## Project Structure & Module Organization

`main.py` starts the server; `app.py` creates the shared FastHTML application and imports route modules for registration. Marketing pages and reusable page components live in `landing/`, while authenticated product screens live in `app_routes/`. Database schema, connection helpers, and migrations are under `db/`; deterministic demo-data generators are in `synthetic/`. Put configuration and shared helpers in `utils/`. Documentation generators belong in `scripts/`, generated documentation in `docs/`, screenshots in `screenshots/`, and served assets in `static/`.

When adding a route module, import it at the bottom of `app.py`; otherwise its decorators will not register.

## Build, Run, and Development Commands

Create and activate a virtual environment before running:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m db.migrate
python -m synthetic.generate --seed 42
PORT=5055 python main.py
```

Use `python -m synthetic.generate --seed 42 --fresh` to rebuild demo data; it truncates seeded records. `python -m db.migrate --drop` is destructive and should be used only intentionally. `docker compose up --build` runs the complete local container setup.

## Coding Style & Naming Conventions

Follow existing Python style: four-space indentation, type hints where they clarify interfaces, `snake_case` for functions and modules, and `UPPER_CASE` for constants. Keep route handlers small and extract shared UI into component helpers. Fully qualify PostgreSQL objects as `factorio.*`. Read environment values through `utils.config.settings()`.

All visible copy must use `t(key, lang)` and provide English, Uzbek, and Russian entries in `utils/i18n.py`. Use `fmt_uzs()` for monetary UI and `NotStr()` for intentional raw HTML/entities.

## Testing Guidelines

No automated test suite or coverage threshold is currently committed. Before submitting, run the app, exercise affected routes, and verify database-backed flows against seeded data. For UI changes, check all three languages and relevant responsive layouts. Regenerate screenshots or documents with the matching script in `scripts/` when generated assets are affected.

## Commit & Pull Request Guidelines

Recent commits use concise, imperative, scope-led subjects, such as `mobile: left nav becomes a slide-in drawer` and `docs(ru): user guide parity`. Keep each commit focused. Pull requests should explain behavior changes, migration or configuration impact, and manual verification performed; link related issues and include before/after screenshots for visible UI changes. Never commit `.env`, credentials, or production data.
