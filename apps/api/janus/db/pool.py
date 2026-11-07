"""PostgreSQL access (privacy design §4.3, DP5).

Medical routes get the database only through `read_only_tx()`, so PostgreSQL rejects any
write. `write_tx()` is used only by `janus/contributions/repository.py` and the resolution
loader `janus/resolution/load.py` (enforced by a test).
All SQL is parameterised.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager

import psycopg
from fastapi import Request
from psycopg_pool import ConnectionPool


class Database:
    def __init__(self, url: str, *, max_size: int = 5) -> None:
        self.pool = ConnectionPool(
            url,
            min_size=1,
            max_size=max_size,
            open=False,
            kwargs={"autocommit": True},
        )

    def open(self) -> None:
        self.pool.open(wait=True, timeout=10)

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def read_only_tx(self) -> Generator[psycopg.Connection]:
        with self.pool.connection() as conn, conn.transaction():
            # One snapshot per request: a dataset switch by the resolution loader during a
            # request is not seen half-way (drug-resolution design §4.8).
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            yield conn

    @contextmanager
    def write_tx(self) -> Generator[psycopg.Connection]:
        with self.pool.connection() as conn, conn.transaction():
            yield conn


class DatabaseUnavailableError(RuntimeError):
    pass


def get_database(request: Request) -> Database:
    db = getattr(request.app.state, "database", None)
    if not isinstance(db, Database):
        raise DatabaseUnavailableError("database not configured")
    return db


def read_only_connection(request: Request) -> Iterator[psycopg.Connection]:
    """FastAPI dependency for medical routes: a connection in a read-only transaction."""
    with get_database(request).read_only_tx() as conn:
        yield conn
