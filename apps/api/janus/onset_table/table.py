"""FAERS time to onset for every PIPC row: the descriptive table (faers-onset-table design §4).
Pure.

One row per PIPC row (1-65): drug A's class -> the adverse event, from FAERS reports in which a
member of the class is a primary or secondary suspect and an event term of the row's event key
is reported. Each such report with a usable interval gives one `ReportInterval`.

Statistics follow the time machine (`janus.timemachine.onset`): empirical median and quartiles,
a percentile bootstrap interval of the median (seeded from the row's (class, event) pair, the
intervals sorted first, so neither report order nor row order matters) and, where the data allow
it, a Weibull shape with its likelihood-ratio interval. After the statistician's review
(review-statistician.md) the table adds an exact order-statistic interval of the median, flags a
zero-width bootstrap interval, counts reports that share an identical date pair (possible
duplicates or case series) and withholds every statistic when one such cluster dominates a row,
and publishes the Weibull shape only where heaping and ties do not decide it.

Thresholds: fewer than `COUNT_ONLY_BELOW` reports with an interval -> the count only; fewer than
`SMALL_SAMPLE_BELOW` -> median with intervals, flagged small sample, no shape. Every row states
that it is descriptive, not causal and not incidence, and counts reports, not people.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import Any, Final

from janus.timemachine.onset import MIN_REPORTS, summarize

COUNT_ONLY_BELOW: Final = MIN_REPORTS  # 10: below this, the count only
SMALL_SAMPLE_BELOW: Final = 30  # below this, no Weibull shape
BOOTSTRAP: Final = 1000
SEED: Final = 20261109
CLUSTER_SHARE_MAX: Final = 0.25  # above: one identical date pair dominates the row
SHAPE_ZERO_SHARE_MAX: Final = 0.5
SHAPE_MIN_DISTINCT: Final = 5
SENSITIVITY_MIN: Final = 10


class Status(StrEnum):
    described = "described"
    small_sample = "small_sample"
    cluster_dominated = "cluster_dominated"
    count_only = "count_only"
    no_interval = "no_interval"
    no_candidate_reports = "no_candidate_reports"


@dataclass(frozen=True, order=True)
class ReportInterval:
    """One candidate report with a usable interval (no report id is kept)."""

    days: int  # from the most recently started class-member suspect line
    longest_days: int  # from the earliest class-member start
    start_dt: str  # YYYYMMDD of the line that gives `days`
    event_dt: str  # YYYYMMDD, one per report
    day_one: bool  # a tied shortest line rests on a date on the 1st of a month
    jan_one: bool  # ... on 1 January
    class_lines: int  # class-member suspect lines with an interval in the report
    event_terms: int  # distinct event terms of the whole report

    def __post_init__(self) -> None:
        if not 0 <= self.days <= self.longest_days:
            raise ValueError("intervals are non-negative and days <= longest_days")


@dataclass(frozen=True)
class RowInput:
    position: int
    system: str
    drug_a: str
    adverse_event: str
    drug_b: str
    locator: str
    index_class: str
    event_key: str
    pts: tuple[str, ...]
    class_keys: tuple[str, ...]
    candidate_reports: int  # reports with a class member as PS/SS and an event term
    reports: tuple[ReportInterval, ...]  # the candidate reports that have a usable interval
    # Candidate reports without an interval, by the furthest `faers_onset` exclusion reason of
    # their lines; sums to candidate_reports - len(reports).
    excluded_by_reason: Mapping[str, int] = field(default_factory=dict[str, int])
    # (key, candidate reports, reports with an interval) for members with candidate reports.
    per_key: tuple[tuple[str, int, int], ...] = ()
    excluded_keys: tuple[str, ...] = ()  # class members left out for this table (curated)
    route_groups: tuple[str, ...] = ("systemic_or_unknown",)
    form_extensions_on: bool = False
    notes: tuple[tuple[str, str], ...] = ()  # (code, English note) from data/onset_row_notes.csv

    def __post_init__(self) -> None:
        if len(self.reports) > self.candidate_reports:
            raise ValueError("more intervals than candidate reports")
        if sum(self.excluded_by_reason.values()) != self.candidate_reports - len(self.reports):
            raise ValueError("exclusion reasons do not account for every candidate report")


def seed_for(index_class: str, event_key: str) -> int:
    digest = hashlib.sha256(f"{SEED}|{index_class}|{event_key}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def exact_median_ci(days: Sequence[float]) -> tuple[float, float, float] | None:
    """Distribution-free interval of the median from order statistics: (x_(k), x_(n-k+1)) with
    the largest k such that P(Bin(n, 1/2) <= k-1) <= 0.025, and its achieved coverage. None when
    n is too small for any such k (n < 6)."""
    n = len(days)
    s = sorted(days)
    cdf, k = 0.0, 0
    for j in range(n + 1):  # cdf = P(Bin <= j)
        cdf += math.comb(n, j) / 2**n
        if cdf > 0.025:
            break
        k = j + 1
    if k < 1:
        return None
    tail = sum(math.comb(n, j) for j in range(k)) / 2**n
    return float(s[k - 1]), float(s[n - k]), 1 - 2 * tail


def largest_cluster(reports: Iterable[ReportInterval]) -> tuple[int, int]:
    """(size of the largest group of reports with the same (start, event) date pair, reports in
    groups of three or more)."""
    sizes = Counter((r.start_dt, r.event_dt) for r in reports).values()
    return max(sizes, default=0), sum(v for v in sizes if v >= 3)


def status_of(candidates: int, n: int, largest: int = 0) -> Status:
    if candidates == 0:
        return Status.no_candidate_reports
    if n == 0:
        return Status.no_interval
    if n < COUNT_ONLY_BELOW:
        return Status.count_only
    if largest / n > CLUSTER_SHARE_MAX:
        return Status.cluster_dominated
    if n < SMALL_SAMPLE_BELOW:
        return Status.small_sample
    return Status.described


OMITTED: Final[Mapping[Status, str]] = {
    Status.no_candidate_reports: "no report in the FAERS window names a class member as a "
    "suspect together with an event term of this row",
    Status.no_interval: "no candidate report has both a complete therapy start date and a "
    "complete event date",
    Status.count_only: f"fewer than {COUNT_ONLY_BELOW} reports with a usable interval: counts "
    "only, no median and no shape",
    Status.cluster_dominated: f"more than {CLUSTER_SHARE_MAX:.0%} of the reports share one "
    "identical (therapy start, event) date pair across different cases, a sign of duplicate "
    "reports or a case series: counts only, no median and no shape",
}


def _r(x: float | None, nd: int = 4) -> float | None:
    return None if x is None else round(x, nd)


def _share(a: int, n: int, status: Status) -> float | None:
    return _r(a / n) if n and status not in (Status.count_only,) else None


def _shape_block(days: list[int], zero_share: float, status: Status) -> str | None:
    """Why no Weibull shape is published, or None when it is."""
    if status is not Status.described:
        return f"no shape below {SMALL_SAMPLE_BELOW} reports or when counts only are published"
    if zero_share > SHAPE_ZERO_SHARE_MAX:
        return (
            f"more than {SHAPE_ZERO_SHARE_MAX:.0%} same-day intervals: the shape would "
            "describe the heaping"
        )
    if len(set(days)) < SHAPE_MIN_DISTINCT:
        return f"fewer than {SHAPE_MIN_DISTINCT} distinct intervals"
    return None


def describe(row: RowInput, shared_with: Sequence[int] = ()) -> dict[str, Any]:
    reports = sorted(row.reports)
    days = [r.days for r in reports]
    n = len(days)
    largest, in_clusters = largest_cluster(reports)
    status = status_of(row.candidate_reports, n, largest)
    zero = sum(1 for d in days if d == 0)
    clean = [r.days for r in reports if not r.day_one]
    years = sorted({int(r.event_dt[:4]) for r in reports})
    out: dict[str, Any] = {
        "pipc_position": row.position,
        "pipc_system": row.system,
        "pipc_drug_a": row.drug_a,
        "pipc_adverse_event": row.adverse_event,
        "pipc_drug_b": row.drug_b,
        "pipc_locator": row.locator,
        "index_class": row.index_class,
        "class_ingredient_keys": list(row.class_keys),
        "excluded_class_keys": list(row.excluded_keys),
        "route_groups_counted": list(row.route_groups),
        "form_extensions_on": row.form_extensions_on,
        "event_key": row.event_key,
        "event_pts": list(row.pts),
        "shared_with_positions": sorted(p for p in shared_with if p != row.position),
        "candidate_reports": row.candidate_reports,
        "reports_with_interval": n,
        "usable_share": _r(n / row.candidate_reports) if row.candidate_reports else None,
        "candidates_without_interval_by_reason": dict(sorted(row.excluded_by_reason.items())),
        "members_with_reports": [
            {"key": k, "candidate_reports": cand, "reports_with_interval": usable}
            for k, cand, usable in sorted(row.per_key, key=lambda x: (-x[1], x[0]))
        ],
        "distinct_intervals": len(set(days)),
        "multi_line_reports": sum(1 for r in reports if r.class_lines > 1),
        "multi_event_reports": sum(1 for r in reports if r.event_terms > 1),
        "event_year_min": years[0] if years else None,
        "event_year_max": years[-1] if years else None,
        "status": status.value,
        "small_sample": status is Status.small_sample,
        "omitted_reason": OMITTED.get(status),
        "median_days": None,
        "q25_days": None,
        "q75_days": None,
        "median_ci_low_days": None,
        "median_ci_high_days": None,
        "median_ci_degenerate": None,
        "median_reflects_zero_heaping": None,
        "median_exact_ci_low_days": None,
        "median_exact_ci_high_days": None,
        "median_exact_ci_coverage": None,
        "median_days_earliest_class_start": None,
        "median_days_distinct_date_pairs": None,
        "zero_day_reports": zero,
        "zero_day_share": _share(zero, n, status),
        "day_one_reports": n - len(clean),
        "jan_one_reports": sum(1 for r in reports if r.jan_one),
        "day_one_share": _share(n - len(clean), n, status),
        "reports_without_day_one": len(clean),
        "median_days_without_day_one": None,
        "sensitivity_omitted_reason": None,
        "largest_date_cluster": largest,
        "reports_in_clusters_ge3": in_clusters,
        "weibull_shape": None,
        "weibull_shape_ci_low": None,
        "weibull_shape_ci_high": None,
        "weibull_scale_days": None,
        "weibull_shape_class": None,
        "shape_omitted_reason": None,
        "row_notes": [{"code": c, "note": t} for c, t in row.notes],
        "descriptive_only": True,
        "causal": False,
        "incidence": False,
        "counts_are": "reports",
    }
    if status not in (Status.described, Status.small_sample):
        return out
    s = summarize(days, random.Random(seed_for(row.index_class, row.event_key)), BOOTSTRAP)
    exact = exact_median_ci(days)
    pairs = sorted({(r.start_dt, r.event_dt): r.days for r in reports}.values())
    out.update(
        median_days=_r(s.median_days, 2),
        q25_days=_r(s.q25_days, 2),
        q75_days=_r(s.q75_days, 2),
        median_ci_low_days=_r(s.median_low, 2),
        median_ci_high_days=_r(s.median_high, 2),
        median_ci_degenerate=s.median_low == s.median_high,
        median_reflects_zero_heaping=zero / n > SHAPE_ZERO_SHARE_MAX,
        median_days_earliest_class_start=_r(float(median(r.longest_days for r in reports)), 2),
        median_days_distinct_date_pairs=_r(float(median(pairs)), 2)
        if len(pairs) >= SENSITIVITY_MIN
        else None,
    )
    if exact is not None:
        out.update(
            median_exact_ci_low_days=exact[0],
            median_exact_ci_high_days=exact[1],
            median_exact_ci_coverage=_r(exact[2]),
        )
    if len(clean) >= SENSITIVITY_MIN:
        out["median_days_without_day_one"] = _r(float(median(clean)), 2)
    else:
        out["sensitivity_omitted_reason"] = (
            f"fewer than {SENSITIVITY_MIN} reports remain without a day-01 date"
        )
    blocked = _shape_block(days, zero / n, status)
    if blocked is None and s.fit is not None:
        out.update(
            weibull_shape=_r(s.fit.shape),
            weibull_shape_ci_low=_r(s.fit.shape_low),
            weibull_shape_ci_high=_r(s.fit.shape_high),
            weibull_scale_days=_r(s.fit.scale, 2),
            weibull_shape_class=s.fit.shape_class.value,
        )
    else:
        out["shape_omitted_reason"] = blocked or "the Weibull fit failed"
    return out


def shared_groups(rows: Iterable[RowInput]) -> dict[int, list[int]]:
    """Position -> every position with the same (index class, event key), itself included."""
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    rows = list(rows)
    for r in rows:
        groups[(r.index_class, r.event_key)].append(r.position)
    return {r.position: sorted(groups[(r.index_class, r.event_key)]) for r in rows}


def table(rows: Iterable[RowInput]) -> list[dict[str, Any]]:
    rows = sorted(rows, key=lambda r: r.position)
    positions = [r.position for r in rows]
    if len(set(positions)) != len(positions):
        raise ValueError("a PIPC position appears twice")
    shared = shared_groups(rows)
    return [describe(r, shared[r.position]) for r in rows]


def counts_by_status(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {s.value: sum(1 for r in records if r["status"] == s.value) for s in Status}
