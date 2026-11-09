"""Time to onset: Weibull fit with the shape-parameter rule (design §7.2, Req 6.3). Pure.

Maximum likelihood through the profile likelihood of the shape β (the scale has a closed form
for a given β); 95 % interval for β from the likelihood-ratio test (χ²₁, 3.841). Shape rule as in
Hatahira 2017 (doi:10.1186/s40780-017-0088-5) and Hasegawa 2020 (doi:10.1002/pds.5108):
interval below 1 → hazard decreasing ("early"), interval containing 1 → constant ("random"),
interval above 1 → increasing ("wear-out"). Cornelius 2012 (doi:10.2165/11599740-000000000-00000)
is the method paper for the shape test.

Same-day onset is recorded as 0 days; a Weibull needs positive times, so every interval is
shifted by half a day (DP-T11).
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

SHIFT_DAYS = 0.5
CHI2_1_95 = 3.841458820694124
MIN_REPORTS = 10
SHAPE_MIN, SHAPE_MAX = 0.01, 100.0  # search range for the shape


class Shape(StrEnum):
    early = "early"  # decreasing hazard
    random = "random"  # constant hazard
    wear_out = "wear_out"  # increasing hazard


@dataclass(frozen=True)
class WeibullFit:
    n: int
    shape: float
    scale: float
    shape_low: float
    shape_high: float

    def quantile(self, p: float) -> float:
        """Quantile in reported days (the half-day shift removed, floored at 0)."""
        if not (0 < p < 1):
            raise ValueError("p must be in (0, 1)")
        return max(self.scale * (-math.log(1 - p)) ** (1 / self.shape) - SHIFT_DAYS, 0.0)

    def cdf(self, t: float) -> float:
        """Share of onsets by reported day t."""
        x = t + SHIFT_DAYS
        return 0.0 if x <= 0 else 1 - math.exp(-((x / self.scale) ** self.shape))

    @property
    def shape_class(self) -> Shape:
        if self.shape_high < 1:
            return Shape.early
        if self.shape_low > 1:
            return Shape.wear_out
        return Shape.random


class FitError(ValueError):
    """Too few or degenerate data for a Weibull fit."""


def _prepare(days: Sequence[float], shift: float) -> tuple[list[float], float]:
    if any(d < 0 or not math.isfinite(d) for d in days):
        raise FitError("onset days must be finite and non-negative")
    x = [d + shift for d in days]
    if min(x) <= 0:
        raise FitError("onset times must be positive after the shift")
    if len(x) < 2 or max(x) == min(x):
        raise FitError("need at least two different onset times")
    g = math.exp(sum(math.log(v) for v in x) / len(x))  # scale by the geometric mean (stability)
    return [v / g for v in x], g


def _log_sum_pow(lx: Sequence[float], beta: float) -> tuple[float, list[float]]:
    """log(sum x^beta) and the normalised weights x^beta / sum x^beta, without overflow."""
    e = [beta * v for v in lx]
    top = max(e)
    w = [math.exp(v - top) for v in e]
    total = sum(w)
    return top + math.log(total), [v / total for v in w]


def _profile(lx: Sequence[float], beta: float) -> float:
    n = len(lx)
    log_s, _ = _log_sum_pow(lx, beta)
    return n * math.log(beta) - n * (log_s - math.log(n)) + (beta - 1) * sum(lx) - n


def _score(lx: Sequence[float], beta: float) -> float:
    """Derivative of the profile log-likelihood / n; strictly decreasing in beta."""
    _, w = _log_sum_pow(lx, beta)
    return 1 / beta + sum(lx) / len(lx) - sum(a * b for a, b in zip(w, lx, strict=True))


def _bisect(fn: Callable[[float], float], lo: float, hi: float, iters: int = 200) -> float:
    """Root of a function that changes sign once on [lo, hi] (geometric bisection)."""
    flo = fn(lo)
    for _ in range(iters):
        mid = math.sqrt(lo * hi)
        fm = fn(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
        if hi / lo < 1 + 1e-12:
            break
    return math.sqrt(lo * hi)


def fit_weibull(days: Sequence[float], shift: float = SHIFT_DAYS) -> WeibullFit:
    """Fit to `days + shift`. The shift is `SHIFT_DAYS` for reported days; tests use 0."""
    x, g = _prepare(days, shift)
    lx = [math.log(v) for v in x]
    lo, hi = SHAPE_MIN, SHAPE_MAX
    beta = _bisect(lambda b: _score(lx, b), lo, hi)
    log_s, _ = _log_sum_pow(lx, beta)
    alpha = math.exp((log_s - math.log(len(x))) / beta) * g
    lmax = _profile(lx, beta)

    def drop(b: float) -> float:
        return 2 * (lmax - _profile(lx, b)) - CHI2_1_95

    b_low = _bisect(drop, lo, beta) if drop(lo) > 0 else lo
    b_high = _bisect(drop, beta, hi) if drop(hi) > 0 else hi
    return WeibullFit(len(x), beta, alpha, min(b_low, beta), max(b_high, beta))


@dataclass(frozen=True)
class OnsetSummary:
    n: int
    median_days: float
    q25_days: float
    q75_days: float
    median_low: float
    median_high: float
    fit: WeibullFit | None
    small_sample: bool


def _empirical(values: Sequence[float], q: float) -> float:
    s = sorted(values)
    pos = (len(s) - 1) * q
    lo = math.floor(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def summarize(days: Sequence[float], rng: random.Random, boot: int = 1000) -> OnsetSummary:
    """Empirical median and quartiles of the reported intervals, a bootstrap 95 % interval for
    the median, and the Weibull fit when there are at least `MIN_REPORTS` reports."""
    if not days:
        raise FitError("no onset data")
    med = _empirical(days, 0.5)
    meds = sorted(
        _empirical([days[rng.randrange(len(days))] for _ in days], 0.5) for _ in range(boot)
    )
    fit: WeibullFit | None = None
    if len(days) >= MIN_REPORTS:
        try:
            fit = fit_weibull(days)
        except FitError:
            fit = None
    return OnsetSummary(
        n=len(days),
        median_days=med,
        q25_days=_empirical(days, 0.25),
        q75_days=_empirical(days, 0.75),
        median_low=_empirical(meds, 0.025),
        median_high=_empirical(meds, 0.975),
        fit=fit,
        small_sample=len(days) < 30,
    )
