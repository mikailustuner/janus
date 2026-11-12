"""Model kit gate study: leave-one-study-out validation (DP-M40, properties M35-M37) and the derived
parameter rules R1, R2, R3 and steady-state Cmax (R5). Research use only."""

from __future__ import annotations

import math
import random
from dataclasses import replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.modelkit.builder import NoSet, ParameterSet, build_set, solve_ka
from janus.modelkit.evidence import Ev, exclusion_reason, population_class
from janus.modelkit.validate import (
    BAND,
    cmax_steady_state,
    fold_rows,
    held_out_candidates,
    predict,
    validate,
    validate_single_split,
)
from janus.timemachine.pk import OneCompartment, concentration
from tests.modelkit_helpers import ev
from tests.test_modelkit_builder import worlds

LN2 = math.log(2)
DRUG = "exampletine"


def two_full_studies() -> list[Ev]:
    """Two studies that each report CL/F, t1/2, tmax, AUC and Cmax: under the single split neither
    tests (both are building studies); leaving one out, each tests the set of the other."""
    rows: list[Ev] = []
    for study, cl in (("A", 10.0), ("B", 12.0)):
        k = cl / (cl * 8.0 / LN2)
        ka = solve_ka(k, 2.0)
        assert ka is not None
        m = OneCompartment(1.0, ka, cl, cl * 8.0 / LN2)
        rows += [
            ev(parameter="cl_f", value=cl, unit="L/h", study_id=study),
            ev(parameter="t_half", value=8.0, unit="h", study_id=study),
            ev(parameter="tmax", value=2.0, unit="h", study_id=study),
            ev(parameter="auc_inf", value=50.0 * 1000 / cl, dose=50.0, study_id=study),
            ev(parameter="cmax", value=1000 * concentration(m, 50.0, 2.0), dose=50.0,
               study_id=study),
        ]  # fmt: skip
    return rows


def test_a_building_study_tests_the_set_built_without_it() -> None:
    rows = two_full_studies()
    ps = build_set(DRUG, rows)
    assert isinstance(ps, ParameterSet)
    assert not validate_single_split(DRUG, rows, ps).points
    val = validate(DRUG, rows, ps)
    assert {(p.study_id, p.metric) for p in val.points} == {
        ("A", "auc"), ("A", "cmax"), ("B", "auc"), ("B", "cmax"),
    }  # fmt: skip
    a_auc = next(p for p in val.points if p.study_id == "A" and p.metric == "auc")
    # predicted by B's CL/F (12 L/h), never by A's own
    assert a_auc.predicted == pytest.approx(50.0 * 1000 / 12.0)
    assert a_auc.ratio == pytest.approx(10.0 / 12.0)
    assert all(p.rebuilt_without_study for p in val.points)
    assert val.status == "validated"


def test_one_point_outside_fails_under_leave_one_study_out() -> None:
    rows = [
        replace(r, value=r.value * 3, value_si=r.value_si * 3)
        if r.study_id == "B" and r.parameter == "auc_inf"
        else r
        for r in two_full_studies()
    ]
    ps = build_set(DRUG, rows)
    val = validate(DRUG, rows, ps)
    assert val.status == "failed"
    bad = next(r for r in rows if r.study_id == "B" and r.parameter == "auc_inf")
    assert bad.eid in val.failed_points


def test_labels_and_linked_studies_never_test() -> None:
    rows = two_full_studies()
    label = [
        replace(r, source_id="dailymed_spl", study_id="label-1") for r in rows if r.study_id == "A"
    ]
    linked = [replace(r, study_group="G1") for r in rows if r.study_id == "B"] + [
        ev(parameter="t_half", value=8.0, unit="h", study_id="B-copy", source_id="pmc_oa",
           study_group="G1"),
    ]  # fmt: skip
    world = [r for r in rows if r.study_id == "A"] + label + linked
    ps = build_set(DRUG, world)
    assert isinstance(ps, ParameterSet)
    val = validate(DRUG, world, ps)
    assert {p.study_id for p in val.points} == {"A"}
    why = dict(val.excluded)
    assert all(why[r.eid] == "label_never_tests" for r in label if r.parameter == "cmax")
    assert all(
        why[r.eid] == "same_study_in_another_source" for r in linked if r.parameter == "cmax"
    )


def test_no_validation_without_a_set_shown() -> None:
    rows = [r for r in two_full_studies() if r.parameter != "cl_f"]
    ps = build_set(DRUG, rows)
    assert isinstance(ps, NoSet)
    val = validate(DRUG, rows, ps)
    assert val.status == "not_validated" and not val.points
    assert "no_parameter_set" in val.reasons


