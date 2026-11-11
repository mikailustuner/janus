"""`modelkit_evidence` pipeline: the evidence store of the drug model kit (spec model-kit).

Reads the small committed seed `data/modelkit/evidence_seed.csv` (one row per fact: value as the
source states it, locator, quote, two reader verdicts), checks every row, normalises units to
canonical ones, derives `confirmed` (both readers agree and the analyte is the parent drug) and
writes the versioned artifact. No network access: the seed is the input. Research use only.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import ClassVar, Final

import polars as pl

from janus_pipelines.core.canonical import Json, Row, sha256_bytes
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import ExpectedSchema, Field, SchemaReport
from janus_pipelines.modelkit.units import Canonical, to_canonical

SCHEMA_VERSION: Final = "modelkit_evidence-2"
PIPELINE_VERSION: Final = "modelkit-evidence-1.0"
SEED_PATH: Final = ("data", "modelkit", "evidence_seed.csv")  # milestone M0 rows
M1_PATH: Final = ("data", "modelkit", "evidence_m1.csv")  # milestone M1 rows (two readers)
PRECISION_PATH: Final = ("data", "modelkit", "precision.json")  # measured precision (M3)
_SPLIT: Final = "\n\x1e\n"
# M0 rows of these sources are replaced by the M1 rows of the same drug (two readers)
SUPERSEDED_SOURCES: Final = frozenset({"clinicaltrials_gov", "dailymed_spl"})

# parameter -> (canonical unit, {stated unit: factor}). Per-kg values keep a per-kg unit.
_MIN_PER_H: Final = 60.0 / 1000.0  # mL/min -> L/h
UNITS: Final[Mapping[str, tuple[str, Mapping[str, float]]]] = {
    "cl": ("L/h", {"L/h": 1.0, "mL/min": _MIN_PER_H}),
    "cl_f": ("L/h", {"L/h": 1.0, "mL/min": _MIN_PER_H}),
    "vss": ("L", {"L": 1.0}),
    "vd": ("L", {"L": 1.0}),
    "v_f": ("L", {"L": 1.0}),
    "t_half": ("h", {"h": 1.0}),
    "tmax": ("h", {"h": 1.0}),
    "f": ("fraction", {"%": 0.01, "fraction": 1.0}),
    "cmax": ("ng/mL", {"ng/mL": 1.0, "ug/L": 1.0}),
    "auc_inf": ("ng*h/mL", {"ng*h/mL": 1.0, "h*ug/L": 1.0}),
    "auc_last": ("ng*h/mL", {"ng*h/mL": 1.0, "h*ug/L": 1.0}),
    "auc_tau": ("ng*h/mL", {"ng*h/mL": 1.0, "h*ug/L": 1.0}),
    "cl_per_kg": ("L/h/kg", {"mL/min/kg": _MIN_PER_H}),
    "vd_per_kg": ("L/kg", {"L/kg": 1.0}),
}
ROUTES: Final = frozenset({"oral", "iv", "unknown"})
REGIMENS: Final = frozenset({"single", "multiple", "unknown"})
FORMULATIONS: Final = frozenset(
    {
        "immediate_release",
        "solution",
        "modified_release",
        "fixed_dose_combination",
        "other_route",
        "unspecified",
    }
)
STATISTICS: Final = frozenset(
    {"mean", "geomean", "median", "stated", "range_geomean", "lower_bound"}
)
ANALYTE_CLASSES: Final = frozenset(
    {
        "parent", "parent_unbound", "metabolite", "enantiomer", "total", "prodrug",
        "combination_partner", "unconfirmed", "unspecified",
    }
)  # fmt: skip
ORIGINS: Final = frozenset({"m0_annotation", "reader_pair", "derived"})
KINDS: Final = frozenset({"pk", "interaction"})
FOODS: Final = frozenset({"fasted", "fed", "unspecified"})
SPREADS: Final = frozenset({"none", "sd", "cv_percent", "range", "ci95", "iqr", "se"})
EXTRA_COLUMNS: Final[tuple[str, ...]] = (
    "arm_id", "origin", "derivation", "evidence_kind", "food", "dispersion_type", "dispersion_low",
    "dispersion_high",
)  # fmt: skip
SOURCES: Final = frozenset({"clinicaltrials_gov", "dailymed_spl", "pmc_oa", "drugsatfda_review"})
VERDICTS: Final = frozenset({"agree", "disagree"})
DRUG_KEY: Final = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
DATE: Final = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

SEED_COLUMNS: Final[tuple[str, ...]] = (
    "drug_key", "analyte", "analyte_class", "parameter", "value", "value_low", "value_high",
    "statistic", "unit", "dose", "dose_unit", "route", "regimen", "interval_h", "population",
    "n_subjects", "formulation", "coadministered", "study_id", "source_id", "source_locator",
    "source_version", "quote", "reader_a", "reader_b", "confirm_reason", "note", "extracted_at",
)  # fmt: skip

SEED_COLUMNS_FULL: Final[tuple[str, ...]] = (*SEED_COLUMNS, *EXTRA_COLUMNS)

EVIDENCE_SCHEMA = ExpectedSchema(
    version=SCHEMA_VERSION,
    fields=tuple(Field(c, frozenset({"str"})) for c in ("drug_key", "parameter", "unit", "quote")),
)

EVIDENCE_ROW: Final[Mapping[str, pl.DataType]] = {
    "drug_key": pl.String(),
    "analyte": pl.String(),
    "analyte_class": pl.String(),
    "parameter": pl.String(),
    "value": pl.Float64(),
    "value_low": pl.Float64(),
    "value_high": pl.Float64(),
    "statistic": pl.String(),
    "unit": pl.String(),
    "value_si": pl.Float64(),
    "dose": pl.Float64(),
    "dose_unit": pl.String(),
    "route": pl.String(),
    "regimen": pl.String(),
    "interval_h": pl.Float64(),
    "population": pl.String(),
    "n_subjects": pl.Int64(),
    "formulation": pl.String(),
    "coadministered": pl.Boolean(),
    "study_id": pl.String(),
    "source_id": pl.String(),
    "source_locator": pl.String(),
    "source_version": pl.String(),
    "quote": pl.String(),
    "reader_a": pl.String(),
    "reader_b": pl.String(),
    "confirmed": pl.Boolean(),
    "confirm_reason": pl.String(),
    "note": pl.String(),
    "extracted_at": pl.String(),
    "pipeline_version": pl.String(),
    "arm_id": pl.String(),
    "origin": pl.String(),
    "derivation": pl.String(),
    "evidence_kind": pl.String(),
    "food": pl.String(),
    "dispersion_type": pl.String(),
    "dispersion_low": pl.Float64(),
    "dispersion_high": pl.Float64(),
}


def to_si(parameter: str, value: float, unit: str) -> float:
    """The value in the parameter's canonical unit; ValueError for a unit not allowed for it."""
    canonical, table = UNITS[parameter]
    if unit not in table:
        raise ValueError(f"unit {unit!r} is not allowed for {parameter!r} (canonical {canonical})")
    return value * table[unit]


