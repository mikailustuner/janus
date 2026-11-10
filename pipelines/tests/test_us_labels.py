"""Tests for the us_labels job. Synthetic openFDA-shaped files only; no network."""

from __future__ import annotations

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
from janus_pipelines.jobs.us_labels import (
    Payload,
    Reduction,
    UsLabelsJob,
    record_row,
    reduce_to_parts,
)
from tests.stub_job import FIXED_NOW

REPO = Path(__file__).resolve().parents[2]
ZIP_URL = "https://download.open.fda.gov/drug/label/drug-label-0001-of-0001.json.zip"
SET_ID = "0a000000-0000-4000-8000-00000000000a"

# Invented label in the published shape (no real product).
SAMPLE: dict[str, Any] = {
    "set_id": SET_ID,
    "id": "0f000000-0000-4000-8000-00000000000f",
    "version": "7",
    "effective_time": "20260129",
    "indications_and_usage": [
        "1 INDICATIONS AND USAGE  Exampletine (invented) is indicated for hypertension. ",
        "Limitations of Use: none.",
    ],
    "dosage_and_administration": ["2 DOSAGE AND ADMINISTRATION Take ZZDOSE."],
    "warnings": ["ZZWARNING"],
    "openfda": {
        "spl_set_id": [SET_ID],
        "product_ndc": ["99999-124", "99999-123"],
        "product_type": ["HUMAN PRESCRIPTION DRUG"],
        "application_number": ["NDA999999"],
        "brand_name": ["Exampletine"],
    },
}


def _label(n: int, **over: Any) -> dict[str, Any]:
    set_id = f"{n:08x}-0000-4000-8000-000000000000"
    openfda: dict[str, Any] = {**SAMPLE["openfda"], "spl_set_id": [set_id]}
    openfda |= over.pop("openfda", {})
    return {**SAMPLE, "set_id": set_id, "openfda": openfda, **over}


def _index(records: int) -> bytes:
    return json.dumps(
        {
            "results": {
                "drug": {
                    "label": {
                        "export_date": "2026-11-09",
                        "partitions": [{"file": ZIP_URL, "size_mb": "0.1", "records": records}],
                    }
                }
            }
        }
    ).encode()


def _zip(records: list[dict[str, Any]]) -> bytes:
    doc = {"meta": {"last_updated": "2026-11-09", "results": {"total": 1}}, "results": records}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("drug-label-0001-of-0001.json", json.dumps(doc, indent=1))
    return buf.getvalue()


def _raw(tmp: Path, records: list[dict[str, Any]], listed: int | None = None) -> RawInput[Payload]:
    scratch = tmp / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    parts, state = reduce_to_parts([_zip(records)], scratch)
    return RawInput(
        payload=Payload(_index(len(records) if listed is None else listed), parts, state, scratch),
        source_urls=("https://api.fda.gov/download.json", ZIP_URL),
        source_sha256="x" * 64,
        retrieved_at=FIXED_NOW,
        snapshot_date="2026-11-09",
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


def test_one_section_as_published(tmp_path: Path) -> None:
    """Validates: plain-medicine-info Req 3.1, 3.2 (L1, L3) — the section kept exactly, nothing
    else of the label carried, licence and data date in the manifest."""
    ctx = _ctx(tmp_path)
    result = run_job(UsLabelsJob(), ctx, _raw(tmp_path, [SAMPLE, _label(2, version=" ")]))
    assert result.outcome is Outcome.SUCCEEDED, result.error
    rows = {r["set_id"]: r for r in Store(ctx.data_dir, "us_labels").read_rows(result.run_id)}
    first = rows[SET_ID]
    assert first["indications"] == SAMPLE["indications_and_usage"]  # inner and outer spaces kept
    assert first["product_ndcs"] == ["99999-123", "99999-124"]
    assert (first["version"], first["effective_date"]) == ("7", "2026-01-29")
    assert first["product_type"] == "HUMAN PRESCRIPTION DRUG"
    assert set(first) == {
        "set_id",
        "version",
        "effective_date",
        "product_type",
        "product_ndcs",
        "indications",
    }
    assert "ZZ" not in json.dumps(list(rows.values()))  # no dosage, no warnings
    assert rows["00000002-0000-4000-8000-000000000000"]["version"] is None
    manifest = result.manifest
    assert manifest.schema_version == "us_labels-1"
    assert manifest.source_id == "openfda_label_indications"
    assert manifest.license == "CC0 1.0 (public domain)"
    assert manifest.snapshot_date == "2026-11-09" and manifest.region == "US"
    assert manifest.metrics["by_product_type"] == {"HUMAN PRESCRIPTION DRUG": 2}
    assert manifest.metrics["product_ndcs"] == 4
    assert (ctx.data_dir / "raw" / "us_labels" / result.run_id / "download.json").exists()


def test_exclusions_with_reasons(tmp_path: Path) -> None:
    """Validates: Req 3.2 (L1)."""
    records = [
        SAMPLE,
        SAMPLE,
        {**SAMPLE, "set_id": ""},
        _label(3, openfda={"product_ndc": []}),
        {**_label(4), "openfda": None},
        _label(5, openfda={"spl_set_id": [SET_ID]}),
        _label(6, openfda={"product_type": ["CELLULAR THERAPY"]}),
        _label(7, openfda={"application_number": ["M012"]}),
        _label(8, openfda={"application_number": []}),
        _label(9, openfda={"application_number": ["NDA999999", "part341"]}),
        _label(10, indications_and_usage=["  ", ""]),
        {k: v for k, v in _label(11).items() if k != "indications_and_usage"},
        _label(
            12, openfda={"application_number": ["ANDA099999"], "product_type": ["HUMAN OTC DRUG"]}
        ),
        _label(13, openfda={"application_number": ["BLA999999"]}),
    ]
    result = UsLabelsJob().parse(_raw(tmp_path, records))
    assert result.excluded == {
        "duplicate_set_id": 1,
        "no_set_id": 1,
        "no_product_code": 2,
        "set_id_not_linked": 1,
        "other_product_type": 1,
        "no_approved_application": 3,
        "no_indications": 2,
    }
    assert result.input_rows == 14 and result.output_rows == 3
    assert result.metrics["by_product_type"] == {
        "HUMAN OTC DRUG": 1,
        "HUMAN PRESCRIPTION DRUG": 2,
    }


def test_count_mismatch_fails(tmp_path: Path) -> None:
    """Validates: Req 3.3 (L3)."""
    result = run_job(UsLabelsJob(), _ctx(tmp_path), _raw(tmp_path, [SAMPLE], listed=2))
    assert result.outcome is Outcome.FAILED
    assert "download index lists 2" in (result.error or "")


def test_missing_field_is_a_schema_failure(tmp_path: Path) -> None:
    record = {k: v for k, v in SAMPLE.items() if k != "effective_time"}
    result = run_job(UsLabelsJob(), _ctx(tmp_path), _raw(tmp_path, [record]))
    assert result.outcome is Outcome.FAILED


@given(
    st.lists(
        st.text(min_size=1, max_size=40).filter(lambda p: p.strip() != ""), min_size=1, max_size=5
    )
)
def test_paragraphs_are_stored_exactly(paragraphs: list[str]) -> None:
    """Validates: Req 1.3, 3.2 (L2)."""
    row = record_row({**SAMPLE, "indications_and_usage": paragraphs}, Reduction())
    assert row is not None and row["indications"] == paragraphs