def test_a_fold_without_a_set_is_named() -> None:
    extra = ev(parameter="auc_inf", value=900.0, dose=50.0, study_id="C")
    only_a = [*(r for r in two_full_studies() if r.study_id != "B"), extra]
    ps = build_set(DRUG, only_a)
    val = validate(DRUG, only_a, ps)
    a_auc = next(r for r in only_a if r.study_id == "A" and r.parameter == "auc_inf")
    assert dict(val.excluded)[a_auc.eid] == "fold_has_no_parameter_set"
    assert {p.study_id for p in val.points} == {"C"}


UNITS = {"cl_f": "L/h", "cl": "L/h", "v_f": "L", "vss": "L", "t_half": "h", "tmax": "h",
         "f": "fraction", "cmax": "ng/mL", "auc_inf": "ng*h/mL", "auc_tau": "ng*h/mL"}  # fmt: skip
VALUES = {"cl_f": (2.0, 40.0), "cl": (2.0, 40.0), "v_f": (20.0, 400.0), "vss": (20.0, 400.0),
          "t_half": (2.0, 30.0), "tmax": (0.5, 4.0), "f": (0.1, 1.0), "cmax": (50.0, 2000.0),
          "auc_inf": (500.0, 20000.0), "auc_tau": (500.0, 20000.0)}  # fmt: skip


@st.composite
def usable_worlds(draw: st.DrawFn) -> list[Ev]:
    """Mostly usable rows (so that sets and points exist), with some rows of every kind the filters
    remove, over 1 to 5 studies of two sources, some linked, some label studies."""
    rows: list[Ev] = []
    for i in range(draw(st.integers(1, 5))):
        source = draw(st.sampled_from(["clinicaltrials_gov", "clinicaltrials_gov", "dailymed_spl"]))
        group = draw(st.sampled_from([None, None, None, "G1"]))
        common = ["cl_f", "t_half", "tmax", "auc_inf", "cmax"] * 3
        params = draw(st.lists(st.sampled_from(sorted(UNITS) + common), min_size=2, max_size=7))
        for j, prm in enumerate(params):
            obs = prm in ("cmax", "auc_inf", "auc_tau")
            regimen = draw(st.sampled_from(["single", "single", "single", "multiple"]))
            route = "iv" if prm in ("cl", "vss") else draw(st.sampled_from(["oral"] * 4 + ["iv"]))
            rows.append(
                ev(
                    parameter=prm,
                    unit=UNITS[prm],
                    value=draw(st.floats(*VALUES[prm])),
                    study_id=f"S{i}",
                    source_id=source,
                    source_locator=f"S{i}-{j}",
                    study_group=group,
                    route=route,
                    regimen=regimen,
                    dose=draw(st.sampled_from([10.0, 50.0])) if obs else None,
                    interval_h=draw(st.sampled_from([None, 12.0, 24.0])),
                    confirmed=draw(st.sampled_from([True] * 6 + [False])),
                    population=draw(st.sampled_from(POPULATIONS)),
                    origin=draw(st.sampled_from(["reader_pair"] * 6 + ["derived"]))
                    if prm == "cl_f"
                    else "reader_pair",
                )
            )
    return rows


POPULATIONS = ["healthy adults", "healthy adults", None, "patients", "special population"]
EXAMPLES = {"worlds": 0, "points": 0, "rebuilt": 0}


def test_the_property_worlds_produce_points() -> None:
    """The property below is not vacuous: its worlds give rebuilt (leave-one-study-out) points."""
    EXAMPLES.update(worlds=0, points=0, rebuilt=0)
    test_held_out_study_never_influences_the_set_that_tests_it()
    # the counts vary with the random worlds (10 to 80 rebuilt points in 300); any is enough
    assert EXAMPLES["rebuilt"] > 0


