"""Tests for the us_label_interactions job. Synthetic openFDA-shaped files only; no network."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.manifest import Outcome
from janus_pipelines.core.registry import load_registry
from janus_pipelines.core.runner import RawInput, RunContext, run_job
from janus_pipelines.core.store import Store
from janus_pipelines.core.validation import SchemaMismatchError
from janus_pipelines.jobs import us_label_interactions as job
from janus_pipelines.jobs.us_label_interactions import (
    Payload,
    UsLabelInteractionsJob,
    iter_results_stream,
    label_row,
    newer,
    parse_partitions,
)
from tests.stub_job import FIXED_NOW

REPO = Path(__file__).resolve().parents[2]
BASE = "https://download.open.fda.gov/drug/label/"

# Invented labels in the published shape (no real label text).
SAMPLE: dict[str, Any] = {
    "set_id": "00000000-0000-4000-8000-000000000001",
    "id": "x1",
    "version": "7",
    "effective_time": "20260105",
    "drug_interactions": [
        "7 DRUG INTERACTIONS Exampletine may raise the level of otherdrug. Monitor closely."
    ],
    "indications_and_usage": ["Not carried."],
    "openfda": {
        "substance_name": ["EXAMPLETINE HYDROCHLORIDE"],
        "product_type": ["HUMAN PRESCRIPTION DRUG"],
        "generic_name": ["EXAMPLETINE"],
    },
}


def label(n: int, **changes: Any) -> dict[str, Any]:
    return {**SAMPLE, "set_id": f"00000000-0000-4000-8000-{n:012d}", **changes}


def _index(counts: list[int]) -> bytes:
    parts = [
        {"file": f"{BASE}drug-label-{i + 1:04d}-of-{len(counts):04d}.json.zip", "records": c}
        for i, c in enumerate(counts)
    ]
    return json.dumps(
        {"results": {"drug": {"label": {"export_date": "2026-11-09", "partitions": parts}}}}
    ).encode()


def _write(
    folder: Path, partitions: list[list[dict[str, Any]]], listed: list[int] | None = None
) -> tuple[bytes, tuple[Path, ...]]:
    folder.mkdir(parents=True, exist_ok=True)
    counts = [len(p) for p in partitions] if listed is None else listed
    (folder / "download.json").write_bytes(_index(counts))
    paths: list[Path] = []
    for i, records in enumerate(partitions):
        name = f"drug-label-{i + 1:04d}-of-{len(partitions):04d}.json"
        doc = {"meta": {"results": {"total": len(records)}}, "results": records}
        path = folder / f"{name}.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(name, json.dumps(doc, indent=1))
        paths.append(path)
    return (folder / "download.json").read_bytes(), tuple(paths)


def _ctx(tmp_path: Path, **options: str) -> RunContext:
    return RunContext(
        data_dir=tmp_path / "data_dir",
        repo_root=tmp_path / "repo",
        registry=load_registry(REPO / "pipelines" / "sources.toml"),
        code_version="test",
        now=lambda: FIXED_NOW,
        is_ignored=lambda _p: True,
        options=dict(options),
    )


# --- the stream reader ------------------------------------------------------------------------

values = st.recursive(
    st.none() | st.booleans() | st.integers(-999, 999) | st.text(max_size=12),
    lambda inner: st.lists(inner, max_size=3) | st.dictionaries(st.text(max_size=4), inner),
    max_leaves=8,
)
records = st.lists(st.dictionaries(st.text(max_size=6), values, max_size=4), max_size=6)


@given(records, values, st.integers(1, 40), st.sampled_from([None, 1]))
def test_stream_reader_equals_json_loads_for_any_piece_size(
    recs: list[dict[str, Any]], meta: Any, size: int, indent: int | None
) -> None:
    """Validates: safety-check Req 3.2 — the records do not depend on where a piece ends."""
    text = json.dumps({"meta": {"results": meta}, "results": recs, "after": meta}, indent=indent)
    pieces = io.StringIO(text)
    assert list(iter_results_stream(lambda _n: pieces.read(size))) == recs


def test_stream_reader_refuses_other_documents() -> None:
    for text in ("[]", '{"meta": {}}', '{"results": {}}'):
        with pytest.raises(SchemaMismatchError):
            list(iter_results_stream(io.StringIO(text).read))
    with pytest.raises(ValueError, match=r"results array|not valid JSON"):
        list(iter_results_stream(io.StringIO('{"results": [{"a": 1}, {"b"').read))


# --- which labels are kept --------------------------------------------------------------------


def test_label_row_keeps_the_section_as_published() -> None:
    row, reason = label_row(label(1, drug_interactions=["  First part. ", "", "Second part."]))
    assert reason is None and row is not None
    assert row == {
        "substance_name": "EXAMPLETINE HYDROCHLORIDE",
        "set_id": "00000000-0000-4000-8000-000000000001",
        "version": "7",
        "effective_date": "2026-01-05",
        "product_type": "HUMAN PRESCRIPTION DRUG",
        "text": "First part.\nSecond part.",
    }


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"drug_interactions": []}, "no_interactions_section"),
        ({"drug_interactions": ["  "]}, "no_interactions_section"),
        ({"drug_interactions": None}, "no_interactions_section"),
        ({"set_id": " "}, "no_set_id"),
        ({"openfda": {}}, "no_substance_name"),
        ({"openfda": None}, "no_substance_name"),
        ({"openfda": {"substance_name": ["A", "B"]}}, "several_substances"),
    ],
)
def test_label_row_exclusions(changes: dict[str, Any], reason: str) -> None:
    """Validates: safety-check Req 3.3 — a section and exactly one active substance."""
    assert label_row({**SAMPLE, **changes}) == (None, reason)


@given(st.permutations([("20260105", 3), ("20260301", 2), ("20260301", 1), ("", 4), ("x", 5)]))
def test_the_newest_label_of_a_substance_is_kept_for_any_order(order: list[Any]) -> None:
    """Validates: safety-check Req 3.3, DP-S7 — latest effective date, then the smaller set id."""
    labels = [label(n, effective_time=date) for date, n in order]
    best: Any = None
    for rec in labels:
        row, _ = label_row(rec)
        assert row is not None
        if best is None or newer(row, best):
            best = row
    assert best is not None and best["set_id"].endswith("1")
    assert best["effective_date"] == "2026-03-01"


def test_run_from_local_partitions(tmp_path: Path) -> None:
    """Validates: safety-check Req 3.2-3.4 — streamed partitions, one row per substance, the
    manifest, nothing but the index kept."""
    other = label(
        9,
        openfda={"substance_name": ["OTHERDRUG"], "product_type": ["HUMAN OTC DRUG"]},
        drug_interactions=["Otherdrug text."],
        effective_time="2025",
    )
    partitions: list[list[dict[str, Any]]] = [
        [label(1), label(2, effective_time="20260201"), {**SAMPLE, "drug_interactions": []}],
        [other, label(3, openfda={"substance_name": ["A", "B"]}), label(4, openfda={})],
    ]
    folder = tmp_path / "input"
    _write(folder, partitions)
    ctx = _ctx(tmp_path, input=str(folder))
    result = run_job(UsLabelInteractionsJob(), ctx)
    assert result.outcome is Outcome.SUCCEEDED, result.error
    rows: Any = Store(ctx.data_dir, "us_label_interactions").read_rows(result.run_id)
    assert [(r["substance_name"], r["set_id"][-1], r["labels_of_substance"]) for r in rows] == [
        ("EXAMPLETINE HYDROCHLORIDE", "2", 2),
        ("OTHERDRUG", "9", 1),
    ]
    assert rows[1]["effective_date"] is None and rows[1]["product_type"] == "HUMAN OTC DRUG"
    assert rows[0]["text"] == SAMPLE["drug_interactions"][0]
    m = result.manifest
    assert (m.schema_version, m.source_id) == (
        "us_label_interactions-1",
        "openfda_label_interactions",
    )
    assert (m.license, m.snapshot_date, m.region) == ("CC0 1.0 (public domain)", "2026-11-09", "US")
    assert m.counts.input == 6 and m.counts.output == 2
    assert m.counts.excluded == {
        "no_interactions_section": 1,
        "older_label_of_the_substance": 1,
        "several_substances": 1,
        "no_substance_name": 1,
    }
    assert m.metrics["substances"] == 2 and m.metrics["labels"] == 6
    raw = ctx.data_dir / "raw" / "us_label_interactions" / result.run_id
    assert sorted(p.name for p in raw.iterdir()) == ["download.json"]  # no partition is kept


def test_count_mismatch_fails(tmp_path: Path) -> None:
    """Validates: safety-check Req 3.4."""
    index, paths = _write(tmp_path / "input", [[label(1)]], listed=[2])
    with pytest.raises(ValueError, match="download index lists 2"):
        parse_partitions(index, paths)
    result = run_job(UsLabelInteractionsJob(), _ctx(tmp_path, input=str(tmp_path / "input")))
    assert result.outcome is Outcome.FAILED


def test_download_writes_partitions_to_scratch_one_at_a_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validates: safety-check Req 3.2 — bulk download, the scratch directory is removed."""
    index, paths = _write(tmp_path / "served", [[label(1)], [label(2, effective_time="20270101")]])
    served: dict[str, bytes] = {job.INDEX_URL: index} | {
        f"{BASE}{p.name}": p.read_bytes() for p in paths
    }
    asked: list[str] = []

    class Response:
        def __init__(self, content: bytes) -> None:
            self.content = content

    class Fetcher:
        def get(self, url: str, **_: Any) -> Response:
            asked.append(url)
            return Response(served[url])

    def make_fetcher(**_: Any) -> Fetcher:
        return Fetcher()

    monkeypatch.setattr(job, "make_fetcher", make_fetcher)
    ctx = _ctx(tmp_path)
    result = run_job(UsLabelInteractionsJob(), ctx)
    assert result.outcome is Outcome.SUCCEEDED, result.error
    assert asked == list(served)
    rows: Any = Store(ctx.data_dir, "us_label_interactions").read_rows(result.run_id)
    assert [r["set_id"][-1] for r in rows] == ["2"]
    assert not (ctx.data_dir / "staging" / "us_label_interactions" / "_scratch").exists()
    assert result.manifest.source_urls == list(served)


def test_payload_is_paths_not_bytes(tmp_path: Path) -> None:
    index, paths = _write(tmp_path / "input", [[label(1)]])
    raw: RawInput[Payload] = UsLabelInteractionsJob().fetch(
        _ctx(tmp_path, input=str(tmp_path / "input"))
    )
    assert raw.payload == Payload(index, paths) and raw.snapshot_date == "2026-11-09"
    assert set(raw.raw_files) == {"download.json"}
