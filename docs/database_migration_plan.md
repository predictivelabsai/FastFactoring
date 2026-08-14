# Production Database Migration Plan

## Scope

Move the existing synthetic Factorio dataset from the legacy `DB_URL` instance to the new `DATABASE_URL_PROD` PostgreSQL instance. Only the isolated `factorio` schema is transferred; other databases and schemas are untouched.

Read-only inventory on 14 August 2026 found 33 source tables and 791 rows. The target was reachable and had no `factorio` schema. The source contains six runtime-created tables not represented in the base schema, so migration uses a complete schema-scoped PostgreSQL archive.

## Preflight

1. Stop writes or place Factorio in maintenance mode.
2. Run `.venv/bin/python -m scripts.migrate_database` and retain the source/target inventory.
3. Require the target `factorio` schema to be absent. The migration refuses a non-empty or pre-existing target.
4. Take a provider snapshot of both PostgreSQL instances and record the deployed commit.

## Migration

Run:

```bash
.venv/bin/python -m scripts.migrate_database --apply --confirm-empty-target
```

The command creates a temporary custom-format `pg_dump` of only `factorio`, restores it in a single target transaction without owners or grants, applies current additive schema definitions, demotes legacy admin identities, and constrains application roles to `investor`, `payer`, `supplier`, or `admin`. Temporary archives are deleted automatically.

## Verification and Cutover

The command compares every source/target table row count. Afterward, run migrations again, start one application instance against `DATABASE_URL_PROD`, and smoke-test landing, login, all four role surfaces, PDFs, admin language/currency settings, and audit writes. Then update the production runtime variable, deploy, and monitor database errors and authentication for at least 30 minutes.

## Rollback

Before accepting new production writes, rollback is configuration-only: point the application back to the legacy URL and redeploy. If writes occur on the new target, stop both instances and reconcile deltas before reverting. Do not drop either schema until the cutover has been stable and independently backed up.