@settings(max_examples=300, deadline=None)
@given(st.one_of(usable_worlds(), worlds()), st.randoms(use_true_random=False), st.floats(0.2, 5.0))
def test_held_out_study_never_influences_the_set_that_tests_it(
    rows: list[Ev], rnd: random.Random, factor: float
) -> None:
    ps = build_set(DRUG, rows)
    val = validate(DRUG, rows, ps)
    by_id = {r.eid: r for r in rows}
    EXAMPLES["worlds"] += 1
    EXAMPLES["points"] += len(val.points)
    EXAMPLES["rebuilt"] += sum(p.rebuilt_without_study for p in val.points)
    # M37: no validation without a set shown; the strict status rule
    if isinstance(ps, NoSet):
        assert not val.points
        return
    for p in val.points:
        e = by_id[p.eid]
        assert exclusion_reason(e) is None and population_class(e.population) != "special"
        assert e.source_id != "dailymed_spl"
        rest = fold_rows(rows, e.study)
        fold = build_set(DRUG, rest)
        assert isinstance(fold, ParameterSet)
        # M35: the fold set holds no row of the held-out study ...
        assert not {r.eid for r in rows if r.study == e.study} & set(fold.used)
        # ... and does not change when any row of that study changes or a row is added to it
        changed = [
            replace(r, value=r.value * factor, value_si=r.value_si * factor)
            if r.study == e.study and r.eid != e.eid
            else r
            for r in rows
        ] + [ev(parameter="cl_f", value=999.0, unit="L/h", study_id=e.study_id)]
        assert build_set(DRUG, fold_rows(changed, e.study)) == fold
        again = validate(DRUG, changed, build_set(DRUG, changed))
        same = [q for q in again.points if q.eid == e.eid]
        assert not same or same[0].predicted == pytest.approx(p.predicted)
        ss = e.interval_h if p.metric == "cmax" and e.regimen == "multiple" else None
        assert p.predicted == pytest.approx(predict(fold, p.metric, p.dose_mg, ss))
        assert p.within_2_fold == (1 / BAND <= p.ratio <= BAND)
    # M36: every point of the single split is a point here, with the same ratio (except label
    # points: the single split let a label study test when it reported only observations, against
    # "labels never test" of DP-M2; leaving one study out enforces that rule)
    single = validate_single_split(DRUG, rows, ps)
    loso = {p.eid: p for p in val.points}
    for p in single.points:
        if by_id[p.eid].source_id == "dailymed_spl":
            assert p.eid not in loso
            continue
        assert p.eid in loso and loso[p.eid].ratio == pytest.approx(p.ratio)
        assert not loso[p.eid].rebuilt_without_study
    # determinism: row order does not matter
    shuffled = list(rows)
    rnd.shuffle(shuffled)
    assert validate(DRUG, shuffled, build_set(DRUG, shuffled)) == val
    # strict status (unchanged)
    outside = [p for p in val.points if not p.within_2_fold]
    tested = {p.metric for p in val.points}
    assert (val.status == "failed") == bool(outside)
    assert (val.status == "validated") == (not outside and tested == {"auc", "cmax"})
    assert set(val.failed_points) == {p.eid for p in outside}
    assert set(held_out_candidates(rows)) >= {by_id[p.eid].study for p in val.points}


# --- rules R1, R2, R3 ----------------------------------------------------------------------------


def test_r1_intravenous_half_life_only_without_an_oral_one() -> None:
    base = [
        ev(parameter="cl_f", value=10.0, unit="L/h", study_id="B1"),
        ev(parameter="t_half", value=6.0, unit="h", study_id="B2", route="iv"),
    ]
    ps = build_set(DRUG, base)
    assert isinstance(ps, ParameterSet)
    v = ps.get("v")
    assert v is not None and v.value == pytest.approx(10.0 * 6.0 / LN2)
    assert v.cls == "C" and v.derivation == "v_from_clf_half_life"
    assert v.note == "half_life_intravenous"
    oral = [*base, ev(parameter="t_half", value=8.0, unit="h", study_id="B3")]
    ps2 = build_set(DRUG, oral)
    assert isinstance(ps2, ParameterSet)
    v2 = ps2.get("v")
    assert v2 is not None and v2.value == pytest.approx(10.0 * 8.0 / LN2) and v2.note is None


def test_r2_intravenous_volume_from_clearance_and_half_life() -> None:
    rows = [
        ev(parameter="cl", value=6.0, unit="L/h", study_id="I1", route="iv"),
        ev(parameter="t_half", value=5.0, unit="h", study_id="I1", route="iv"),
        ev(parameter="f", value=0.5, unit="fraction", study_id="O1"),
    ]
    ps = build_set(DRUG, rows)
    assert isinstance(ps, ParameterSet) and ps.basis == "iv"
    v = ps.get("v")
    assert v is not None and v.value == pytest.approx(6.0 * 5.0 / LN2)
    assert v.cls == "C" and v.derivation == "v_from_cl_half_life"
    # a stated volume wins
    stated = build_set(DRUG, [*rows, ev(parameter="vss", value=40.0, unit="L", study_id="I1",
                                          route="iv")])  # fmt: skip
    assert isinstance(stated, ParameterSet)
    sv = stated.get("v")
    assert sv is not None and sv.value == pytest.approx(40.0) and sv.derivation is None


