"""Rule-base loader: P19 and examples (cascade-engine design §5, §9; task 10). PostgreSQL 16."""

from __future__ import annotations

import csv
import datetime as dt
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import psycopg
import pytest
from alembic import command
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test

from janus.cascades import repository
from janus.cascades.load import LoadedFiles, RuleBaseLoadError, load, read_files
from janus.cascades.rulebase import CLASSES_FILE, PIPC_FILE, RuleBaseError
from janus.db.pool import Database
from janus.integrity import repository as integrity_repository
from janus.integrity.load import LoadInputs
from janus.integrity.load import load as integrity_load
from janus.integrity.model import EvidenceRecord
from janus.integrity.records import records_from_papers
from janus.integrity.registry import read_sources
from janus.resolution.atc import DATA_DIR
from tests.conftest import DB_EXAMPLES, alembic_config
from tests.integrity_db import reset as reset_evidence

REGISTRY = DATA_DIR.parent / "pipelines" / "sources.toml"
TODAY = dt.date(2026, 11, 7)
PIPC_DOI = "10.1007/s41999-025-01215-x"


class InjectedFailureError(RuntimeError):
    pass


@pytest.fixture
def database(db_url: str) -> Iterator[Database]:
    db = Database(db_url)
    db.open()
    yield db
    db.close()


