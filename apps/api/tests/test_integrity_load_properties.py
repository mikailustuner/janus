"""Loader and status-change log against PostgreSQL 16 (evidence-integrity design §5):
P4 (database), P13 (database), P14 (database), P15, P16 and example tests."""

from __future__ import annotations

import datetime as dt
import itertools
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import psycopg
import pytest
from alembic import command
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test

from janus.db.pool import Database
from janus.integrity import repository
from janus.integrity.load import LoadInputs, gather, load, register_records
from janus.integrity.model import EvidenceRecord, Status
from janus.integrity.records import RecordError
from janus.integrity.status import Incoming, incoming_from_row
from janus.resolution.load import LoadError
from tests.conftest import DB_EXAMPLES, alembic_config
from tests.integrity_db import (
    CORRECTION,
    NOTICE_DOI,
    PIPC_DOI,
    REGISTRY,
    SOURCES,
    dump,
    reset,
    retraction_row,
    write_artifacts,
)

DAY1 = dt.date(2026, 11, 7)
DAY2 = dt.date(2026, 11, 14)
PAPER_DOI = "10.1136/bmj-2025-100499"


@pytest.fixture(scope="module")
def database(db_url: str) -> Iterator[Database]:
    db = Database(db_url)
    db.open()
    yield db
    db.close()


def _gather(root: Path, papers: Path | None = None) -> LoadInputs:
    return gather(root, REGISTRY, papers or root / "none.csv")


def _snapshot(db: Database) -> repository.IntegritySnapshot:
    with db.read_only_tx() as conn:
        return repository.load_snapshot(conn)


def _papers_file(root: Path) -> Path:
    p = root / "evidence_papers.csv"
    p.write_text(
        "key,doi,source_id,title,verified_on,note\n"
        f"e100499,{PAPER_DOI},bmj_2026,BMJ 2026 e100499,2026-11-07,\n",
        encoding="utf-8",
    )
    return p


# --- example tests (task 8.6) ---------------------------------------------------------------


@pytest.mark.db
def test_pipc_load_gives_corrected_with_its_notice(
    database: Database, db_conn: psycopg.Connection, tmp_path: Path
) -> None:
    reset(db_conn)
    root = write_artifacts(
        tmp_path, retractions=[retraction_row(PIPC_DOI, "corrected", [CORRECTION])]
    )
    result = load(database, _gather(root), DAY1)
    assert result.by_status["corrected"] == 1
    assert result.not_yet_checked == 0
    snap = _snapshot(database)
    state = snap.states["dataset:pipc"]
    assert state.status == Status.CORRECTED
    (n,) = state.notices
    assert (n.type, n.source, n.notice_doi, n.date) == (
        "correction",
        "publisher",
        NOTICE_DOI,
        dt.date(2025, 12, 18),
    )
    assert state.checked_at == dt.date(2026, 11, 7)
    assert snap.records["dataset:pipc"].doi == PIPC_DOI
    assert snap.sources["pipc"].cadence_days == 365
    assert snap.sources["crossref"].cadence_days == 7
    assert set(snap.records) == {
        "dataset:pipc",
        "dataset:titck",
        "dataset:openfda_ndc",
        "dataset:wikidata",
        "dataset:crossref",
    }


@pytest.mark.db
def test_doi_without_a_check_row_is_unknown_and_reported(
    database: Database, db_conn: psycopg.Connection, tmp_path: Path
) -> None:
    reset(db_conn)
    root = write_artifacts(tmp_path, retractions=None)
    result = load(database, _gather(root), DAY1)
    assert result.not_yet_checked == 1
    state = _snapshot(database).states["dataset:pipc"]
    assert (state.status, state.reason, state.checked_at) == (
        Status.UNKNOWN,
        "not_yet_checked",
        None,
    )


