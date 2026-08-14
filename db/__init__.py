from __future__ import annotations

import logging
from contextlib import contextmanager
from functools import lru_cache

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from utils.config import settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def pool() -> ConnectionPool:
    url = settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL_PROD or DB_URL is not set")
    p = ConnectionPool(conninfo=url, min_size=1, max_size=8, open=False)
    p.open()
    return p


@contextmanager
def connect():
    with pool().connection() as conn:
        yield conn


def fetch_all(sql: str, params: tuple | dict | None = None) -> list[dict]:
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params or ())
            return list(cur.fetchall())


def fetch_one(sql: str, params: tuple | dict | None = None) -> dict | None:
    with connect() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()


def execute(sql: str, params: tuple | dict | None = None) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
        conn.commit()
