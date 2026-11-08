"""Disproportionality statistics for one 2x2 table of FAERS reports (collective-memory design §3).

Pure: no I/O, no clock. Decisions (PRR >= 2, chi-squared >= 4, the zero-cell rule) are made with
exact integers and `fractions.Fraction`; only the logarithm and the square root of the ROR
interval use floats. Counts are reports, never people.

2x2 table for drug D and event E:  a = D and E, b = D without E, c = E without D, d = neither.

    PRR = (a/(a+b)) / (c/(c+d))          ROR = (a*d) / (b*c)
    interval = exp(ln ROR +- 1.96 * sqrt(1/a + 1/b + 1/c + 1/d))        (Woolf, 95%)
    chi-squared = Pearson with Yates' continuity correction, 1 df, on the RAW table

When any raw cell is zero, 0.5 is added to all four cells (Haldane) for PRR, ROR and the
interval; chi-squared never uses the corrected cells. Evans criteria: PRR >= 2, chi-squared >= 4,
at least 3 reports (Evans, Waller, Davis, Pharmacoepidemiol Drug Saf 2001;10(6):483-486).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Final

from janus.memory.model import Assessment


class StatsError(ValueError):
    """A table is not a valid 2x2 table of counts. The message never names a medicine or event."""


@dataclass(frozen=True)
class Params:
    min_reports: int = 3  # display threshold and minimum a of the criteria
    weak_below: int = 5  # `disproportionate` needs a >= weak_below
    prr_min: Fraction = Fraction(2)
    chi2_min: Fraction = Fraction(4)
    z: float = 1.96  # 95% interval
    ci_level: float = 0.95
    haldane: Fraction = Fraction(1, 2)


PARAMS: Final = Params()
CHI2_FORM: Final = "yates"
INTERVAL_METHOD: Final = "woolf_log"


@dataclass(frozen=True)
class Table:
    a: int
    b: int
    c: int
    d: int

    @property
    def n(self) -> int:
        return self.a + self.b + self.c + self.d


@dataclass(frozen=True)
class Interval:
    low: float
    high: float
    level: float
    method: str


@dataclass(frozen=True)
class Estimates:
    prr: float
    ror: float
    ror_ci: Interval
    chi2: float
    chi2_form: str


@dataclass(frozen=True)
class Stats:
    cells: Table
    haldane_applied: bool
    estimates: Estimates | None  # None exactly when a == 0
    evans_met: bool  # PRR >= 2, chi-squared >= 4 and a >= min_reports
    ror_signal: bool  # lower bound of the ROR interval > 1 and a >= min_reports
    assessment: Assessment


@dataclass(frozen=True)
class Sensitivity:
    """The same statistics with N = all reports (`data-pipelines` DP32)."""

    stats: Stats
    differs: bool  # five-class assessment differs from the primary one


def validate(t: Table) -> None:
    for v in (t.a, t.b, t.c, t.d):
        if isinstance(v, bool) or not isinstance(v, int):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise StatsError("counts must be integers")
        if v < 0:
            raise StatsError("a count is negative")


def cells_from_counts(a: int, ingredient: int, event: int, n: int) -> Table:
    """b = ingredient - a, c = event - a, d = n - ingredient - event + a (Req 15.5).

    Raises `StatsError` instead of repairing an inconsistent count (Req 1.1).
    """
    t = Table(a, ingredient - a, event - a, n - ingredient - event + a)
    validate(t)
    return t


def chi2_yates_exact(t: Table) -> Fraction:
    """Yates-corrected Pearson chi-squared on the raw table; 0 when a margin is zero."""
    n = t.n
    m = (t.a + t.b) * (t.c + t.d) * (t.a + t.c) * (t.b + t.d)
    if n == 0 or m == 0:
        return Fraction(0)
    excess = max(0, 2 * abs(t.a * t.d - t.b * t.c) - n)
    return Fraction(n * excess * excess, 4 * m)


def chi2_pearson_exact(t: Table) -> Fraction:
    """Uncorrected Pearson chi-squared (kept for tests and comparison; not used for decisions)."""
    n = t.n
    m = (t.a + t.b) * (t.c + t.d) * (t.a + t.c) * (t.b + t.d)
    if n == 0 or m == 0:
        return Fraction(0)
    diff = t.a * t.d - t.b * t.c
    return Fraction(n * diff * diff, m)


def _cells(t: Table, params: Params) -> tuple[Fraction, Fraction, Fraction, Fraction, bool]:
    corrected = 0 in (t.a, t.b, t.c, t.d)
    h = params.haldane if corrected else Fraction(0)
    return t.a + h, t.b + h, t.c + h, t.d + h, corrected


def prr_exact(t: Table, params: Params = PARAMS) -> Fraction:
    a, b, c, d, _ = _cells(t, params)
    return (a / (a + b)) / (c / (c + d))


def ror_exact(t: Table, params: Params = PARAMS) -> Fraction:
    a, b, c, d, _ = _cells(t, params)
    return (a * d) / (b * c)


def ror_interval(t: Table, params: Params = PARAMS) -> Interval:
    a, b, c, d, _ = _cells(t, params)
    ln_ror = math.log(float((a * d) / (b * c)))
    se = math.sqrt(float(1 / a + 1 / b + 1 / c + 1 / d))
    return Interval(
        low=math.exp(ln_ror - params.z * se),
        high=math.exp(ln_ror + params.z * se),
        level=params.ci_level,
        method=INTERVAL_METHOD,
    )


def assess(a: int, *, evans_met: bool, ror_signal: bool, params: Params = PARAMS) -> Assessment:
    """The statistician's rule (statistics review Q5)."""
    if a == 0:
        return "no_reports"
    if a < params.min_reports:
        return "insufficient_data"
    if evans_met and ror_signal and a >= params.weak_below:
        return "disproportionate"
    if evans_met or ror_signal:
        return "weak"
    return "not_disproportionate"


