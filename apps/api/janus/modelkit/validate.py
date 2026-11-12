"""Validation of a parameter set against held-out studies (design DP-M7, DP-M8, DP-M39; Req 3).

Held-out design (DP-M39, leave one study out): every study that reports an observation (except label
studies and studies linked to another study) is held out in turn; the set is built again from the
drug's OTHER studies only, with the unchanged builder, and the held-out study's observations are
predicted by that set. A held-out study therefore never influences the set that tests it. The set
shown is built from every study; its validation is cross-validated over studies.

Strict rule (owner decision 2026-11-11): a drug is Validated only if AUC and Cmax were both tested
and EVERY held-out observation point (each AUC and each Cmax point, every study) has a ratio
predicted / observed within [0.5, 2]. If any tested point is outside 2-fold the status is Failed and
the points and the suspect parameter are named; otherwise Not validated, with the reasons. The
geometric mean ratio per metric is still reported, but it no longer decides the status. No interval
is shown that the data cannot support. Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Literal

from janus.modelkit.builder import NoSet, ParameterSet, build_set, set_reference
from janus.modelkit.evidence import (
    OBS_PARAMS,
    Ev,
    compatible_populations,
    exclusion_reason,
    linked_studies,
    population_class,
    split_studies,
)
from janus.timemachine.pk import OneCompartment, auc_inf, cmax

Status = Literal["validated", "not_validated", "failed"]
Design = Literal["leave_one_study_out", "single_split"]
BAND = 2.0
MIN_STUDIES_FOR_INTERVAL = 20
MIN_DRUGS_FOR_INTERPRETATION = 10
LABEL_SOURCES = frozenset({"dailymed_spl"})  # labels never test (DP-M2)


@dataclass(frozen=True)
class Point:
    eid: str
    metric: Literal["auc", "cmax"]
    study_id: str
    dose_mg: float
    observed: float
    predicted: float
    ratio: float
    within_2_fold: bool
    # the study also builds the set shown; this point is predicted by the set built without it
    rebuilt_without_study: bool = False


@dataclass(frozen=True)
class Metric:
    name: Literal["auc", "cmax"]
    tested: bool
    n_points: int
    n_studies: int
    gm_ratio: float | None
    gmfe: float | None
    within_2_fold_points: int
    all_within_2_fold: bool | None  # every point of the metric is within 2-fold


@dataclass(frozen=True)
class Validation:
    drug_key: str
    status: Status
    reasons: tuple[str, ...]
    metrics: tuple[Metric, Metric]
    points: tuple[Point, ...]
    excluded: tuple[tuple[str, str], ...]
    suspect: tuple[str, ...]
    interval: str
    failed_points: tuple[str, ...] = ()  # evidence ids of the points outside 2-fold
    design: Design = "leave_one_study_out"  # DP-M39; "single_split" is the M0 to M6 design


def cmax_steady_state(f: float, ka: float, cl: float, v: float, dose: float, tau: float) -> float:
    """Peak concentration (mg/L) at steady state of a one-compartment model with first-order
    absorption, `dose` every `tau` hours (superposition; ka != k)."""
    k = cl / v
    rk, ra = 1.0 - math.exp(-k * tau), 1.0 - math.exp(-ka * tau)
    t = math.log((ka * rk) / (k * ra)) / (ka - k)
    return f * dose * ka / (v * (ka - k)) * (math.exp(-k * t) / rk - math.exp(-ka * t) / ra)


def predict(
    ps: ParameterSet, metric: str, dose_mg: float, interval_h: float | None = None
) -> float | None:
    """Predicted AUC (ng*h/mL, to infinity of one dose = over a dosing interval at steady state) or
    Cmax (ng/mL; one dose, or at steady state when `interval_h` is given) from a set; None if the
    set cannot predict it (no absorption rate for Cmax)."""
    f, cl, v, ka = ps.engine()
    if metric == "auc":
        return auc_inf(OneCompartment(f, 1.0, cl, v), dose_mg) * 1000.0
    if ka is None or abs(ka - cl / v) < 1e-12:
        return None
    if interval_h:
        return cmax_steady_state(f, ka, cl, v, dose_mg, interval_h) * 1000.0
    return cmax(OneCompartment(f, ka, cl, v), dose_mg) * 1000.0


def _obs_reason(e: Ev, ps: ParameterSet, allowed: frozenset[str]) -> str | None:
    why = exclusion_reason(e)
    if why:
        return why
    if population_class(e.population) not in allowed:
        return "not_reference_population"
    if e.parameter == "auc_last":
        return "auc_to_last_sampling_time_not_comparable"
    if e.parameter not in ("cmax", "auc_inf", "auc_tau"):
        return "not_an_observation"
    if e.dose is None or e.route != "oral":
        return "needs_oral_dose"
    if e.parameter == "auc_tau" and not (e.regimen == "multiple" and e.interval_h):
        return "auc_tau_needs_multiple_dose_interval"
    if (
        e.parameter == "cmax"
        and e.regimen != "single"
        and not (e.regimen == "multiple" and e.interval_h)
    ):
        return "steady_state_cmax_needs_interval"
    if e.parameter == "auc_inf" and e.regimen != "single":
        return "auc_inf_needs_single_dose"
    if (ps.engine()[3] is None) and e.parameter == "cmax":
        return "set_has_no_absorption_rate"
    return None


def _metric(name: Literal["auc", "cmax"], pts: list[Point]) -> Metric:
    if not pts:
        return Metric(name, False, 0, 0, None, None, 0, None)
    by_study: dict[str, list[float]] = defaultdict(list)
    for p in pts:
        by_study[p.study_id].append(math.log(p.ratio))
    study_logs = [sum(v) / len(v) for v in by_study.values()]
    gm = math.exp(sum(study_logs) / len(study_logs))
    gmfe = math.exp(sum(abs(math.log(p.ratio)) for p in pts) / len(pts))
    all_in = all(p.within_2_fold for p in pts)
    return Metric(
        name,
        True,
        len(pts),
        len(by_study),
        gm,
        gmfe,
        sum(p.within_2_fold for p in pts),
        all_in,
    )


def _point(e: Ev, ps: ParameterSet, rebuilt: bool) -> Point | None:
    metric: Literal["auc", "cmax"] = "cmax" if e.parameter == "cmax" else "auc"
    assert e.dose is not None  # noqa: S101 - checked in _obs_reason
    ss = e.interval_h if metric == "cmax" and e.regimen == "multiple" else None
    pred = predict(ps, metric, e.dose, ss)
    if pred is None or pred <= 0:
        return None
    ratio = pred / e.value_si
    return Point(
        e.eid,
        metric,
        e.study_id,
        e.dose,
        e.value_si,
        pred,
        ratio,
        1 / BAND <= ratio <= BAND,
        rebuilt,
    )


def held_out_candidates(rows: list[Ev]) -> list[tuple[str, str]]:
    """The studies of one drug that are held out in turn (DP-M39): a study with an observation row,
    not a label study, not linked to another study (M5 identity guard: it never tests)."""
    linked = linked_studies(rows)
    return sorted(
        {
            e.study
            for e in rows
            if e.parameter in OBS_PARAMS
            and e.origin != "derived"
            and e.source_id not in LABEL_SOURCES
            and e.study not in linked
        }
    )


def fold_rows(rows: list[Ev], study: tuple[str, str]) -> list[Ev]:
    """The rows of a held-out study's fold set: every row of the drug except that study's."""
    return [r for r in rows if r.study != study]


def validate(drug_key: str, rows: list[Ev], ps: ParameterSet | NoSet) -> Validation:
    """Leave-one-study-out validation (DP-M39) of the drug's set. The strict status rule is
    unchanged; every point is predicted by a set built without the point's study."""
    rows = [r for r in rows if r.drug_key == drug_key]
    if isinstance(ps, NoSet):
        return replace(validate_single_split(drug_key, rows, ps), design="leave_one_study_out")
    _, test = split_studies(rows)
    linked = linked_studies(rows)
    cands = set(held_out_candidates(rows))
    by_study: dict[tuple[str, str], list[Ev]] = defaultdict(list)
    for e in rows:
        if e.parameter in OBS_PARAMS:
            by_study[e.study].append(e)
    pts: list[Point] = []
    excluded: list[tuple[str, str]] = []
    for study in sorted(by_study):
        obs = sorted(by_study[study], key=lambda e: e.eid)
        if study not in cands:
            why_all = "same_study_in_another_source" if study in linked else "label_never_tests"
            excluded += [(e.eid, why_all) for e in obs]
            continue
        fold: ParameterSet | NoSet | None = None
        allowed: frozenset[str] = frozenset()
        for e in obs:
            why = exclusion_reason(e)
            if why is None:
                if fold is None:
                    rest = fold_rows(rows, study)
                    fold = build_set(drug_key, rest)
                    if isinstance(fold, ParameterSet):
                        allowed = compatible_populations(set_reference(fold.used, rest))
                if isinstance(fold, NoSet):
                    why = "fold_has_no_parameter_set"
                else:
                    why = _obs_reason(e, fold, allowed)
            if why:
                excluded.append((e.eid, why))
                continue
            assert isinstance(fold, ParameterSet)  # noqa: S101 - set above
            p = _point(e, fold, study not in test)
            if p is None:
                excluded.append((e.eid, "set_cannot_predict_metric"))
            else:
                pts.append(p)
    return _decide(drug_key, pts, excluded, "leave_one_study_out")