def from_si(parameter: str, value_si: float, unit: str) -> float:
    """Inverse of `to_si`."""
    canonical, table = UNITS[parameter]
    if unit not in table:
        raise ValueError(f"unit {unit!r} is not allowed for {parameter!r} (canonical {canonical})")
    return value_si / table[unit]


def _num(row: Mapping[str, str], key: str, where: str, *, required: bool = False) -> float | None:
    text = row[key].strip()
    if not text:
        if required:
            raise ValueError(f"{where}: {key} is required")
        return None
    try:
        x = float(text)
    except ValueError:
        raise ValueError(f"{where}: {key} is not a number") from None
    if not math.isfinite(x) or x <= 0:
        raise ValueError(f"{where}: {key} must be positive and finite")
    return x


def _choice(row: Mapping[str, str], key: str, allowed: frozenset[str], where: str) -> str:
    text = row[key].strip()
    if text not in allowed:
        raise ValueError(f"{where}: {key} {text!r} is not one of {sorted(allowed)}")
    return text


def evidence_row(raw: Mapping[str, str], where: str) -> Row:
    """One checked, normalised output row from one seed line. Raises ValueError naming the line."""
    parameter = _choice(raw, "parameter", frozenset(UNITS), where)
    drug = raw["drug_key"].strip()
    if not DRUG_KEY.match(drug):
        raise ValueError(f"{where}: bad drug_key")
    value = _num(raw, "value", where, required=True)
    assert value is not None  # noqa: S101 - narrowed by required=True
    unit = raw["unit"].strip()
    canon = to_canonical(parameter, value, unit)
    if not isinstance(canon, Canonical):
        raise ValueError(f"{where}: unit {unit!r} for {parameter!r}: {canon.issue}")
    if canon.parameter != parameter:
        raise ValueError(
            f"{where}: a per-kg unit makes {parameter!r} a {canon.parameter!r} (never converted)"
        )
    value_si = canon.value_si
    low, high = _num(raw, "value_low", where), _num(raw, "value_high", where)
    statistic = _choice(raw, "statistic", STATISTICS, where)
    if (statistic == "range_geomean") != (low is not None and high is not None):
        raise ValueError(f"{where}: a range needs both bounds and statistic range_geomean")
    if low is not None and high is not None and not (low <= high):
        raise ValueError(f"{where}: range bounds out of order")
    if low is not None and high is not None and abs(value - math.sqrt(low * high)) > 1e-3 * value:
        raise ValueError(f"{where}: value is not the geometric mean of the stated range")
    dose = _num(raw, "dose", where)
    if (dose is None) != (not raw["dose_unit"].strip()):
        raise ValueError(f"{where}: dose and dose_unit go together")
    if raw["dose_unit"].strip() not in ("", "mg"):
        raise ValueError(f"{where}: only mg doses are accepted")
    n_text = raw["n_subjects"].strip()
    if n_text and (not n_text.isdigit() or int(n_text) < 1):
        raise ValueError(f"{where}: n_subjects must be a positive integer")
    reader_a = _choice(raw, "reader_a", VERDICTS, where)
    reader_b = _choice(raw, "reader_b", VERDICTS, where)
    analyte_class = _choice(raw, "analyte_class", ANALYTE_CLASSES, where)
    source_id = _choice(raw, "source_id", SOURCES, where)
    for key in (
        "analyte",
        "study_id",
        "source_locator",
        "source_version",
        "quote",
        "confirm_reason",
    ):
        if not raw[key].strip():
            raise ValueError(f"{where}: {key} is required")
    if parameter in ("cmax", "auc_inf", "auc_last", "auc_tau") and dose is None:
        raise ValueError(f"{where}: an observation needs its dose")
    if not DATE.match(raw["extracted_at"].strip()):
        raise ValueError(f"{where}: extracted_at must be YYYY-MM-DD")
    coadmin = raw["coadministered"].strip().lower()
    if coadmin not in ("true", "false"):
        raise ValueError(f"{where}: coadministered must be true or false")
    confirmed = reader_a == "agree" and reader_b == "agree" and analyte_class == "parent"
    origin = (raw.get("origin") or "m0_annotation").strip()
    kind = (raw.get("evidence_kind") or "pk").strip()
    food = (raw.get("food") or "unspecified").strip()
    spread = (raw.get("dispersion_type") or "none").strip()
    for name, val, allowed in (
        ("origin", origin, ORIGINS), ("evidence_kind", kind, KINDS), ("food", food, FOODS),
        ("dispersion_type", spread, SPREADS),
    ):  # fmt: skip
        if val not in allowed:
            raise ValueError(f"{where}: {name} {val!r} is not one of {sorted(allowed)}")
    if origin == "derived" and not (raw.get("derivation") or "").strip():
        raise ValueError(f"{where}: a derived value needs its derivation")
    disp_low = _num(raw, "dispersion_low", where) if "dispersion_low" in raw else None
    disp_high = _num(raw, "dispersion_high", where) if "dispersion_high" in raw else None
    return {
        "drug_key": drug,
        "analyte": raw["analyte"].strip(),
        "analyte_class": analyte_class,
        "parameter": parameter,
        "value": value,
        "value_low": low,
        "value_high": high,
        "statistic": statistic,
        "unit": unit,
        "value_si": value_si,
        "dose": dose,
        "dose_unit": raw["dose_unit"].strip() or None,
        "route": _choice(raw, "route", ROUTES, where),
        "regimen": _choice(raw, "regimen", REGIMENS, where),
        "interval_h": _num(raw, "interval_h", where),
        "population": raw["population"].strip() or None,
        "n_subjects": int(n_text) if n_text else None,
        "formulation": _choice(raw, "formulation", FORMULATIONS, where),
        "coadministered": coadmin == "true",
        "study_id": raw["study_id"].strip(),
        "source_id": source_id,
        "source_locator": raw["source_locator"].strip(),
        "source_version": raw["source_version"].strip(),
        "quote": raw["quote"].strip(),
        "reader_a": reader_a,
        "reader_b": reader_b,
        "confirmed": confirmed,
        "confirm_reason": raw["confirm_reason"].strip(),
        "note": raw["note"].strip() or None,
        "extracted_at": raw["extracted_at"].strip(),
        "pipeline_version": PIPELINE_VERSION,
        "arm_id": (raw.get("arm_id") or "").strip() or None,
        "origin": origin,
        "derivation": (raw.get("derivation") or "").strip() or None,
        "evidence_kind": kind,
        "food": food,
        "dispersion_type": spread,
        "dispersion_low": disp_low,
        "dispersion_high": disp_high,
    }


