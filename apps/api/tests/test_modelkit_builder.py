"""Model kit: builder, held-out rule, status function, pooling (properties M1-M6, M8, M10)."""

from __future__ import annotations

import math
import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.modelkit.builder import (
    NoSet,
    ParameterSet,
    build_set,
    choose_model,
    pool,
    solve_ka,
)
from janus.modelkit.evidence import Ev, exclusion_reason, split_studies
from janus.modelkit.validate import (
    BAND,
    conformal_fold_width,
    system_report,
    validate,
    wilson,
)
from tests.modelkit_helpers import ev, seed_rows

LN2 = math.log(2)


def oral_world(**over: object) -> list[Ev]:
    """CL/F 10 L/h, t1/2 8 h, tmax 2 h from one building study; two test studies."""
    rows = [
        ev(parameter="cl_f", value=10.0, unit="L/h", study_id="B1"),
        ev(parameter="t_half", value=8.0, study_id="B1"),
        ev(parameter="tmax", value=2.0, study_id="B1"),
    ]
    k = 10.0 / (10.0 * 8.0 / LN2)
    ka = solve_ka(k, 2.0)
    assert ka is not None
    for study, dose in (("T1", 50.0), ("T2", 100.0)):
        auc = dose * 1000 / 10.0
        rows.append(ev(parameter="auc_inf", value=auc, dose=dose, study_id=study))
        rows.append(ev(parameter="cmax", value=1.0, dose=dose, study_id=study))
    return rows


def test_solve_ka_reproduces_tmax() -> None:
    k = 0.1
    ka = solve_ka(k, 2.0)
    assert ka is not None and ka > k
    assert math.log(ka / k) / (ka - k) == pytest.approx(2.0, rel=1e-9)
    assert solve_ka(k, 10.5) is None  # at or beyond 1 / k
    assert solve_ka(0.0, 2.0) is None


@given(st.floats(0.01, 2.0), st.floats(0.05, 0.9))
def test_solve_ka_property(k: float, frac: float) -> None:
    tmax = frac / k
    ka = solve_ka(k, tmax)
    if ka is not None:
        assert math.log(ka / k) / (ka - k) == pytest.approx(tmax, rel=1e-6)


def test_builder_apparent_oral_set() -> None:
    ps = build_set("exampletine", oral_world())
    assert isinstance(ps, ParameterSet)
    assert ps.basis == "oral_apparent" and ps.apparent and ps.complete
    cl, v = ps.get("cl"), ps.get("v")
    assert cl and v and cl.value == pytest.approx(10.0)
    assert v.value == pytest.approx(10.0 * 8.0 / LN2) and v.cls == "C"
    assert ps.model == "one_compartment"
    assert {s for _, s in ps.test_studies} == {"T1", "T2"}


def test_iv_preferred_over_oral_apparent() -> None:
    rows = [
        *oral_world(),
        ev(parameter="cl", value=5.0, unit="L/h", route="iv", study_id="L1"),
        ev(parameter="vss", value=40.0, unit="L", route="iv", study_id="L1"),
        ev(parameter="f", value=0.5, unit="fraction", study_id="L1"),
    ]
    ps = build_set("exampletine", rows)
    assert isinstance(ps, ParameterSet) and ps.basis == "iv" and not ps.apparent
    assert ps.get("cl").value == 5.0 and ps.get("f").value == 0.5  # type: ignore[union-attr]
    # the oral apparent rows are not used when intravenous evidence exists
    assert all(r.parameter != "cl_f" or r.eid not in ps.used for r in rows)


def test_iv_without_bioavailability_is_no_set() -> None:
    rows = [
        ev(parameter="cl", value=5.0, route="iv", study_id="L1"),
        ev(parameter="vss", value=40.0, route="iv", study_id="L1"),
    ]
    ps = build_set("exampletine", rows)
    assert isinstance(ps, NoSet) and ps.reasons == ("iv_without_bioavailability",)


def test_missing_tmax_gives_an_incomplete_set() -> None:
    rows = [r for r in oral_world() if r.parameter != "tmax"]
    ps = build_set("exampletine", rows)
    assert isinstance(ps, ParameterSet) and not ps.complete and ps.missing
    assert ps.get("ka") is None
    val = validate("exampletine", rows, ps)
    assert val.status == "not_validated" and "cmax_not_tested" in val.reasons


def test_per_kg_is_never_converted() -> None:
    rows = [
        ev(parameter="cl_per_kg", value=0.384, unit="mL/min/kg", route="iv", study_id="L1"),
        ev(parameter="vd_per_kg", value=2.9, unit="L/kg", route="iv", study_id="L1"),
        ev(parameter="f", value=0.75, unit="fraction", study_id="L1"),
    ]
    ps = build_set("exampletine", rows)
    assert isinstance(ps, NoSet)
    assert exclusion_reason(rows[0]) == "per_kg_not_converted"


