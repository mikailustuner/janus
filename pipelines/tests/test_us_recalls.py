"""Tests for the us_recalls job. Synthetic openFDA-shaped files only; no network."""

from __future__ import annotations

import datetime as dt
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.manifest import Outcome
from janus_pipelines.core.registry import load_registry
from janus_pipelines.core.runner import RawInput, RunContext, run_job
from janus_pipelines.core.store import Store
from janus_pipelines.jobs.us_recalls import UsRecallsJob, iso_date, text_or_none
from tests.stub_job import FIXED_NOW

REPO = Path(__file__).resolve().parents[2]
ZIP_URL = "https://download.open.fda.gov/drug/enforcement/drug-enforcement-0001-of-0001.json.zip"

# Invented record in the published shape (no real recall).
SAMPLE: dict[str, Any] = {
    "status": "Ongoing",
    "classification": "Class II",
    "openfda": {"product_ndc": ["99999-123", "99999-124"]},
    "product_type": "Drugs",
    "event_id": "90001",
    "recalling_firm": "Example Labs (invented)",
    "voluntary_mandated": "Voluntary: Firm initiated",
    "recall_number": "D-0001-2026",
    "product_description": " Exampletine Tablets 10 mg, 30-count bottle, NDC 99999-123-30 ",
    "reason_for_recall": "Failed Dissolution Specifications",
    "recall_initiation_date": "20260105",
    "center_classification_date": "20260120",
    "report_date": "20260128",
    "code_info": "Lot #: AB1234, Exp 06/2027",
}


def _index(records: int, export_date: str = "2026-11-03") -> bytes:
    return json.dumps(
        {
            "results": {
                "drug": {
                    "ndc": {"export_date": "2026-11-06", "partitions": []},
                    "enforcement": {
                        "export_date": export_date,
                        "partitions": [{"file": ZIP_URL, "size_mb": "0.1", "records": records}],
                    },
                }
            }
        }
    ).encode()


def _zip(records: list[dict[str, Any]]) -> bytes:
    doc = {"meta": {"last_updated": "2026-11-03", "results": {"total": 1}}, "results": records}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("drug-enforcement-0001-of-0001.json", json.dumps(doc, indent=1))
    return buf.getvalue()


def _raw(records: list[dict[str, Any]], listed: int | None = None) -> RawInput[Any]:
    return RawInput(
        payload=(_index(len(records) if listed is None else listed), (_zip(records),)),
        source_urls=("https://api.fda.gov/download.json", ZIP_URL),
        source_sha256="x" * 64,
        retrieved_at=FIXED_NOW,
        snapshot_date="2026-11-03",
        raw_files={"download.json": b"{}"},
    )


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(
        data_dir=tmp_path / "data_dir",
        repo_root=tmp_path / "repo",
        registry=load_registry(REPO / "pipelines" / "sources.toml"),
        code_version="test",
        now=lambda: FIXED_NOW,
        is_ignored=lambda _p: True,
    )