def _read_csv(text: str, name: str) -> list[tuple[str, dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text))
    if tuple(reader.fieldnames or ()) not in (SEED_COLUMNS, SEED_COLUMNS_FULL):
        raise ValueError(f"{name}: header differs from the expected columns")
    return [(f"{name}:{i}", dict(raw)) for i, raw in enumerate(reader, 2)]


def parse_seed(
    text: str, ctgov: Sequence[Row] = (), precision: Mapping[str, Json] | None = None
) -> ParseResult:
    """The seed text: the M0 file alone, or the M0 file and the M1 file joined by a record
    separator line. Rows of superseded sources (M0) are dropped for drugs the M1 file covers.
    `ctgov` are the checked rows of the `modelkit_ctgov` job (milestone M2); they replace every
    ClinicalTrials.gov row of the seed files for the drugs they cover."""
    parts = text.split(_SPLIT)
    lines = _read_csv(parts[0], "evidence_seed.csv")
    if len(parts) > 1:
        m1 = _read_csv(parts[1], "evidence_m1.csv")
        covered = {raw["drug_key"] for _, raw in m1}
        lines = [
            (w, r)
            for w, r in lines
            if not (r["drug_key"] in covered and r["source_id"] in SUPERSEDED_SOURCES)
        ] + m1
    rows: list[Row] = []
    seen: set[tuple[str, str, str, str]] = set()
    input_rows = 0
    ctgov_drugs = {str(r["drug_key"]) for r in ctgov}
    lines = [
        (w, r)
        for w, r in lines
        if not (r["drug_key"] in ctgov_drugs and r["source_id"] == "clinicaltrials_gov")
    ]
    for where, raw in lines:
        input_rows += 1
        row = evidence_row(raw, where)
        key = (
            str(row["drug_key"]),
            str(row["parameter"]),
            str(row["source_locator"]),
            str(row["value"]),
        )
        if key in seen:
            raise ValueError(f"{where}: duplicate row")
        seen.add(key)
        rows.append(row)
    for row in ctgov:
        input_rows += 1
        key = (
            str(row["drug_key"]),
            str(row["parameter"]),
            str(row["source_locator"]),
            str(row["value"]),
        )
        if key in seen:
            raise ValueError(f"modelkit_ctgov: duplicate row {key}")
        seen.add(key)
        rows.append(row)
    by_drug = Counter(str(r["drug_key"]) for r in rows)
    confirmed = sum(1 for r in rows if r["confirmed"])
    metrics: dict[str, Json] = {
        "rows": len(rows),
        "confirmed": confirmed,
        "not_confirmed": len(rows) - confirmed,
        "confirmed_share": round(confirmed / len(rows), 4) if rows else None,
        "by_drug": dict(sorted(by_drug.items())),
        "by_source": dict(sorted(Counter(str(r["source_id"]) for r in rows).items())),
        "studies": len({(r["source_id"], r["study_id"]) for r in rows}),
    }
    if precision:
        metrics["precision"] = dict(precision)
    return ParseResult(
        rows=rows, input_rows=input_rows, excluded={}, schema=SchemaReport(), metrics=metrics
    )