def test_filters_remove_unfit_rows() -> None:
    base = oral_world()
    for bad in (
        {"coadministered": True},
        {"formulation": "modified_release"},
        {"formulation": "fixed_dose_combination"},
        {"confirmed": False, "reader_b": "disagree"},
        {"analyte_class": "metabolite"},
        {"statistic": "lower_bound"},
    ):
        rows = [r for r in base if r.parameter != "cl_f"] + [
            ev(parameter="cl_f", value=10.0, unit="L/h", study_id="B1", **bad)
        ]
        assert isinstance(build_set("exampletine", rows), NoSet), bad


def test_held_out_study_is_the_one_without_building_parameters() -> None:
    rows = oral_world()
    building, test = split_studies(rows)
    assert ("clinicaltrials_gov", "B1") in building and ("clinicaltrials_gov", "T1") in test
    # an unconfirmed building parameter still makes its study a building study
    rows.append(
        ev(parameter="t_half", value=9.0, study_id="T1", confirmed=False, reader_b="disagree")
    )
    building, test = split_studies(rows)
    assert ("clinicaltrials_gov", "T1") in building and ("clinicaltrials_gov", "T1") not in test


def test_validation_passes_and_fails() -> None:
    ps = build_set("exampletine", oral_world())
    assert isinstance(ps, ParameterSet)
    val = validate("exampletine", oral_world(), ps)
    auc = val.metrics[0]
    assert auc.tested and auc.n_studies == 2 and auc.gm_ratio == pytest.approx(1.0)
    # Cmax observed 1 ng/mL is far below the prediction: outside 2-fold, absorption suspect
    assert val.status == "failed" and val.metrics[1].all_within_2_fold is False
    assert "absorption_rate_or_volume" in val.suspect
    # AUC wrong by 3-fold: failed with clearance suspect
    rows = [r for r in oral_world() if r.parameter != "auc_inf"] + [
        ev(parameter="auc_inf", value=1666.0, dose=50.0, study_id="T1")
    ]
    val = validate("exampletine", rows, ps)
    assert val.status == "failed" and "clearance_or_bioavailability" in val.suspect


def test_validated_when_both_in_band() -> None:
    rows = oral_world()
    ps = build_set("exampletine", rows)
    assert isinstance(ps, ParameterSet)
    f, cl, v, ka = ps.engine()
    from janus.timemachine.pk import OneCompartment, cmax

    c = cmax(OneCompartment(f, ka or 1.0, cl, v), 50.0) * 1000
    rows = [r for r in rows if r.parameter != "cmax"] + [
        ev(parameter="cmax", value=c * 1.2, dose=50.0, study_id="T1")
    ]
    val = validate("exampletine", rows, ps)
    assert val.status == "validated" and not val.suspect


def test_one_point_outside_2_fold_fails_even_if_the_drug_level_ratio_is_inside() -> None:
    rows = oral_world()
    ps = build_set("exampletine", rows)
    assert isinstance(ps, ParameterSet)
    f, cl, v, ka = ps.engine()
    from janus.timemachine.pk import OneCompartment, cmax

    c = cmax(OneCompartment(f, ka or 1.0, cl, v), 50.0) * 1000
    # two Cmax points of one study: ratios 1/0.45 = 2.2 and 1/1.8; geometric mean about 1.1 (inside)
    rows = [r for r in rows if r.parameter != "cmax"] + [
        ev(parameter="cmax", value=c * 0.45, dose=50.0, study_id="T1", source_locator="a"),
        ev(parameter="cmax", value=c * 1.8, dose=50.0, study_id="T1", source_locator="b"),
    ]
    val = validate("exampletine", rows, ps)
    assert 0.5 < val.metrics[1].gm_ratio < 2.0  # type: ignore[operator]
    assert val.status == "failed" and "point_outside_2_fold" in val.reasons
    assert len(val.failed_points) == 1 and "absorption_rate_or_volume" in val.suspect


def test_no_observation_is_not_validated() -> None:
    rows = [r for r in oral_world() if r.study_id == "B1"]
    ps = build_set("exampletine", rows)
    val = validate("exampletine", rows, ps)
    assert val.status == "not_validated" and "no_independent_observation" in val.reasons