@pytest.mark.db
def test_refused_inputs(tmp_path: Path) -> None:
    row = [retraction_row(PIPC_DOI, "corrected", [CORRECTION])]
    with pytest.raises(LoadError, match="content hash"):
        _gather(write_artifacts(tmp_path / "a", retractions=row, tamper=True))
    with pytest.raises(LoadError, match="not promoted"):
        _gather(write_artifacts(tmp_path / "b", retractions=row, outcome="needs_review"))
    _gather(write_artifacts(tmp_path / "c", retractions=row, outcome="needs_review", promoted=True))
    with pytest.raises(LoadError, match="run did not succeed"):
        _gather(write_artifacts(tmp_path / "d", retractions=row, outcome="failed"))
    bad = [retraction_row(PIPC_DOI, "ok", [CORRECTION])]
    with pytest.raises(LoadError, match="notices_on_ok"):
        _gather(write_artifacts(tmp_path / "e", retractions=bad))


@pytest.mark.db
def test_migrations_are_reversible(db_url: str, db_conn: psycopg.Connection) -> None:
    cfg = alembic_config(db_url)

    def schema() -> list[tuple[Any, ...]]:
        cols = db_conn.execute(
            "SELECT table_name, column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name LIKE 'evidence%%' OR (table_name = 'res_source_version' "
            "AND column_name = 'cadence_days') ORDER BY 1, 2"
        ).fetchall()
        cons = db_conn.execute(
            "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) "
            "FROM pg_constraint "
            "WHERE conrelid::regclass::text LIKE 'evidence%%' "
            "OR conname = 'res_source_cadence_range' ORDER BY 1, 2"
        ).fetchall()
        return [tuple(r) for r in (*cols, *cons)]

    before = schema()
    assert before
    command.downgrade(cfg, "0002")
    assert schema() == []
    command.upgrade(cfg, "head")
    assert schema() == before


@pytest.mark.db
def test_database_rejects_bad_evidence_rows(
    db_conn: psycopg.Connection, database: Database
) -> None:
    reset(db_conn)
    db_conn.execute("INSERT INTO evidence_source VALUES ('s', 'S', 'cache', 7)")
    good: tuple[Any, ...] = (
        "dataset:s",
        "dataset",
        "s",
        "https://example.org",
        "L",
        None,
        "2026-01-01",
        False,
        None,
    )
    ins = (
        "INSERT INTO evidence (id, kind, source_id, source_url, license, region, snapshot_date, "
        "snapshot_is_retrieval_time, doi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    for idx, bad in [
        (0, "Dataset:s"),
        (1, "blog"),
        (3, "ftp://x"),
        (4, " "),
        (5, "DE"),
        (8, "10.1000/UPPER"),
    ]:
        row = list(good)
        row[idx] = bad
        with pytest.raises(psycopg.errors.CheckViolation), db_conn.transaction():
            db_conn.execute(ins, row)  # pyright: ignore[reportArgumentType]
    db_conn.execute(ins, list(good))  # pyright: ignore[reportArgumentType]
    reset(db_conn)


# --- P4 (database part) ---------------------------------------------------------------------


@pytest.mark.db
def test_p4_loading_twice_changes_nothing(
    database: Database, db_conn: psycopg.Connection, tmp_path: Path
) -> None:
    """Feature: evidence-integrity, Property P4 (database part) (Req 1.1, 8.2, 8.4)."""
    reset(db_conn)
    root = write_artifacts(
        tmp_path, retractions=[retraction_row(PIPC_DOI, "corrected", [CORRECTION])]
    )
    inputs = _gather(root, _papers_file(tmp_path))
    first = load(database, inputs, DAY1)
    state, version = dump(db_conn), _snapshot(database).version()
    assert first.changes == 2  # PIPC dataset and the paper: first sightings
    second = load(database, _gather(root, tmp_path / "evidence_papers.csv"), DAY2)
    assert second.changes == 0
    assert dump(db_conn) == state
    assert _snapshot(database).version() == version


# --- P13 (database part) --------------------------------------------------------------------


