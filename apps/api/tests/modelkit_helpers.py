"""Shared helpers of the model kit tests: synthetic evidence rows, the committed seed as rows and a
temporary release directory (what the pipeline job writes, built here with DuckDB)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import duckdb

from janus.modelkit.evidence import COLUMNS, Ev, ev_from_mapping
from janus.paths import repo_root

SEED = repo_root() / "data" / "modelkit" / "evidence_seed.csv"
RUN_ID = "20261111T120000Z-0a1b2c3d-0001"
# Same factors as the pipeline job (pipelines/janus_pipelines/jobs/modelkit_evidence.py).
_ML_MIN = 0.06
FACTORS: dict[tuple[str, str], float] = {
    ("cl", "mL/min"): _ML_MIN,
    ("cl_f", "mL/min"): _ML_MIN,
    ("cl_per_kg", "mL/min/kg"): _ML_MIN,
    ("f", "%"): 0.01,
}


def to_si(parameter: str, value: float, unit: str) -> float:
    return value * FACTORS.get((parameter, unit), 1.0)


def _f(text: str) -> float | None:
    return float(text) if text.strip() else None


def seed_dicts() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with SEED.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            both = r["reader_a"] == "agree" and r["reader_b"] == "agree"
            out.append(
                {
                    **r,
                    "value": float(r["value"]),
                    "value_low": _f(r["value_low"]),
                    "value_high": _f(r["value_high"]),
                    "value_si": to_si(r["parameter"], float(r["value"]), r["unit"]),
                    "dose": _f(r["dose"]),
                    "dose_unit": r["dose_unit"] or None,
                    "interval_h": _f(r["interval_h"]),
                    "population": r["population"] or None,
                    "n_subjects": int(r["n_subjects"]) if r["n_subjects"] else None,
                    "coadministered": r["coadministered"] == "true",
                    "confirmed": both and r["analyte_class"] == "parent",
                    "note": r["note"] or None,
                    "pipeline_version": "modelkit-evidence-1.0",
                }
            )
    return out


def seed_rows() -> list[Ev]:
    return [ev_from_mapping(d) for d in seed_dicts()]


def write_run(data_dir: Path, rows: list[dict[str, Any]]) -> Path:
    """`<data_dir>/artifacts/modelkit_evidence/runs/<id>` with rows.parquet and manifest.json and a
    `current` link, as the pipeline runner leaves it."""
    base = data_dir / "artifacts" / "modelkit_evidence"
    run = base / "runs" / RUN_ID
    run.mkdir(parents=True)
    jsonl = run / "rows.jsonl"
    jsonl.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    con = duckdb.connect()
    cols = ", ".join(COLUMNS)
    con.execute(
        f"COPY (SELECT {cols} FROM read_json_auto(?, sample_size=-1)) "  # noqa: S608
        f"TO '{run / 'rows.parquet'}' (FORMAT parquet)",
        [str(jsonl)],
    )
    con.close()
    jsonl.unlink()
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "outcome": "succeeded",
                "source_id": "modelkit_evidence",
                "schema_version": "modelkit_evidence-1",
                "run_id": RUN_ID,
                "snapshot_date": "2026-11-11",
                "license": "Per row: each row keeps the terms of its own source",
                "metrics": {},
            }
        ),
        encoding="utf-8",
    )
    (base / "current").symlink_to(run)
    return run


_DEFAULTS: dict[str, Any] = {
    "drug_key": "exampletine", "analyte": "exampletine", "analyte_class": "parent",
    "parameter": "t_half", "value": 10.0, "value_low": None, "value_high": None,
    "statistic": "stated", "unit": "h", "value_si": 10.0, "dose": None, "route": "oral",
    "regimen": "single", "interval_h": None, "population": "healthy adults", "n_subjects": 12,
    "formulation": "immediate_release", "coadministered": False, "study_id": "S1",
    "source_id": "clinicaltrials_gov", "source_locator": "loc", "source_version": "v",
    "quote": "q", "reader_a": "agree", "reader_b": "agree", "confirmed": True,
    "confirm_reason": "both agree", "note": None, "extracted_at": "2026-11-11",
}  # fmt: skip


def ev(**changes: Any) -> Ev:
    """One synthetic evidence row; `value_si` follows `value` unless given."""
    d = {**_DEFAULTS, **changes}
    if "value_si" not in changes:
        d["value_si"] = d["value"]
    if "source_locator" not in changes:
        d["source_locator"] = (
            f"{d['study_id']}/{d['parameter']}/{d['value']}/{d['route']}/{d['dose']}"
        )
    return ev_from_mapping(d)
