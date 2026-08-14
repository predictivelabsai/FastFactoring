#!/usr/bin/env python3
"""Plan, clone, and verify the Factorio schema into DATABASE_URL_PROD.

The source is DATABASE_URL_SOURCE/DB_URL. For this repository's transitional
local file, ``DB_URL=#postgresql://...`` is also understood as a disabled source
credential. The default command is read-only:

    .venv/bin/python -m scripts.migrate_database

Applying requires an explicit empty-target confirmation:

    .venv/bin/python -m scripts.migrate_database --apply --confirm-empty-target
"""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

import psycopg
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
SCHEMA = "factorio"
ADMIN_EMAIL = "kaljuvee@gmail.com"


def _urls() -> tuple[str, str]:
    values = dotenv_values(ENV_FILE)
    source = os.getenv("DATABASE_URL_SOURCE") or os.getenv("DB_URL") or values.get("DATABASE_URL_SOURCE") or values.get("DB_URL") or ""
    target = os.getenv("DATABASE_URL_PROD") or values.get("DATABASE_URL_PROD") or ""
    source = str(source).strip().lstrip("#")
    if not source and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("DB_URL="):
                source = line.split("=", 1)[1].strip().lstrip("#")
                break
    return source, str(target).strip()


@dataclass(frozen=True)
class Inventory:
    host: str
    database: str
    schema_exists: bool
    rows: dict[str, int]


def _label(url: str) -> tuple[str, str]:
    parsed = urlsplit(url)
    return parsed.hostname or "", (parsed.path or "").lstrip("/")


def inventory(url: str) -> Inventory:
    host, database = _label(url)
    with psycopg.connect(url, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name=%s)",
                (SCHEMA,),
            )
            exists = bool(cursor.fetchone()[0])
            rows: dict[str, int] = {}
            if exists:
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema=%s AND table_type='BASE TABLE' ORDER BY table_name",
                    (SCHEMA,),
                )
                for (table,) in cursor.fetchall():
                    cursor.execute(f'SELECT count(*) FROM {SCHEMA}."{table}"')
                    rows[table] = int(cursor.fetchone()[0])
    return Inventory(host, database, exists, rows)


def _pg_args(url: str) -> tuple[list[str], dict[str, str]]:
    parsed = urlsplit(url)
    args = ["--host", parsed.hostname or "", "--port", str(parsed.port or 5432),
            "--username", unquote(parsed.username or ""),
            "--dbname", (parsed.path or "").lstrip("/")]
    env = os.environ.copy()
    env["PGPASSWORD"] = unquote(parsed.password or "")
    query = dict(item.split("=", 1) for item in parsed.query.split("&") if "=" in item)
    if query.get("sslmode"):
        env["PGSSLMODE"] = query["sslmode"]
    return args, env


def clone(source: str, target: str) -> None:
    source_inventory = inventory(source)
    target_inventory = inventory(target)
    if source == target:
        raise RuntimeError("source and target resolve to the same URL")
    if not source_inventory.schema_exists or not source_inventory.rows:
        raise RuntimeError("source factorio schema is missing or empty")
    if target_inventory.schema_exists:
        raise RuntimeError("target factorio schema already exists; refusing to overwrite it")

    with tempfile.TemporaryDirectory(prefix="fastfactoring-migration-") as directory:
        archive = Path(directory) / "factorio.dump"
        source_args, source_env = _pg_args(source)
        subprocess.run(
            ["pg_dump", *source_args, "--format=custom", f"--schema={SCHEMA}",
             "--no-owner", "--no-privileges", f"--file={archive}"],
            check=True, env=source_env,
        )
        target_args, target_env = _pg_args(target)
        subprocess.run(
            ["pg_restore", *target_args, "--no-owner", "--no-privileges",
             "--exit-on-error", "--single-transaction", str(archive)],
            check=True, env=target_env,
        )

    # Apply additive current definitions and enforce the new identity boundary.
    with psycopg.connect(target) as connection:
        connection.execute((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
        connection.execute(
            "UPDATE factorio.app_users SET role='investor',subrole='ops' "
            "WHERE role='admin' AND lower(email)<>%s",
            (ADMIN_EMAIL,),
        )
        connection.execute("ALTER TABLE factorio.app_users DROP CONSTRAINT IF EXISTS app_users_role_check")
        connection.execute(
            "ALTER TABLE factorio.app_users ADD CONSTRAINT app_users_role_check "
            "CHECK (role IN ('investor','payer','supplier','admin'))"
        )
        connection.commit()

    verify(source, target)


def verify(source: str, target: str) -> None:
    before, after = inventory(source), inventory(target)
    missing = sorted(set(before.rows) - set(after.rows))
    mismatched = {
        table: (before.rows[table], after.rows.get(table))
        for table in before.rows if before.rows[table] != after.rows.get(table)
    }
    if missing or mismatched:
        raise RuntimeError(f"verification failed: missing={missing}, row_counts={mismatched}")
    print(f"verified {len(before.rows)} tables and {sum(before.rows.values())} rows")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-empty-target", action="store_true")
    args = parser.parse_args()
    source, target = _urls()
    if not source or not target:
        raise SystemExit("DATABASE_URL_SOURCE/DB_URL and DATABASE_URL_PROD are required")
    for name, value in (("source", source), ("target", target)):
        current = inventory(value)
        print(f"{name}: host={current.host} db={current.database} "
              f"schema={current.schema_exists} tables={len(current.rows)} rows={sum(current.rows.values())}")
    if args.apply:
        if not args.confirm_empty_target:
            raise SystemExit("--apply also requires --confirm-empty-target")
        clone(source, target)
    else:
        print("read-only plan complete; rerun with --apply --confirm-empty-target after approval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
