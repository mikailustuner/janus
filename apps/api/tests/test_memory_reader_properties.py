"""Counts reader: fail closed, follow `current`, freshness (design §10: P22, P23)."""

from __future__ import annotations

import datetime as dt
import shutil
import tempfile
import tomllib
from pathlib import Path

import duckdb
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.memory.faers_build import COUNTS_DB, counts_root
from janus.memory.reader import (
    FAERS_CADENCE_DAYS,
    CountsError,
    CountsHolder,
    CountsReader,
    counts_match_served,
    snapshot_freshness,
)
from tests.memory_counts import make_counts, reports
from tests.test_faers_build_properties import ReportFact, build, write_artifact

ONE = [ReportFact("100001", "2026Q3", "US", (("PS", ("ASPIRIN",)),), ("Pain",))]


def current_db(data_dir: Path) -> Path:
    return counts_root(data_dir) / "current" / COUNTS_DB


@settings(max_examples=8, deadline=None)
@given(reports())
def test_a_good_file_opens_and_has_its_metadata(facts: list[ReportFact]) -> None:
    """Feature: collective-memory, Property P22 (positive part) — Validates: Req 7.6."""
    with tempfile.TemporaryDirectory() as d:
        result = make_counts(Path(d), facts)
        reader = CountsHolder(Path(d)).current()
        assert reader.meta.build_id == result.build_id
        assert reader.meta.schema_version == "faers_counts-2"
        assert reader.meta.window == ("2025Q4", "2026Q1", "2026Q2", "2026Q3")
        with reader.session() as s:
            assert s.totals()["ALL"][1] == len(facts)
            assert s.statements == 1


def test_no_file_no_directory_no_link_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(CountsError):
        CountsHolder(None).current()
    with pytest.raises(CountsError):
        CountsHolder(tmp_path).current()


def _mutate(db: Path, how: str) -> None:
    if how == "garbage":
        db.write_bytes(b"not a duckdb file" * 50)
        return
    if how == "truncated":
        data = db.read_bytes()
        db.write_bytes(data[: len(data) // 3])
        return
    con = duckdb.connect(str(db))
    try:
        if how == "other_schema":
            con.execute(
                "UPDATE faers_meta SET value = 'faers_counts-1' WHERE key = 'schema_version'"
            )
        elif how == "missing_meta_key":
            con.execute("DELETE FROM faers_meta WHERE key = 'snapshot_date'")
        elif how == "missing_table":
            con.execute("DROP TABLE faers_region_basis")
        elif how == "rows_removed":
            con.execute(
                "DELETE FROM faers_pair_counts "
                "WHERE rowid = (SELECT min(rowid) FROM faers_pair_counts)"
            )
        elif how == "rows_added":
            con.execute("INSERT INTO faers_totals VALUES ('XX', 1, 1)")
        elif how == "bad_window":
            con.execute("UPDATE faers_meta SET value = 'not json' WHERE key = 'window'")
        con.execute("CHECKPOINT")
    finally:
        con.close()


@pytest.mark.parametrize(
    "how",
    [
        "garbage",
        "truncated",
        "other_schema",
        "missing_meta_key",
        "missing_table",
        "rows_removed",
        "rows_added",
        "bad_window",
    ],
)
def test_a_damaged_file_is_refused_with_no_numbers(tmp_path: Path, how: str) -> None:
    """Feature: collective-memory, Property P22 — Validates: Req 7.6, 11.4."""
    facts = [
        ReportFact("100001", "2026Q3", "US", (("PS", ("ASPIRIN",)),), ("Pain", "Rash")),
        ReportFact("100002", "2026Q3", "EU", (("C", ("METFORMIN",)),), ("Rash",)),
    ]
    make_counts(tmp_path, facts)
    _mutate(current_db(tmp_path), how)
    with pytest.raises(CountsError):
        CountsHolder(tmp_path).current()


def test_a_promoted_build_is_picked_up_and_an_interrupted_one_never_read(tmp_path: Path) -> None:
    """Feature: collective-memory, Property P22 — Validates: Req 7.6."""
    first = make_counts(tmp_path, ONE)
    holder = CountsHolder(tmp_path)
    reader1 = holder.current()
    assert reader1.meta.build_id == first.build_id
    assert holder.current() is reader1  # same build: same handle

    class BoomError(Exception):
        pass

    def fault(step: str) -> None:
        if step == "promote_replace":
            raise BoomError

    write_artifact(tmp_path, ONE, name="run2")
    with pytest.raises(BoomError):
        build(tmp_path, fault=fault)
    assert (
        holder.current().meta.build_id == first.build_id
    )  # the interrupted build was not promoted

    second = build(tmp_path)
    reader2 = holder.current()
    assert reader2.meta.build_id == second.build_id != first.build_id
    with reader1.session() as s:  # an in-flight request on the old handle still works
        assert s.totals()["ALL"][1] == 1


def test_the_reader_cannot_write_or_spill(tmp_path: Path) -> None:
    target = tmp_path / "out.csv"
    make_counts(tmp_path, ONE)
    reader = CountsReader(current_db(tmp_path))
    with reader.session() as s, pytest.raises(CountsError):
        s._all("CREATE TABLE x (a INTEGER)")  # pyright: ignore[reportPrivateUsage]
    with reader.session() as s, pytest.raises(CountsError):
        s._all(f"COPY faers_totals TO '{target}'")  # pyright: ignore[reportPrivateUsage]
    assert not target.exists()


# --- P23 ---------------------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(
    st.dates(min_value=dt.date(2020, 1, 1), max_value=dt.date(2030, 1, 1)), st.integers(-30, 400)
)
def test_stale_exactly_when_older_than_twice_the_cadence(snapshot: dt.date, offset: int) -> None:
    """Feature: collective-memory, Property P23 — Validates: Req 7.8."""
    today = snapshot + dt.timedelta(days=offset)
    f = snapshot_freshness(snapshot.isoformat(), today)
    age = max(0, offset)
    assert f.age_days == age
    assert (f.state == "stale") == (age > 2 * FAERS_CADENCE_DAYS == 182)


@given(st.text(min_size=1, max_size=12), st.one_of(st.none(), st.text(min_size=1, max_size=12)))
def test_version_notice_exactly_when_versions_differ(counts: str, served: str | None) -> None:
    """Feature: collective-memory, Property P23 — Validates: Req 7.7."""
    got = counts_match_served(counts, served)
    assert got is None if served is None else got == (counts == served)


def test_the_cadence_constant_equals_the_source_registry() -> None:
    registry = Path(__file__).resolve().parents[3] / "pipelines" / "sources.toml"
    sources = tomllib.loads(registry.read_text(encoding="utf-8"))["sources"]
    faers = next(s for s in sources if s["id"] == "faers")
    assert faers["cadence_days"] == FAERS_CADENCE_DAYS


# keep the fixtures import used for type checkers
_ = shutil