def reset(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM cascade_rule_base_current")
    conn.execute("DELETE FROM cascade_rule_base")
    reset_evidence(conn)


def seed_evidence(db: Database) -> None:
    """The PIPC paper and the curated papers, as the integrity loader registers them."""
    sources = read_sources(REGISTRY)
    pipc = EvidenceRecord(
        id="dataset:pipc",
        kind="dataset",
        source_id="pipc",
        source_url="https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12712104/fullTextXML",
        license="CC BY 4.0",
        region=None,
        snapshot_date=dt.date(2025, 7, 31),
        snapshot_is_retrieval_time=False,
        doi=PIPC_DOI,
        title="PIPC list of prescribing cascades",
    )
    with (DATA_DIR / "evidence_papers.csv").open(encoding="utf-8", newline="") as f:
        papers = records_from_papers(list(csv.DictReader(f)), sources)
    integrity_load(db, LoadInputs((pipc, *papers), sources, {}, None), TODAY)


def dump(conn: psycopg.Connection) -> dict[str, list[tuple[Any, ...]]]:
    return {
        "rule_base": sorted(
            tuple(r)
            for r in conn.execute(
                "SELECT version, content::text, inputs::text FROM cascade_rule_base"
            ).fetchall()
        ),
        "current": [tuple(r) for r in conn.execute("SELECT * FROM cascade_rule_base_current")],
        "rules": sorted(
            tuple(r)
            for r in conn.execute(
                "SELECT e.id, e.source_url, e.license, e.locator, e.title, "
                "array_agg(b.basis_id ORDER BY b.basis_id) FROM evidence e "
                "LEFT JOIN evidence_basis b ON b.evidence_id = e.id "
                "WHERE e.kind = 'rule' GROUP BY 1, 2, 3, 4, 5"
            ).fetchall()
        ),
    }


def with_window(files: LoadedFiles, w: int) -> LoadedFiles:
    return replace(files, window_months=w)


def broken(files: LoadedFiles, what: str) -> LoadedFiles:
    texts = dict(files.texts)
    if what == "bad_pattern":
        texts[CLASSES_FILE] = texts[CLASSES_FILE].replace(",C08,", ",C8,", 1)
    else:  # pipc text changed: hash mismatch
        texts[PIPC_FILE] = texts[PIPC_FILE].replace("Cough remedy", "Cough remedies", 1)
    return replace(files, texts=texts)


class LoadMachine(RuleBasedStateMachine):
    database: Database
    conn: psycopg.Connection
    files: LoadedFiles

    def __init__(self) -> None:
        super().__init__()
        reset(self.conn)
        seed_evidence(self.database)
        self.expected = dump(self.conn)

    @rule(window=st.sampled_from([12, 13]))
    def good_load(self, window: int) -> None:
        before = dump(self.conn)
        result = load(self.database, with_window(self.files, window), TODAY)
        after = dump(self.conn)
        if not result.created:  # reloading a stored version only moves the pointer
            assert after["rule_base"] == before["rule_base"]
        assert after["current"] == [(True, result.version)]
        assert len(after["rules"]) == 65
        assert all(r[5] == ["dataset:pipc"] for r in after["rules"])
        assert all(r[1] == f"https://doi.org/{PIPC_DOI}" for r in after["rules"])
        self.expected = after

    @rule(what=st.sampled_from(["bad_pattern", "pipc_text"]))
    def refused_load(self, what: str) -> None:
        with pytest.raises(RuleBaseError):
            load(self.database, broken(self.files, what), TODAY)

    @rule(
        stage=st.sampled_from(["rule_base", "evidence", "current"]),
        window=st.sampled_from([12, 14]),
    )
    def failing_load(self, stage: str, window: int) -> None:
        def hook(name: str) -> None:
            if name == stage:
                raise InjectedFailureError

        with pytest.raises(InjectedFailureError):
            load(self.database, with_window(self.files, window), TODAY, hook=hook)

    @invariant()
    def state_is_that_of_the_last_good_load(self) -> None:
        assert dump(self.conn) == self.expected


@pytest.mark.db
def test_p19_atomic_idempotent_load(database: Database, db_conn: psycopg.Connection) -> None:
    """Feature: cascade-engine, Property 19. Validates: Req 1.1, 10.1-10.3.

    Any sequence of good, refused and failing loads leaves exactly the state of the last good
    load; reloading unchanged inputs adds nothing; each load registers the 65 rule records with
    basis `dataset:pipc`.
    """
    LoadMachine.database = database
    LoadMachine.conn = db_conn
    LoadMachine.files = read_files()
    run_state_machine_as_test(
        LoadMachine,
        settings=settings(
            max_examples=max(10, DB_EXAMPLES // 5), stateful_step_count=5, deadline=None
        ),
    )


@pytest.mark.db
def test_reload_unchanged_writes_nothing(database: Database, db_conn: psycopg.Connection) -> None:
    """Req 10.2."""
    reset(db_conn)
    seed_evidence(database)
    first = load(database, read_files(), TODAY)
    snap = dump(db_conn)
    second = load(database, read_files(), TODAY)
    assert first.created and not second.created and first.version == second.version
    assert dump(db_conn) == snap
    with database.read_only_tx() as conn:
        rb = repository.current_rule_base(conn)
    assert rb is not None and rb.version == first.version and len(rb.rules) == 65


@pytest.mark.db
def test_refused_before_integrity_load(database: Database, db_conn: psycopg.Connection) -> None:
    """Loading before the evidence is registered is refused with a clear error. Req 10.1."""
    reset(db_conn)
    with pytest.raises(RuleBaseLoadError, match=r"janus\.integrity\.load"):
        load(database, read_files(), TODAY)
    assert dump(db_conn) == {"rule_base": [], "current": [], "rules": []}


@pytest.mark.db
def test_rule_record_carries_the_pipc_correction(
    database: Database, db_conn: psycopg.Connection
) -> None:
    """A rule record rests on the PIPC paper, so its notice reaches the rule. Req 1.5."""
    from janus.integrity.citability import roots

    reset(db_conn)
    seed_evidence(database)
    load(database, read_files(), TODAY)
    with database.read_only_tx() as conn:
        snap = integrity_repository.load_snapshot(conn)
    assert roots(snap, "rule:pipc:12") == ("dataset:pipc",)
    assert snap.records["rule:pipc:12"].locator == "Table 1, row 12"


@pytest.mark.db
def test_migration_0005_is_reversible(db_url: str, db_conn: psycopg.Connection) -> None:
    """Upgrade → downgrade → upgrade gives an identical schema. Req 10.3."""

    def schema() -> list[tuple[Any, ...]]:
        cols = db_conn.execute(
            "SELECT table_name, column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_name LIKE 'cascade_%' ORDER BY 1, 2"
        ).fetchall()
        cons = db_conn.execute(
            "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) "
            "FROM pg_constraint "
            "WHERE conrelid::regclass::text LIKE 'cascade_%' ORDER BY 1, 2"
        ).fetchall()
        return [tuple(r) for r in cols] + [tuple(r) for r in cons]

    reset(db_conn)
    cfg = alembic_config(db_url)
    before = schema()
    assert before
    command.downgrade(cfg, "0004")
    assert schema() == []
    command.upgrade(cfg, "head")
    assert schema() == before


def test_curated_files_are_read_from_data() -> None:
    """The loader reads the curated files from the repository's data/ directory."""
    files = read_files()
    assert Path(DATA_DIR / PIPC_FILE).is_file() and files.inputs().pipc_csv.startswith("position,")