def validate_single_split(drug_key: str, rows: list[Ev], ps: ParameterSet | NoSet) -> Validation:
    """The single study split of milestones M0 to M6 (DP-M2): only studies without building
    parameters test, against the set shown. Kept for comparison and for drugs without a set."""
    rows = [r for r in rows if r.drug_key == drug_key]
    _, test = split_studies(rows)
    empty = (_metric("auc", []), _metric("cmax", []))
    if isinstance(ps, NoSet):
        return Validation(
            drug_key, "not_validated", ("no_parameter_set", *ps.reasons), empty, (), (), (),
            "interval_n_too_small",
        )  # fmt: skip
    pts: list[Point] = []
    excluded: list[tuple[str, str]] = []
    linked = linked_studies(rows)
    allowed: frozenset[str] = compatible_populations(set_reference(ps.used, rows))
    for e in rows:
        if e.parameter not in ("cmax", "auc_inf", "auc_last", "auc_tau"):
            continue
        if e.study not in test:
            excluded.append(
                (
                    e.eid,
                    "same_study_in_another_source"
                    if e.study in linked
                    else "observation_in_building_study",
                )
            )
            continue
        why = _obs_reason(e, ps, allowed)
        if why:
            excluded.append((e.eid, why))
            continue
        p = _point(e, ps, False)
        if p is None:
            excluded.append((e.eid, "set_cannot_predict_metric"))
            continue
        pts.append(p)
    return _decide(drug_key, pts, excluded, "single_split")


