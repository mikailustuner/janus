# pyright: reportUnknownMemberType=false
"""Time machine source parsers (time-machine design §4-§5, P1-P3)."""

from __future__ import annotations

import json

from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.jobs.time_machine import (
    CHEMBL,
    PK_GENES,
    POTENCY_NAMES,
    PUBLIC_DOMAIN_DEPOSITORS,
    Comparator,
    Constituent,
    classify_depositor,
    find_term,
    parse_bioactivity,
    parse_labels,
    parse_molecules,
)

depositors = st.sampled_from([*sorted(PUBLIC_DOMAIN_DEPOSITORS), CHEMBL, "824", "Burnham", ""])
activity = st.fixed_dictionaries(
    {
        "AID": st.integers(1, 50).map(str),
        "CID": st.just("1"),
        "compound": st.just("x"),
        "Activity Outcome": st.sampled_from(["Active", "Inactive"]),
        "Target GeneID": st.sampled_from(["", "1576", "8856", "7421"]),
        "Activity Name": st.sampled_from([*sorted(POTENCY_NAMES), "", "Inhibition"]),
        "Activity Value [uM]": st.sampled_from(["", "0.027", "12.5"]),
    }
)


@given(depositors)
def test_only_allowlisted_depositors_are_public_domain(name: str) -> None:
    assert (classify_depositor(name) == "public_domain") == (name in PUBLIC_DOMAIN_DEPOSITORS)


@given(st.lists(activity, max_size=40), st.dictionaries(st.integers(1, 50).map(str), depositors))
def test_bioactivity_licence_filter_and_accounting(
    rows: list[dict[str, str]], deps: dict[str, str]
) -> None:
    result = parse_bioactivity(rows, deps)
    assert result.input_rows == len(rows)
    assert len(result.rows) + sum(result.excluded.values()) == len(rows)
    for r in result.rows:
        assert r["depositor"] in PUBLIC_DOMAIN_DEPOSITORS  # P2: no ChEMBL or unverified value
        assert r["activity_name"] in POTENCY_NAMES
    pointers = result.metrics["pk_interaction_pointers"]
    assert isinstance(pointers, list)
    for p in pointers:
        assert isinstance(p, dict)
        assert p["entrez_gene"] in PK_GENES
        assert "value_um" not in p  # P3: a pointer never carries the excluded value


def _sparql(rows: list[dict[str, str]]) -> bytes:
    return json.dumps(
        {"results": {"bindings": [{k: {"value": v} for k, v in r.items()} for r in rows]}}
    ).encode()


W = "http://www.wikidata.org/entity/"


def test_molecules_require_the_curated_taxon_and_count_exclusions() -> None:
    cons = [
        Constituent("a", ("Q1",), "c1", "1", "AAAAAAAAAAAAAA-BBBBBBBBBB-C"),
        Constituent("a", ("Q1",), "c2", "2", "DDDDDDDDDDDDDD-BBBBBBBBBB-C"),
        Constituent("b", ("Q9",), "c3", "3", "EEEEEEEEEEEEEE-BBBBBBBBBB-C"),
        Constituent("v", (), "acid", "4", "FFFFFFFFFFFFFF-BBBBBBBBBB-C"),
    ]
    occ = _sparql(
        [
            {"ik": cons[0].inchikey, "c": W + "Q10", "taxon": W + "Q1", "art": W + "Q100"},
            {"ik": cons[1].inchikey, "c": W + "Q11", "taxon": W + "Q2", "art": W + "Q101"},
            {"ik": cons[3].inchikey, "c": W + "Q13"},
        ]
    )
    inter = _sparql(
        [{"key": "drug", "c": W + "Q50", "protein": W + "Q60", "gene": W + "Q70", "entrez": "5743"}]
    )
    r = parse_molecules(cons, [Comparator("k", "a", "drug", ("pain",))], occ, inter)
    assert r.excluded == {"not_found_in_taxon": 1, "no_wikidata_item": 1}
    assert r.input_rows == len(r.rows) + sum(r.excluded.values())
    occ_rows = [x for x in r.rows if x["kind"] == "occurrence"]
    assert [x["compound"] for x in occ_rows] == ["c1", "acid"]
    assert occ_rows[0]["reference_qids"] == ["Q100"]


@given(st.text(max_size=200), st.text(min_size=1, max_size=10))
def test_find_term_excerpt_contains_the_term(text: str, term: str) -> None:
    hit = find_term(text, [term])
    assert (hit is not None) == (term.lower() in text.lower())


def test_label_without_the_term_is_excluded() -> None:
    comps = [
        Comparator("k", "s", "d1", ("neuropathic pain",)),
        Comparator("k", "s", "d2", ("pain",)),
    ]
    body = json.dumps(
        {
            "results": [
                {"set_id": "x", "effective_time": "2026", "indications_and_usage": ["For fever."]}
            ]
        }
    ).encode()
    r = parse_labels(comps, {"d1": body})
    assert r.rows == [] and r.excluded == {"indication_term_not_in_label": 2}