def test_observations_of_other_formulations_or_coadministration_are_not_tested() -> None:
    rows = [
        *oral_world(),
        ev(
            parameter="auc_inf", value=1.0, dose=50.0, study_id="T3", formulation="modified_release"
        ),
        ev(parameter="auc_inf", value=1.0, dose=50.0, study_id="T4", coadministered=True),
        ev(parameter="auc_last", value=1.0, dose=50.0, study_id="T5"),
    ]
    ps = build_set("exampletine", rows)
    val = validate("exampletine", rows, ps)
    assert {p.study_id for p in val.points} == {"T1", "T2"}
    why = " ".join(r for _, r in val.excluded)
    assert "formulation_not_immediate_release" in why and "coadministered" in why
    assert "last_sampling" in why


def test_pooling_class_and_spread() -> None:
    a = pool(
        [ev(value=10.0, study_id="A", n_subjects=10), ev(value=12.0, study_id="B", n_subjects=30)]
    )
    assert a is not None and a.cls == "A" and a.n_studies == 2 and a.spread_cv is not None
    assert 10.0 < a.value < 12.0 and a.value > math.sqrt(120)  # weighted towards the larger study
    b = pool([ev(value=10.0, study_id="A"), ev(value=30.0, study_id="B")])
    assert b is not None and b.cls == "B" and b.note == "studies_disagree"
    c = pool([ev(value=10.0, statistic="range_geomean", value_low=5.0, value_high=20.0)])
    assert c is not None and c.cls == "C"
    h = pool([ev(value=10.0, study_id="A", population="patients"), ev(value=20.0, study_id="B")])
    assert h is not None and h.value == 20.0  # healthy adults preferred
    assert pool([]) is None


def test_arms_of_one_study_count_once() -> None:
    p = pool(
        [
            ev(value=10.0, study_id="A", source_locator="a1"),
            ev(value=14.0, study_id="A", source_locator="a2"),
        ]
    )
    assert p is not None and p.n_studies == 1 and p.cls == "B"


def test_choose_model_needs_two_volumes() -> None:
    assert choose_model(None, 50.0)[0] == "one_compartment"
    assert choose_model(20.0, 50.0)[0] == "two_compartment"
    assert choose_model(45.0, 50.0)[0] == "one_compartment"


def test_interval_and_wilson() -> None:
    assert conformal_fold_width([1.1] * 19) is None  # fewer than 20 studies
    w = conformal_fold_width([1.0 + 0.01 * i for i in range(30)])
    assert w is not None and w >= 1.0
    lo, hi = wilson(3, 4) or (0, 0)
    assert 0.3 < lo < 0.75 < hi <= 1.0
    assert wilson(0, 0) is None


# --- properties over random worlds ---------------------------------------------------------------

PARAMS = [
    "cl_f",
    "cl",
    "vss",
    "v_f",
    "t_half",
    "tmax",
    "f",
    "cmax",
    "auc_inf",
    "auc_last",
    "auc_tau",
]


@st.composite
def worlds(draw: st.DrawFn) -> list[Ev]:
    rows: list[Ev] = []
    for i in range(draw(st.integers(1, 6))):
        for j in range(draw(st.integers(1, 4))):
            p = draw(st.sampled_from(PARAMS))
            rows.append(
                ev(
                    parameter=p,
                    value=draw(st.floats(0.5, 500.0)),
                    unit="fraction"
                    if p == "f"
                    else {"cl_f": "L/h", "cl": "L/h"}.get(
                        p,
                        "h"
                        if p in ("t_half", "tmax")
                        else "L"
                        if p in ("vss", "v_f")
                        else "ng/mL"
                        if p == "cmax"
                        else "ng*h/mL",
                    ),
                    study_id=f"S{i}",
                    source_locator=f"S{i}-{j}",
                    route=draw(st.sampled_from(["oral", "iv"])),
                    dose=draw(st.sampled_from([None, 10.0, 50.0]))
                    if p not in ("cmax", "auc_inf", "auc_tau", "auc_last")
                    else draw(st.sampled_from([10.0, 50.0])),
                    regimen=draw(st.sampled_from(["single", "multiple"])),
                    interval_h=draw(st.sampled_from([None, 24.0])),
                    coadministered=draw(st.booleans()),
                    formulation=draw(
                        st.sampled_from(["immediate_release", "modified_release", "solution"])
                    ),
                    confirmed=draw(st.booleans()),
                    n_subjects=draw(st.sampled_from([None, 6, 24])),
                )
            )
    # values of fractions must be in (0, 1]
    return [
        r
        if r.parameter != "f"
        else ev(
            parameter="f",
            value=min(r.value / 500.0 + 0.01, 1.0),
            unit="fraction",
            study_id=r.study_id,
            source_locator=r.source_locator,
            route=r.route,
            coadministered=r.coadministered,
            formulation=r.formulation,
            confirmed=r.confirmed,
        )
        for r in rows
    ]


