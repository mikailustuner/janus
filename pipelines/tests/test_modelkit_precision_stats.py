"""Precision statistics of the B3a protocol: Wilson, kappa, stratified cluster bootstrap, design
effect, acceptance rule."""

from __future__ import annotations

import pytest

from janus_pipelines.modelkit.precision_stats import (
    Item,
    accepted,
    cluster_bootstrap,
    estimate,
    kappa,
    summarise,
    wilson,
)


def items(spec: list[tuple[str, str, int, int]]) -> list[Item]:
    """(cluster, stratum, correct, incorrect) -> agreed items."""
    out: list[Item] = []
    for c, s, k, e in spec:
        out += [Item(c, s, "correct", "correct")] * k + [Item(c, s, "incorrect", "incorrect")] * e
    return out


def test_wilson_matches_the_published_census_interval() -> None:
    lo, hi = wilson(125, 126) or (0, 0)
    assert round(lo, 3) == 0.956 and round(hi, 3) == 0.999
    assert wilson(0, 0) is None


def test_kappa_perfect_and_chance() -> None:
    assert kappa(["correct", "incorrect"], ["correct", "incorrect"]) == 1.0
    assert kappa(["correct", "incorrect"], ["incorrect", "correct"]) == pytest.approx(-1.0)


def test_unagreed_and_undecidable_items_leave_the_denominator() -> None:
    its = [
        Item("a", "s", "correct", "correct"),
        Item("a", "s", "correct", "incorrect"),
        Item("b", "s", "cannot_judge", "cannot_judge"),
    ]
    s = summarise(its, resamples=200)
    assert (s.items, s.agreed, s.correct, s.precision) == (3, 1, 1, 1.0)
    assert s.conservative == pytest.approx(1 / 3)


def test_stratum_weights_combine_band_precisions() -> None:
    its = items([("a", "L3", 10, 0), ("b", "L0", 5, 5)])
    assert estimate(its) == pytest.approx(15 / 20)
    assert estimate(its, {"L3": 1, "L0": 3}) == pytest.approx((1 * 1.0 + 3 * 0.5) / 4)


def test_bootstrap_is_deterministic_for_a_seed() -> None:
    its = items([(f"s{i}", "x", 4, i % 2) for i in range(12)])
    assert cluster_bootstrap(its, resamples=300, seed=1) == cluster_bootstrap(
        its, resamples=300, seed=1
    )


def test_errors_concentrated_in_one_study_give_a_design_effect_above_one() -> None:
    spread = items([(f"s{i}", "x", 9, 1) for i in range(10)])
    lumped = items([(f"s{i}", "x", 10, 0) for i in range(9)] + [("s9", "x", 0, 10)])
    a, b = summarise(spread, resamples=1000), summarise(lumped, resamples=1000)
    assert a.precision == b.precision == pytest.approx(0.9)
    assert b.design_effect is not None and a.design_effect is not None
    assert b.design_effect > 3 * a.design_effect
    assert b.cluster_lower is not None and a.cluster_lower is not None
    assert b.cluster_lower < a.cluster_lower


def test_without_errors_the_design_effect_is_the_mean_study_size() -> None:
    its = items([(f"s{i}", "x", 6, 0) for i in range(8)])
    s = summarise(its, resamples=200)
    assert s.design_effect == pytest.approx(6.0) and not s.design_effect_estimated
    assert s.n_effective == pytest.approx(8.0)
    assert s.cluster_lower is not None and s.wilson is not None
    assert s.cluster_lower < s.wilson[0]


def test_acceptance_needs_the_cluster_lower_bound() -> None:
    many = items([(f"s{i}", "x", 3, 0) for i in range(60)])
    few = items([(f"s{i}", "x", 30, 0) for i in range(6)])
    assert accepted(summarise(many, resamples=200))
    assert not accepted(summarise(few, resamples=200))
