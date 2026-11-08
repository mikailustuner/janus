"""Example tests for the donations migration and database settings (design §7; tasks 7.1-7.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg
import pytest
from alembic import command

from tests.conftest import alembic_config

REPO = Path(__file__).resolve().parents[3]

VALID: dict[str, Any] = {
    "report_week": "2026-11-02",
    "age_band": 65,
    "sex": "female",
    "region": "TR",
    "ingredients": ["Q18216", "Q421094"],
    "event": "cough",
    "direction": "adverse",
    "consent_version": "2026-11-v1",
    "deletion_token_hash": b"\x01" * 32,
}


def _schema(conn: psycopg.Connection) -> dict[str, list[tuple[Any, ...]]]:
    columns = conn.execute(
        "SELECT column_name, data_type, is_nullable, column_default "
        "FROM information_schema.columns WHERE table_name = 'contributions' ORDER BY 1"
    ).fetchall()
    constraints = conn.execute(
        "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = 'contributions'::regclass ORDER BY 1"
    ).fetchall()
    indexes = conn.execute(
        "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'contributions' ORDER BY 1"
    ).fetchall()
    return {"columns": columns, "constraints": constraints, "indexes": indexes}


def _table_exists(conn: psycopg.Connection) -> bool:
    row = conn.execute("SELECT to_regclass('public.contributions') IS NOT NULL").fetchone()
    return bool(row and row[0])


@pytest.mark.db
def test_migration_is_reversible(db_url: str, db_conn: psycopg.Connection) -> None:
    """Task 7.1. Validates Req 3.5."""
    cfg = alembic_config(db_url)
    db_conn.execute("TRUNCATE contributions")
    before = _schema(db_conn)
    command.downgrade(cfg, "base")
    assert not _table_exists(db_conn)
    command.upgrade(cfg, "head")
    assert _schema(db_conn) == before
    assert {c[0] for c in before["columns"]} == {
        "id",
        "report_week",
        "age_band",
        "sex",
        "region",
        "ingredients",
        "event",
        "direction",
        "consent_version",
        "deletion_token_hash",
    }


def _insert(conn: psycopg.Connection, row: dict[str, Any]) -> None:
    cols = list(row)
    placeholders = ", ".join(["%s"] * len(cols))
    query = f"INSERT INTO contributions ({', '.join(cols)}) VALUES ({placeholders})"  # noqa: S608 (fixed column names)
    with conn.transaction():
        conn.execute(query.encode(), list(row.values()))  # pyright: ignore[reportArgumentType]


BAD_VALUES: list[tuple[str, Any]] = [
    ("report_week", "2026-11-03"),  # a Tuesday
    ("age_band", 15),  # minors are not accepted
    ("age_band", 0),
    ("age_band", 22),
    ("age_band", 95),
    ("sex", "other"),
    ("region", "DE"),
    ("region", "tr"),
    ("ingredients", []),
    ("ingredients", ["aspirin"]),
    ("ingredients", ["Q0"]),
    ("ingredients", [f"Q{i}" for i in range(1, 22)]),
    ("ingredients", ["Q1", None]),
    ("event", "Free text, with spaces"),
    ("event", ""),
    ("direction", "neutral"),
    ("consent_version", "V1 accepted"),
    ("deletion_token_hash", b"\x01" * 31),
]


@pytest.mark.db
@pytest.mark.parametrize(("column", "value"), BAD_VALUES)
def test_database_rejects_out_of_domain_values(
    db_conn: psycopg.Connection, column: str, value: Any
) -> None:
    """Task 7.2: the CHECKs hold without the API. Validates Req 3.2."""
    db_conn.execute("TRUNCATE contributions")
    row = {**VALID, column: value}
    with pytest.raises((psycopg.errors.CheckViolation, psycopg.errors.NotNullViolation)):
        _insert(db_conn, row)
    _insert(db_conn, VALID)  # the valid row itself is accepted
    db_conn.execute("TRUNCATE contributions")


def test_compose_postgres_has_terse_logging() -> None:
    """Task 7.3 (configuration). Validates Req 2.3."""
    text = (REPO / "docker-compose.yml").read_text(encoding="utf-8")
    for flag in (
        "log_error_verbosity=terse",
        "log_min_error_statement=panic",
        "log_statement=none",
        "log_min_duration_statement=-1",
    ):
        assert flag in text


@pytest.mark.db
def test_database_logging_is_terse(db_conn: psycopg.Connection) -> None:
    """Task 7.3 (live). Validates Req 2.3. CI applies the same settings to its service."""
    settings = {
        name: db_conn.execute(f"SHOW {name}").fetchone()  # pyright: ignore[reportArgumentType]
        for name in ("log_error_verbosity", "log_min_error_statement", "log_statement")
    }
    assert settings["log_error_verbosity"] == ("terse",)
    assert settings["log_min_error_statement"] == ("panic",)
    assert settings["log_statement"] == ("none",)


@pytest.mark.db
def test_0007_accepts_janus_keys_and_the_downgrade_removes_them(
    db_url: str, db_conn: psycopg.Connection
) -> None:
    """collective-memory DP17: donations accept `J<n>`; the downgrade restores the old check."""
    cfg = alembic_config(db_url)
    db_conn.execute("TRUNCATE contributions")
    n = [0]

    def row(ingredients: list[str]) -> dict[str, Any]:
        n[0] += 1
        return {
            **VALID,
            "ingredients": ingredients,
            "deletion_token_hash": n[0].to_bytes(32, "big"),
        }

    _insert(db_conn, row(["Q18216", "J1"]))
    _insert(db_conn, row(["J123456"]))
    for bad in (["J0"], ["J1234567"], ["j1"], ["J"], ["Q1", "X2"], ["Q0"], ["J01"]):
        with pytest.raises(psycopg.errors.CheckViolation):
            _insert(db_conn, row(bad))
    _insert(db_conn, row(["Q18216"]))
    command.downgrade(cfg, "0006")
    try:
        left = db_conn.execute("SELECT count(*) FROM contributions").fetchone()
        assert left is not None and left[0] == 1  # only the donation without a Janus key remains
        with pytest.raises(psycopg.errors.CheckViolation):
            _insert(db_conn, row(["J1"]))
    finally:
        command.upgrade(cfg, "head")
    _insert(db_conn, row(["J1"]))
    db_conn.execute("TRUNCATE contributions")
