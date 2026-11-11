"""Formulation and route resolvers A and B (M3): evidence into the vocabulary."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.modelkit import formulation, formulation_a, formulation_b
from janus_pipelines.modelkit.confirm import Context
from janus_pipelines.modelkit.formref import BrandTable, Resolution, decide
from janus_pipelines.modelkit.model import Candidate
from janus_pipelines.modelkit.pairing import Paired
from janus_pipelines.modelkit.resolver import IdentityTable
from janus_pipelines.modelkit.units import Stat

REPO = Path(__file__).resolve().parents[2]
TABLE = IdentityTable.from_csv(
    (REPO / "data" / "modelkit" / "identity_m1.csv").read_text(encoding="utf-8")
)
BRANDS = BrandTable.from_csv(
    "brand,drug_key,form_class,route\n"
    "tivicay,dolutegravir,immediate_release,oral\n"
    "tivicay xr,dolutegravir,modified_release,oral\n"
    "dovato,dolutegravir,fixed_dose_combination,oral\n"
    "tivipatch,dolutegravir,other_route,\n"
)
LOC = "NCT00000001#outcome-1/OG000"


def record(
    iv_name: str = "Dolutegravir",
    iv_desc: str = "",
    arm_desc: str = "",
    group_title: str = "Dolutegravir",
    group_desc: str = "",
    outcome_title: str = "AUC of Dolutegravir",
    other_interventions: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    ivs = [{"type": "DRUG", "name": iv_name, "description": iv_desc}] + [
        {"type": "DRUG", "name": n, "description": d} for n, d in (other_interventions or [])
    ]
    names = [f"Drug: {i['name']}" for i in ivs]
    return {
        "protocolSection": {
            "identificationModule": {"nctId": "NCT00000001"},
            "armsInterventionsModule": {
                "armGroups": [
                    {"label": group_title, "description": arm_desc, "interventionNames": names}
                ],
                "interventions": ivs,
            },
        },
        "resultsSection": {
            "outcomeMeasuresModule": {
                "outcomeMeasures": [
                    {
                        "title": outcome_title,
                        "description": "",
                        "groups": [
                            {"id": "OG000", "title": group_title, "description": group_desc}
                        ],
                    }
                ]
            }
        },
    }


def both(s: dict[str, Any]) -> tuple[Resolution, Resolution]:
    return (
        formulation_a.resolve(s, "dolutegravir", LOC, TABLE, BRANDS),
        formulation_b.resolve(s, "dolutegravir", LOC, TABLE, BRANDS),
    )


@pytest.mark.parametrize(
    ("kwargs", "form", "route"),
    [
        ({"iv_desc": "Dolutegravir 50 mg extended-release tablet"}, "modified_release", "oral"),
        ({"iv_name": "Dolutegravir XR 100 mg"}, "modified_release", "unknown"),
        ({"iv_desc": "Dolutegravir oral solution, 10 mg/mL"}, "solution", "oral"),
        ({"iv_desc": "Dolutegravir IV infusion over 60 minutes"}, "solution", "iv"),
        ({"iv_name": "Tivicay"}, "immediate_release", "oral"),
        ({"iv_name": "Tivicay XR"}, "modified_release", "oral"),
        ({"iv_name": "Dovato"}, "fixed_dose_combination", "oral"),
        ({"iv_desc": "Dolutegravir 50 mg film-coated tablet"}, "immediate_release", "oral"),
        ({"iv_desc": "Dolutegravir immediate-release tablet"}, "immediate_release", "oral"),
        ({"iv_desc": "Dolutegravir 50 mg intramuscular injection"}, "other_route", "unknown"),
        ({"group_desc": "Single dose of dolutegravir oral suspension"}, "solution", "oral"),
        ({"iv_desc": "Dolutegravir orally disintegrating tablet"}, "unspecified", "oral"),
    ],
)
def test_both_resolvers_resolve_stated_forms(kwargs: dict[str, Any], form: str, route: str) -> None:
    a, b = both(record(**kwargs))
    assert (a.formulation, a.route) == (form, route), a
    assert (b.formulation, b.route) == (form, route), b


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"iv_desc": "Dolutegravir 50 mg"},
        {"iv_desc": "Dolutegravir administered orally once daily"},
        {"arm_desc": "Participants receive the study drug at the clinic"},
    ],
)
def test_nothing_stated_stays_unspecified(kwargs: dict[str, Any]) -> None:
    for r in both(record(**kwargs)):
        assert r.formulation == "unspecified"


def test_oral_words_alone_give_a_route_but_no_formulation() -> None:
    for r in both(record(iv_desc="Dolutegravir administered orally")):
        assert (r.formulation, r.route) == ("unspecified", "oral")


def test_modified_release_word_wins_over_a_generic_tablet() -> None:
    s = record(iv_name="Dolutegravir tablets", arm_desc="Dolutegravir extended release formulation")
    for r in both(s):
        assert r.formulation == "modified_release"


def test_another_drugs_form_is_not_this_drugs_form() -> None:
    s = record(
        iv_desc="",
        other_interventions=[("Midazolam", "oral syrup"), ("Rifampin", "intravenous infusion")],
        arm_desc="Dolutegravir 50 mg. Midazolam oral syrup. Rifampin intravenous infusion.",
    )
    for r in both(s):
        assert (r.formulation, r.route) == ("unspecified", "unknown"), r


def test_a_placebo_clause_gives_no_evidence() -> None:
    s = record(iv_desc="Dolutegravir 50 mg. Matching placebo tablets.")
    for r in both(s):
        assert r.formulation == "unspecified"


def test_oral_and_iv_in_one_layer_is_a_conflict_and_unresolved() -> None:
    s = record(group_desc="Dolutegravir oral tablet, then dolutegravir IV infusion")
    for r in both(s):
        assert (r.formulation, r.route) == ("unspecified", "unknown")


def test_the_results_group_is_more_specific_than_the_study_level_text() -> None:
    s = record(
        group_title="Dolutegravir IV",
        group_desc="Dolutegravir intravenous infusion",
        iv_desc="Dolutegravir tablets and intravenous formulation",
    )
    for r in both(s):
        assert (r.formulation, r.route) == ("solution", "iv")


def test_roman_numeral_iv_is_not_a_route() -> None:
    for r in both(record(iv_desc="Dolutegravir in phase IV and stage IV disease")):
        assert r.route == "unknown"


def test_disagreement_is_unresolved() -> None:
    res = formulation.combine(
        Resolution("solution", "iv", "solution"), Resolution("immediate_release", "oral", "ir")
    )
    assert res.formulation == "unspecified" and res.route == "unknown"
    ok = formulation.combine(
        Resolution("modified_release", "oral", "mr"), Resolution("modified_release", "oral", "mr")
    )
    assert ok.formulation == "modified_release" and ok.route == "oral"


def _candidate(locator: str, form: str = "unspecified", route: str = "unknown") -> Candidate:
    return Candidate(
        "dolutegravir", "clinicaltrials_gov", "NCT00000001", "OG000", locator, "auc_inf", 10.0,
        "ng*h/mL", Stat(10.0, "geometric", "none", None, None), "parent",
        Context(formulation=form, route=route), 50.0, 12, "q", "v",
    )  # fmt: skip


def test_resolve_pairs_sets_the_same_formulation_on_both_and_recomputes_confirmation() -> None:
    from collections import Counter

    from janus_pipelines.modelkit.confirm import Confirmation

    # the readers disagreed on the formulation (tablet word vs nothing): the resolvers now decide
    a, b = _candidate(LOC, "immediate_release"), _candidate(LOC, "unspecified")
    p = Paired(a, b, Confirmation(False, "context_differs", ("formulation",)))
    s = record(iv_desc="Dolutegravir 50 mg extended-release tablet")
    (out,) = formulation.resolve_pairs([p], s, TABLE, BRANDS, Counter())
    assert out.a.context.formulation == out.b.context.formulation == "modified_release"  # type: ignore[union-attr]
    assert out.result.confirmed
    assert any(n.startswith("formulation:") for n in out.a.notes)


def test_resolve_pairs_makes_the_route_unknown_on_an_oral_and_intravenous_statement() -> None:
    """Owner decision 2026-11-11 (M4): the readers' own route does not survive an oral/IV conflict."""
    from collections import Counter

    from janus_pipelines.modelkit.confirm import Confirmation

    s = record(group_desc="Dolutegravir oral tablet, then dolutegravir IV infusion")
    p = Paired(
        _candidate(LOC, "immediate_release", "oral"),
        _candidate(LOC, "immediate_release", "oral"),
        Confirmation(True, "agree"),
    )
    counts: Counter[str] = Counter()
    (out,) = formulation.resolve_pairs([p], s, TABLE, BRANDS, counts)
    assert out.a.context.route == out.b.context.route == "unknown"  # type: ignore[union-attr]
    assert counts["route_oral_iv_conflict"] == 1
    # without the conflict the readers' route is still used where the resolvers found none
    p2 = Paired(_candidate(LOC, "unspecified", "oral"), _candidate(LOC, "unspecified", "oral"), Confirmation(True, "agree"))
    (out2,) = formulation.resolve_pairs([p2], record(iv_desc="Dolutegravir 50 mg"), TABLE, BRANDS, Counter())
    assert out2.a.context.route == "oral"  # type: ignore[union-attr]


