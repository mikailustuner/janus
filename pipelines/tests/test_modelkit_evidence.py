"""Tests for the modelkit_evidence job: seed, unit normalisation, row checks, a run."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import polars as pl
import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.manifest import Outcome
from janus_pipelines.core.registry import load_registry
from janus_pipelines.core.runner import RunContext, run_job
from janus_pipelines.core.store import Store
from janus_pipelines.jobs.modelkit_evidence import (
    SEED_COLUMNS,
    UNITS,
    ModelkitEvidenceJob,
    evidence_row,
    from_si,
    parse_seed,
    to_si,
)
from tests.stub_job import FIXED_NOW

REPO = Path(__file__).resolve().parents[2]
SEED = REPO / "data" / "modelkit" / "evidence_seed.csv"


def base(**changes: str) -> dict[str, str]:
    row = dict.fromkeys(SEED_COLUMNS, "")
    row.update(
        drug_key="exampletine",
        analyte="exampletine",
        analyte_class="parent",
        parameter="t_half",
        value="10",
        statistic="stated",
        unit="h",
        route="oral",
        regimen="single",
        formulation="immediate_release",
        coadministered="false",
        study_id="S1",
        source_id="dailymed_spl",
        source_locator="loc",
        source_version="v1",
        quote="a sentence",
        reader_a="agree",
        reader_b="agree",
        confirm_reason="both agree",
        extracted_at="2026-11-11",
    )
    row.update(changes)
    return row


def test_seed_parses_and_derives_confirmed() -> None:
    result = parse_seed(SEED.read_text(encoding="utf-8"))
    assert result.metrics["rows"] == len(result.rows) > 50
    drugs = set(result.metrics["by_drug"])  # type: ignore[arg-type]
    assert drugs == {
        "dolutegravir",
        "ertugliflozin",
        "gabapentin",
        "sunitinib",
        "tramadol",
        "telmisartan",
    }
    for r in result.rows:
        both = r["reader_a"] == "agree" and r["reader_b"] == "agree"
        assert r["confirmed"] == (both and r["analyte_class"] == "parent")
        assert r["quote"] and r["source_locator"]
    assert any(not r["confirmed"] for r in result.rows)  # disagreements stay in the store


def test_seed_is_small_and_has_no_raw_dumps() -> None:
    assert SEED.stat().st_size < 1_000_000
    for line in csv.DictReader(io.StringIO(SEED.read_text(encoding="utf-8"))):
        assert len(line["quote"]) <= 700


@given(
    st.sampled_from(sorted(UNITS)),
    st.floats(min_value=1e-6, max_value=1e9, allow_nan=False, allow_infinity=False),
    st.data(),
)
def test_unit_conversion_reverses(parameter: str, value: float, data: st.DataObject) -> None:
    unit = data.draw(st.sampled_from(sorted(UNITS[parameter][1])))
    back = from_si(parameter, to_si(parameter, value, unit), unit)
    assert back == pytest.approx(value, rel=1e-9)


def test_known_conversions() -> None:
    assert to_si("cl_f", 208.8, "mL/min") == pytest.approx(12.528)
    assert to_si("f", 60, "%") == pytest.approx(0.6)
    assert to_si("auc_inf", 3000, "h*ug/L") == 3000


def test_unit_not_allowed_for_parameter() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        to_si("t_half", 3, "L")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"unit": "L"}, "dimension_mismatch"),
        ({"parameter": "bogus"}, "parameter"),
        ({"value": "-1"}, "positive"),
        ({"reader_a": "yes"}, "reader_a"),
        ({"quote": " "}, "quote"),
        ({"statistic": "range_geomean"}, "range"),
        ({"parameter": "cmax", "unit": "ng/mL"}, "dose"),
        ({"route": "rectal"}, "route"),
        ({"drug_key": "Bad Key"}, "drug_key"),
        ({"extracted_at": "yesterday"}, "extracted_at"),
    ],
)
def test_bad_rows_are_refused(changes: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        evidence_row(base(**changes), "line")


def test_range_must_match_its_bounds() -> None:
    good = base(value="8.4853", value_low="6", value_high="12", statistic="range_geomean")
    assert evidence_row(good, "l")["value_low"] == 6.0
    with pytest.raises(ValueError, match="geometric mean"):
        evidence_row(
            base(value="9", value_low="6", value_high="12", statistic="range_geomean"), "l"
        )


def test_a_metabolite_or_one_disagreement_is_not_confirmed() -> None:
    assert evidence_row(base(), "l")["confirmed"] is True
    assert evidence_row(base(reader_b="disagree"), "l")["confirmed"] is False
    assert evidence_row(base(analyte_class="metabolite"), "l")["confirmed"] is False


def test_duplicate_row_is_refused() -> None:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=SEED_COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows([base(), base()])
    with pytest.raises(ValueError, match="duplicate"):
        parse_seed(out.getvalue())


def test_header_must_match() -> None:
    with pytest.raises(ValueError, match="header"):
        parse_seed("a,b\n1,2\n")


def test_run_writes_a_versioned_artifact(tmp_path: Path) -> None:
    ctx = RunContext(
        data_dir=tmp_path / "data_dir",
        repo_root=REPO,
        registry=load_registry(REPO / "pipelines" / "sources.toml"),
        code_version="test",
        now=lambda: FIXED_NOW,
        is_ignored=lambda _p: True,
    )
    result = run_job(ModelkitEvidenceJob(), ctx)
    assert result.outcome in (Outcome.SUCCEEDED, Outcome.NEEDS_REVIEW)
    store = Store(ctx.data_dir, "modelkit_evidence")
    assert store.current_run_id() == result.run_id
    df = pl.read_parquet(store.run_dir(result.run_id) / "rows.parquet")
    assert df.height == result.manifest.counts.output
    assert df["confirmed"].sum() > 0
    assert result.manifest.license.startswith("Per row")
