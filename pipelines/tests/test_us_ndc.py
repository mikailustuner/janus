"""Tests for the us_ndc job. Synthetic openFDA-shaped files only; no network."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest

from janus_pipelines.core.manifest import Outcome
from janus_pipelines.core.registry import load_registry
from janus_pipelines.core.runner import RawInput, RunContext, run_job
from janus_pipelines.core.store import Store
from janus_pipelines.jobs.us_ndc import UsNdcJob, iter_results
from tests.stub_job import FIXED_NOW

REPO = Path(__file__).resolve().parents[2]
ZIP_URL = "https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip"

SAMPLE: dict[str, Any] = {
    "product_ndc": "0071-0155",
    "generic_name": "Atorvastatin Calcium",
    "brand_name": "Lipitor",
    "product_type": "HUMAN PRESCRIPTION DRUG",
    "marketing_end_date": None,
    "active_ingredients": [{"name": "ATORVASTATIN CALCIUM TRIHYDRATE", "strength": "10 mg/1"}],
    "packaging": [
        {"package_ndc": "0071-0155-23", "description": "90 TABLET in 1 BOTTLE"},
        {"package_ndc": "0071-0155-40", "description": "5000 TABLET in 1 BOTTLE"},
    ],
    "openfda": {"rxcui": ["617310", "617312"], "manufacturer_name": ["Pfizer"]},
}


def _index(records: int, export_date: str = "2026-11-06") -> bytes:
    return json.dumps(
        {
            "results": {
                "drug": {
                    "ndc": {
                        "export_date": export_date,
                        "partitions": [{"file": ZIP_URL, "size_mb": "0.1", "records": records}],
                    }
                }
            }
        }
    ).encode()


def _zip(records: list[dict[str, Any]]) -> bytes:
    doc = {"meta": {"last_updated": "2026-11-05"}, "results": records}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("drug-ndc-0001-of-0001.json", json.dumps(doc, indent=1))
    return buf.getvalue()


def _raw(records: list[dict[str, Any]], listed: int | None = None) -> RawInput[Any]:
    return RawInput(
        payload=(_index(len(records) if listed is None else listed), (_zip(records),)),
        source_urls=("https://api.fda.gov/download.json", ZIP_URL),
        source_sha256="x" * 64,
        retrieved_at=FIXED_NOW,
        snapshot_date="2026-11-06",
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


def test_count_mismatch_fails(tmp_path: Path) -> None:
    """Validates: Req 8.2."""
    result = run_job(UsNdcJob(), _ctx(tmp_path), _raw([SAMPLE], listed=2))
    assert result.outcome is Outcome.FAILED
    assert result.error is not None and "lists 2" in result.error


def test_sample_record_as_published(tmp_path: Path) -> None:
    """Validates: Req 8.3, 8.4 — fields as published, NDC not normalised; raw files cached."""
    second = {"product_ndc": "12345-678", "product_type": "HUMAN OTC DRUG", "generic_name": "X"}
    ctx = _ctx(tmp_path)
    result = run_job(UsNdcJob(), ctx, _raw([SAMPLE, second]))
    assert result.outcome is Outcome.SUCCEEDED, result.error
    rows = Store(ctx.data_dir, "us_ndc").read_rows(result.run_id)
    lipitor = next(r for r in rows if r["product_ndc"] == "0071-0155")
    assert lipitor["package_ndcs"] == ["0071-0155-23", "0071-0155-40"]
    assert lipitor["active_ingredients"] == [
        {"name": "ATORVASTATIN CALCIUM TRIHYDRATE", "strength": "10 mg/1"}
    ]
    assert lipitor["rxcuis"] == ["617310", "617312"]
    assert lipitor["brand_name"] == "Lipitor"
    other = next(r for r in rows if r["product_ndc"] == "12345-678")
    assert other["brand_name"] is None and other["package_ndcs"] == []
    assert result.manifest.snapshot_date == "2026-11-06"
    assert (ctx.data_dir / "raw" / "us_ndc" / result.run_id / "download.json").exists()


def test_missing_product_ndc_excluded() -> None:
    result = UsNdcJob().parse(_raw([SAMPLE, {**SAMPLE, "product_ndc": " "}]))
    assert result.excluded == {"missing_product_ndc": 1}
    assert result.input_rows == 2


def test_renamed_field_is_schema_failure(tmp_path: Path) -> None:
    renamed = {("generic" if k == "generic_name" else k): v for k, v in SAMPLE.items()}
    result = run_job(UsNdcJob(), _ctx(tmp_path), _raw([renamed]))
    assert result.outcome is Outcome.FAILED
    assert result.error is not None and "generic_name" in result.error


def test_iter_results_skips_meta_results() -> None:
    """openFDA files carry meta.results ({skip, limit, total}) before the real array."""
    text = (
        '{"meta": {"results": {"skip": 0, "total": 2}, "x": [[1]]},\n'
        ' "results": [ {"a": 1},\n {"a": [2, {"b": "]"}]} ]}'
    )
    assert list(iter_results(text)) == [{"a": 1}, {"a": [2, {"b": "]"}]}]


def test_bad_index_is_schema_failure(tmp_path: Path) -> None:
    raw = RawInput(
        payload=(b'{"results": {}}', ()),
        source_urls=(),
        source_sha256="x",
        retrieved_at=FIXED_NOW,
        snapshot_date=None,
    )
    result = run_job(UsNdcJob(), _ctx(tmp_path), raw)
    assert result.outcome is Outcome.FAILED
    assert result.error is not None and "download.json" in result.error


@pytest.mark.parametrize("bad", ['{"results": [1]}', '{"meta": {}}'])
def test_iter_results_rejects_bad_shape(bad: str) -> None:
    from janus_pipelines.core.validation import SchemaMismatchError

    with pytest.raises(SchemaMismatchError):
        list(iter_results(bad))
