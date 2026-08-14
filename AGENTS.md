# Repository Guidelines

## Project Structure & Module Organization

`main.py` starts the server; `app.py` creates the shared FastHTML application and imports route modules for registration. Marketing pages and reusable components live in `landing/`, while authenticated product screens live in `app_routes/`. Import every new route module at the bottom of `app.py` so its decorators register.

Database schema, connections, and migrations are under `db/`; fully qualify PostgreSQL objects as `factorio.*`. Put deterministic demo-data generators in `synthetic/`, shared configuration and helpers in `utils/`, documentation generators in `scripts/`, generated documentation in `docs/`, screenshots in `screenshots/`, and served assets in `static/`.

Framework-agnostic GTM and outreach skills live in `agents/skills/`. Keep their `SKILL.md`, references, and deterministic scripts portable; vendor-specific discovery manifests belong outside this repository.

## Build, Test, and Development Commands

Create and activate a virtual environment before running:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m db.migrate
python -m synthetic.generate --seed 42 --limit 5
PORT=5055 python main.py
```

Use `python -m synthetic.generate --seed 42 --fresh` to replace demo data; it is destructive. `python -m db.migrate --drop` is also destructive and should be used only intentionally. `docker compose up --build` runs the complete local container setup. Configure `DB_URL` locally or `DATABASE_URL_PROD` for the production migration tool.

## Coding Style & Naming Conventions

Follow existing Python style: four-space indentation, useful type hints, module docstrings, `snake_case` functions/modules, and `UPPER_SNAKE_CASE` constants. Keep routes thin and extract shared behavior into `utils/`, components, or `app_routes/_shared.py`. Read environment values through `utils.config.settings()`.

Use `t(key, lang)` for keyed copy, run the i18n inventory after visible-copy changes, format monetary UI through `utils.money`, and wrap intentional raw HTML/entities with `NotStr()`. Russian and Uzbek catalogues remain in source for compatibility but are disabled by default.

## Testing Guidelines

Run `python -m unittest discover -s tests -v` and `python -m scripts.update_i18n`. Then migrate, seed a small dataset, and smoke-test affected language and role variants. For data-layer changes, verify both a clean migration and an idempotent rerun. Name tests `tests/test_<area>.py` and functions `test_<behavior>`. Regenerate screenshots or documents with their matching scripts when generated assets change.

## Commit & Pull Request Guidelines

Recent commits use concise, imperative, scope-led subjects, such as `mobile: left nav becomes a slide-in drawer` and `docs(ru): user guide parity`. Keep each commit focused. PRs should explain behavior, migration/configuration impact, and verification; link related issues and include before/after screenshots for visible UI changes. Never commit `.env`, credentials, or production data.

## Release Versioning

`VERSION` is the release source of truth. For release-significant commits, use `skills/factorio-version-release/SKILL.md` to choose the Semantic Versioning bump and prepend the matching entry to `docs/change_log.md` in the same commit. Do not bump for intermediate commits, generated screenshots, formatting, tests, or archive-only changes unless they are intentionally released.
