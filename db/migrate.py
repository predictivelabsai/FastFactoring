"""Idempotent database migration runner.

Usage:
    python -m db.migrate            # create schema + tables
    python -m db.migrate --drop     # DESTRUCTIVE: drop and recreate
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import psycopg
from utils.config import settings

SCHEMA_DIR = pathlib.Path(__file__).parent
SCHEMA_FILES = ["schema.sql"]


def _apply(sql: str) -> None:
    with psycopg.connect(settings().database_url, autocommit=True) as conn:
        conn.execute(sql)


def migrate(drop: bool = False) -> None:
    if drop:
        print("[migrate] dropping schema factorio ...")
        _apply("DROP SCHEMA IF EXISTS factorio CASCADE;")

    for fname in SCHEMA_FILES:
        path = SCHEMA_DIR / fname
        sql = path.read_text()
        print(f"[migrate] applying {fname} ...")
        _apply(sql)

    print("[migrate] done")


def main():
    parser = argparse.ArgumentParser(description="Run FastFactoring DB migrations")
    parser.add_argument("--drop", action="store_true", help="Drop and recreate schema (DESTRUCTIVE)")
    args = parser.parse_args()
    migrate(drop=args.drop)


if __name__ == "__main__":
    main()
