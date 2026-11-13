"""Cross-study plausibility check (model kit gate, phase B4; pre-registered in
docs/research/modelkit-gate-protocol.md section 3). Abstention only: the check never confirms a
value."""

from __future__ import annotations

import inspect
import math
import random
from collections import Counter
from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.modelkit import ctgov_bulk, plausibility
from janus_pipelines.modelkit.confirm import Confirmation, Context
from janus_pipelines.modelkit.model import Candidate
from janus_pipelines.modelkit.pairing import Paired
from janus_pipelines.modelkit.plausibility import FACTOR, Obs, cross_study_outliers
from janus_pipelines.modelkit.units import Stat

KEY = ("dasatinib", "cl_f", "oral")
studies = st.sampled_from([f"NCT{i:08d}" for i in range(6)])
values = st.floats(min_value=1e-3, max_value=1e4, allow_nan=False, allow_infinity=False)
obs_lists = st.lists(
    st.builds(Obs, st.just(KEY), studies, values, st.booleans(), st.booleans()), max_size=25
)


@given(st.lists(st.tuples(values, st.booleans()), max_size=20))
def test_a_single_study_is_never_checked(vals: list[tuple[float, bool]]) -> None:
    obs = [Obs(KEY, "NCT1", v, cand) for v, cand in vals]
    assert cross_study_outliers(obs) == frozenset()


@given(st.lists(st.tuples(studies, st.floats(0.0, 1.0), st.booleans()), max_size=25), values)
def test_values_within_a_10_fold_band_are_never_withheld(
    rows: list[tuple[str, float, bool]], low: float
) -> None:
    # every value in [low, low * FACTOR]: any value / median of others is within FACTOR
    obs = [Obs(KEY, s, low * FACTOR**u, cand) for s, u, cand in rows]
    assert cross_study_outliers(obs) == frozenset()


@given(
    st.lists(st.tuples(studies, st.floats(0.0, 1.0)), min_size=1, max_size=12),
    values,
    st.sampled_from([1000.0, 1e-3, 60.0, 1 / 60, 24.0, 1 / 24]),
)
def test_a_unit_error_is_always_withheld(
    others: list[tuple[str, float]], base: float, scale: float
) -> None:
    # other studies agree within 2-fold; one study's value is off by a unit factor
    obs = [Obs(KEY, s, base * 2**u, False) for s, u in others]
    obs.append(Obs(KEY, "NCT99999999", base * scale, True))
    assert len(obs) - 1 in cross_study_outliers(obs)


@given(obs_lists, st.randoms(use_true_random=False))
def test_order_does_not_matter(obs: list[Obs], rnd: random.Random) -> None:
    order = list(range(len(obs)))
    rnd.shuffle(order)
    shuffled = [obs[i] for i in order]
    flagged = {order[j] for j in cross_study_outliers(shuffled)}
    assert flagged == set(cross_study_outliers(obs))


@given(obs_lists, st.sampled_from([1e-6, 1e-3, 0.5, 3.0, 1000.0, 1e6]))
def test_unit_scale_does_not_matter(obs: list[Obs], c: float) -> None:
    scaled = [replace(o, value=o.value * c) for o in obs]
    assert cross_study_outliers(scaled) == cross_study_outliers(obs)


@given(obs_lists, obs_lists)
def test_keys_are_independent(a: list[Obs], b: list[Obs]) -> None:
    other = [replace(o, key=("other", "cmax", "oral", "single")) for o in b]
    flagged = cross_study_outliers(a + other)
    assert {i for i in flagged if i < len(a)} == set(cross_study_outliers(a))


@given(obs_lists)
def test_only_candidates_are_withheld(obs: list[Obs]) -> None:
    assert all(obs[i].candidate for i in cross_study_outliers(obs))


def test_boundary_exactly_10_fold_is_kept() -> None:
    for ratio, withheld in ((FACTOR, False), (1 / FACTOR, False), (FACTOR * 1.000001, True)):
        obs = [Obs(KEY, "A", 1.0, False), Obs(KEY, "B", ratio, True)]
        assert (1 in cross_study_outliers(obs)) is withheld


def test_two_disagreeing_studies_are_both_withheld() -> None:
    obs = [Obs(KEY, "A", 0.2, True), Obs(KEY, "B", 250.0, True)]
    assert cross_study_outliers(obs) == frozenset({0, 1})


def test_one_wrong_study_among_four_is_the_only_one_withheld() -> None:
    good = [Obs(KEY, s, v, True) for s, v in (("A", 200.0), ("B", 300.0), ("D", 250.0))]
    assert cross_study_outliers([*good, Obs(KEY, "C", 0.3, True)]) == frozenset({3})


def test_with_three_studies_one_wrong_study_takes_the_others_with_it() -> None:
    # each candidate's reference is the geometric mean of two other studies, one of them wrong
    # (as pre-registered: the median of the other studies; robust only from three other studies)
    obs = [Obs(KEY, "A", 200.0, True), Obs(KEY, "B", 300.0, True), Obs(KEY, "C", 0.3, True)]
    assert cross_study_outliers(obs) == frozenset({0, 1, 2})


def test_study_summary_is_a_median_and_even_counts_use_the_geometric_mean() -> None:
    # study B: 1 and 100 -> summary 10 (geometric mean of the two middle values);
    # A at 100 is exactly 10-fold: kept
    obs = [Obs(KEY, "B", 1.0, False), Obs(KEY, "B", 100.0, False), Obs(KEY, "A", 100.0, True)]
    assert cross_study_outliers(obs) == frozenset()
    obs.append(Obs(KEY, "A2", 100.1, True))  # 10.01-fold from B; A is also another study for A2
    # A2's others: B (10) and A (100) -> reference sqrt(10*100) = 31.6 -> 3.2-fold: kept
    assert cross_study_outliers(obs) == frozenset()