@given(
    defect=st.sampled_from(
        ["unknown_source", "no_cadence", "bad_doi", "basis_cycle", "rule_without_basis"]
    )
)
@settings(max_examples=DB_EXAMPLES, deadline=None)
def test_p13_refused_record_set_changes_nothing(
    defect: str,
    database: Database,
    db_conn: psycopg.Connection,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Feature: evidence-integrity, Property P13 (database part) (Req 4.1)."""
    reset(db_conn)
    root = write_artifacts(
        tmp_path_factory.mktemp("d"), retractions=[retraction_row(PIPC_DOI, "ok")]
    )
    good = _gather(root)
    load(database, good, DAY1)
    before = dump(db_conn)
    base = good.records[0]
    sources = dict(good.sources)
    if defect == "unknown_source":
        bad = replace(base, id="paper:nowhere:x", kind="paper", source_id="nowhere")
    elif defect == "no_cadence":
        sources["onsides"] = replace(sources["onsides"], cadence_days=None)
        bad = replace(base, id="label:onsides:x", kind="label", source_id="onsides")
    elif defect == "bad_doi":
        bad = replace(base, id="paper:bmj_2026:z", kind="paper", source_id="bmj_2026", doi="NOT")
    elif defect == "basis_cycle":
        bad = replace(
            base,
            id="paper:bmj_2026:z",
            kind="paper",
            source_id="bmj_2026",
            basis=("paper:bmj_2026:z",),
        )
    else:
        bad = replace(base, id="rule:pipc:1", kind="rule", source_id="pipc", basis=())
    with pytest.raises(RecordError) as exc:
        load(database, replace(good, records=(*good.records, bad), sources=sources), DAY2)
    assert exc.value.code == defect
    assert dump(db_conn) == before


# --- P14 (database part) --------------------------------------------------------------------


@pytest.mark.db
def test_p14_new_run_keeps_ids_and_nothing_is_deleted(
    database: Database, db_conn: psycopg.Connection, tmp_path: Path
) -> None:
    """Feature: evidence-integrity, Property P14 (database part) (Req 4.2)."""
    reset(db_conn)
    rows = [retraction_row(PIPC_DOI, "ok")]
    r1 = write_artifacts(tmp_path / "one", retractions=rows)
    load(database, _gather(r1), DAY1)
    ids_before = set(_snapshot(database).records)
    # A later run covers fewer pipelines and carries another snapshot date.
    r2 = write_artifacts(
        tmp_path / "two",
        retractions=rows,
        datasets=["pipc"],
        run="r2",
        snapshot_override="2026-11-09",
    )
    load(database, _gather(r2), DAY2)
    snap = _snapshot(database)
    assert set(snap.records) == ids_before
    assert snap.records["dataset:pipc"].snapshot_date == dt.date(2026, 11, 9)
    assert snap.records["dataset:titck"].snapshot_date == dt.date(2026, 11, 6)


# --- P15: status-change log -----------------------------------------------------------------

COMPLETED = [Status.OK, Status.CORRECTED, Status.EXPRESSION_OF_CONCERN, Status.RETRACTED]


def _incoming(kind: str, status: Status | None, doi: str) -> Incoming | None:
    if kind == "missing":
        return None
    if kind == "complete":
        assert status is not None
        notes = [] if status == Status.OK else [CORRECTION]
        return incoming_from_row(retraction_row(doi, status.value, notes))
    eff = "retracted" if status == Status.RETRACTED else "unknown"
    return incoming_from_row(retraction_row(doi, "unknown", reason="check_failed", effective=eff))


EVENT = st.one_of(
    st.tuples(st.just("missing"), st.just(Status.UNKNOWN)),
    st.tuples(st.just("complete"), st.sampled_from(COMPLETED)),
    st.tuples(st.just("failed"), st.sampled_from([Status.UNKNOWN, Status.RETRACTED])),
)


def _model_next(prev: Status | None, kind: str, status: Status) -> Status:
    if kind == "missing":
        return prev if prev is not None else Status.UNKNOWN
    if kind == "complete":
        return status
    if prev == Status.RETRACTED or status == Status.RETRACTED:
        return Status.RETRACTED
    return Status.UNKNOWN


def _inputs_for(base: LoadInputs, events: dict[str, tuple[str, Status]], run: str) -> LoadInputs:
    inc: dict[str, Incoming] = {}
    for doi, (kind, status) in events.items():
        row = _incoming(kind, status, doi)
        if row is not None:
            inc[doi] = row
    return replace(base, incoming=inc, check_run_id=run)


def _base_inputs() -> LoadInputs:
    def rec(
        i: str, kind: str, source: str, doi: str | None, basis: tuple[str, ...] = ()
    ) -> EvidenceRecord:
        return EvidenceRecord(
            id=i,
            kind=kind,
            source_id=source,
            source_url="https://example.org/x",
            license="L",
            region=None,
            snapshot_date=dt.date(2026, 1, 1),
            snapshot_is_retrieval_time=False,
            doi=doi,
            basis=basis,
        )

    records = (
        rec("dataset:pipc", "dataset", "pipc", PIPC_DOI),
        rec("paper:bmj_2026:a", "paper", "bmj_2026", PAPER_DOI),
        rec("rule:pipc:1", "rule", "pipc", None, ("dataset:pipc", "paper:bmj_2026:a")),
    )
    return LoadInputs(records, SOURCES, {}, None)


DOIS = {"dataset:pipc": PIPC_DOI, "paper:bmj_2026:a": PAPER_DOI}


@pytest.mark.db
@given(
    steps=st.lists(
        st.fixed_dictionaries({PIPC_DOI: EVENT, PAPER_DOI: EVENT}), min_size=1, max_size=5
    )
)
@settings(max_examples=DB_EXAMPLES, deadline=None)
def test_p15_status_change_log(
    steps: list[dict[str, tuple[str, Status]]], database: Database, db_conn: psycopg.Connection
) -> None:
    """Feature: evidence-integrity, Property P15 (Req 3.3)."""
    reset(db_conn)
    base = _base_inputs()
    model: dict[str, Status | None] = {PIPC_DOI: None, PAPER_DOI: None}
    expected_rows = 0
    for n, step in enumerate(steps):
        day = DAY1 + dt.timedelta(days=n)
        load(database, _inputs_for(base, step, f"run-{n}"), day)
        for doi, (kind, status) in step.items():
            prev = model[doi]
            new = _model_next(prev, kind, status)
            if prev is None or prev != new:
                expected_rows += 1
            model[doi] = new
    snap = _snapshot(database)
    assert snap.states["dataset:pipc"].status == model[PIPC_DOI]
    assert snap.states["paper:bmj_2026:a"].status == model[PAPER_DOI]
    rows = db_conn.execute(
        "SELECT evidence_id, from_status, to_status, observed_on FROM evidence_status_change "
        "ORDER BY observed_on, evidence_id"
    ).fetchall()
    assert len(rows) == expected_rows
    for eid, doi in (("dataset:pipc", PIPC_DOI), ("paper:bmj_2026:a", PAPER_DOI)):
        mine = [r for r in rows if r[0] == eid]
        assert mine[0][1] is None
        final = model[doi]
        assert final is not None
        assert mine[-1][2] == final.value
        for a, b in itertools.pairwise(mine):
            assert b[1] == a[2]  # each change starts where the last one ended
            assert b[1] != b[2]
    with database.read_only_tx() as conn:
        listed = repository.changes_since(conn, DAY1, 500)
        assert [c.evidence_id for c in listed] == [
            c.evidence_id
            for c in sorted(
                listed, key=lambda c: (-c.observed_on.toordinal(), c.evidence_id, c.to_status)
            )
        ]
        assert all(c.from_status != c.to_status for c in listed)
        assert len(listed) == sum(1 for r in rows if r[1] is not None)
        later = repository.changes_since(conn, DAY1 + dt.timedelta(days=2), 500)
        assert all(c.observed_on >= DAY1 + dt.timedelta(days=2) for c in later)
        assert len(repository.changes_since(conn, DAY1, 1)) <= 1


# --- P16: atomic load -----------------------------------------------------------------------


class InjectedFailureError(RuntimeError):
    pass


class LoadMachine(RuleBasedStateMachine):
    database: Database
    conn: psycopg.Connection

    def __init__(self) -> None:
        super().__init__()
        reset(self.conn)
        self.base = _base_inputs()
        self.expected = dump(self.conn)
        self.n = 0

    @rule(step=st.fixed_dictionaries({PIPC_DOI: EVENT, PAPER_DOI: EVENT}))
    def good_load(self, step: dict[str, tuple[str, Status]]) -> None:
        self.n += 1
        load(
            self.database,
            _inputs_for(self.base, step, f"run-{self.n}"),
            DAY1 + dt.timedelta(days=self.n),
        )
        self.expected = dump(self.conn)

    @rule(
        step=st.fixed_dictionaries({PIPC_DOI: EVENT, PAPER_DOI: EVENT}),
        stage=st.sampled_from(["sources", "records", "basis", "integrity"]),
    )
    def failing_load(self, step: dict[str, tuple[str, Status]], stage: str) -> None:
        def hook(name: str) -> None:
            if name == stage:
                raise InjectedFailureError

        with pytest.raises(InjectedFailureError):
            load(self.database, _inputs_for(self.base, step, "run-x"), DAY2, hook=hook)

    @rule(defect=st.sampled_from(["unknown_basis", "basis_cycle"]))
    def refused_load(self, defect: str) -> None:
        bad = replace(
            self.base.records[2],
            basis=("dataset:missing",) if defect == "unknown_basis" else ("rule:pipc:1",),
        )
        inputs = replace(self.base, records=(*self.base.records[:2], bad))
        with pytest.raises(RecordError):
            load(self.database, inputs, DAY2)

    @invariant()
    def state_is_that_of_the_last_good_load(self) -> None:
        assert dump(self.conn) == self.expected


@pytest.mark.db
def test_p16_atomic_load(database: Database, db_conn: psycopg.Connection) -> None:
    """Feature: evidence-integrity, Property P16 (Req 8.1)."""
    LoadMachine.database = database
    LoadMachine.conn = db_conn
    run_state_machine_as_test(
        LoadMachine,
        settings=settings(
            max_examples=max(20, DB_EXAMPLES // 2), stateful_step_count=6, deadline=None
        ),
    )


@pytest.mark.db
def test_register_records_gives_first_sighting_unknown(
    database: Database, db_conn: psycopg.Connection, tmp_path: Path
) -> None:
    """Other specs register records inside their own transaction (Req 4.3, 8.6)."""
    reset(db_conn)
    load(
        database,
        _gather(write_artifacts(tmp_path, retractions=[retraction_row(PIPC_DOI, "ok")])),
        DAY1,
    )
    paper = EvidenceRecord(
        id="paper:bmj_2026:a",
        kind="paper",
        source_id="bmj_2026",
        source_url=f"https://doi.org/{PAPER_DOI}",
        license="Paywalled",
        region=None,
        snapshot_date=dt.date(2026, 11, 7),
        snapshot_is_retrieval_time=False,
        doi=PAPER_DOI,
    )
    rule_rec = EvidenceRecord(
        id="rule:pipc:12",
        kind="rule",
        source_id="pipc",
        source_url="https://example.org/r",
        license="CC BY 4.0",
        region=None,
        snapshot_date=dt.date(2025, 7, 31),
        snapshot_is_retrieval_time=False,
        locator="Table 1, row 12",
        basis=("dataset:pipc", "paper:bmj_2026:a"),
    )
    with database.write_tx() as conn:
        changes = register_records(conn, [paper, rule_rec], DAY2)
    assert changes == 1
    snap = _snapshot(database)
    assert snap.states["paper:bmj_2026:a"].reason == "not_yet_checked"
    assert snap.records["rule:pipc:12"].basis == ("dataset:pipc", "paper:bmj_2026:a")
    with pytest.raises(RecordError), database.write_tx() as conn:
        register_records(conn, [replace(rule_rec, id="rule:pipc:13", basis=())], DAY2)