def test_record_as_published_with_iso_dates(tmp_path: Path) -> None:
    """Validates: recall-check Req 1.3, 2.1, 2.3 — text kept, dates ISO, licence recorded."""
    terminated = {
        **SAMPLE,
        "recall_number": "D-12-2014",
        "status": "Terminated",
        "termination_date": "20150302",
        "more_code_info": "",
    }
    ctx = _ctx(tmp_path)
    result = run_job(UsRecallsJob(), ctx, _raw([SAMPLE, terminated]))
    assert result.outcome is Outcome.SUCCEEDED, result.error
    rows = {
        r["recall_number"]: r for r in Store(ctx.data_dir, "us_recalls").read_rows(result.run_id)
    }
    first = rows["D-0001-2026"]
    assert first["product_description"] == (
        "Exampletine Tablets 10 mg, 30-count bottle, NDC 99999-123-30"
    )
    assert first["code_info"] == "Lot #: AB1234, Exp 06/2027"
    assert first["reason_for_recall"] == "Failed Dissolution Specifications"
    assert first["status"] == "Ongoing" and first["classification"] == "Class II"
    assert first["recall_initiation_date"] == "2026-01-05"
    assert first["center_classification_date"] == "2026-01-20"
    assert first["report_date"] == "2026-01-28"
    assert first["termination_date"] is None and first["more_code_info"] is None
    assert "openfda" not in first  # openFDA's added block is not carried (design DP-R2)
    assert rows["D-12-2014"]["termination_date"] == "2015-03-02"
    manifest = result.manifest
    assert manifest.schema_version == "us_recalls-1"
    assert manifest.source_id == "openfda_enforcement"
    assert manifest.license == "CC0 1.0 (public domain)"
    assert manifest.snapshot_date == "2026-11-03" and manifest.region == "US"
    assert manifest.metrics["by_status"] == {"Ongoing": 1, "Terminated": 1}
    assert manifest.metrics["first_report_date"] == "2026-01-28"
    assert (ctx.data_dir / "raw" / "us_recalls" / result.run_id / "download.json").exists()


def test_bad_and_repeated_recall_numbers_are_excluded() -> None:
    """Validates: recall-check Req 2.2."""
    result = UsRecallsJob().parse(
        _raw([SAMPLE, {**SAMPLE, "recall_number": ""}, {**SAMPLE, "recall_number": "N/A"}, SAMPLE])
    )
    assert result.excluded == {"invalid_recall_number": 2, "duplicate_recall_number": 1}
    assert result.input_rows == 4 and len(result.rows) == 1


def test_count_mismatch_fails(tmp_path: Path) -> None:
    """Validates: recall-check Req 2.4."""
    result = run_job(UsRecallsJob(), _ctx(tmp_path), _raw([SAMPLE], listed=2))
    assert result.outcome is Outcome.FAILED
    assert result.error is not None and "lists 2" in result.error


def test_renamed_field_is_schema_failure(tmp_path: Path) -> None:
    renamed = {("lots" if k == "code_info" else k): v for k, v in SAMPLE.items()}
    result = run_job(UsRecallsJob(), _ctx(tmp_path), _raw([renamed]))
    assert result.outcome is Outcome.FAILED
    assert result.error is not None and "code_info" in result.error


def test_missing_enforcement_index_is_schema_failure(tmp_path: Path) -> None:
    raw = RawInput(
        payload=(b'{"results": {"drug": {"ndc": {}}}}', ()),
        source_urls=(),
        source_sha256="x",
        retrieved_at=FIXED_NOW,
        snapshot_date=None,
    )
    result = run_job(UsRecallsJob(), _ctx(tmp_path), raw)
    assert result.outcome is Outcome.FAILED
    assert result.error is not None and "enforcement" in result.error


def test_invalid_date_is_null_and_counted() -> None:
    """Validates: recall-check Req 2.5."""
    result = UsRecallsJob().parse(_raw([{**SAMPLE, "report_date": "20261341"}]))
    assert result.rows[0]["report_date"] is None
    assert result.metrics["invalid_dates"] == 1


@given(st.dates(min_value=dt.date(1900, 1, 1)))
def test_iso_date_round_trips_every_real_date(day: dt.date) -> None:
    """Validates: recall-check Req 2.1 — YYYYMMDD → the same day as an ISO date."""
    assert iso_date(day.strftime("%Y%m%d")) == day.isoformat()


@given(st.text(max_size=12))
def test_iso_date_never_invents_a_date(text: str) -> None:
    """Validates: recall-check Req 2.5 — anything else is null, never a guessed date."""
    out = iso_date(text)
    if out is not None:
        assert dt.date.fromisoformat(out).strftime("%Y%m%d") == text.strip()


@given(st.text(max_size=40))
def test_text_is_kept_as_published(text: str) -> None:
    """Validates: recall-check Req 2.3 — only surrounding whitespace goes; empty is null."""
    out = text_or_none(text)
    assert out == (text.strip() or None)
