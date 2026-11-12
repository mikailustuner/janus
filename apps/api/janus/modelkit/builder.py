"""Parameter-set builder (design DP-M2 to DP-M6; requirements 2.1-2.9). Pure and deterministic:
the same rows in any order give the same set.

One-compartment model with first-order absorption, as the Janus engine
(`janus.timemachine.pk.OneCompartment`). Intravenous clearance and volume are preferred; without
them apparent oral values (CL/F, V/F) are used and labelled apparent. A per-kg value is never
converted (there is no body weight). The absorption rate is derived from the time of peak
concentration. Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from janus.modelkit.evidence import (
    BUILD_PARAMS,
    Ev,
    compatible_populations,
    exclusion_reason,
    linked_studies,
    population_class,
    split_studies,
)

LN2 = math.log(2.0)
Cls = Literal["A", "B", "C"]
Basis = Literal["iv", "oral_apparent"]
# the (parameter, routes) the builder reads; nothing else can enter a set
READS: dict[str, frozenset[str]] = {
    "cl": frozenset({"iv"}),
    "vss": frozenset({"iv"}),
    "vd": frozenset({"iv"}),
    "f": frozenset({"oral"}),
    "cl_f": frozenset({"oral"}),
    "v_f": frozenset({"oral"}),
    # an intravenous half-life is read only where no oral one exists (rule R1 of the gate study)
    "t_half": frozenset({"oral", "unknown", "iv"}),
    "tmax": frozenset({"oral"}),
}


def solve_ka(k: float, tmax: float) -> float | None:
    """The absorption rate ka (> k) for which a one-compartment model peaks at `tmax`:
    tmax = ln(ka / k) / (ka - k). None when no such rate exists (tmax at or above 1 / k)."""
    if not (k > 0 and tmax > 0) or tmax >= 1.0 / k * 0.999:
        return None

    def g(ka: float) -> float:
        return math.log(ka / k) / (ka - k) - tmax

    lo, hi = k * (1 + 1e-9), max(k, 1e-3) * 1e4 + 1e3
    if g(lo) <= 0 or g(hi) >= 0:  # g decreases from 1/k - tmax > 0 to about -tmax < 0
        return None
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        if g(mid) > 0:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def choose_model(vc: float | None, vss: float | None) -> tuple[str, str]:
    """One compartment unless a central and a steady-state volume exist and differ (design DP-M5
    of the spec; requirement 2.7). M0 has no central-volume parameter in its vocabulary."""
    if vc is None or vss is None:
        return "one_compartment", "no_central_volume_evidence"
    if vss / vc >= 1.25:
        return "two_compartment", "two_volumes_differ"
    return "one_compartment", "two_volumes_agree"


@dataclass(frozen=True)
class Pooled:
    value: float
    cls: Cls
    n_studies: int
    spread_cv: float | None
    eids: tuple[str, ...]
    note: str | None = None
    derived: bool = False  # every contributing row is a clearance derived from dose and AUC
    derivation: str | None = None  # code of the rule that made the value (rules R2, R3)


def _gmean(xs: list[float]) -> float:
    if len(xs) == 1:
        return xs[0]
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def pool(rows: list[Ev]) -> Pooled | None:
    """One value per study (geometric mean of the study's rows), then the geometric mean over
    studies weighted by the number of subjects (1 when unknown). Healthy-adult rows win when any
    exist. Class A: two or more independent studies within 2-fold; B: one study, or studies that
    disagree; C: every contributing row is a stated range."""
    if not rows:
        return None
    healthy = [r for r in rows if "healthy" in (r.population or "")]
    use = healthy or rows
    by_study: dict[tuple[str, str], list[Ev]] = defaultdict(list)
    for r in use:
        by_study[r.study].append(r)
    vals: list[float] = []
    weights: list[float] = []
    for study in sorted(by_study):
        rs = by_study[study]
        vals.append(_gmean([r.value_si for r in rs]))
        weights.append(float(max((r.n_subjects or 1) for r in rs)))
    value = (
        vals[0]
        if len(vals) == 1
        else math.exp(
            sum(w * math.log(v) for w, v in zip(weights, vals, strict=True)) / sum(weights)
        )
    )
    spread = None
    if len(vals) >= 2:
        logs = [math.log(v) for v in vals]
        m = sum(logs) / len(logs)
        sd = math.sqrt(sum((x - m) ** 2 for x in logs) / (len(logs) - 1))
        spread = math.sqrt(math.expm1(sd * sd))
    agree = len(vals) >= 2 and max(vals) / min(vals) <= 2.0
    cls: Cls = "A" if agree else "B"
    all_derived = all(r.origin == "derived" for r in use)
    if all_derived or all(r.statistic == "range_geomean" for r in use):
        cls = "C"
    note = "studies_disagree" if len(vals) >= 2 and not agree else None
    if healthy and len(healthy) < len(rows):
        note = (note + ";" if note else "") + "healthy_adult_preferred"
    return Pooled(
        value, cls, len(vals), spread, tuple(sorted(r.eid for r in use)), note, all_derived
    )


@dataclass(frozen=True)
class Param:
    name: str
    label: str
    value: float
    unit: str
    cls: Cls
    n_studies: int
    spread_cv: float | None
    evidence: tuple[str, ...]
    derivation: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class ParameterSet:
    drug_key: str
    model: str
    model_reason: str
    basis: Basis
    apparent: bool
    params: tuple[Param, ...]
    complete: bool
    missing: tuple[str, ...]
    used: tuple[str, ...]
    left_out: tuple[tuple[str, str], ...]
    test_studies: tuple[tuple[str, str], ...]
    warnings: tuple[str, ...] = ()
    implied_half_life_h: float | None = None
    stated_half_life_h: float | None = None

    def get(self, name: str) -> Param | None:
        return next((p for p in self.params if p.name == name), None)

    def engine(self) -> tuple[float, float, float, float | None]:
        """(F, CL, V, ka) of the model; F is 1 for apparent parameters (inside CL/F and V/F)."""
        f = self.get("f")
        cl, v, ka = self.get("cl"), self.get("v"), self.get("ka")
        assert cl is not None and v is not None and f is not None  # noqa: S101 - set is usable
        return f.value, cl.value, v.value, ka.value if ka else None


@dataclass(frozen=True)
class NoSet:
    drug_key: str
    reasons: tuple[str, ...]
    left_out: tuple[tuple[str, str], ...]
    test_studies: tuple[tuple[str, str], ...]


def _p(name: str, label: str, unit: str, pooled: Pooled, derivation: str | None = None) -> Param:
    how = derivation or pooled.derivation or ("cl_from_dose_and_auc" if pooled.derived else None)
    return Param(
        name, label, pooled.value, unit, pooled.cls, pooled.n_studies, pooled.spread_cv,
        pooled.eids, how, pooled.note,
    )  # fmt: skip


def building_populations(rows: list[Ev]) -> frozenset[str]:
    """The population classes that may build a set of one drug (plan section 7 rule 3): healthy
    adults and unspecified rows when the drug has a healthy-adult row the builder can read in a
    building study, otherwise also patients. Special populations never build."""
    building, _ = split_studies(rows)
    healthy = any(
        exclusion_reason(r) is None
        and r.study in building
        and r.route in READS.get(r.parameter, frozenset())
        and population_class(r.population) == "healthy"
        for r in rows
    )
    if healthy:
        return frozenset({"healthy", "unspecified"})
    return frozenset({"healthy", "patients", "unspecified"})


def set_reference(used: set[str] | tuple[str, ...], rows: list[Ev]) -> str:
    """The reference population of a set: the class of the rows it uses (healthy before patients;
    `unspecified` when no used row states its population)."""
    ids = set(used)
    seen = {population_class(r.population) for r in rows if r.eid in ids}
    if "healthy" in seen:
        return "healthy"
    return "patients" if "patients" in seen else "unspecified"


def _half_life(oral: Pooled | None, iv: Pooled | None) -> Pooled | None:
    """R1: the terminal half-life is a property of the drug; an oral half-life (or one whose route
    is not stated) keeps priority, an intravenous one is used only without it."""
    return oral or iv


def _v_from_cl_half_life(cl: Pooled | None, t_half: Pooled | None) -> Pooled | None:
    """R2: V = CL x t1/2 / ln 2 for an intravenous set without a stated volume (class C)."""
    if cl is None or t_half is None:
        return None
    return Pooled(
        cl.value * t_half.value / LN2,
        "C",
        min(cl.n_studies, t_half.n_studies),
        None,
        tuple(sorted({*cl.eids, *t_half.eids})),
        derivation="v_from_cl_half_life",
    )


def f_from_same_study_auc(rows: list[Ev]) -> Pooled | None:
    """R3 (plan section 7 rule 1): F = (AUC_oral / dose_oral) / (AUC_iv / dose_iv) from the
    single-dose AUC to infinity of both routes in ONE study (geometric mean over each route's
    arms); one value per study, pooled over studies weighted by subjects. Class C. `rows` are the
    rows the builder may read (confirmed, building study, building population)."""
    by: dict[tuple[str, str], dict[str, list[Ev]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if (
            r.parameter == "auc_inf"
            and r.regimen == "single"
            and r.origin != "derived"
            and r.route in ("oral", "iv")
            and r.dose
            and r.value_si > 0
        ):
            by[r.study][r.route].append(r)
    vals: list[float] = []
    weights: list[float] = []
    eids: list[str] = []
    for study in sorted(by):
        oral, iv = by[study]["oral"], by[study]["iv"]
        if not (oral and iv):
            continue
        per_dose = {
            route: _gmean([r.value_si / float(r.dose or 1.0) for r in rs])
            for route, rs in (("oral", oral), ("iv", iv))
        }
        vals.append(per_dose["oral"] / per_dose["iv"])
        weights.append(float(max((r.n_subjects or 1) for r in oral + iv)))
        eids += [r.eid for r in oral + iv]
    if not vals:
        return None
    value = math.exp(
        sum(w * math.log(v) for w, v in zip(weights, vals, strict=True)) / sum(weights)
    )
    return Pooled(
        value, "C", len(vals), None, tuple(sorted(eids)), derivation="f_from_same_study_auc"
    )


def build_set(drug_key: str, rows: list[Ev]) -> ParameterSet | NoSet:
    """The parameter set of one drug from its evidence rows, or why there is none."""
    rows = sorted((r for r in rows if r.drug_key == drug_key), key=lambda r: r.eid)
    building, test = split_studies(rows)
    allowed = building_populations(rows)
    ok = [
        r
        for r in rows
        if exclusion_reason(r) is None
        and r.study in building
        and population_class(r.population) in allowed
    ]

    def get(parameter: str) -> Pooled | None:
        return pool([r for r in ok if r.parameter == parameter and r.route in READS[parameter]])

    def get_routes(parameter: str, routes: frozenset[str]) -> Pooled | None:
        return pool([r for r in ok if r.parameter == parameter and r.route in routes])

    cl_iv = get("cl")
    f_oral = get("f") or f_from_same_study_auc(ok)
    t_half_iv = get_routes("t_half", frozenset({"iv"}))
    t_half = _half_life(get_routes("t_half", frozenset({"oral", "unknown"})), t_half_iv)
    v_iv = get("vss") or get("vd") or _v_from_cl_half_life(cl_iv, t_half_iv)
    cl_f, v_f = get("cl_f"), get("v_f")
    tmax = get("tmax")

    params: list[Param] = []
    reasons: list[str] = []
    capped = False
    basis: Basis
    if cl_iv and v_iv and f_oral:
        basis, apparent = "iv", False
        f = min(f_oral.value, 1.0)
        params += [
            _p("cl", "CL (intravenous)", "L/h", cl_iv),
            _p("v", "V (intravenous)", "L", v_iv),
            _p("f", "F (oral bioavailability)", "fraction", f_oral),
        ]
        if f != f_oral.value:
            capped = True
    elif cl_f:
        basis, apparent = "oral_apparent", True
        if v_f:
            v_param = _p("v", "V/F (apparent)", "L", v_f)
        elif t_half:
            derived = Pooled(
                cl_f.value * t_half.value / LN2,
                "C",
                min(cl_f.n_studies, t_half.n_studies),
                None,
                tuple(sorted({*cl_f.eids, *t_half.eids})),
                "half_life_intravenous" if t_half is t_half_iv else None,
            )
            v_param = _p("v", "V/F (apparent)", "L", derived, "v_from_clf_half_life")
        else:
            v_param = None
            reasons.append("no_volume_and_no_half_life")
        params.append(_p("cl", "CL/F (apparent)", "L/h", cl_f))
        if v_param:
            params.append(v_param)
        params.append(
            Param("f", "F (inside CL/F and V/F)", 1.0, "fraction", "C", 0, None, (),
                  "f_fixed_apparent", None)
        )  # fmt: skip
    else:
        if cl_iv and v_iv and not f_oral:
            reasons.append("iv_without_bioavailability")
        else:
            if not (cl_iv or cl_f):
                reasons.append("no_confirmed_clearance")
            if not (v_iv or v_f):
                reasons.append("no_confirmed_volume")
            if (cl_iv or v_iv) and not (cl_iv and v_iv):
                reasons.append("iv_evidence_incomplete")
        return NoSet(
            drug_key, tuple(reasons), _left_out(rows, set(), building, test), tuple(sorted(test))
        )

    cl_p, v_p = (
        next((p for p in params if p.name == "cl"), None),
        next((p for p in params if p.name == "v"), None),
    )
    if cl_p is None or v_p is None:
        return NoSet(
            drug_key, tuple(reasons), _left_out(rows, set(), building, test), tuple(sorted(test))
        )
    k = cl_p.value / v_p.value
    warnings: list[str] = ["bioavailability_capped"] if capped else []
    implied_half_life: float | None = None
    stated_half_life: float | None = None
    missing: list[str] = []
    ka_param: Param | None = None
    if tmax:
        ka = solve_ka(k, tmax.value)
        if ka is None:
            missing.append("missing_absorption_no_solution")
        else:
            ka_param = Param(
                "ka", "ka (derived from the time of peak concentration)", ka, "1/h", "C",
                tmax.n_studies, None, tmax.eids,
                "ka_from_tmax", tmax.note,
            )  # fmt: skip
            params.append(ka_param)
    else:
        missing.append("missing_absorption_no_peak_time")
    if t_half:
        implied = LN2 / k
        ratio = max(implied, t_half.value) / min(implied, t_half.value)
        implied_half_life, stated_half_life = implied, t_half.value
        if ratio > 1.5:
            warnings.append("half_life_inconsistent")
    model, model_reason = choose_model(None, None)
    used = {e for p in params for e in p.evidence}
    if t_half:
        used |= set(t_half.eids)
    if set_reference(used, ok) == "patients":
        warnings.append("reference_population_patients")
    return ParameterSet(
        drug_key=drug_key,
        model=model,
        model_reason=model_reason,
        basis=basis,
        apparent=apparent,
        params=tuple(params),
        complete=ka_param is not None,
        missing=tuple(missing),
        used=tuple(sorted(used)),
        left_out=_left_out(rows, used, building, test),
        test_studies=tuple(sorted(test)),
        warnings=tuple(warnings),
        implied_half_life_h=implied_half_life,
        stated_half_life_h=stated_half_life,
    )


def _left_out(
    rows: list[Ev],
    used: set[str],
    building: frozenset[tuple[str, str]],
    test: frozenset[tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    """Every row of the drug that did not build the set, with the first reason."""
    out: list[tuple[str, str]] = []
    linked = linked_studies(rows)
    build_ok = building_populations(rows)
    test_ok = compatible_populations(set_reference(used, rows))
    for r in rows:
        if r.eid in used:
            continue
        why = exclusion_reason(r)
        cls = population_class(r.population)
        if why is None and cls not in (test_ok if r.study in test else build_ok):
            why = "not_reference_population"
        if why is None:
            if r.study in test:
                why = "held_out_study"
            elif r.parameter not in BUILD_PARAMS:
                why = (
                    "same_study_in_another_source"
                    if r.study in linked
                    else "observation_in_building_study"
                )
            else:
                why = "not_needed_preferred_basis"
        out.append((r.eid, why))
    return tuple(out)