CTGOV_PIPELINE: Final = "modelkit_ctgov"


def _current_ctgov(ctx: RunContext) -> tuple[str, list[Row]]:
    """(fingerprint, rows) of the current `modelkit_ctgov` artifact; ("", []) when there is none.
    The rows were checked by that job; they are checked again here, as the seed rows are."""
    run = ctx.data_dir / "artifacts" / CTGOV_PIPELINE / "current"
    rows_file = run / "rows.parquet"
    if not rows_file.is_file():
        return "", []
    manifest = (run / "manifest.json").read_bytes()
    frame = pl.read_parquet(rows_file)
    rows = [
        evidence_row(_as_text(r), f"{CTGOV_PIPELINE}:{i}") for i, r in enumerate(frame.to_dicts())
    ]
    return sha256_bytes(manifest), rows


def _as_text(r: Mapping[str, object]) -> dict[str, str]:
    """A stored row back to the strings of a seed line."""
    out = {c: "" for c in SEED_COLUMNS_FULL}
    for k, v in r.items():
        if k in out and v is not None:
            out[k] = ("true" if v else "false") if isinstance(v, bool) else str(v)
    return out


def _ctgov_dates(rows: Sequence[Row]) -> list[str]:
    return [str(r["extracted_at"]) for r in rows[:1]]


