"""Properties of the light-face core: signals, ranking, candidates (design §5, §6).

Feature: light-face, Properties P1, P2, P5, P6, P7, P9, P12, P15.
"""

from __future__ import annotations

import math
import random
from decimal import Decimal, getcontext
from fractions import Fraction

from hypothesis import given
from hypothesis import strategies as st

from janus.light.candidates import rank_goal
from janus.light.inverse import Counts, inverse_signal, is_inverse
from janus.light.keys import Item, build_key_map, map_ingredients
from janus.light.labels import label_signals, single_key
from janus.light.model import InverseSignal, Label, LabelSignal
from janus.light.ranking import sort_key, tied_ranks, wilson_low
from tests.light_world import (
    KEY_OF,
    KEYS,
    MAPPING,
    ONSIDES_IDS,
    counts,
    inverse_signals,
    labels,
    stats_for,
)
from tests.light_world import label_signals as label_signal_lists

# --- P6, P2: label aggregation -------------------------------------------------------------------


@given(labels(), st.randoms(use_true_random=False))
def test_label_signals_ignore_order_and_duplicates(rows: list[Label], rnd: random.Random) -> None:
    """Feature: light-face, Property P6: row order and repeated rows never change the signals."""
    base = label_signals(rows, MAPPING, KEY_OF)
    shuffled = rows + rows[: len(rows) // 2]
    rnd.shuffle(shuffled)
    assert label_signals(shuffled, MAPPING, KEY_OF) == base


@given(labels())
def test_multi_ingredient_labels_never_count(rows: list[Label]) -> None:
    """Feature: light-face, Property P6: only labels with exactly one mapped key contribute."""
    singles = [lb for lb in rows if single_key(lb, KEY_OF) is not None]
    assert label_signals(rows, MAPPING, KEY_OF) == label_signals(singles, MAPPING, KEY_OF)
    for s in label_signals(rows, MAPPING, KEY_OF).values():
        assert 1 <= s.labels_with_effect <= s.labels_total
        assert s.evidence[0] == "dataset:onsides"
        assert set(s.terms) <= {t for t, m in MAPPING.items() if m.goal == s.goal}


@given(labels(), labels(ids=tuple(ONSIDES_IDS[20:24])))
def test_unrelated_labels_never_change_existing_signals(
    rows: list[Label], other: list[Label]
) -> None:
    """Feature: light-face, Property P2: labels of other ingredients leave a signal unchanged."""
    base = label_signals(rows, MAPPING, KEY_OF)
    shifted = [
        Label(lb.label_id + 10_000, lb.source, lb.set_id, lb.ingredients, lb.effects)
        for lb in other
    ]
    merged = label_signals(rows + shifted, MAPPING, KEY_OF)
    for k, s in base.items():
        assert merged[k] == s


@given(labels())
def test_unmapped_terms_never_change_signals(rows: list[Label]) -> None:
    """Feature: light-face, Property P2: an extra unmapped effect changes nothing."""
    base = label_signals(rows, MAPPING, KEY_OF)
    noisy = [
        Label(lb.label_id, lb.source, lb.set_id, lb.ingredients, (*lb.effects, ("Zz other", "AR")))
        for lb in rows
    ]
    assert label_signals(noisy, MAPPING, KEY_OF) == base


def test_nonspecific_flag_needs_every_term_nonspecific() -> None:
    """A label signal is nonspecific only when every matched term is (pharmacologist F4)."""
    one = Label(1, "US", "s1", ("1001",), (("Term beta", "AR"),))
    both = Label(2, "US", "s2", ("1001",), (("Term alpha", "AR"), ("Term beta", "AR")))
    assert label_signals([one], MAPPING, KEY_OF)[("Q1", "goal_a")].nonspecific
    assert not label_signals([one, both], MAPPING, KEY_OF)[("Q1", "goal_a")].nonspecific


# --- P12: key mapping ----------------------------------------------------------------------------


@given(
    st.lists(
        st.tuples(
            st.sampled_from(KEYS[:6]),
            st.sampled_from(["1", "2", "3"]),
            st.sampled_from(["a", "b", "c"]),
        ),
        max_size=10,
    )
)
def test_key_mapping_is_one_to_one(rows: list[tuple[str, str, str]]) -> None:
    """Feature: light-face, Property P12: an RxCUI or a name shared by two items maps to nothing."""
    items = [Item(q, (r,), n) for q, r, n in rows]
    km = build_key_map(items)
    for r, q in km.by_rxcui.items():
        assert {it.qid for it in items if r in it.rxcuis} == {q}
    for n, q in km.by_label.items():
        assert {it.qid for it in items if it.label_en.casefold() == n} == {q}
    out, methods = map_ingredients({"1": "a", "OMOP2": "b", "9": "zz"}, km)
    assert sum(methods.values()) == 3
    assert "9" not in out
    assert km.key_for("OMOP2", "b")[1] in ("label_en", "unmapped")


# --- P5: inverse rule against a reference --------------------------------------------------------


def _reference_upper(c: Counts) -> Decimal:
    getcontext().prec = 50
    a, b = c.a, c.ingredient - c.a
    cc, d = c.event_mapped - c.a, c.n_mapped - c.ingredient - c.event_mapped + c.a
    cells = [Fraction(x) for x in (a, b, cc, d)]
    if 0 in (a, b, cc, d):
        cells = [x + Fraction(1, 2) for x in cells]
    fa, fb, fc, fd = cells
    ror = Decimal(fa.numerator * fd.numerator * fb.denominator * fc.denominator) / Decimal(
        fa.denominator * fd.denominator * fb.numerator * fc.numerator
    )
    var = sum((Decimal(x.denominator) / Decimal(x.numerator) for x in cells), Decimal(0))
    return (ror.ln() + Decimal("1.96") * var.sqrt()).exp()


@given(counts())
def test_inverse_rule_matches_reference(c: Counts) -> None:
    """Feature: light-face, Property P5: listed iff a >= 3 and the Woolf upper bound < 1."""
    found = inverse_signal(c)
    if c.a < 3 or c.ingredient - c.a < 0:
        assert found is None
        return
    upper = _reference_upper(c)
    if abs(upper - 1) < Decimal("1e-9"):
        return  # at the boundary floats may differ; not a decision the property can check
    assert (found is not None) == (upper < 1)
    if found is not None:
        assert is_inverse(found[0])
        est = found[0].estimates
        assert est is not None and est.ror_ci.low <= est.ror <= est.ror_ci.high < 1


@given(st.integers(0, 2), st.integers(10, 10_000))
def test_inverse_needs_three_reports(a: int, ingredient: int) -> None:
    """Feature: light-face, Property P5: fewer than 3 reports never give an inverse signal."""
    c = Counts(a, ingredient, 100_000, 100_000, 10_000_000, 10_000_000)
    assert inverse_signal(c) is None


# --- P9: Wilson bound ---------------------------------------------------------------------------


@given(st.integers(0, 500), st.integers(0, 500))
def test_wilson_bound_in_range_and_monotone(k: int, extra: int) -> None:
    """Feature: light-face, Property P9: 0 <= bound <= k/n, increasing in k for fixed n."""
    n = k + extra
    low = wilson_low(k, n)
    assert 0.0 <= low <= (k / n if n else 0.0) + 1e-12
    if k < n:
        assert wilson_low(k + 1, n) > low
    if n:
        assert math.isclose(wilson_low(k, n), wilson_low(k, n))


# --- P7, P15, P1: ranking -------------------------------------------------------------------------


@given(st.lists(st.tuples(st.integers(0, 3), st.integers(0, 3)), max_size=30))
def test_tied_ranks_partition_positions(raw: list[tuple[int, int]]) -> None:
    """Feature: light-face, Property P7: ranges partition 1..n and equal keys share a range."""
    keys = sorted((-a, 0.0, 0, 0, 0, -b) for a, b in raw)
    ranks = tied_ranks(keys)
    assert len(ranks) == len(keys)
    for i, r in enumerate(ranks):
        assert r.best <= i + 1 <= r.worst and r.population == len(keys)
        for j, s in enumerate(ranks):
            assert (keys[i] == keys[j]) == (r == s)


@given(label_signal_lists(), inverse_signals(), st.randoms(use_true_random=False))
def test_rank_goal_is_order_invariant(
    ls: list[LabelSignal], inv: list[InverseSignal], rnd: random.Random
) -> None:
    """Feature: light-face, Properties P7, P1: same candidates and ranks in any input order."""
    base = rank_goal("goal_a", ls, inv)
    ls2, inv2 = list(ls), list(inv)
    rnd.shuffle(ls2)
    rnd.shuffle(inv2)
    assert rank_goal("goal_a", ls2, inv2) == base
    assert {c.key for c in base} == {s.key for s in ls} | {s.key for s in inv}
    for c in base:
        assert c.label is not None or c.inverse is not None
    assert [sort_key(c.label, c.inverse) for c in base] == sorted(
        sort_key(c.label, c.inverse) for c in base
    )


@given(inverse_signals(), st.integers(1, 50))
def test_ratio_never_changes_a_rank(inv: list[InverseSignal], scale: int) -> None:
    """Feature: light-face, Properties P7, P15: same report counts, other ratios, same ranks."""
    base = rank_goal("goal_a", [], inv)
    other: list[InverseSignal] = []
    for s in inv:
        a = s.stats.cells.a
        st_, se = stats_for(a, a * 100 * scale, 10_000 * scale, 1_000_000 * scale)
        other.append(InverseSignal(s.key, s.goal, st_, se, s.pts))
    assert [(c.key, c.rank) for c in rank_goal("goal_a", [], other)] == [
        (c.key, c.rank) for c in base
    ]
    reports = [c.inverse.stats.cells.a for c in base if c.inverse]
    assert reports == sorted(reports, reverse=True)
