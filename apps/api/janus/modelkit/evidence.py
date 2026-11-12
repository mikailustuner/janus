"""Evidence rows of the model kit store (`modelkit_evidence-1`) and the filters every later step
shares. Pure after `read_run`. Research use only. Not for clinical decisions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import duckdb

PIPELINE = "modelkit_evidence"
SOURCE_ID = "modelkit_evidence"
SCHEMA_VERSION = "modelkit_evidence-3"
# milestone M5 adds the study identity columns; a run of schema 2 is read with empty ones
SCHEMA_VERSIONS = frozenset({"modelkit_evidence-2", SCHEMA_VERSION})

# Parameters a parameter set is built from; observations only test a set.
BUILD_PARAMS = frozenset({"cl", "cl_f", "vss", "vd", "v_f", "t_half", "tmax", "f"})
OBS_PARAMS = frozenset({"cmax", "auc_inf", "auc_last", "auc_tau"})
IMMEDIATE = frozenset({"immediate_release", "solution"})

COLUMNS = (
    "drug_key", "analyte", "analyte_class", "parameter", "value", "value_low", "value_high",
    "statistic", "unit", "value_si", "dose", "dose_unit", "route", "regimen", "interval_h",
    "population", "n_subjects", "formulation", "coadministered", "study_id", "source_id",
    "source_locator", "source_version", "quote", "reader_a", "reader_b", "confirmed",
    "confirm_reason", "note", "extracted_at", "pipeline_version", "arm_id", "origin", "derivation",
    "evidence_kind", "food", "dispersion_type", "dispersion_low", "dispersion_high",
)  # fmt: skip
IDENTITY_COLUMNS = ("study_keys", "study_group")  # schema 3 (M5)


@dataclass(frozen=True)
class Ev:
    """One evidence row. `eid` is a stable id derived from the row's identity."""

    eid: str
    drug_key: str
    analyte: str
    analyte_class: str
    parameter: str
    value: float
    value_low: float | None
    value_high: float | None
    statistic: str
    unit: str
    value_si: float
    dose: float | None
    route: str
    regimen: str
    interval_h: float | None
    population: str | None
    n_subjects: int | None
    formulation: str
    coadministered: bool
    study_id: str
    source_id: str
    source_locator: str
    source_version: str
    quote: str
    reader_a: str
    reader_b: str
    confirmed: bool
    confirm_reason: str
    note: str | None
    extracted_at: str
    arm_id: str | None = None
    origin: str = "m0_annotation"  # m0_annotation, reader_pair, derived
    derivation: str | None = None  # how a derived value was made
    evidence_kind: str = "pk"  # pk, interaction
    food: str = "unspecified"
    dispersion_type: str = "none"
    dispersion_low: float | None = None
    dispersion_high: float | None = None
    study_keys: str | None = None  # NCT:..|CODE:..|DOC:.. (M5 study identity)
    study_group: str | None = None  # the study's identity group; None: the study alone

    @property
    def study(self) -> tuple[str, str]:
        return (self.source_id, self.study_id)

    @property
    def group(self) -> str:
        return self.study_group or f"{self.source_id}:{self.study_id}"

    def public(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__}
        return d


def make_eid(drug: str, parameter: str, locator: str, value: float) -> str:
    text = json.dumps([drug, parameter, locator, repr(float(value))], separators=(",", ":"))
    return "ev_" + hashlib.sha256(text.encode()).hexdigest()[:12]


def ev_from_mapping(m: dict[str, Any]) -> Ev:
    return Ev(
        eid=make_eid(m["drug_key"], m["parameter"], m["source_locator"], m["value"]),
        drug_key=m["drug_key"],
        analyte=m["analyte"],
        analyte_class=m["analyte_class"],
        parameter=m["parameter"],
        value=float(m["value"]),
        value_low=m["value_low"],
        value_high=m["value_high"],
        statistic=m["statistic"],
        unit=m["unit"],
        value_si=float(m["value_si"]),
        dose=m["dose"],
        route=m["route"],
        regimen=m["regimen"],
        interval_h=m["interval_h"],
        population=m["population"],
        n_subjects=m["n_subjects"],
        formulation=m["formulation"],
        coadministered=bool(m["coadministered"]),
        study_id=m["study_id"],
        source_id=m["source_id"],
        source_locator=m["source_locator"],
        source_version=m["source_version"],
        quote=m["quote"],
        reader_a=m["reader_a"],
        reader_b=m["reader_b"],
        confirmed=bool(m["confirmed"]),
        confirm_reason=m["confirm_reason"],
        note=m["note"],
        extracted_at=str(m["extracted_at"]),
        arm_id=m.get("arm_id"),
        origin=m.get("origin") or "m0_annotation",
        derivation=m.get("derivation"),
        evidence_kind=m.get("evidence_kind") or "pk",
        food=m.get("food") or "unspecified",
        dispersion_type=m.get("dispersion_type") or "none",
        dispersion_low=m.get("dispersion_low"),
        dispersion_high=m.get("dispersion_high"),
        study_keys=m.get("study_keys"),
        study_group=m.get("study_group"),
    )


