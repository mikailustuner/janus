"""Validation of a parameter set against held-out studies (design DP-M7, DP-M8; Req 3).

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
from dataclasses import dataclass, field
from typing import Literal

from janus.modelkit.builder import NoSet, ParameterSet
from janus.modelkit.evidence import Ev, exclusion_reason, split_studies
from janus.timemachine.pk import OneCompartment, auc_inf, cmax

Status = Literal["validated", "not_validated", "failed"]
BAND = 2.0
MIN_STUDIES_FOR_INTERVAL = 20
MIN_DRUGS_FOR_INTERPRETATION = 10


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


def predict(ps: ParameterSet, metric: str, dose_mg: float) -> float | None:
    """Predicted AUC (ng*h/mL, to infinity) or Cmax (ng/mL, one dose) from a set; None if the set
    cannot predict it (no absorption rate for Cmax)."""
    f, cl, v, ka = ps.engine()
    if metric == "auc":
        return auc_inf(OneCompartment(f, 1.0, cl, v), dose_mg) * 1000.0
    if ka is None or abs(ka - cl / v) < 1e-12:
        return None
    return cmax(OneCompartment(f, ka, cl, v), dose_mg) * 1000.0


def _obs_reason(e: Ev, ps: ParameterSet) -> str | None:
    why = exclusion_reason(e)
    if why:
        return why
    if e.parameter == "auc_last":
        return "auc_to_last_sampling_time_not_comparable"
    if e.parameter not in ("cmax", "auc_inf", "auc_tau"):
        return "not_an_observation"
    if e.dose is None or e.route != "oral":
        return "needs_oral_dose"
    if e.parameter == "auc_tau" and not (e.regimen == "multiple" and e.interval_h):
        return "auc_tau_needs_multiple_dose_interval"
    if e.parameter == "cmax" and e.regimen != "single":
        return "steady_state_cmax_not_modelled"
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


def validate(drug_key: str, rows: list[Ev], ps: ParameterSet | NoSet) -> Validation:
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
    for e in rows:
        if e.parameter not in ("cmax", "auc_inf", "auc_last", "auc_tau"):
            continue
        if e.study not in test:
            excluded.append((e.eid, "observation_in_building_study"))
            continue
        why = _obs_reason(e, ps)
        if why:
            excluded.append((e.eid, why))
            continue
        metric = "cmax" if e.parameter == "cmax" else "auc"
        assert e.dose is not None  # noqa: S101 - checked in _obs_reason
        pred = predict(ps, metric, e.dose)
        if pred is None or pred <= 0:
            excluded.append((e.eid, "set_cannot_predict_metric"))
            continue
        ratio = pred / e.value_si
        pts.append(
            Point(
                e.eid,
                metric,
                e.study_id,
                e.dose,
                e.value_si,
                pred,
                ratio,
                1 / BAND <= ratio <= BAND,
            )
        )
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
        tuple(suspect), interval, failed_points,
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
