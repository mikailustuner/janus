"""Time machine pure modules (time-machine design §9, P4-P9, P12-P14)."""

from __future__ import annotations

import math
import random
from pathlib import Path

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from janus.timemachine.exposure import Verdict, compare
from janus.timemachine.onset import FitError, Shape, fit_weibull, summarize
from janus.timemachine.pk import (
    Band,
    LogNormal,
    OneCompartment,
    ParamSpec,
    Uniform,
    amounts,
    auc_inf,
    cmax,
    concentration,
    simulate,
    tmax,
)
from janus.timemachine.twin import Agreement, Published, PublishedKind, agreement
from janus.timemachine.units import Interval, Unit, UnitError, load_units, to_grams

UNITS = Path(__file__).resolve().parents[3] / "data" / "time_machine" / "units.csv"

pos = st.floats(0.05, 50.0, allow_nan=False)
models = st.builds(
    OneCompartment,
    f=st.floats(0.01, 1.0),
    ka=st.floats(0.05, 10.0),
    cl=st.floats(0.05, 100.0),
    v=st.floats(1.0, 2000.0),
    tlag=st.floats(0.0, 3.0),
)
times = st.floats(0.0, 500.0)
doses = st.floats(0.01, 2000.0)


# --- units (P4) ------------------------------------------------------------------------------


def test_unit_table_is_ordered_and_cited() -> None:
    units = load_units(UNITS)
    assert {"dirham", "mithqal"} <= set(units)
    for u in units.values():
        assert u.sources
    assert units["dirham"].grams.high < units["mithqal"].grams.low  # a dirham is 7/10 mithqal


@given(st.floats(0.01, 100.0), st.floats(0.01, 100.0))
def test_to_grams_is_linear_in_amount(a: float, b: float) -> None:
    units = {"u": Unit("u", Interval(2.8, 3.0, 3.3), ("s",))}
    x, y, xy = to_grams(a, "u", units), to_grams(b, "u", units), to_grams(a + b, "u", units)
    assert math.isclose(x.low + y.low, xy.low, rel_tol=1e-9)
    assert math.isclose(x.high + y.high, xy.high, rel_tol=1e-9)
    assert x.low <= x.central <= x.high


@given(st.floats(max_value=0.0, allow_nan=False))
def test_to_grams_refuses_non_positive_amounts(a: float) -> None:
    with pytest.raises(UnitError):
        to_grams(a, "dirham", load_units(UNITS))


# --- PK solver invariants (P5-P7) ------------------------------------------------------------


@given(models, doses, times)
def test_concentration_is_non_negative_and_mass_is_conserved(
    m: OneCompartment, d: float, t: float
) -> None:
    assert concentration(m, d, t) >= 0
    a = amounts(m, d, t)
    assert min(a.gut, a.central, a.eliminated, a.not_absorbed) >= -1e-9 * d
    assert math.isclose(a.gut + a.central + a.eliminated + a.not_absorbed, d, rel_tol=1e-9)


@given(models, doses, times, st.floats(0.1, 10.0))
def test_concentration_is_linear_in_dose(m: OneCompartment, d: float, t: float, c: float) -> None:
    assert math.isclose(
        concentration(m, c * d, t), c * concentration(m, d, t), rel_tol=1e-9, abs_tol=1e-15
    )


@given(models, doses, times, st.floats(1.0, 48.0), st.integers(1, 6))
def test_repeated_doses_superpose(
    m: OneCompartment, d: float, t: float, tau: float, n: int
) -> None:
    total = concentration(m, d, t, tau, n)
    parts = sum(concentration(m, d, t - i * tau) for i in range(n) if t - i * tau > 0)
    assert math.isclose(total, parts, rel_tol=1e-12, abs_tol=1e-15)


@given(models)
def test_auc_and_cmax_match_the_curve(m: OneCompartment) -> None:
    assume(m.half_life < 200 and m.ka > 0.1)
    end = m.tlag + 12 * max(m.half_life, math.log(2) / m.ka)
    steps = 20000
    h = end / steps
    ys = [concentration(m, 100.0, i * h) for i in range(steps + 1)]
    trap = h * (sum(ys) - (ys[0] + ys[-1]) / 2)
    assert math.isclose(trap, auc_inf(m, 100.0), rel_tol=0.01)
    assert cmax(m, 100.0) >= max(ys) * (1 - 1e-6)
    assert tmax(m) >= m.tlag


def test_simulation_bands_are_ordered_and_reproducible() -> None:
    spec = ParamSpec(
        Uniform(0.5, 0.7), LogNormal(1.0, 1.5), LogNormal(10.0, 1.3), LogNormal(50.0, 1.2)
    )
    grid = [0.5 * i for i in range(1, 49)]
    a = simulate(spec, 10.0, grid, random.Random(7), n=200)
    b = simulate(spec, 10.0, grid, random.Random(7), n=200)
    assert a == b
    for x in [*a[0], a[1], a[2]]:
        assert x.p5 <= x.p50 <= x.p95


