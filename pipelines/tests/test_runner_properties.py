"""Property and example tests for the runner and store (P1, P3, P10)."""

from __future__ import annotations

import hashlib
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    initialize,
    invariant,
    rule,
)

from janus_pipelines.core.canonical import Json, Row, content_hash
from janus_pipelines.core.manifest import Outcome
from janus_pipelines.core.runner import PromotionError, promote_run, run_job
from janus_pipelines.core.store import Store
from tests.strategies import TEXT
from tests.stub_job import (
    STUB_SCHEMA,
    FileStubJob,
    Records,
    StubJob,
    context,
    raw_input,
    snapshot_tree,
)

RECORD = st.fixed_dictionaries(
    {
        "id": TEXT,
        "n": st.one_of(st.none(), st.integers(0, 10**9)),
        "names": st.lists(TEXT, max_size=3),
        "flag": st.booleans(),
    }
)
RECORDS = cast(st.SearchStrategy[Records], st.lists(RECORD, min_size=1, max_size=15))


@given(RECORDS)
def test_runner_is_deterministic(records: Records) -> None:
    """Feature: data-pipelines, Property P1 (runner) — Validates: Req 1.1, 1.2, 1.3.

    The same input run into two fresh data directories gives the same rows and content hash.
    """
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        results = [run_job(StubJob(), context(Path(d)), raw_input(records)) for d in (a, b)]
        assert all(r.outcome is Outcome.SUCCEEDED for r in results)
        hashes = {r.manifest.content_sha256 for r in results}
        assert len(hashes) == 1
        stores = [Store(Path(d), "stub") for d in (a, b)]
        read = [s.read_rows(r.run_id) for s, r in zip(stores, results, strict=True)]
        assert content_hash(cast(list[Row], read[0]), STUB_SCHEMA.version) == hashes.pop()
        assert sorted(map(repr, read[0])) == sorted(map(repr, read[1]))


MUTATIONS = st.sampled_from(["drop", "rename", "retype"])
REQUIRED = st.sampled_from([f.name for f in STUB_SCHEMA.fields])


def _mutate(records: Records, mutation: str, column: str) -> Records:
    out: Records = []
    for r in records:
        m = dict(r)
        if mutation in ("drop", "rename"):
            value = m.pop(column)
            if mutation == "rename":
                m[column.upper() + "_X"] = value
        else:
            # A kind the schema does not allow for this column.
            m[column] = 1.5 if column != "n" else "text"
        out.append(m)
    return out


@given(RECORDS, RECORDS, MUTATIONS, REQUIRED)
def test_schema_mismatch_never_replaces_current(
    first: Records, second: Records, mutation: str, column: str
) -> None:
    """Feature: data-pipelines, Property P3 — Validates: Req 2.1.

    For a valid current artifact and an input with a required column dropped, renamed or
    retyped, the run fails, names the column, and the current artifact is byte-identical.
    """
    with tempfile.TemporaryDirectory() as d:
        data_dir = Path(d)
        ctx = context(data_dir)
        good = run_job(StubJob(), ctx, raw_input(first))
        assert good.outcome is Outcome.SUCCEEDED
        store = Store(data_dir, "stub")
        before = snapshot_tree(store.run_dir(good.run_id))
        current_before = store.current_run_id()

        bad = run_job(StubJob(), ctx, raw_input(_mutate(second, mutation, column)))

        assert bad.outcome is Outcome.FAILED
        assert bad.error is not None and column in bad.error
        assert store.current_run_id() == current_before == good.run_id
        assert snapshot_tree(store.run_dir(good.run_id)) == before
        assert not (store.run_dir(bad.run_id) / "rows.parquet").exists()


FAULT_STEPS = ["write_rows", "write_manifest", "finish", "promote_link", "promote_replace"]


class InjectedFaultError(Exception):
    pass