@settings(max_examples=150, deadline=None)
@given(worlds(), st.randoms(use_true_random=False))
def test_properties_of_the_builder(rows: list[Ev], rnd: random.Random) -> None:
    ps = build_set("exampletine", rows)
    val = validate("exampletine", rows, ps)
    by_id = {r.eid: r for r in rows}
    building, test = split_studies(rows)
    assert building.isdisjoint(test)
    used: set[str] = set(ps.used) if isinstance(ps, ParameterSet) else set()
    # M1: the studies of the validation points never built the set
    pts = {p.eid for p in val.points}
    assert not (used & pts)
    assert all(by_id[e].study in test for e in pts)
    assert all(by_id[e].study in building for e in used)
    # M2 and M6: only confirmed, parent, not co-administered, immediate-release rows
    for e in used | pts:
        assert exclusion_reason(by_id[e]) is None
    # M10: no per-kg parameter
    assert all(not by_id[e].parameter.endswith("per_kg") for e in used)
    # M3: every estimated parameter lists evidence that exists
    if isinstance(ps, ParameterSet):
        for p in ps.params:
            if p.name != "f" or not ps.apparent:
                assert p.evidence and set(p.evidence) <= {r.eid for r in rows}
    # M5: order independence
    shuffled = list(rows)
    rnd.shuffle(shuffled)
    assert build_set("exampletine", shuffled) == ps
    # M8: status follows the metrics
    tested = [m for m in val.metrics if m.tested]
    if val.status == "failed":
        assert any(m.all_within_2_fold is False for m in tested)
    if val.status == "validated":
        assert len(tested) == 2 and all(m.all_within_2_fold for m in tested)
        # strict rule (owner decision 2026-11-11): Validated => every point within [0.5, 2]
        assert val.points and all(0.5 <= p.ratio <= 2.0 for p in val.points)
        assert not val.failed_points
    if any(m.tested and m.all_within_2_fold is False for m in tested):
        assert val.status == "failed"
    assert set(val.failed_points) == {p.eid for p in val.points if not p.within_2_fold}
    for p in val.points:
        assert p.within_2_fold == (1 / BAND <= p.ratio <= BAND)


# --- the committed seed (golden outcomes of milestone M0) ---------------------------------------


def _seed_result() -> dict[str, tuple[str, str, bool]]:
    rows = seed_rows()
    out: dict[str, tuple[str, str, bool]] = {}
    for d in sorted({r.drug_key for r in rows}):
        ps = build_set(d, rows)
        out[d] = (
            validate(d, rows, ps).status,
            type(ps).__name__,
            isinstance(ps, ParameterSet) and ps.complete,
        )
    return out


def test_seed_outcomes_are_stable() -> None:
    got = _seed_result()
    assert got["ertugliflozin"] == ("validated", "ParameterSet", True)
    # strict rule: one Cmax point at 0.499 makes sunitinib Failed (drug-level ratio said Validated)
    assert got["sunitinib"] == ("failed", "ParameterSet", True)
    sun = validate("sunitinib", seed_rows(), build_set("sunitinib", seed_rows()))
    assert "point_outside_2_fold" in sun.reasons and "absorption_rate_or_volume" in sun.suspect
    bad = [p for p in sun.points if not p.within_2_fold]
    assert len(bad) == 1 and bad[0].metric == "cmax" and bad[0].ratio < 0.5
    assert sun.failed_points == (bad[0].eid,)
    assert got["dolutegravir"] == ("not_validated", "ParameterSet", True)
    for d in ("gabapentin", "telmisartan", "tramadol"):
        assert got[d] == ("not_validated", "NoSet", False)


def test_seed_sunitinib_label_values_come_from_the_parent_not_the_metabolite() -> None:
    rows = seed_rows()
    t_half = [r for r in rows if r.drug_key == "sunitinib" and r.parameter == "t_half"]
    assert t_half and all(not r.confirmed for r in t_half)  # the 80-110 h value is the metabolite's
    ps = build_set("sunitinib", rows)
    assert isinstance(ps, ParameterSet) and not any(r.eid in ps.used for r in t_half)


def test_system_report_counts() -> None:
    rows = seed_rows()
    vals = [validate(d, rows, build_set(d, rows)) for d in sorted({r.drug_key for r in rows})]
    rep = system_report(vals)
    assert rep.n_drugs == 6 and sum(rep.by_status.values()) == 6
    assert rep.interpretable is False and rep.min_drugs_for_interpretation == 10
    assert rep.conformal == "interval_n_too_small"