def _decide(
    drug_key: str, pts: list[Point], excluded: list[tuple[str, str]], design: Design
) -> Validation:
    """The strict status function (DP-M7, owner decision 2026-11-11), unchanged."""
    auc = _metric("auc", [p for p in pts if p.metric == "auc"])
    cm = _metric("cmax", [p for p in pts if p.metric == "cmax"])
    reasons: list[str] = []
    suspect: list[str] = []
    studies = {p.study_id for p in pts}
    if not pts:
        reasons.append("no_independent_observation")
    for m in (auc, cm):
        if not m.tested and pts:
            reasons.append(f"{m.name}_not_tested")
    failed = [m for m in (auc, cm) if m.tested and m.all_within_2_fold is False]
    failed_points = tuple(sorted(p.eid for p in pts if not p.within_2_fold))
    if failed:
        status: Status = "failed"
        for m in failed:
            suspect.append(
                "clearance_or_bioavailability" if m.name == "auc" else "absorption_rate_or_volume"
            )
        reasons.append("point_outside_2_fold")
    elif auc.tested and cm.tested:
        status = "validated"
        reasons.append("all_points_within_2_fold")
    else:
        status = "not_validated"
    interval = (
        "interval_n_too_small"
        if len(studies) < MIN_STUDIES_FOR_INTERVAL
        else "interval_system_level_only"
    )
    return Validation(
        drug_key, status, tuple(reasons), (auc, cm), tuple(pts), tuple(sorted(excluded)),
        tuple(suspect), interval, failed_points, design,
    )  # fmt: skip


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float] | None:
    """Wilson score interval of a share; None for n = 0."""
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (c - h) / d), min(1.0, (c + h) / d)


def conformal_fold_width(ratios: list[float], coverage: float = 0.8) -> float | None:
    """Split-conformal width (fold, symmetric in log10) covering `coverage` of new ratios, from
    held-out predicted/observed ratios of independent studies. None below 20 studies."""
    n = len(ratios)
    if n < MIN_STUDIES_FOR_INTERVAL:
        return None
    errs = sorted(abs(math.log10(r)) for r in ratios)
    rank = math.ceil((n + 1) * coverage)
    if rank > n:
        return None
    return 10 ** (2 * errs[rank - 1])