# --- Weibull (P8-P9) -------------------------------------------------------------------------


@given(st.floats(0.5, 3.0), st.floats(5.0, 200.0), st.integers(0, 10_000))
def test_weibull_fit_recovers_the_shape_on_synthetic_data(
    beta: float, alpha: float, seed: int
) -> None:
    rng = random.Random(seed)
    # Exact Weibull draws, fitted without the half-day shift used for reported days.
    days = [rng.weibullvariate(alpha, beta) for _ in range(3000)]
    fit = fit_weibull(days, shift=0.0)
    # 5 asymptotic standard errors of the MLE: SE(shape)/shape ~ 0.78/sqrt(n),
    # SE(log scale) ~ 1.05/(shape sqrt(n)).
    n = len(days)
    assert abs(fit.shape - beta) / beta < 5 * 0.78 / math.sqrt(n)
    assert abs(math.log(fit.scale / alpha)) < 5 * 1.05 / (beta * math.sqrt(n))
    assert fit.shape_low <= fit.shape <= fit.shape_high


@given(st.lists(st.integers(0, 3650), min_size=2, max_size=200))
def test_weibull_interval_and_class_are_coherent(days: list[int]) -> None:
    assume(len(set(days)) > 1)
    fit = fit_weibull([float(d) for d in days])
    assert fit.shape_low <= fit.shape <= fit.shape_high
    if fit.shape_class is Shape.early:
        assert fit.shape_high < 1
    elif fit.shape_class is Shape.wear_out:
        assert fit.shape_low > 1
    q = [fit.quantile(p) for p in (0.1, 0.5, 0.9)]
    assert q == sorted(q) and q[0] >= 0


def test_weibull_refuses_degenerate_data() -> None:
    with pytest.raises(FitError):
        fit_weibull([3.0, 3.0, 3.0])
    with pytest.raises(FitError):
        fit_weibull([-1.0, 2.0])


@given(st.lists(st.integers(0, 365), min_size=1, max_size=60), st.integers(0, 100))
def test_summary_quartiles_are_ordered_and_small_samples_flagged(
    days: list[int], seed: int
) -> None:
    s = summarize([float(d) for d in days], random.Random(seed), boot=200)
    assert s.q25_days <= s.median_days <= s.q75_days
    assert s.median_low <= s.median_high
    assert s.small_sample == (len(days) < 30)
    assert (s.fit is None) or len(days) >= 10


@given(
    st.lists(st.integers(0, 365), min_size=1, max_size=60),
    st.integers(0, 100),
    st.randoms(use_true_random=False),
)
def test_summary_does_not_depend_on_row_order(
    days: list[int], seed: int, shuffler: random.Random
) -> None:
    """The bootstrap interval is the same for any order of the same reports (the query's GROUP BY
    order is not stable; found 2026-11-09 when two builds gave 9 and 19 days)."""
    a = [float(d) for d in days]
    b = list(a)
    shuffler.shuffle(b)
    sa = summarize(a, random.Random(seed), boot=100)
    sb = summarize(b, random.Random(seed), boot=100)
    assert (sa.median_low, sa.median_high) == (sb.median_low, sb.median_high)


# --- exposure (P12) and agreement (P13) ------------------------------------------------------


bands = st.tuples(pos, pos, pos).map(lambda t: Band(*sorted(t)))


@given(bands, pos, st.one_of(st.none(), st.floats(0.001, 1.0)), st.floats(1.0, 100.0))
def test_exposure_verdict_is_monotone_in_concentration(
    b: Band, potency: float, fu: float | None, k: float
) -> None:
    order = [Verdict.stays_below, Verdict.overlaps, Verdict.reaches]
    low = compare(b, potency, fu)
    high = compare(Band(b.p5 * k, b.p50 * k, b.p95 * k), potency, fu)
    assert order.index(high.verdict) >= order.index(low.verdict)
    assert (low.verdict is Verdict.reaches) == (low.margin_low >= 1)
    assert (low.verdict is Verdict.stays_below) == (low.margin_high < 1)


@given(st.lists(st.integers(0, 365), min_size=1, max_size=40))
def test_published_window_equal_to_ours_agrees(days: list[int]) -> None:
    s = summarize([float(d) for d in days], random.Random(0), boot=50)
    same = Published("x", PublishedKind.median_iqr, s.q25_days, s.q75_days, s.median_days)
    assert agreement(s, same) is Agreement.agrees
    assert agreement(s, Published("x", PublishedKind.qualitative)) is Agreement.not_comparable
    far = Published("x", PublishedKind.window, s.q75_days + 1, s.q75_days + 2)
    assert agreement(s, far) is Agreement.disagrees