class AlwaysUsableArtifact(RuleBasedStateMachine):
    """Feature: data-pipelines, Property P10 — Validates: Req 4.2.

    After any sequence of runs (success, schema failure, empty output, crash at any step,
    needs_review, manual promotion), `current` is absent before the first promotion, and
    otherwise points to a complete run whose rows hash to its manifest and which is the
    last promoted run.
    """

    review_runs = Bundle("review_runs")

    @initialize()
    def setup(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name)
        self.fault_at: str | None = None
        self.ctx = context(self.data_dir, fault=self._fault)
        self.store = Store(self.data_dir, "stub")
        self.last_promoted: str | None = None

    def _fault(self, step: str) -> None:
        if step == self.fault_at:
            raise InjectedFaultError(step)

    @rule(records=RECORDS)
    def run_success(self, records: Records) -> None:
        result = run_job(StubJob(), self.ctx, raw_input(records))
        assert result.outcome is Outcome.SUCCEEDED
        self.last_promoted = result.run_id

    @rule(records=RECORDS)
    def run_success_file_backed(self, records: Records) -> None:
        result = run_job(FileStubJob(self.data_dir), self.ctx, raw_input(records))
        assert result.outcome is Outcome.SUCCEEDED
        self.last_promoted = result.run_id

    @rule(records=RECORDS, step=st.sampled_from(FAULT_STEPS))
    def run_crash_file_backed(self, records: Records, step: str) -> None:
        self.fault_at = step
        try:
            result = run_job(FileStubJob(self.data_dir), self.ctx, raw_input(records))
        finally:
            self.fault_at = None
        assert result.outcome is Outcome.FAILED
        assert not self.store.scratch_dir().exists()

    @rule(records=RECORDS, mutation=MUTATIONS, column=REQUIRED)
    def run_schema_failure(self, records: Records, mutation: str, column: str) -> None:
        result = run_job(StubJob(), self.ctx, raw_input(_mutate(records, mutation, column)))
        assert result.outcome is Outcome.FAILED

    @rule()
    def run_empty(self) -> None:
        result = run_job(StubJob(), self.ctx, raw_input([]))
        assert result.outcome is Outcome.FAILED

    @rule(records=RECORDS, step=st.sampled_from(FAULT_STEPS))
    def run_crash(self, records: Records, step: str) -> None:
        self.fault_at = step
        try:
            result = run_job(StubJob(), self.ctx, raw_input(records))
        finally:
            self.fault_at = None
        assert result.outcome is Outcome.FAILED

    @rule(target=review_runs, records=RECORDS)
    def run_needs_review(self, records: Records) -> str:
        result = run_job(StubJob(review_reasons=["forced"]), self.ctx, raw_input(records))
        assert result.outcome is Outcome.NEEDS_REVIEW
        return result.run_id

    @rule(run_id=review_runs)
    def promote_review_run(self, run_id: str) -> None:
        promote_run(StubJob(), self.ctx, run_id, by="maintainer")
        self.last_promoted = run_id

    @invariant()
    def current_is_complete_and_last_promoted(self) -> None:
        if not hasattr(self, "store"):
            return
        current = self.store.current_run_id()
        assert current == self.last_promoted
        if current is None:
            return
        manifest = self.store.read_manifest(current)
        assert manifest.outcome in (Outcome.SUCCEEDED, Outcome.NEEDS_REVIEW)
        rows = cast(list[Row], self.store.read_rows(current))
        assert content_hash(rows, STUB_SCHEMA.version) == manifest.content_sha256
        assert len(rows) == manifest.counts.output

    def teardown(self) -> None:
        if hasattr(self, "_tmp"):
            self._tmp.cleanup()


AlwaysUsableArtifact.TestCase.settings = settings(
    AlwaysUsableArtifact.TestCase.settings, stateful_step_count=25
)
TestAlwaysUsableArtifact = AlwaysUsableArtifact.TestCase


def _records(n: int) -> Records:
    return [{"id": f"r{i}", "n": i, "names": ["a"], "flag": True} for i in range(n)]


def test_needs_review_not_promoted_then_manual_promote(tmp_path: Path) -> None:
    """Validates: Req 2.2 (DP4) — a big row-count change is not promoted until `promote`."""
    ctx = context(tmp_path)
    first = run_job(StubJob(threshold=Fraction(1, 10)), ctx, raw_input(_records(100)))
    second = run_job(StubJob(threshold=Fraction(1, 10)), ctx, raw_input(_records(50)))
    store = Store(tmp_path, "stub")
    assert second.outcome is Outcome.NEEDS_REVIEW
    assert "100 to 50" in second.manifest.review_reasons[0]
    assert store.current_run_id() == first.run_id

    with pytest.raises(PromotionError):
        promote_run(StubJob(), ctx, second.run_id, by="  ")
    promotion = promote_run(StubJob(), ctx, second.run_id, by="mikail")
    assert store.current_run_id() == second.run_id
    assert promotion.promoted_by == "mikail"
    assert promotion.previous_run_id == first.run_id
    assert (store.run_dir(second.run_id) / "promotion.json").exists()


