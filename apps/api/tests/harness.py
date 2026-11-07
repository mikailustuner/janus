"""Reusable privacy test harness (privacy design §7).

- `stub_medical_router()`: medical routes that misbehave on purpose (log values, raise with
  values in the message, try to write through a read-only transaction).
- `capture_logs()`: captures every log record and anything printed to stdout/stderr.
- `db_snapshot()` / `tmp_snapshot()` and `assert_stateless()`: later specs call
  `assert_stateless` for their own medical endpoints.
"""

from __future__ import annotations

import contextlib
import io
import logging
import os
import tempfile
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Annotated, Any

import psycopg
from fastapi import Depends
from psycopg import sql
from pydantic import BaseModel

from janus.db.pool import read_only_connection
from janus.http_policy.routes import medical_router
from janus.observability.logging import configure_logging

STUB_TABLE = "privacy_stub"
_stub_log = logging.getLogger("janus.test_stub")
_lib_log = logging.getLogger("httpx2")


class EchoIn(BaseModel):
    values: list[str]
    fail: bool = False


def stub_medical_router(with_db: bool = False) -> Any:
    router = medical_router()

    @router.get("/test/resolve/{code}")
    def resolve(code: str, q: str = "", mode: str = "ok") -> dict[str, object]:
        _stub_log.warning("resolving %s %s", code, q)  # log-guard: ignore (test plants a leak)
        url = "https://api.fda.gov/drug/ndc.json?search=%s"
        _lib_log.info("HTTP Request: GET " + url, code)  # log-guard: ignore
        if mode == "raise":
            raise RuntimeError(f"failed for {code} {q}")
        return {"n": len(code)}

    @router.post("/test/echo")
    def echo(body: EchoIn) -> dict[str, int]:
        _stub_log.error("echo %s", body.values)  # log-guard: ignore (test plants a leak)
        if body.fail:
            raise ValueError(", ".join(body.values))
        return {"n": len(body.values)}

    if with_db:

        @router.get("/test/db/{code}")
        def db_route(
            code: str, conn: Annotated[psycopg.Connection, Depends(read_only_connection)]
        ) -> dict[str, object]:
            conn.execute("SELECT 1")
            try:
                with conn.transaction():
                    conn.execute(
                        sql.SQL("INSERT INTO {} (v) VALUES (%s)").format(
                            sql.Identifier(STUB_TABLE)
                        ),
                        (code,),
                    )
            except psycopg.errors.ReadOnlySqlTransaction:
                return {"write_blocked": True}
            return {"write_blocked": False}

    return router


@contextlib.contextmanager
def capture_logs() -> Generator[io.StringIO]:
    buffer = io.StringIO()
    configure_logging(buffer)
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        yield buffer
    configure_logging()


def db_snapshot(conn: psycopg.Connection) -> dict[str, tuple[int, str | None]]:
    """Row count and an md5 of the sorted rows of every user table."""
    tables = conn.execute(
        "SELECT schemaname, tablename FROM pg_tables "
        "WHERE schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY 1, 2"
    ).fetchall()
    snap: dict[str, tuple[int, str | None]] = {}
    for schema, table in tables:
        query = sql.SQL(
            "SELECT count(*), md5(string_agg(t::text, '|' ORDER BY t::text)) FROM {}.{} t"
        ).format(sql.Identifier(schema), sql.Identifier(table))
        row = conn.execute(query).fetchone()
        assert row is not None
        snap[f"{schema}.{table}"] = (int(row[0]), row[1])
    return snap


def tmp_snapshot(root: Path) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            p = Path(dirpath) / name
            st = p.stat()
            out.append((str(p.relative_to(root)), st.st_size, st.st_mtime_ns))
    return sorted(out)


@contextlib.contextmanager
def isolated_tempdir() -> Generator[Path]:
    """Point `tempfile` at a fresh empty directory for the duration."""
    old = tempfile.tempdir
    with tempfile.TemporaryDirectory() as d:
        tempfile.tempdir = d
        try:
            yield Path(d)
        finally:
            tempfile.tempdir = old


def assert_stateless(conn: psycopg.Connection, tmp_root: Path, call: Callable[[], Any]) -> Any:
    """Run `call` (one request) and assert the database and temp directory are unchanged."""
    before_db, before_tmp = db_snapshot(conn), tmp_snapshot(tmp_root)
    result = call()
    assert db_snapshot(conn) == before_db, "a medical request changed the database"
    assert tmp_snapshot(tmp_root) == before_tmp, "a medical request wrote a temporary file"
    return result