def read_run(run: Path) -> tuple[dict[str, Any], list[Ev]]:
    """The manifest and the rows of one run directory. Raises `OSError` or `ValueError`."""
    manifest: dict[str, Any] = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    outcome = manifest.get("outcome")
    if outcome == "needs_review" and not (run / "promotion.json").exists():
        raise ValueError("needs_review run was not promoted")
    if outcome not in ("succeeded", "needs_review"):
        raise ValueError("run did not succeed")
    if (
        manifest.get("source_id") != SOURCE_ID
        or manifest.get("schema_version") not in SCHEMA_VERSIONS
    ):
        raise ValueError("not a modelkit_evidence run")
    cols = COLUMNS + (IDENTITY_COLUMNS if manifest["schema_version"] == SCHEMA_VERSION else ())
    con = duckdb.connect()
    try:
        cur = con.execute(
            f"SELECT {', '.join(cols)} FROM read_parquet(?)",  # noqa: S608 - constant columns
            [str(run / "rows.parquet")],
        )
        rows = [ev_from_mapping(dict(zip(cols, r, strict=True))) for r in cur.fetchall()]
    except duckdb.Error as exc:
        raise ValueError("rows cannot be read") from exc
    finally:
        con.close()
    return manifest, sorted(rows, key=lambda e: e.eid)


# --- filters (design DP-M2, DP-M3, DP-M4) --------------------------------------------------------


def exclusion_reason(e: Ev) -> str | None:
    """Why a row can never be used (build or test), or None. The first reason in a fixed order."""
    if not e.confirmed:
        return "not_confirmed"
    if e.analyte_class != "parent":
        return "analyte_not_parent"
    if e.coadministered or e.evidence_kind == "interaction":
        return "coadministered"
    if e.formulation == "fixed_dose_combination":
        return "fixed_dose_combination"
    if e.formulation not in IMMEDIATE:
        return "formulation_not_immediate_release"
    if e.statistic == "lower_bound":
        return "bound_not_a_value"
    if e.parameter.endswith("_per_kg"):
        return "per_kg_not_converted"
    if population_class(e.population) == "special":
        return "special_population"
    return None


def linked_studies(rows: list[Ev]) -> frozenset[tuple[str, str]]:
    """Studies of one drug that share an identity group with another study (milestone M5: a shared
    NCT number, a shared sponsor study code, a numerical duplicate, or a review's document-level
    study with the coded studies of its PDF)."""
    members: dict[str, set[tuple[str, str]]] = {}
    for e in rows:
        members.setdefault(e.group, set()).add(e.study)
    return frozenset(s for m in members.values() if len(m) > 1 for s in m)


def split_studies(
    rows: list[Ev], identity: bool = True
) -> tuple[frozenset[tuple[str, str]], frozenset[tuple[str, str]]]:
    """(building studies, test studies) of one drug. Looks only at which parameters a study
    reports, in every row (confirmed or not), so the split cannot depend on confirmation.

    Only rows of the parent drug count: a half-life of a metabolite does not make a study a
    building study (M1). A derived row (clearance made from dose and AUC of one arm) is not a
    parameter the study reports: it does not make its study a building study. When a drug has no
    stated clearance at all but has derived clearances, ONE study is designated to build the set:
    the first in sorted order among the studies with derived rows. The others stay test studies,
    and the designated study never tests (it builds).

    Study identity (M5, pre-registered): a study that may be the same study as another one (same
    identity group) never tests; it is put on the training side. It can build only through its
    own building parameters. `identity=False` gives the split without this rule (for reports)."""
    stated = [e for e in rows if e.origin != "derived" and e.analyte_class == "parent"]
    building = {
        e.study for e in stated if e.parameter in BUILD_PARAMS or e.parameter.endswith("_per_kg")
    }
    if not any(e.parameter in ("cl", "cl_f") for e in stated):
        derived = sorted({e.study for e in rows if e.origin == "derived"})
        if derived:
            building.add(derived[0])
    obs_rows = [e for e in rows if e.parameter in OBS_PARAMS and e.origin != "derived"]
    test = {e.study for e in obs_rows if e.analyte_class == "parent"} - building
    if identity:
        linked = linked_studies(rows)
        building |= test & linked
        test -= linked
    return frozenset(building), frozenset(test)


# --- population (milestone M6; plan section 7 rule 3) --------------------------------------------

PopClass = Literal["special", "healthy", "patients", "unspecified"]


def population_class(population: str | None) -> PopClass:
    """The class of a row's population field: `special` (the readers' special-population class:
    children, older adults, renal or hepatic impairment), `healthy`, `patients` or `unspecified`."""
    p = (population or "").lower()
    if "special" in p:
        return "special"
    if "healthy" in p:
        return "healthy"
    if "patient" in p:
        return "patients"
    return "unspecified"


def compatible_populations(reference: str) -> frozenset[PopClass]:
    """The population classes a set of this reference population may be tested on: the reference
    itself and `unspecified`; with an `unspecified` reference every class but special."""
    if reference == "healthy":
        return frozenset({"healthy", "unspecified"})
    if reference == "patients":
        return frozenset({"patients", "unspecified"})
    return frozenset({"healthy", "patients", "unspecified"})
