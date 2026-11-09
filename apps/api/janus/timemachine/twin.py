"""Digital twin of a cascade: risk window over time and agreement with published timing
(design §7.3-§7.4, Req 7). Pure.

The risk window is the central 80 % of the reported time to onset (10th-90th percentile of the
Weibull fit, or of the reports when there is no fit). The PK part adds, per virtual person, the
time to reach 90 % of steady state. Both are descriptive: FAERS intervals are what reporters
wrote down (spontaneous reports, not incidence), and the PK curves are model outputs.

Agreement with a published window (DP-T12):
* published median with IQR → `agrees` when the two IQRs overlap, else `disagrees`;
* published window [low, high] (e.g. "first 4 months") → `agrees` when the reported median lies
  inside, else `disagrees`;
* qualitative only (no numbers) → `not_comparable`.
With fewer than 10 reports the verdict is still computed but flagged as a small sample.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from janus.timemachine.onset import OnsetSummary, WeibullFit


class PublishedKind(StrEnum):
    median_iqr = "median_iqr"
    window = "window"
    qualitative = "qualitative"


class Agreement(StrEnum):
    agrees = "agrees"
    disagrees = "disagrees"
    not_comparable = "not_comparable"


@dataclass(frozen=True)
class Published:
    reference: str
    kind: PublishedKind
    low_days: float | None = None  # q25 or window start
    high_days: float | None = None  # q75 or window end
    median_days: float | None = None

    def __post_init__(self) -> None:
        if self.kind is PublishedKind.qualitative:
            return
        if (
            self.low_days is None
            or self.high_days is None
            or not (0 <= self.low_days <= self.high_days)
        ):
            raise ValueError("numeric published window needs 0 <= low <= high")


def agreement(ours: OnsetSummary, pub: Published) -> Agreement:
    if pub.kind is PublishedKind.qualitative:
        return Agreement.not_comparable
    if pub.low_days is None or pub.high_days is None:  # excluded by __post_init__
        raise ValueError("numeric published window without bounds")
    if pub.kind is PublishedKind.median_iqr:
        overlap = ours.q25_days <= pub.high_days and pub.low_days <= ours.q75_days
        return Agreement.agrees if overlap else Agreement.disagrees
    inside = pub.low_days <= ours.median_days <= pub.high_days
    return Agreement.agrees if inside else Agreement.disagrees


@dataclass(frozen=True)
class RiskWindow:
    start_days: float
    end_days: float
    basis: str  # "weibull" | "reports"


def risk_window(ours: OnsetSummary, days: Sequence[float]) -> RiskWindow:
    fit: WeibullFit | None = ours.fit
    if fit is not None:
        return RiskWindow(fit.quantile(0.10), fit.quantile(0.90), "weibull")
    s = sorted(days)
    lo = s[round((len(s) - 1) * 0.10)]
    hi = s[round((len(s) - 1) * 0.90)]
    return RiskWindow(float(lo), float(hi), "reports")


def onset_curve(fit: WeibullFit, grid: Sequence[float]) -> list[float]:
    """Share of the reported onsets expected by each day (Weibull CDF), for the research chart."""
    return [fit.cdf(t) for t in grid]
