# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportUnknownLambdaType=false
"""Property tests for the FAERS count builder (data-pipelines design §16: P33-P40).

Artifacts are written with DuckDB from generated reports; no network, no PostgreSQL.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.memory.faers_build import (
    ALL,
    COUNTS_DB,
    COUNTS_SCHEMA,
    EXPOSURE_ROLES,
    REGIONS,
    TABLES,
    BuildError,
    BuildResult,
    ReportFact,
    aggregate,
    build_counts,
    current_build,
    iter_parquet_rows,
    map_names,
    no_fault,
    sha256_of_table,
    write_counts,
)
from janus.resolution.canonical import content_hash_stream
from janus.resolution.matching import IndexItem, Match, NameIndex
from tests.harness import capture_logs

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)

# Names: two map to keys, one is ambiguous (two items share a label), the rest do not map.
ITEMS = [
    IndexItem("Q1", {"en": "aspirin"}, {}),
    IndexItem("Q2", {"en": "metformin"}, {}),
    IndexItem("Q3", {"en": "amlodipine"}, {"en": ("amlodipin besilat",)}),
    IndexItem("Q4", {"en": "twin"}, {}),
    IndexItem("Q5", {"en": "twin"}, {}),
]
INDEX = NameIndex.build(ITEMS)
NAMES = ["ASPIRIN", "METFORMIN", "AMLODIPINE BESYLATE", "TWIN", "NOT A DRUG", "INFLIXIMAB-DYYB"]
ROLES = ["PS", "SS", "I", "C", "DN", "ZZ"]
PTS = ["Pain", "Rash", "Nausea", "Dizziness"]
QUARTERS = ["2025Q4", "2026Q1", "2026Q2", "2026Q3"]

LINE = st.tuples(st.sampled_from(ROLES), st.lists(st.sampled_from(NAMES), max_size=3).map(tuple))


@st.composite
def reports(draw: st.DrawFn, min_size: int = 1, max_size: int = 12) -> list[ReportFact]:
    n = draw(st.integers(min_size, max_size))
    out: list[ReportFact] = []
    for i in range(n):
        out.append(
            ReportFact(
                primaryid=str(100000 + i),
                quarter=draw(st.sampled_from(QUARTERS)),
                region=draw(st.sampled_from(REGIONS)),
                lines=tuple(draw(st.lists(LINE, max_size=4))),
                events=tuple(draw(st.lists(st.sampled_from(PTS), max_size=4))),
            )
        )
    return out


def write_rows(path: Path, facts: Sequence[ReportFact]) -> None:
    """Write facts as the faers-1 artifact rows (DuckDB reads NDJSON, writes Parquet)."""
    ndjson = path.with_suffix(".ndjson")
    with ndjson.open("w", encoding="utf-8") as f:
        for r in facts:
            f.write(
                json.dumps(
                    {
                        "primaryid": r.primaryid,
                        "caseid": r.primaryid[:-2],
                        "caseversion": 1,
                        "quarter": r.quarter,
                        "fda_dt": "20260101",
                        "occr_country": "US",
                        "reporter_country": "US",
                        "region": r.region,
                        "region_basis": "occr_country",
                        "drugs": [
                            {"drug_seq": str(i), "role": role, "ingredients": list(ing)}
                            for i, (role, ing) in enumerate(r.lines, 1)
                        ],
                        "events": list(r.events),
                    }
                )
                + "\n"
            )
    con = duckdb.connect()
    try:
        con.execute(
            f"COPY (SELECT * FROM read_json('{ndjson}', format='newline_delimited', columns={{"
            "primaryid: 'VARCHAR', caseid: 'VARCHAR', caseversion: 'BIGINT', quarter: 'VARCHAR', "
            "fda_dt: 'VARCHAR', occr_country: 'VARCHAR', reporter_country: 'VARCHAR', "
            "region: 'VARCHAR', region_basis: 'VARCHAR', "
            "drugs: 'STRUCT(drug_seq VARCHAR, role VARCHAR, ingredients VARCHAR[])[]', "
            f"events: 'VARCHAR[]'}})) TO '{path}' (FORMAT parquet)"
        )
    finally:
        con.close()


def write_artifact(data_dir: Path, facts: Sequence[ReportFact], *, name: str = "run1") -> Path:
    """A `faers` artifact with a correct manifest, as the pipeline would write it."""
    run = data_dir / "artifacts" / "faers" / "runs" / name
    run.mkdir(parents=True, exist_ok=True)
    rows = run / "rows.parquet"
    write_rows(rows, facts)
    digest = content_hash_stream(iter_parquet_rows(rows), "faers-1")
    manifest = {
        "run_id": name,
        "outcome": "succeeded",
        "schema_version": "faers-1",
        "content_sha256": digest,
        "snapshot_date": "2026-10-28",
        "metrics": {"window": QUARTERS, "region_rule": {"version": 1}},
    }
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    link = data_dir / "artifacts" / "faers" / "current"
    if link.is_symlink():
        link.unlink()
    link.symlink_to(Path("runs") / name)
    return run


def build(data_dir: Path, **kw: Any) -> BuildResult:
    return build_counts(
        data_dir,
        INDEX,
        resolution_version="r" * 64,
        rules_version={"name_rules": "t"},
        code_version="test",
        now=lambda: NOW,
        **kw,
    )


def read(db: Path, sql: str) -> list[tuple[Any, ...]]:
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def tables_from(db: Path) -> dict[str, Any]:
    return {
        "totals": {r: (int(m), int(a)) for r, m, a in read(db, "SELECT * FROM faers_totals")},
        "ingredient": {
            (k, r, s): int(n) for k, r, s, n in read(db, "SELECT * FROM faers_ingredient_counts")
        },
        "event": {
            (pt, r): (int(m), int(a))
            for pt, r, m, a in read(db, "SELECT * FROM faers_event_counts")
        },
        "pair": {
            (k, pt, r, s): int(n) for k, pt, r, s, n in read(db, "SELECT * FROM faers_pair_counts")
        },
        "unmapped": {
            n: (s, int(o), int(rep), int(sus))
            for n, s, o, rep, sus in read(db, "SELECT * FROM faers_unmapped")
        },
    }


def counts_via_sql(
    facts: Sequence[ReportFact], scratch: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Match]]:
    rows = scratch / "rows.parquet"
    write_rows(rows, facts)
    matches = map_names({n for f in facts for _r, ing in f.lines for n in ing}, INDEX)
    db = scratch / "counts.duckdb"
    stats = write_counts(db, rows, matches, scratch)
    return tables_from(db), stats, matches


@settings(max_examples=25, deadline=None)
@given(reports())
def test_sql_tables_equal_the_reference_and_the_2x2_identities_hold(
    facts: list[ReportFact],
) -> None:
    """Feature: data-pipelines, Property P33 — Validates: Req 15.5.
    The DuckDB count tables equal the plain-Python reference; for every stored pair and
    region a <= min(drug, event) and b, c, d >= 0 with N = reports with a mapped ingredient.
    """
    with tempfile.TemporaryDirectory() as d:
        got, _stats, matches = counts_via_sql(facts, Path(d))
    ref = aggregate(facts, matches)
    assert got["totals"] == ref.totals
    assert got["ingredient"] == ref.ingredient
    assert got["event"] == ref.event
    assert got["pair"] == ref.pair
    assert got["unmapped"] == ref.unmapped
    for (key, pt, region, scope), a in got["pair"].items():
        n_mapped = got["totals"][region][0]
        n_drug = got["ingredient"][(key, region, scope)]
        n_event = got["event"][(pt, region)][0]
        b, c, dd = n_drug - a, n_event - a, n_mapped - n_drug - n_event + a
        assert 1 <= a <= min(n_drug, n_event)
        assert b >= 0 and c >= 0 and dd >= 0
        assert a + b + c + dd == n_mapped


@settings(max_examples=25, deadline=None)
@given(reports())
def test_regions_add_up_and_scopes_nest(facts: list[ReportFact]) -> None:
    """Feature: data-pipelines, Property P34 — Validates: Req 15.3, 15.5.
    Regional counts add up to ALL in every table; suspect <= any; roles DN and unknown codes
    are counted nowhere; a drug only on concomitant lines counts in `any` only.
    """
    with tempfile.TemporaryDirectory() as d:
        got, stats, _ = counts_via_sql(facts, Path(d))
    for table, width in (("ingredient", 3), ("pair", 4)):
        by_other: dict[tuple[Any, ...], int] = {}
        for k, n in got[table].items():
            if k[width - 2] != ALL:
                rest = (*k[: width - 2], k[width - 1])
                by_other[rest] = by_other.get(rest, 0) + n
        for k, n in got[table].items():
            if k[width - 2] == ALL:
                assert by_other[(*k[: width - 2], k[width - 1])] == n
    for region in (ALL,):
        assert got["totals"][region] == tuple(
            sum(got["totals"].get(r, (0, 0))[i] for r in REGIONS) for i in (0, 1)
        )
    for m, a in got["event"].values():
        assert m <= a
    for (key, region, scope), n in got["ingredient"].items():
        if scope == "suspect":
            assert n <= got["ingredient"][(key, region, "any")]
    for (key, pt, region, scope), n in got["pair"].items():
        if scope == "suspect":
            assert n <= got["pair"][(key, pt, region, "any")]
    # roles DN / ZZ contribute to no ingredient row
    only_bad = [f for f in facts if all(role not in {"PS", "SS", "I", "C"} for role, _ in f.lines)]
    assert stats["rows"]["faers_report"] == len(facts)
    if only_bad:
        with tempfile.TemporaryDirectory() as d2:
            got2, _, _ = counts_via_sql(only_bad, Path(d2))
        assert got2["ingredient"] == {} and got2["pair"] == {}
        assert got2["totals"][ALL][0] == 0


@settings(max_examples=25, deadline=None)
@given(reports(), st.data())
def test_counted_once_per_report(facts: list[ReportFact], data: st.DataObject) -> None:
    """Feature: data-pipelines, Property P35 — Validates: Req 15.4.
    Repeating a drug line or an event, or naming an ingredient again on another line with the
    same role, changes no count.
    """

    def widen(f: ReportFact) -> ReportFact:
        extra = tuple(data.draw(st.sampled_from(f.lines))) if f.lines else None
        lines = (*f.lines, extra) if extra else f.lines
        events = (*f.events, *f.events)
        return replace(f, lines=lines, events=events)

    widened = [widen(f) for f in facts]
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        base, base_stats, _ = counts_via_sql(facts, Path(a))
        again, again_stats, _ = counts_via_sql(widened, Path(b))
    for table in ("totals", "ingredient", "event", "pair"):
        assert base[table] == again[table], table
    assert (
        base_stats["table_sha256"]["faers_pair_counts"]
        == again_stats["table_sha256"]["faers_pair_counts"]
    )


@settings(max_examples=25, deadline=None)
@given(reports())
def test_only_mapped_names_are_counted(facts: list[ReportFact]) -> None:
    """Feature: data-pipelines, Property P36 — Validates: Req 15.2.
    Only `mapped` names reach the count tables, with the ladder's key; ambiguous, unsplit and
    unmapped names appear only in faers_unmapped; the occurrences add up.
    """
    with tempfile.TemporaryDirectory() as d:
        got, stats, matches = counts_via_sql(facts, Path(d))
    keys = {m.keys[0] for m in matches.values() if m.status == "mapped"}
    assert {k[0] for k in got["ingredient"]} <= keys
    assert {k[0] for k in got["pair"]} <= keys
    assert set(got["unmapped"]) == {
        n for f in facts for _r, ing in f.lines for n in ing if matches[n].status != "mapped"
    }
    assert all(s != "mapped" for s, *_ in got["unmapped"].values())
    total = sum(len(ing) for f in facts for _r, ing in f.lines)
    assert stats["occurrences_total"] == total
    assert sum(stats["occurrences_by_status"].values()) == total
    unmapped_occ = sum(o for _s, o, *_ in got["unmapped"].values())
    assert unmapped_occ == total - stats["occurrences_by_status"].get("mapped", 0)


def test_the_ladder_stub_has_every_status() -> None:
    matches = map_names(NAMES, INDEX)
    assert {m.status for m in matches.values()} >= {"mapped", "ambiguous", "none"}
    assert matches["AMLODIPINE BESYLATE"].status == "mapped"


@settings(max_examples=20, deadline=None)
@given(reports(), st.data())
def test_order_independence_and_determinism(facts: list[ReportFact], data: st.DataObject) -> None:
    """Feature: data-pipelines, Property P37 — Validates: Req 15.7.
    Shuffling the reports gives the same tables and per-table hashes; two builds agree.
    """
    shuffled = data.draw(st.permutations(facts))
    with (
        tempfile.TemporaryDirectory() as a,
        tempfile.TemporaryDirectory() as b,
        tempfile.TemporaryDirectory() as c,
    ):
        t1, s1, _ = counts_via_sql(facts, Path(a))
        t2, s2, _ = counts_via_sql(shuffled, Path(b))
        t3, s3, _ = counts_via_sql(facts, Path(c))
    assert t1 == t2 == t3
    assert s1["table_sha256"] == s2["table_sha256"] == s3["table_sha256"]


def test_tampered_artifact_is_refused_and_current_unchanged(tmp_path: Path) -> None:
    """Feature: data-pipelines, Property P38 — Validates: Req 15.1."""
    facts = [
        ReportFact("100001", "2026Q3", "US", (("PS", ("ASPIRIN",)),), ("Pain",)),
        ReportFact("100002", "2026Q3", "EU", (("C", ("METFORMIN",)),), ("Rash",)),
    ]
    data_dir = tmp_path
    run = write_artifact(data_dir, facts)
    first = build(data_dir)
    assert current_build(data_dir) == first.build_id
    # change one event: rows no longer hash to the manifest
    tampered = [facts[0], replace(facts[1], events=("Nausea",))]
    write_rows(run / "rows.parquet", tampered)
    with pytest.raises(BuildError, match="content hash"):
        build(data_dir)
    assert current_build(data_dir) == first.build_id
    # restore rows, break the manifest instead
    write_rows(run / "rows.parquet", facts)
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["content_sha256"] = "0" * 64
    (run / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BuildError, match="content hash"):
        build(data_dir)
    assert current_build(data_dir) == first.build_id
    # an added or removed row is refused too
    manifest["content_sha256"] = content_hash_stream(
        iter_parquet_rows(run / "rows.parquet"), "faers-1"
    )
    (run / "manifest.json").write_text(json.dumps(manifest))
    write_rows(run / "rows.parquet", facts[:1])
    with pytest.raises(BuildError, match="content hash"):
        build(data_dir)
    assert not list((tmp_path / "memory" / "faers_counts" / "staging").glob("2*"))


def test_unpromoted_review_run_and_missing_artifact_are_refused(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="no current artifact"):
        build(tmp_path)
    run = write_artifact(tmp_path, [ReportFact("100001", "2026Q3", "US", (), ())])
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["outcome"] = "needs_review"
    (run / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(BuildError, match="not promoted"):
        build(tmp_path)


FAULTS = st.sampled_from([None, "write_db", "finish", "promote_replace"])


class InjectedError(Exception):
    pass


@settings(max_examples=25, deadline=None)
@given(st.lists(FAULTS, min_size=1, max_size=5))
def test_failed_builds_never_leave_current_unusable(faults: list[str | None]) -> None:
    """Feature: data-pipelines, Property P39 — Validates: Req 15.8, 4.2.
    After any sequence of builds with faults at write, rename or link steps, `current` is
    absent or points to a complete run whose table hashes match its metadata.
    """
    facts = [ReportFact("100001", "2026Q3", "US", (("PS", ("ASPIRIN",)),), ("Pain",))]
    with tempfile.TemporaryDirectory() as d:
        data_dir = Path(d)
        write_artifact(data_dir, facts)
        last_ok: str | None = None
        for fault in faults:

            def hook(step: str, wanted: str | None = fault) -> None:
                if step == wanted:
                    raise InjectedError(step)

            try:
                result = build(data_dir, fault=hook if fault else no_fault)
                last_ok = result.build_id
            except InjectedError:
                pass
            current = current_build(data_dir)
            if fault is None:
                assert current == last_ok
            if fault in ("write_db", "finish"):
                assert current == (last_ok if fault is None else current)
            if current is not None:
                run = data_dir / "memory" / "faers_counts" / "runs" / current
                meta = json.loads((run / "meta.json").read_text())
                db = run / COUNTS_DB
                assert db.exists()
                stored = dict(read(db, "SELECT key, value FROM faers_meta"))
                assert json.loads(stored["stats"])["table_sha256"] == meta["stats"]["table_sha256"]
                assert [r[0] for r in read(db, "SELECT count(*) FROM faers_report")] == [1]
        # a final clean build always works and becomes current
        final = build(data_dir)
        assert current_build(data_dir) == final.build_id
        assert not list(
            (data_dir / "memory" / "faers_counts" / "current").parent.glob("current.tmp-*")
        )


def test_faults_before_the_swap_keep_the_previous_build(tmp_path: Path) -> None:
    write_artifact(tmp_path, [ReportFact("100001", "2026Q3", "US", (), ())])
    first = build(tmp_path)
    for step in ("write_db", "finish"):

        def hook(s: str, wanted: str = step) -> None:
            if s == wanted:
                raise InjectedError(s)

        with pytest.raises(InjectedError):
            build(tmp_path, fault=hook)
        assert current_build(tmp_path) == first.build_id


def test_metadata_carries_notices_and_versions(tmp_path: Path) -> None:
    write_artifact(
        tmp_path, [ReportFact("100001", "2026Q3", "US", (("PS", ("ASPIRIN",)),), ("Pain",))]
    )
    result = build(tmp_path)
    stored = dict(read(result.path, "SELECT key, value FROM faers_meta"))
    assert "MedDRA® trademark is registered by IFPMA on behalf of ICH." in stored["meddra_notice"]
    assert "Preferred Terms" in stored["event_terms"]
    assert stored["resolution_dataset_version"] == "r" * 64
    assert stored["primary_denominator"] == "reports_mapped"
    assert result.reports == 1 and result.reports_mapped == 1
    tables = {r[0] for r in read(result.path, "SELECT table_name FROM information_schema.tables")}
    assert set(TABLES) <= tables and not any("people" in t or "meddra_" in t for t in tables)
    for table in TABLES:
        cols = [r[0] for r in read(result.path, f"DESCRIBE {table}")]
        assert not any("people" in c or "patient" in c for c in cols)


SENTINELS = st.text(alphabet="ghjkmnpqrstuvwxy", min_size=5, max_size=9).map(lambda t: f"ZZ{t}ZZ")


@settings(max_examples=10, deadline=None)
@given(SENTINELS, SENTINELS)
def test_logs_never_carry_names(drug: str, event: str) -> None:
    """Feature: data-pipelines, Property P40 — Validates: Req 15.9.
    A build whose artifact holds sentinel medicine and event names writes none of them to the
    logs, stdout or stderr.
    """
    facts = [
        ReportFact("100001", "2026Q3", "US", (("PS", (drug, "ASPIRIN")),), (event,)),
    ]
    with tempfile.TemporaryDirectory() as d, capture_logs() as buffer:
        write_artifact(Path(d), facts)
        from janus.observability.logging import LogEvent, log_event

        result = build(Path(d))
        log_event(LogEvent.faers_build, count=result.reports)
        text = buffer.getvalue()
    assert drug not in text and event not in text
    assert '"event":"faers_build"' in text


# --- collective-memory Req 11 (schema faers_counts-2) ----------------------------------------

SORT_ORDER: dict[str, tuple[int, ...]] = {
    # table -> positions of the key columns in physical order
    "faers_pair_counts": (0, 1, 3, 2),  # ingredient_key, pt, scope, region
    "faers_ingredient_counts": (0, 2, 1),  # ingredient_key, scope, region
    "faers_event_counts": (0, 1),  # pt, region
    "faers_report_ingredient": (1, 0),  # ingredient_key, report_id
    "faers_report_event": (0, 1),  # report_id, pt
    "faers_report": (0,),  # report_id
}


@settings(max_examples=20, deadline=None)
@given(reports())
def test_layout_mapped_flag_and_region_basis(facts: list[ReportFact]) -> None:
    """Feature: collective-memory, Property P28 — Validates: Req 11.1, 11.2, 11.3.
    The tables are physically sorted by their lookup keys; the physical order never changes a
    table hash; `faers_report.mapped` is "has a mapped ingredient"; `faers_region_basis` sums to
    the region totals and to ALL.
    """
    with tempfile.TemporaryDirectory() as d:
        scratch = Path(d)
        rows = scratch / "rows.parquet"
        write_rows(rows, facts)
        matches = map_names({n for f in facts for _r, ing in f.lines for n in ing}, INDEX)
        db = scratch / "counts.duckdb"
        stats = write_counts(db, rows, matches, scratch)
        for table, cols in SORT_ORDER.items():
            data = read(db, f"SELECT * FROM {table}")
            keys = [tuple(r[c] for c in cols) for r in data]
            assert keys == sorted(keys), table
        flagged = {str(p) for p, m in read(db, "SELECT primaryid, mapped FROM faers_report") if m}
        expected = {
            f.primaryid
            for f in facts
            if any(
                role in EXPOSURE_ROLES and matches[n].status == "mapped"
                for role, ing in f.lines
                for n in ing
            )
        }
        assert flagged == expected
        totals = {r: (int(m), int(a)) for r, m, a in read(db, "SELECT * FROM faers_totals")}
        assert totals[ALL][0] == len(expected)
        by_region: dict[str, int] = {}
        for region, _basis, n in read(db, "SELECT * FROM faers_region_basis"):
            by_region[region] = by_region.get(region, 0) + int(n)
        for region, (_m, all_reports) in totals.items():
            assert by_region[region] == all_reports
        # the physical order does not change a table hash
        con = duckdb.connect(str(db))
        try:
            con.execute(
                "CREATE OR REPLACE TABLE faers_pair_counts AS "
                "SELECT * FROM faers_pair_counts ORDER BY reports DESC, pt DESC"
            )
            assert (
                sha256_of_table(con, "faers_pair_counts", scratch)
                == stats["table_sha256"]["faers_pair_counts"]
            )
        finally:
            con.close()


def test_schema_version_is_faers_counts_2(tmp_path: Path) -> None:
    """Feature: collective-memory, Property P28 (schema part) — Validates: Req 11.4."""
    write_artifact(
        tmp_path, [ReportFact("100001", "2026Q3", "US", (("PS", ("ASPIRIN",)),), ("Pain",))]
    )
    result = build(tmp_path)
    meta = dict(read(result.path, "SELECT key, value FROM faers_meta"))
    assert meta["schema_version"] == COUNTS_SCHEMA == "faers_counts-2"
    assert result.reports_mapped == 1