def test_r3_bioavailability_from_one_study_with_both_routes() -> None:
    rows = [
        ev(parameter="cl", value=6.0, unit="L/h", study_id="X", route="iv"),
        ev(parameter="vss", value=40.0, unit="L", study_id="X", route="iv"),
        ev(parameter="auc_inf", value=1000.0, dose=10.0, study_id="X", route="iv"),
        ev(parameter="auc_inf", value=3000.0, dose=50.0, study_id="X", route="oral"),
        # an oral AUC of ANOTHER study never pairs
        ev(parameter="auc_inf", value=9000.0, dose=50.0, study_id="Y", route="oral"),
        ev(parameter="t_half", value=5.0, unit="h", study_id="Y"),
    ]
    ps = build_set(DRUG, rows)
    assert isinstance(ps, ParameterSet) and ps.basis == "iv"
    f = ps.get("f")
    assert f is not None and f.value == pytest.approx((3000.0 / 50.0) / (1000.0 / 10.0))
    assert f.cls == "C" and f.derivation == "f_from_same_study_auc"
    assert {r.study_id for r in rows if r.eid in f.evidence} == {"X"}
    # the study is held out in its own fold: its AUC rows then test a set built without them
    val = validate(DRUG, rows, ps)
    assert all(p.study_id != "X" or p.rebuilt_without_study for p in val.points)


def test_r3_needs_both_routes() -> None:
    rows = [
        ev(parameter="cl", value=6.0, unit="L/h", study_id="X", route="iv"),
        ev(parameter="vss", value=40.0, unit="L", study_id="X", route="iv"),
        ev(parameter="auc_inf", value=3000.0, dose=50.0, study_id="X", route="oral"),
    ]
    ps = build_set(DRUG, rows)
    assert isinstance(ps, NoSet) and "iv_without_bioavailability" in ps.reasons


# --- R5: steady-state Cmax ------------------------------------------------------------------------


@settings(max_examples=60, deadline=None)
@given(st.floats(0.02, 0.5), st.floats(1.2, 20.0), st.sampled_from([6.0, 8.0, 12.0, 24.0]))
def test_steady_state_cmax_matches_superposition(k: float, ratio: float, tau: float) -> None:
    v = 50.0
    m = OneCompartment(0.8, k * ratio, k * v, v)
    n = int(40.0 / (k * tau)) + 2  # enough doses for steady state
    grid = [(n - 1) * tau + i * tau / 2000 for i in range(2001)]
    numeric = max(concentration(m, 100.0, t, tau, n) for t in grid)
    assert cmax_steady_state(m.f, m.ka, m.cl, m.v, 100.0, tau) == pytest.approx(numeric, rel=2e-3)


def test_steady_state_cmax_is_tested_only_with_an_interval() -> None:
    rows = two_full_studies()
    ps = build_set(DRUG, rows)
    assert isinstance(ps, ParameterSet)
    ss = ev(parameter="cmax", value=1500.0, dose=50.0, regimen="multiple", interval_h=12.0,
            study_id="S")  # fmt: skip
    no_tau = ev(parameter="cmax", value=1500.0, dose=50.0, regimen="multiple", study_id="S2")
    val = validate(DRUG, [*rows, ss, no_tau], ps)
    pt = next(p for p in val.points if p.eid == ss.eid)
    f, cl, v, ka = ps.engine()
    assert ka is not None
    assert pt.predicted == pytest.approx(1000 * cmax_steady_state(f, ka, cl, v, 50.0, 12.0))
    assert dict(val.excluded)[no_tau.eid] == "steady_state_cmax_needs_interval"


def test_r3_bioavailability_above_one_is_capped_and_predicts() -> None:
    rows = [
        ev(parameter="cl", value=6.0, unit="L/h", study_id="X", route="iv"),
        ev(parameter="vss", value=40.0, unit="L", study_id="X", route="iv"),
        ev(parameter="auc_inf", value=1000.0, dose=10.0, study_id="X", route="iv"),
        ev(parameter="auc_inf", value=6000.0, dose=50.0, study_id="X", route="oral"),
        ev(parameter="auc_inf", value=8000.0, dose=50.0, study_id="Y", route="oral"),
    ]
    ps = build_set(DRUG, rows)
    assert isinstance(ps, ParameterSet)
    f = ps.get("f")
    assert f is not None and f.value == 1.0 and "bioavailability_capped" in ps.warnings
    assert predict(ps, "auc", 50.0) == pytest.approx(50.0 * 1000 / 6.0)