def test_small_change_promotes(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    run_job(StubJob(threshold=Fraction(1, 10)), ctx, raw_input(_records(100)))
    again = run_job(StubJob(threshold=Fraction(1, 10)), ctx, raw_input(_records(105)))
    assert again.outcome is Outcome.SUCCEEDED


def test_failed_run_cannot_be_promoted(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    failed = run_job(StubJob(), ctx, raw_input([]))
    with pytest.raises(PromotionError, match="failed"):
        promote_run(StubJob(), ctx, failed.run_id, by="m")


def test_no_promoted_artifact_means_unavailable(tmp_path: Path) -> None:
    """Validates: Req 4.2 — with no promoted run there is no current artifact."""
    ctx = context(tmp_path)
    run_job(StubJob(), ctx, raw_input([]))
    store = Store(tmp_path, "stub")
    assert store.current_run_id() is None
    assert store.current_manifest() is None


def test_manifest_and_evidence_record(tmp_path: Path) -> None:
    """Validates: Req 1.1, 1.2, 1.4."""
    ctx = context(tmp_path)
    result = run_job(StubJob(), ctx, raw_input(_records(3)))
    store = Store(tmp_path, "stub")
    m = store.read_manifest(result.run_id)
    assert m.run_id == result.run_id
    assert m.license == "CC0"
    assert m.source_sha256 and m.content_sha256
    assert m.counts.input == m.counts.output == 3
    assert m.snapshot_date == "2026-11-07"
    evidence = store.current_evidence()
    assert evidence is not None
    assert evidence.run_id == result.run_id
    assert evidence.source_url == "https://example.org/stub"


def test_unknown_source_is_refused(tmp_path: Path) -> None:
    from janus_pipelines.core.registry import UnknownSourceError

    class Other(StubJob):
        source_id = "not_registered"

    with pytest.raises(UnknownSourceError):
        run_job(Other(), context(tmp_path), raw_input(_records(1)))
    assert not any(tmp_path.iterdir())


def test_rows_type_alias_is_json() -> None:
    value: Json = {"a": [1, "b", None]}
    assert isinstance(value, dict)


@given(RECORDS, st.integers(1, 5), st.integers(0, 4))
def test_file_backed_run_has_same_hash_as_in_memory_run(
    records: Records, row_group: int, side_rows: int
) -> None:
    """Feature: data-pipelines, Property P17 (round-trip part) — Validates: Req 14.2, 1.3.
    Rows written to Parquet by the job, read back in batches and hashed in a stream give the
    hash of the same rows held in memory; the scratch directory is gone afterwards.
    """
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        mem = run_job(StubJob(), context(Path(a)), raw_input(records))
        job = FileStubJob(Path(b), row_group=row_group, side_rows=side_rows)
        file = run_job(job, context(Path(b)), raw_input(records))
        assert mem.outcome is file.outcome is Outcome.SUCCEEDED
        assert mem.manifest.content_sha256 == file.manifest.content_sha256
        assert mem.manifest.counts == file.manifest.counts
        store = Store(Path(b), "stub")
        assert sorted(map(repr, store.read_rows(file.run_id))) == sorted(
            map(repr, Store(Path(a), "stub").read_rows(mem.run_id))
        )
        assert not store.scratch_dir().exists()


@given(RECORDS, st.integers(0, 4), st.integers(0, 4))
def test_side_tables_are_outside_the_hash_and_recorded(
    records: Records, side_a: int, side_b: int
) -> None:
    """Feature: data-pipelines, Property P18 — Validates: Req 14.3, 1.2.
    Side tables never change the content hash; the manifest records each table's row count and
    the SHA-256 of its file; the run's files do not change after the run.
    """
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        ra = run_job(FileStubJob(Path(a), side_rows=side_a), context(Path(a)), raw_input(records))
        rb = run_job(FileStubJob(Path(b), side_rows=side_b), context(Path(b)), raw_input(records))
        assert ra.manifest.content_sha256 == rb.manifest.content_sha256
        for result, d, n in ((ra, a, side_a), (rb, b, side_b)):
            store = Store(Path(d), "stub")
            (table,) = store.read_manifest(result.run_id).side_tables
            path = store.run_dir(result.run_id) / "removed.parquet"
            assert table.name == "removed" and table.rows == n
            assert table.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
            before = snapshot_tree(store.run_dir(result.run_id))
            run_job(FileStubJob(Path(d)), context(Path(d)), raw_input(records))
            assert snapshot_tree(store.run_dir(result.run_id)) == before


def test_a_run_without_urls_keeps_the_registry_urls(tmp_path: Path) -> None:
    """A derived job (the model kit) fetches nothing itself and names no URL; the manifest and the
    evidence record then carry the registry's URLs, so the integrity loader can cite the source."""
    from dataclasses import replace

    raw = replace(raw_input(_records(3)), source_urls=())
    result = run_job(StubJob(), context(tmp_path), raw)
    assert result.outcome is Outcome.SUCCEEDED
    assert result.manifest.source_urls == ["https://example.org/stub"]
    evidence = (Store(tmp_path, "stub").run_dir(result.run_id) / "evidence_source.json").read_text()
    assert '"source_url": "https://example.org/stub"' in evidence
