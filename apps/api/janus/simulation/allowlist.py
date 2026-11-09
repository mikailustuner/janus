"""The allow-list of the simulation service (simulation-service design §3, DP-S1). Pure after
loading: `data/simulation/compounds.json` names the compounds, the predefined virtual populations,
dose bounds, scenarios, httk chemical names, validation verdicts and limits;
`data/time_machine/compartmental_pk.csv` gives the cited model parameters and spreads.

Owner decision 2026-11-09: no individualised simulation. A request names a compound and a
virtual population and may set a dose, an interval and a number of doses within hard bounds;
there is no body weight, age, kidney function or any other person-specific input. Everything
passed to a model comes from here.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal

from janus.paths import repo_root

Credibility = Literal["credible", "borderline", "failed"]


@dataclass(frozen=True)
class Validation:
    credibility: Credibility
    cmax_fold: float
    auc_fold: float
    auc_independent: bool
    reference_key: str
    cmax_direction: Literal["model_lower", "model_higher"]
    auc_direction: Literal["model_lower", "model_higher"]


@dataclass(frozen=True)
class Bounds:
    low: float
    default: float
    high: float

    def __post_init__(self) -> None:
        if not (0 < self.low <= self.default <= self.high):
            raise ValueError("bounds must satisfy 0 < low <= default <= high")

    def contains(self, x: float) -> bool:
        return self.low <= x <= self.high


@dataclass(frozen=True)
class Scenario:
    id: str
    dose_mg: float
    kind: Literal["validation", "historical"]
    reference_keys: tuple[str, ...]
    note: str | None = None


@dataclass(frozen=True)
class Population:
    """A predefined virtual population of the compartmental model: the cited parameters with
    clearance scaled by `cl_factor` (a cited ratio), drawn with the cited spreads."""

    id: str
    cl_factor: float
    reference_keys: tuple[str, ...]
    basis: str


@dataclass(frozen=True)
class CompartmentalCompound:
    id: str
    f: float
    ka: float
    cl: float
    v: float
    tlag: float
    ka_gsd: float
    cl_gsd: float
    v_gsd: float
    dose: Bounds
    dose_basis: str
    intervals_h: tuple[int, ...]
    f_fixed: bool  # apparent parameters (F already in CL/F, V/F): no spread on F
    scenarios: tuple[Scenario, ...]
    populations: dict[str, Population]
    validation: Validation
    validated_scope: str
    reference_keys: tuple[str, ...]


@dataclass(frozen=True)
class HttkCompound:
    id: str
    chem: str
    validation: Validation


@dataclass(frozen=True)
class HttkPopulation:
    id: str
    age_low: int
    age_high: int
    basis: str


@dataclass(frozen=True)
class Limits:
    doses_max: int
    horizon_after_last_dose_h: int
    horizon_max_h: int
    population_samples_min: int
    population_samples_max: int
    compartmental_samples_min: int
    compartmental_samples_max: int


@dataclass(frozen=True)
class AllowList:
    version: str
    compartmental: dict[str, CompartmentalCompound]
    httk: dict[str, HttkCompound]
    httk_populations: dict[str, HttkPopulation]
    httk_basis: str
    limits: Limits


def _validation(raw: dict[str, Any]) -> Validation:
    return Validation(
        credibility=raw["credibility"],
        cmax_fold=float(raw["cmax_fold"]),
        auc_fold=float(raw["auc_fold"]),
        auc_independent=bool(raw["auc_independent"]),
        reference_key=str(raw["reference_key"]),
        cmax_direction=raw["cmax_direction"],
        auc_direction=raw["auc_direction"],
    )


def parse(raw: dict[str, Any], pk_rows: list[dict[str, str]]) -> AllowList:
    pk = {r["drug"]: r for r in pk_rows}
    comp: dict[str, CompartmentalCompound] = {}
    for c in raw["compartmental"]:
        r = pk[c["id"]]  # KeyError: a compound without cited parameters is a data defect
        d = c["dose_mg"]
        comp[c["id"]] = CompartmentalCompound(
            id=c["id"],
            f=float(r["f"]),
            ka=float(r["ka_per_h"]),
            cl=float(r["cl_l_per_h"]),
            v=float(r["v_l"]),
            tlag=float(r["tlag_h"]),
            ka_gsd=float(r["ka_gsd"]),
            cl_gsd=float(r["cl_gsd"]),
            v_gsd=float(r["v_gsd"]),
            dose=Bounds(float(d["low"]), float(d["default"]), float(d["high"])),
            dose_basis=str(c["dose_basis"]),
            intervals_h=tuple(int(i) for i in c["intervals_h"]),
            f_fixed=bool(c["f_fixed"]),
            scenarios=tuple(
                Scenario(
                    s["id"],
                    float(s["dose_mg"]),
                    s["kind"],
                    tuple(s["reference_keys"]),
                    s.get("note"),
                )
                for s in c["scenarios"]
            ),
            populations={
                p["id"]: Population(
                    p["id"], float(p["cl_factor"]), tuple(p["reference_keys"]), p["basis"]
                )
                for p in c["populations"]
            },
            validation=_validation(c["validation"]),
            validated_scope=str(c["validated_scope"]),
            reference_keys=tuple(r["reference_keys"].split("|")),
        )
    lim = raw["limits"]
    return AllowList(
        version=str(raw["version"]),
        compartmental=comp,
        httk={
            h["id"]: HttkCompound(h["id"], h["chem"], _validation(h["validation"]))
            for h in raw["httk"]
        },
        httk_populations={
            p["id"]: HttkPopulation(
                p["id"], int(p["age_years"][0]), int(p["age_years"][1]), p["basis"]
            )
            for p in raw["httk_populations"]
        },
        httk_basis=str(raw["httk_comparison"]["basis"]),
        limits=Limits(**{k: int(v) for k, v in lim.items()}),
    )


def load(root: Path | None = None) -> AllowList:
    base = root or repo_root() / "data"
    raw = json.loads((base / "simulation" / "compounds.json").read_text(encoding="utf-8"))
    with (base / "time_machine" / "compartmental_pk.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return parse(raw, rows)


@cache
def allowlist() -> AllowList:
    return load()