def evaluate(t: Table, params: Params = PARAMS) -> Stats:
    validate(t)
    if t.a == 0:
        return Stats(t, False, None, False, False, "no_reports")
    corrected = 0 in (t.b, t.c, t.d)
    prr = prr_exact(t, params)
    ror = ror_exact(t, params)
    chi2 = chi2_yates_exact(t)
    interval = ror_interval(t, params)
    enough = t.a >= params.min_reports
    evans_met = enough and prr >= params.prr_min and chi2 >= params.chi2_min
    ror_signal = enough and interval.low > 1.0
    return Stats(
        cells=t,
        haldane_applied=corrected,
        estimates=Estimates(
            prr=float(prr),
            ror=float(ror),
            ror_ci=interval,
            chi2=float(chi2),
            chi2_form=CHI2_FORM,
        ),
        evans_met=evans_met,
        ror_signal=ror_signal,
        assessment=assess(t.a, evans_met=evans_met, ror_signal=ror_signal, params=params),
    )


def sensitivity(
    primary: Stats,
    *,
    a: int,
    ingredient: int,
    event_all: int,
    n_all: int,
    params: Params = PARAMS,
) -> Sensitivity:
    """Recompute with N = all reports and event counts over all reports; b is unchanged.

    The flag compares the five-class assessment (statistics review Q1).
    """
    other = evaluate(cells_from_counts(a, ingredient, event_all, n_all), params)
    return Sensitivity(other, other.assessment != primary.assessment)


def estimates_from_numbers(
    prr: float, chi2: float, ror_low: float, a: int, params: Params = PARAMS
) -> tuple[bool, bool]:
    """Re-evaluate the two criteria from serialised numbers (round-trip check, P5)."""
    enough = a >= params.min_reports
    return (
        enough and prr >= float(params.prr_min) and chi2 >= float(params.chi2_min),
        enough and ror_low > 1.0,
    )
