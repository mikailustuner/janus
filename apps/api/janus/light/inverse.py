"""Inverse FAERS signals: reported less often than expected (design §5.3, Req 1.1, DP6; P5). Pure.

For a goal's FAERS Preferred Terms (a union at report level) and an ingredient (scope `any`,
region `ALL`, N = mapped reports) the 2x2 table and its statistics come from `janus.memory.stats`
unchanged: Haldane when a cell is zero, Woolf interval, Yates chi-squared, the sensitivity table
with N = all reports. The pair is listed only when there are at least `MIN_REPORTS` reports and the
upper bound of the ROR interval is below 1.

A lower-than-expected count is not evidence of protection (Uesawa, Drug Saf 2026): reporting bias
(notoriety, indication) can create it, and the screening criteria are met by most pairs.
"""

from __future__ import annotations

from dataclasses import dataclass

from janus.memory.stats import PARAMS, Params, Sensitivity, Stats, cells_from_counts, evaluate
from janus.memory.stats import sensitivity as sensitivity_of


@dataclass(frozen=True)
class Counts:
    """Report counts behind one table (scope any, region ALL)."""

    a: int  # reports naming the ingredient and any PT of the goal
    ingredient: int  # reports naming the ingredient
    event_mapped: int  # reports with any PT of the goal, among mapped reports
    event_all: int  # the same among all reports
    n_mapped: int
    n_all: int


def faers_stats(c: Counts, params: Params = PARAMS) -> tuple[Stats, Sensitivity]:
    primary = evaluate(cells_from_counts(c.a, c.ingredient, c.event_mapped, c.n_mapped), params)
    sens = sensitivity_of(
        primary,
        a=c.a,
        ingredient=c.ingredient,
        event_all=c.event_all,
        n_all=c.n_all,
        params=params,
    )
    return primary, sens


def is_inverse(stats: Stats, params: Params = PARAMS) -> bool:
    est = stats.estimates
    return est is not None and stats.cells.a >= params.min_reports and est.ror_ci.high < 1.0


def inverse_signal(c: Counts, params: Params = PARAMS) -> tuple[Stats, Sensitivity] | None:
    """The statistics when the pair is an inverse signal, else None."""
    if c.a < params.min_reports:
        return None
    primary, sens = faers_stats(c, params)
    return (primary, sens) if is_inverse(primary, params) else None