def test_resolve_pairs_leaves_an_unmatched_candidate_alone() -> None:
    from collections import Counter

    from janus_pipelines.modelkit.confirm import Confirmation

    p = Paired(_candidate(LOC), None, Confirmation(False, "reader_b_found_nothing"))
    (out,) = formulation.resolve_pairs([p], record(), TABLE, BRANDS, Counter())
    assert out is p


# --- properties --------------------------------------------------------------------------------

_FILLER = st.sampled_from(
    "participants receive study drug single dose fasted healthy adults daily morning water clinic "
    "visit day washout period cohort treatment arm group 50 mg 100 mg randomized crossover".split()
)
_TEXT = st.lists(_FILLER, min_size=0, max_size=14).map(" ".join)
_MR_PHRASES = st.sampled_from(
    [
        "extended-release",
        "extended release",
        "modified-release",
        "sustained release",
        "prolonged-release",
        "delayed release",
    ]
)
_GENERIC = st.sampled_from(["tablet", "tablets", "capsule", "capsules", "film-coated tablet"])


@given(_TEXT, _TEXT)
def test_property_unspecified_never_becomes_immediate_release_without_evidence(
    a: str, b: str
) -> None:
    s = record(iv_desc=f"Dolutegravir {a}", arm_desc=b, group_desc=a)
    for r in both(s):
        assert r.formulation == "unspecified"