def test_reference_only_values_count_but_are_never_withheld() -> None:
    obs = [Obs(KEY, "A", 250.0, False), Obs(KEY, "B", 0.2, True)]
    assert cross_study_outliers(obs) == frozenset({1})
    # a non-reference value (e.g. co-administered arm) does not make a reference
    obs = [Obs(KEY, "A", 250.0, False, reference=False), Obs(KEY, "B", 0.2, True)]
    assert cross_study_outliers(obs) == frozenset()


# --- wiring into the intake (apply) -------------------------------------------------------------


def _cand(study: str, value: float, unit: str, parameter: str = "cl_f", **ctx: object) -> Candidate:
    context = Context(
        formulation="immediate_release", route="oral", regimen="single", population="patients"
    )
    context = replace(context, **ctx)  # type: ignore[arg-type]
    return Candidate(
        "dasatinib", "clinicaltrials_gov", study, "OG000", f"{study}#o/OG000/{value}", parameter,
        value, unit, Stat(value, "geometric"), "parent", context, 100.0, 12, "q", "v",
    )  # fmt: skip


def _paired(c: Candidate, result: Confirmation) -> Paired:
    return Paired(c, c, result)


def test_apply_withholds_the_dasatinib_unit_error_and_leaves_the_rest() -> None:
    confirmed = Confirmation(True, "both_readers_agree")
    abstained = Confirmation(False, "strict_check", ("product",))
    pairs = [
        _paired(_cand("NCT00339144", 200.12, "L/hour"), abstained),
        _paired(_cand("NCT00339144", 135.36, "L/hour"), abstained),
        _paired(_cand("NCT00529763", 211.09, "mL/h"), confirmed),
        _paired(_cand("NCT00529763", 221.84, "mL/h"), confirmed),
        _paired(_cand("NCT00529763", 1.5, "hours", "tmax"), confirmed),
        _paired(_cand("NCT00000002", 3.0, "mL/h"), Confirmation(False, "values_differ")),
    ]
    counts: Counter[str] = Counter()
    out = plausibility.apply(pairs, counts)
    assert [p.result.confirmed for p in out] == [False, False, False, False, True, False]
    assert out[2].result.reason == out[3].result.reason == plausibility.REASON
    for i in (0, 1, 4, 5):
        assert out[i] is pairs[i]
    assert counts == Counter({"cross_study_check_withheld": 2})


def test_apply_normalises_units_and_doses() -> None:
    confirmed = Confirmation(True, "both_readers_agree")
    # the same exposure per mg in different units and doses: consistent, nothing withheld
    a = replace(_cand("A", 1.0, "ug*h/mL", "auc_inf"), dose_mg=10.0)
    b = replace(_cand("B", 2000.0, "ng*h/mL", "auc_inf"), dose_mg=20.0)
    out = plausibility.apply([_paired(a, confirmed), _paired(b, confirmed)], Counter())
    assert all(p.result.confirmed for p in out)
    # without a dose a dose-dependent value takes no part
    c = replace(_cand("C", 2.0, "ng*h/mL", "auc_inf"), dose_mg=None)
    out = plausibility.apply([_paired(a, confirmed), _paired(c, confirmed)], Counter())
    assert all(p.result.confirmed for p in out)


def test_apply_ignores_disagreements_and_unplain_references() -> None:
    confirmed = Confirmation(True, "both_readers_agree")
    wrong = _paired(_cand("A", 250.0, "L/h"), Confirmation(False, "values_differ"))
    coadmin = _paired(_cand("B", 250.0, "L/h", coadministered="ketoconazole"), confirmed)
    special = _paired(_cand("C", 250.0, "L/h", population="special"), confirmed)
    target = _paired(_cand("D", 0.2, "L/h"), confirmed)
    out = plausibility.apply([wrong, coadmin, special, target], Counter())
    assert out[3].result.confirmed  # no plain agreed reference from another study
    # the co-administered and special-population values are still checked as candidates
    out = plausibility.apply(
        [coadmin, target, _paired(_cand("E", 0.25, "L/h"), confirmed)], Counter()
    )
    assert [p.result.confirmed for p in out] == [False, True, True]


@given(
    st.lists(
        st.tuples(
            studies,
            values,
            st.sampled_from(["L/h", "mL/h", "mL/min"]),
            st.booleans(),
            st.booleans(),
        ),
        max_size=15,
    )
)
def test_apply_only_withholds(rows: list[tuple[str, float, str, bool, bool]]) -> None:
    pairs = [
        _paired(
            _cand(s, v, u),
            Confirmation(True, "both_readers_agree")
            if conf
            else Confirmation(False, "strict_check" if agreed else "values_differ"),
        )
        for s, v, u, conf, agreed in rows
    ]
    out = plausibility.apply(pairs, Counter())
    assert len(out) == len(pairs)
    for before, after in zip(pairs, out, strict=True):
        assert after.a is before.a
        if not before.result.confirmed:
            assert after is before
        if after.result.confirmed:
            assert after is before


def test_log_median() -> None:
    assert plausibility._log_median([math.log(1), math.log(100)]) == math.log(10)  # pyright: ignore[reportPrivateUsage]


def test_the_intake_runs_the_check_only_when_asked() -> None:
    # off by default: the pre-registered decision rule was not met (docs/research/modelkit-gate.md)

    assert inspect.signature(ctgov_bulk.read_bulk).parameters["cross_study"].default is False
