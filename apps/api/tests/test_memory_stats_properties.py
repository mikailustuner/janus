"""Property tests for the pure statistics (collective-memory design §10: P1-P6, P9 pure part, P29).

No I/O. The reference implementations are written independently: `Decimal` with 50 digits for the
real-valued results and the integer inequalities of design §3.1 for the decisions.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from decimal import Decimal, getcontext
from fractions import Fraction

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from janus.memory.model import ASSESSMENT_ORDER
from janus.memory.stats import (
    PARAMS,
    StatsError,
    Table,
    assess,
    cells_from_counts,
    chi2_pearson_exact,
    chi2_yates_exact,
    estimates_from_numbers,
    evaluate,
    sensitivity,
)

getcontext().prec = 50

BIG = 2_000_000
counts = st.integers(0, BIG)
small = st.integers(0, 40)
positive = st.integers(1, BIG)


@st.composite
def tables(draw: st.DrawFn, *, min_a: int = 0, zeros: bool = True) -> Table:
    lo = 0 if zeros else 1
    pick = st.one_of(st.integers(lo, 60), st.integers(lo, BIG))
    return Table(
        draw(pick) if min_a == 0 else draw(st.integers(min_a, BIG)),
        draw(pick),
        draw(pick),
        draw(pick),
    )


def ref_cells(t: Table) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    h = Decimal("0.5") if 0 in (t.a, t.b, t.c, t.d) else Decimal(0)
    return Decimal(t.a) + h, Decimal(t.b) + h, Decimal(t.c) + h, Decimal(t.d) + h


def ref_prr_ge_2(t: Table) -> bool:
    """Integer inequalities of design §3.1."""
    a, b, c, d = t.a, t.b, t.c, t.d
    if 0 in (a, b, c, d):
        return (2 * a + 1) * (c + d + 1) >= 2 * (2 * c + 1) * (a + b + 1)
    return a * (c + d) >= 2 * c * (a + b)


def ref_chi2_yates_ge_4(t: Table) -> bool:
    a, b, c, d = t.a, t.b, t.c, t.d
    n = t.n
    delta2 = 2 * abs(a * d - b * c)
    if delta2 < n:
        return False
    return n * (delta2 - n) ** 2 >= 16 * (a + b) * (c + d) * (a + c) * (b + d)


def rel_close(x: float, y: Decimal, tol: float = 1e-12) -> bool:
    return abs(Decimal(x) - y) <= Decimal(tol) * abs(y)


# --- P1 ----------------------------------------------------------------------------------------


@settings(max_examples=300, deadline=None)
@given(tables(min_a=1))
def test_estimates_are_well_formed(t: Table) -> None:
    """Feature: collective-memory, Property P1 — Validates: Req 1.2, 1.6."""
    s = evaluate(t)
    assert s.estimates is not None
    e = s.estimates
    for v in (e.prr, e.ror, e.ror_ci.low, e.ror_ci.high, e.chi2):
        assert math.isfinite(v)
    assert e.prr > 0 and e.ror > 0 and e.ror_ci.low > 0
    assert e.ror_ci.low <= e.ror * (1 + 1e-12)
    assert e.ror * (1 - 1e-12) <= e.ror_ci.high
    assert e.chi2 >= 0 and e.chi2_form == "yates"
    assert e.ror_ci.level == 0.95


# --- P2 ----------------------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(tables(zeros=False, min_a=0))
def test_row_swap_inverts_ror_and_transposition_keeps_it(t: Table) -> None:
    """Feature: collective-memory, Property P2 — Validates: Req 1.6."""
    s = evaluate(t)
    swapped = evaluate(Table(t.c, t.d, t.a, t.b))
    transposed = evaluate(Table(t.a, t.c, t.b, t.d))
    assert s.estimates and swapped.estimates and transposed.estimates
    e, w, x = s.estimates, swapped.estimates, transposed.estimates
    assert w.ror == pytest.approx(1 / e.ror, rel=1e-12)
    assert w.ror_ci.low == pytest.approx(1 / e.ror_ci.high, rel=1e-9)
    assert w.ror_ci.high == pytest.approx(1 / e.ror_ci.low, rel=1e-9)
    assert w.chi2 == pytest.approx(e.chi2, rel=1e-12, abs=1e-12)
    assert x.ror == pytest.approx(e.ror, rel=1e-12)
    assert x.ror_ci.low == pytest.approx(e.ror_ci.low, rel=1e-9)
    assert x.ror_ci.high == pytest.approx(e.ror_ci.high, rel=1e-9)
    assert x.chi2 == pytest.approx(e.chi2, rel=1e-12, abs=1e-12)


# --- P3 ----------------------------------------------------------------------------------------


@settings(max_examples=200, deadline=None)
@given(
    st.tuples(*[st.integers(1, 5000)] * 4).map(lambda v: Table(*v)),
    st.integers(2, 50),
)
def test_scaling_keeps_ratios_and_narrows_the_interval(t: Table, k: int) -> None:
    """Feature: collective-memory, Property P3 — Validates: Req 1.6."""
    big = Table(t.a * k, t.b * k, t.c * k, t.d * k)
    s, b = evaluate(t), evaluate(big)
    assert s.estimates and b.estimates
    assert b.estimates.prr == pytest.approx(s.estimates.prr, rel=1e-12)
    assert b.estimates.ror == pytest.approx(s.estimates.ror, rel=1e-12)
    assert (b.estimates.ror_ci.high / b.estimates.ror_ci.low) < (
        s.estimates.ror_ci.high / s.estimates.ror_ci.low
    )
    assert chi2_pearson_exact(big) == k * chi2_pearson_exact(t)
    assert chi2_yates_exact(big) >= k * chi2_yates_exact(t)


# --- P4 ----------------------------------------------------------------------------------------


@settings(max_examples=400, deadline=None)
@given(tables(min_a=1))
def test_exact_reference(t: Table) -> None:
    """Feature: collective-memory, Property P4 — Validates: Req 1.1, 1.2, 1.9.
    Real values agree with a 50-digit reference to 1e-12; the decisions equal the integer
    inequalities; nothing overflows or becomes NaN.
    """
    s = evaluate(t)
    assert s.estimates
    a, b, c, d = ref_cells(t)
    prr = (a / (a + b)) / (c / (c + d))
    ror = (a * d) / (b * c)
    se = (1 / a + 1 / b + 1 / c + 1 / d).sqrt()
    lo = (ror.ln() - Decimal("1.96") * se).exp()
    hi = (ror.ln() + Decimal("1.96") * se).exp()
    e = s.estimates
    assert rel_close(e.prr, prr) and rel_close(e.ror, ror)
    assert rel_close(e.ror_ci.low, lo, 1e-10) and rel_close(e.ror_ci.high, hi, 1e-10)
    n, m = t.n, (t.a + t.b) * (t.c + t.d) * (t.a + t.c) * (t.b + t.d)
    if m:
        excess = max(0, 2 * abs(t.a * t.d - t.b * t.c) - n)
        chi2 = Decimal(n * excess * excess) / Decimal(4 * m)
        assert rel_close(e.chi2, chi2) if chi2 else e.chi2 == 0.0
    enough = t.a >= 3
    assert s.evans_met == (enough and ref_prr_ge_2(t) and ref_chi2_yates_ge_4(t))


@settings(max_examples=200, deadline=None)
@given(st.integers(1, 10**6), st.sampled_from([0, 1]), st.integers(0, 10**6), st.integers(1, 10**6))
def test_zero_margin_gives_zero_chi2_and_no_nan(a: int, zero_b: int, c: int, d: int) -> None:
    """A table with a zero margin is evaluated totally (chi-squared 0.0, no NaN, no division)."""
    t = Table(a, 0 if zero_b else 5, c, d)
    s = evaluate(t)
    assert s.estimates and math.isfinite(s.estimates.chi2)
    if (t.a + t.b) * (t.c + t.d) * (t.a + t.c) * (t.b + t.d) == 0:
        assert s.estimates.chi2 == 0.0
    assert evaluate(Table(a, 7, 0, 0)).estimates.chi2 == 0.0  # type: ignore[union-attr]


# --- P5 ----------------------------------------------------------------------------------------


@settings(max_examples=300, deadline=None)
@given(tables())
def test_flags_are_exact(t: Table) -> None:
    """Feature: collective-memory, Property P5 — Validates: Req 1.2, 1.3, 1.6."""
    s = evaluate(t)
    if t.a == 0:
        assert s.estimates is None and s.assessment == "no_reports"
        assert not s.haldane_applied and not s.evans_met and not s.ror_signal
        return
    assert s.haldane_applied == (0 in (t.b, t.c, t.d))
    assert (s.assessment == "insufficient_data") == (t.a < 3)
    assert s.estimates is not None
    # chi-squared comes from the raw table, never from the corrected cells
    n, m = t.n, (t.a + t.b) * (t.c + t.d) * (t.a + t.c) * (t.b + t.d)
    expected = 0.0 if m == 0 else n * max(0.0, 2 * abs(t.a * t.d - t.b * t.c) - n) ** 2 / (4 * m)
    assert s.estimates.chi2 == pytest.approx(expected, rel=1e-9, abs=1e-12)
    # round trip: the booleans re-evaluated from the serialised numbers agree (away from the edge)
    wire = json.loads(json.dumps(asdict(s)))
    e = wire["estimates"]
    near = (
        abs(e["prr"] - 2) < 1e-9 * 2
        or abs(e["chi2"] - 4) < 1e-9 * 4
        or abs(e["ror_ci"]["low"] - 1) < 1e-9
    )
    assume(not near)
    assert estimates_from_numbers(e["prr"], e["chi2"], e["ror_ci"]["low"], t.a) == (
        s.evans_met,
        s.ror_signal,
    )


# --- P6 ----------------------------------------------------------------------------------------


def reference_assessment(t: Table) -> str | None:
    """Pseudocode of the statistics review, with the real-valued parts from Decimal."""
    if t.a == 0:
        return "no_reports"
    if t.a < 3:
        return "insufficient_data"
    a, b, c, d = ref_cells(t)
    ln_ror = ((a * d) / (b * c)).ln()
    lower = (ln_ror - Decimal("1.96") * (1 / a + 1 / b + 1 / c + 1 / d).sqrt()).exp()
    if abs(lower - 1) < Decimal("1e-9"):
        return None  # too close to the boundary for a float comparison
    evans = ref_prr_ge_2(t) and ref_chi2_yates_ge_4(t)
    ror = lower > 1
    if evans and ror and t.a >= 5:
        return "disproportionate"
    if evans or ror:
        return "weak"
    return "not_disproportionate"


@settings(max_examples=400, deadline=None)
@given(tables())
def test_assessment_equals_the_rule(t: Table) -> None:
    """Feature: collective-memory, Property P6 — Validates: Req 1.6."""
    expected = reference_assessment(t)
    assume(expected is not None)
    s = evaluate(t)
    assert s.assessment == expected
    if t.a < 3:
        assert s.assessment in ("no_reports", "insufficient_data")
        assert not s.evans_met and not s.ror_signal
    if s.assessment == "disproportionate":
        assert t.a >= 5 and s.evans_met and s.ror_signal
    if s.assessment == "weak":
        assert t.a >= 3


@pytest.mark.parametrize(
    ("a", "evans", "ror", "expected"),
    [
        (0, False, False, "no_reports"),
        (1, True, True, "insufficient_data"),
        (2, True, True, "insufficient_data"),
        (3, True, True, "weak"),
        (4, True, True, "weak"),
        (5, True, True, "disproportionate"),
        (5, True, False, "weak"),
        (9, False, True, "weak"),
        (9, False, False, "not_disproportionate"),
    ],
)
def test_assess_boundaries(a: int, evans: bool, ror: bool, expected: str) -> None:
    assert assess(a, evans_met=evans, ror_signal=ror) == expected


# --- P9 (pure part) ----------------------------------------------------------------------------


@settings(max_examples=300, deadline=None)
@given(
    st.integers(0, 200),
    st.integers(0, 2000),
    st.integers(0, 2000),
    st.integers(0, 5000),
    st.integers(0, 5000),
    st.integers(0, 5000),
)
def test_sensitivity_table(
    a: int, extra_i: int, extra_e: int, spare: int, more_e: int, more_n: int
) -> None:
    """Feature: collective-memory, Property P9 (pure part) — Validates: Req 1.7."""
    ing, ev_m = a + extra_i, a + extra_e
    n_m = ing + ev_m - a + spare  # d >= 0
    ev_all, n_all = ev_m + more_e, n_m + more_n + more_e
    primary = evaluate(cells_from_counts(a, ing, ev_m, n_m))
    sens = sensitivity(primary, a=a, ingredient=ing, event_all=ev_all, n_all=n_all)
    cells = sens.stats.cells
    assert (cells.a, cells.b) == (a, ing - a)
    assert cells.c == ev_all - a and cells.d == n_all - ing - ev_all + a
    assert sens.differs == (sens.stats.assessment != primary.assessment)
    same = sensitivity(primary, a=a, ingredient=ing, event_all=ev_m, n_all=n_m)
    assert same.stats == primary and not same.differs


# --- P29 ---------------------------------------------------------------------------------------


@settings(max_examples=300, deadline=None)
@given(
    st.integers(1, 1_000_000),
    st.integers(1, 1_000_000),
    st.integers(1, 1_000_000),
    st.integers(1, 3000),
    st.integers(1, 3000),
)
def test_monotone_in_a(b: int, c: int, d: int, a1: int, a2: int) -> None:
    """Feature: collective-memory, Property P29 — Validates: Req 1.6."""
    lo_a, hi_a = sorted((a1, a2))
    lo, hi = evaluate(Table(lo_a, b, c, d)), evaluate(Table(hi_a, b, c, d))
    assert lo.estimates and hi.estimates
    assert hi.estimates.prr >= lo.estimates.prr * (1 - 1e-12)
    assert hi.estimates.ror >= lo.estimates.ror * (1 - 1e-12)
    assert hi.estimates.ror_ci.low >= lo.estimates.ror_ci.low * (1 - 1e-12)
    assert ASSESSMENT_ORDER.index(hi.assessment) >= ASSESSMENT_ORDER.index(lo.assessment)


# --- examples ----------------------------------------------------------------------------------


def test_worked_table() -> None:
    s = evaluate(Table(20, 180, 100, 9700))
    assert s.estimates
    assert s.estimates.prr == pytest.approx(9.8)
    assert s.estimates.ror == pytest.approx(194000 / 18000)
    assert not s.haldane_applied
    assert s.assessment == "disproportionate" and s.evans_met and s.ror_signal


def test_zero_c_uses_haldane_but_chi_squared_uses_the_raw_table() -> None:
    t = Table(4, 100, 0, 100_000)
    s = evaluate(t)
    assert s.haldane_applied and s.estimates
    assert s.estimates.prr == pytest.approx((4.5 / 105.0) / (0.5 / 100_001.0))
    assert s.estimates.chi2 == float(chi2_yates_exact(t))


def test_no_reports_has_no_estimates() -> None:
    s = evaluate(Table(0, 10, 10, 1000))
    assert s.estimates is None and s.assessment == "no_reports"


@pytest.mark.parametrize("bad", [Table(-1, 1, 1, 1), Table(1, 1, 1, -1)])
def test_negative_cell_raises(bad: Table) -> None:
    with pytest.raises(StatsError):
        evaluate(bad)


def test_inconsistent_counts_are_not_repaired() -> None:
    with pytest.raises(StatsError):
        cells_from_counts(5, 4, 10, 100)  # a > ingredient count
    with pytest.raises(StatsError):
        cells_from_counts(5, 50, 60, 100)  # d < 0


def test_parameters_are_the_reviewed_ones() -> None:
    assert (PARAMS.min_reports, PARAMS.weak_below, PARAMS.prr_min, PARAMS.chi2_min) == (3, 5, 2, 4)
    assert PARAMS.z == 1.96 and PARAMS.haldane == Fraction(1, 2)