@given(_TEXT, _MR_PHRASES, _GENERIC, st.booleans())
def test_property_modified_release_words_win_over_generic_tablet(
    filler: str, mr: str, generic: str, mr_first: bool
) -> None:
    desc = (
        f"Dolutegravir {mr} {generic} {filler}"
        if mr_first
        else f"Dolutegravir {generic} {filler} {mr} form"
    )
    for r in both(record(iv_desc=desc)):
        assert r.formulation == "modified_release"


@given(
    st.sets(st.sampled_from(["fdc", "other_route", "mr", "special", "solution", "ir", "ir_weak"])),
    st.sets(st.sampled_from(["iv", "oral"])),
)
def test_property_decide_never_gives_immediate_release_without_ir_evidence(
    cls: set[str], routes: set[str]
) -> None:
    res = decide(frozenset(cls), frozenset(routes))
    if res.formulation == "immediate_release":
        assert cls & {"ir", "ir_weak"}
        assert not cls & {"fdc", "other_route", "mr", "special", "solution"}
        assert "iv" not in routes
    if cls & {"fdc", "other_route", "mr"}:
        assert res.formulation != "immediate_release"
    if not cls and not routes:
        assert res.formulation == "unspecified"


def _imports(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            out.append(n.module + ":" + ",".join(a.name for a in n.names))
        elif isinstance(n, ast.Import):
            out.extend(a.name for a in n.names)
    return " ".join(sorted(out))


def test_resolver_b_shares_no_code_with_resolver_a_or_the_readers() -> None:
    root = Path(formulation_b.__file__).parent
    b = _imports(root / "formulation_b.py")
    for forbidden in (
        "formulation_a",
        "reader_a",
        "reader_b",
        "pairing",
        "arm_context",
        "classify_analyte",
        "formulation:",
    ):
        assert forbidden not in b, forbidden
    a = _imports(root / "formulation_a.py")
    assert "formulation_b" not in a and "pairing" not in a and "reader_b" not in a


def test_product_table_is_consistent() -> None:
    import csv

    rows = list(
        csv.DictReader((REPO / "data" / "modelkit" / "product_forms.csv").open(encoding="utf-8"))
    )
    assert len(rows) > 500
    by = {(r["brand"], r["drug_key"]): r["form_class"] for r in rows}
    assert by[("seroquel xr", "quetiapine")] == "modified_release"
    assert by[("seroquel", "quetiapine")] == "immediate_release"
    assert all(len(r["brand"]) >= 5 for r in rows)
    assert {r["form_class"] for r in rows} <= {
        "immediate_release",
        "solution",
        "modified_release",
        "fixed_dose_combination",
        "other_route",
    }
    assert len(by) == len(rows)  # one class per brand and drug


@given(st.sampled_from(["iv", "oral"]))
def test_property_a_conflict_never_keeps_a_reader_route(reader_route: str) -> None:
    from collections import Counter

    from janus_pipelines.modelkit.confirm import Confirmation

    s = record(group_desc="Dolutegravir given orally and as an intravenous infusion")
    p = Paired(
        _candidate(LOC, "unspecified", reader_route),
        _candidate(LOC, "unspecified", reader_route),
        Confirmation(True, "agree"),
    )
    (out,) = formulation.resolve_pairs([p], s, TABLE, BRANDS, Counter())
    assert out.a.context.route == "unknown"  # type: ignore[union-attr]