class ModelkitEvidenceJob(Job[bytes]):
    name = "modelkit_evidence"
    source_id = "modelkit_evidence"
    schema = EVIDENCE_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = EVIDENCE_ROW

    def __init__(self) -> None:
        self._ctgov: list[Row] = []
        self._precision: dict[str, Json] | None = None

    def fetch(self, ctx: RunContext) -> RawInput[bytes]:
        data = ctx.repo_root.joinpath(*SEED_PATH).read_bytes()
        m1 = ctx.repo_root.joinpath(*M1_PATH)
        if m1.exists():
            data = data + _SPLIT.encode() + m1.read_bytes()
        prec = ctx.repo_root.joinpath(*PRECISION_PATH)
        self._precision = json.loads(prec.read_text("utf-8")) if prec.exists() else None
        retrieved = ctx.now()
        fingerprint, self._ctgov = _current_ctgov(ctx)
        dates = sorted(
            {d for d in re.findall(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}$", data.decode(), re.M)}
        )
        return RawInput(
            payload=data,
            source_urls=(),
            source_sha256=sha256_bytes(
                data + fingerprint.encode() + json.dumps(self._precision, sort_keys=True).encode()
            ),
            retrieved_at=retrieved,
            snapshot_date=max([*dates, *_ctgov_dates(self._ctgov)])
            if dates or self._ctgov
            else retrieved.date().isoformat(),
        )

    def parse(self, raw: RawInput[bytes]) -> ParseResult:
        return parse_seed(raw.payload.decode("utf-8"), self._ctgov, self._precision)