@dataclass(frozen=True)
class SystemMetric:
    name: Literal["auc", "cmax"]
    n_drugs: int
    gmfe: float | None
    within_2_fold: int
    within_2_fold_share: float | None
    wilson_low: float | None
    wilson_high: float | None
    n_points: int = 0  # held-out points of the metric over all drugs (point level)
    points_within_2_fold: int = 0
    points_gmfe: float | None = None


@dataclass(frozen=True)
class IntervalInfo:
    """Split-conformal interval of one metric over all held-out studies of the release (DP-M8).
    Shown only from `MIN_STUDIES_FOR_INTERVAL` studies; below that `fold_width` is None."""

    name: Literal["auc", "cmax"]
    n_studies: int
    shown: bool
    fold_width: float | None
    coverage: float


COVERAGE = 0.8


def conformal_intervals(vals: list[Validation]) -> tuple[IntervalInfo, IntervalInfo]:
    """One score per (drug, held-out study, metric): the geometric mean of the study's ratios."""
    out: list[IntervalInfo] = []
    for name in ("auc", "cmax"):
        per: dict[tuple[str, str], list[float]] = defaultdict(list)
        for v in vals:
            for p in v.points:
                if p.metric == name:
                    per[(v.drug_key, p.study_id)].append(math.log(p.ratio))
        ratios = [math.exp(sum(x) / len(x)) for x in per.values()]
        width = conformal_fold_width(ratios, COVERAGE)
        out.append(
            IntervalInfo(name, len(ratios), width is not None, width, COVERAGE)  # type: ignore[arg-type]
        )
    return out[0], out[1]


@dataclass(frozen=True)
class SystemReport:
    n_drugs: int
    by_status: dict[str, int]
    metrics: tuple[SystemMetric, SystemMetric]
    n_studies: int
    interpretable: bool
    min_drugs_for_interpretation: int
    conformal: str
    n_drugs_both_tested: int = 0  # drugs with AUC and Cmax both tested on held-out studies
    intervals: tuple[IntervalInfo, IntervalInfo] = (
        IntervalInfo("auc", 0, False, None, COVERAGE),
        IntervalInfo("cmax", 0, False, None, COVERAGE),
    )
    reasons_not_validated: dict[str, int] = field(default_factory=lambda: dict[str, int]())


def system_report(vals: list[Validation]) -> SystemReport:
    by_status = {"validated": 0, "not_validated": 0, "failed": 0}
    for v in vals:
        by_status[v.status] += 1
    out: list[SystemMetric] = []
    for name in ("auc", "cmax"):
        ms = [m for v in vals for m in v.metrics if m.name == name and m.tested]
        n = len(ms)
        within = sum(1 for m in ms if m.all_within_2_fold)
        gmfe = math.exp(sum(abs(math.log(m.gm_ratio)) for m in ms if m.gm_ratio) / n) if n else None
        w = wilson(within, n)
        pts = [p for v in vals for p in v.points if p.metric == name]
        out.append(
            SystemMetric(
                name,
                n,
                gmfe,
                within,
                within / n if n else None,
                w[0] if w else None,
                w[1] if w else None,
                len(pts),
                sum(p.within_2_fold for p in pts),
                math.exp(sum(abs(math.log(p.ratio)) for p in pts) / len(pts)) if pts else None,
            )  # type: ignore[arg-type]
        )
    both = sum(1 for v in vals if all(m.tested for m in v.metrics))
    studies = sum(max(m.n_studies for m in v.metrics) for v in vals)
    iv = conformal_intervals(vals)
    reasons: dict[str, int] = defaultdict(int)
    for v in vals:
        if v.status == "not_validated":
            for r in v.reasons:
                reasons[r] += 1
    return SystemReport(
        len(vals),
        by_status,
        (out[0], out[1]),
        studies,
        both >= MIN_DRUGS_FOR_INTERPRETATION,
        MIN_DRUGS_FOR_INTERPRETATION,
        "interval_shown" if any(i.shown for i in iv) else "interval_n_too_small",
        both,
        iv,
        dict(sorted(reasons.items())),
    )
