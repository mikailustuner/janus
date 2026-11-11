"""CL/F = dose / AUC(0-inf), labelled derived, for one study arm only."""

from __future__ import annotations

from typing import Any

import pytest

from janus_pipelines.jobs.modelkit_evidence import SEED_COLUMNS_FULL, evidence_row
from janus_pipelines.modelkit.derive import derive_clearance


def auc_row(**changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "drug_key": "exampletine", "analyte": "exampletine", "analyte_class": "parent",
        "parameter": "auc_inf", "value": 1350.0, "value_low": None, "value_high": None,
        "statistic": "geomean", "unit": "ng*h/mL", "value_si": 1350.0, "dose": 50.0,
        "dose_unit": "mg", "route": "oral", "regimen": "single", "interval_h": None,
        "population": "healthy adults", "n_subjects": 12, "formulation": "immediate_release",
        "coadministered": False, "study_id": "NCT00000001", "source_id": "clinicaltrials_gov",
        "source_locator": "NCT00000001#outcome-1/OG000", "source_version": "v", "quote": "q",
        "reader_a": "agree", "reader_b": "agree", "confirmed": True, "confirm_reason": "both",
        "note": None, "extracted_at": "2026-11-11", "arm_id": "OG000", "origin": "reader_pair",
        "derivation": None, "evidence_kind": "pk", "food": "fasted", "dispersion_type": "none",
        "dispersion_low": None, "dispersion_high": None,
    }  # fmt: skip
    row.update(changes)
    return row


def test_cl_f_is_dose_over_auc_and_labelled_derived() -> None:
    [d] = derive_clearance([auc_row()])
    assert d["parameter"] == "cl_f" and d["origin"] == "derived"
    assert d["value"] == pytest.approx(50.0 * 1000.0 / 1350.0)  # 37.04 L/h
    assert d["unit"] == "L/h" and "dose / AUC" in d["derivation"]
    assert d["source_locator"].endswith("#derived-cl_f")
    assert d["confirmed"] is True  # it inherits the confirmation of its AUC row


def test_intravenous_dose_gives_cl() -> None:
    [d] = derive_clearance([auc_row(route="iv", dose=10.0, value_si=500.0)])
    assert d["parameter"] == "cl" and d["value"] == pytest.approx(10.0 * 1000.0 / 500.0)


def test_nothing_is_derived_without_the_same_arm_dose_or_confirmation() -> None:
    for change in (
        {"arm_id": ""}, {"arm_id": None}, {"dose": None}, {"confirmed": False},
        {"regimen": "multiple"}, {"coadministered": True}, {"analyte_class": "metabolite"},
        {"route": "unknown"}, {"parameter": "auc_last"}, {"evidence_kind": "interaction"},
        {"origin": "derived"},
    ):  # fmt: skip
        assert derive_clearance([auc_row(**change)]) == [], change


def test_a_derived_row_passes_the_job_checks() -> None:
    [d] = derive_clearance([auc_row()])
    raw = {k: ("" if v is None else str(v)) for k, v in d.items() if k in SEED_COLUMNS_FULL}
    raw["coadministered"] = "false"
    raw["dose_unit"] = "mg"
    out = evidence_row(raw, "test")
    assert out["origin"] == "derived" and out["parameter"] == "cl_f"
    assert out["value_si"] == pytest.approx(d["value_si"])
