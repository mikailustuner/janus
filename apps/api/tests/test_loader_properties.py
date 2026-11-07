"""Loader tests (drug-resolution design §8: P23, P8 load part; tasks 10.1-10.3)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb
import psycopg
import pytest
from alembic import command
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test

from janus.db.pool import Database
from janus.resolution.load import (
    Artifact,
    LoadError,
    activate,
    current_dataset,
    load,
    read_artifact,
)
from janus.resolution.prepare import TITCK
from tests.conftest import DB_EXAMPLES, alembic_config
from tests.resolution_db import RES_TABLES, artifact, datasets_of_rows, dump, inputs, reset
from tests.resolution_strategies import barcode13, sources, titck_row, wikidata_row

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def database(db_url: str) -> Iterator[Database]:
    db = Database(db_url)
    db.open()
    yield db
    db.close()


class InjectedFailureError(RuntimeError):
    pass


def _tamper(a: Artifact) -> Artifact:
    rows = [dict(r) for r in a.rows] + [titck_row(barcode13(99), "EKSTRA", ["x"], None)]
    return Artifact(a.source_id, a.manifest, a.evidence, rows)


class LoadMachine(RuleBasedStateMachine):
    """Feature: drug-resolution, Property P23. Validates Req 9.1, 9.2.

    For any sequence of good loads, refused artifacts and failures injected before any table,
    the served dataset is either the previous one or the new one, complete, never a mix.
    """

    database: Database
    conn: psycopg.Connection

    def __init__(self) -> None:
        super().__init__()
        reset(self.conn)
        self.served: str | None = None
        self.complete: dict[str, dict[str, list[tuple[Any, ...]]]] = {}

    @rule(src=sources(), run=st.sampled_from(["a", "b", "c"]))
    def good_load(self, src: tuple[list[Any], list[Any], list[Any]], run: str) -> None:
        result = load(self.database, inputs(*src, run=run))
        self.served = result.dataset_version
        if result.dataset_version not in self.complete:
            self.complete[result.dataset_version] = dump(self.conn, result.dataset_version)

    @rule(src=sources())
    def refused_load(self, src: tuple[list[Any], list[Any], list[Any]]) -> None:
        inp = inputs(*src)
        bad = dict(inp.artifacts)
        bad[TITCK] = _tamper(bad[TITCK])
        with pytest.raises(LoadError):
            load(self.database, type(inp)(bad, inp.rules, inp.route_map, inp.synonyms, inp.code))

    @rule(src=sources(), table=st.sampled_from(RES_TABLES))
    def failing_load(self, src: tuple[list[Any], list[Any], list[Any]], table: str) -> None:
        def hook(name: str) -> None:
            if name == table:
                raise InjectedFailureError(name)

        try:
            load(self.database, inputs(*src, run="f"), hook=hook)
        except InjectedFailureError:
            pass

    @invariant()
    def one_complete_dataset_served(self) -> None:
        current = current_dataset(self.conn)
        assert current == self.served
        if current is None:
            for table, ids in datasets_of_rows(self.conn).items():
                assert not ids, table
            return
        assert dump(self.conn, current) == self.complete[current]
        kept = {r[0] for r in self.conn.execute("SELECT id FROM res_dataset").fetchall()}
        assert current in kept and len(kept) <= 2
        for table, ids in datasets_of_rows(self.conn).items():
            assert ids <= kept, table


def test_atomic_load(database: Database, db_conn: psycopg.Connection) -> None:
    LoadMachine.database = database
    LoadMachine.conn = db_conn
    run_state_machine_as_test(
        LoadMachine,
        settings=settings(max_examples=max(10, DB_EXAMPLES // 5), stateful_step_count=6),
    )


@settings(max_examples=max(10, DB_EXAMPLES // 5))
@given(src=sources())
def test_same_artifacts_same_dataset(
    database: Database, db_conn: psycopg.Connection, src: tuple[list[Any], list[Any], list[Any]]
) -> None:
    """Feature: drug-resolution, Property P8 (load part). Validates Req 9.4, 7.3.

    Loading the same artifacts gives the same dataset version and identical rows whatever the
    file row order; a reload under another run id with the same content is a no-op (the
    version depends on content, not run ids).
    """
    reset(db_conn)
    first = load(database, inputs(*src, run="x"))
    rows = dump(db_conn, first.dataset_version)
    assert not load(database, inputs(*src, run="y")).changed
    reset(db_conn)
    tr, us, wd = src
    again = load(database, inputs(list(reversed(tr)), list(reversed(us)), list(reversed(wd)), "x"))
    assert again.dataset_version == first.dataset_version
    assert dump(db_conn, again.dataset_version) == rows


def test_source_versions_and_activate(database: Database, db_conn: psycopg.Connection) -> None:
    """Task 10.3: source versions come from the manifest and evidence record; --activate."""
    reset(db_conn)
    wd = [wikidata_row("Q1", ["C08CA01"], {"en": "amlodipine"})]
    first = load(
        database, inputs([titck_row(barcode13(1), "A", ["amlodipine"], "C08CA01")], [], wd)
    )
    second = load(
        database, inputs([titck_row(barcode13(2), "B", ["amlodipine"], "C08CA01")], [], wd)
    )
    rows = db_conn.execute(
        "SELECT source_id, run_id, region, license, source_url FROM res_source_version "
        "WHERE dataset_id = %s ORDER BY 1",
        (second.dataset_version,),
    ).fetchall()
    assert rows[0] == (
        "openfda_ndc",
        "openfda_ndc-run-1",
        "US",
        "CC0 1.0 (public domain)",
        "https://example.org/openfda_ndc",
    )
    assert [r[0] for r in rows] == ["openfda_ndc", "titck", "wikidata"]
    activate(database, first.dataset_version)
    assert current_dataset(db_conn) == first.dataset_version
    with pytest.raises(LoadError):
        activate(database, "0" * 64)


def test_refused_artifact_changes_nothing(database: Database, db_conn: psycopg.Connection) -> None:
    """Task 10.3: a hash mismatch is refused and the served dataset stays."""
    reset(db_conn)
    wd = [wikidata_row("Q1", ["C08CA01"], {"en": "amlodipine"})]
    good = load(database, inputs([titck_row(barcode13(1), "A", ["amlodipine"], None)], [], wd))
    before = dump(db_conn, good.dataset_version)
    inp = inputs([titck_row(barcode13(1), "A", ["amlodipine"], None)], [], wd)
    bad = dict(inp.artifacts)
    bad[TITCK] = _tamper(bad[TITCK])
    with pytest.raises(LoadError, match="content hash"):
        load(database, type(inp)(bad, inp.rules, inp.route_map, inp.synonyms, inp.code))
    assert current_dataset(db_conn) == good.dataset_version
    assert dump(db_conn, good.dataset_version) == before


def test_read_artifact_from_parquet(tmp_path: Path) -> None:
    """Task 10.3: rows read from Parquet (DuckDB) hash to the manifest."""
    run = tmp_path / "artifacts" / "titck" / "current"
    run.mkdir(parents=True)
    row = titck_row(
        barcode13(1), "AMLIPIN 10 / 10", ["amlodipin besilat", "lisinopril dihidrat"], "C09BB03"
    )
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE t (barcode VARCHAR, name_only BOOLEAN, product_name VARCHAR, "
        "ingredient_text VARCHAR, ingredients VARCHAR[], atc_code VARCHAR, "
        "suspension_status BIGINT)"
    )
    con.execute("INSERT INTO t VALUES (?, ?, ?, ?, ?, ?, ?)", list(row.values()))
    con.execute(f"COPY t TO '{run / 'rows.parquet'}' (FORMAT parquet)")
    con.close()
    a = artifact(TITCK, [row])
    (run / "manifest.json").write_text(json.dumps(a.manifest))
    (run / "evidence_source.json").write_text(json.dumps(a.evidence))
    read = read_artifact(tmp_path, TITCK)
    read.verify()
    assert read.rows == [row]


def test_migration_0002_is_reversible(db_url: str, db_conn: psycopg.Connection) -> None:
    """Task 10.3: upgrade → downgrade → upgrade gives the same resolution schema."""

    def schema() -> list[tuple[Any, ...]]:
        return db_conn.execute(
            "SELECT table_name, column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name LIKE 'res\\_%' ORDER BY 1, 2"
        ).fetchall()

    reset(db_conn)
    cfg = alembic_config(db_url)
    before = schema()
    assert {r[0] for r in before} >= {"res_dataset", "res_current", "res_product", "res_name"}
    command.downgrade(cfg, "0001")
    assert schema() == []
    command.upgrade(cfg, "head")
    assert schema() == before
