"""Curated ATC code exclusions (drug-resolution Req 15, DP45; P49-P50). Synthetic rows (invented
names), plus the committed file.

P49: the file parser refuses each single defect and names only the row.
P50: an excluded (key, code, source) disappears from the key's codes and nothing else changes: the
other codes of the key, the codes of other keys, the products and their published codes stay as
they were; a stale entry refuses the build.
"""

from __future__ import annotations

import csv
import io
from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.resolution.atc import CombinationRules, RouteMap, RulesFileError
from janus.resolution.code_exclusions import (
    HEADER,
    CodeExclusion,
    apply_to_rows,
    parse_code_exclusions,
    version_of,
)
from janus.resolution.load import EXCLUSIONS_FILE, read_code_exclusions
from janus.resolution.prepare import PreparedDataset, prepare_dataset
from tests.resolution_strategies import barcode13, titck_row, wikidata_row

URL = "https://atcddd.fhi.no/atc_ddd_index/?code=M01AE&showdescription=no"
RULES = CombinationRules.load()
ROUTES = RouteMap.load()


def good(**kw: str) -> dict[str, str]:
    row = {
        "key": "Q11",
        "code": "M01AE03",
        "source": "titck",
        "reason": "wrong_substance",
        "evidence": "names another substance",
        "whocc_url": URL,
        "whocc_date": "2026-11-08",
        "note": "n",
    }
    return {**row, **kw}


def text(*rows: dict[str, str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=HEADER, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


# --- P49 ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        good(key="J2"),  # not a Wikidata item
        good(key="Q0"),
        good(code="M01AE"),  # not seven characters
        good(code="m01ae03"),
        good(source="openfda"),
        good(reason="because"),
        good(evidence=""),
        good(note=" "),
        good(whocc_url="https://example.org/atc"),
        good(whocc_date="08.11.2026"),
    ],
)
def test_p49_a_bad_row_is_refused_and_the_message_names_the_row_only(bad: dict[str, str]) -> None:
    """Feature: drug-resolution, Property P49. Validates Req 15.2."""
    with pytest.raises(RulesFileError) as err:
        parse_code_exclusions(text(bad))
    assert "row 2" in str(err.value) and "names another" not in str(err.value)


def test_p49_header_repeats_and_the_committed_file() -> None:
    with pytest.raises(RulesFileError, match="header"):
        parse_code_exclusions(text(good()).replace("source", "origin"))
    with pytest.raises(RulesFileError, match="repeated"):
        parse_code_exclusions(text(good(), good(note="again")))
    both = parse_code_exclusions(text(good(), good(source="wikidata")))
    assert [e.source for e in both] == ["titck", "wikidata"]
    assert parse_code_exclusions(",".join(HEADER) + "\n") == ()
    committed = read_code_exclusions(EXCLUSIONS_FILE)
    assert len(committed) == 12 and version_of(committed) != ""
    assert version_of(committed) == version_of(list(reversed(committed)))
    assert {e.reason for e in committed} <= {"wrong_substance", "old_code", "not_a_medicine"}
    assert all(e.whocc_date == "2026-11-08" and e.evidence and e.note for e in committed)


# --- P50 ---------------------------------------------------------------------------------------

# Two invented ingredients; both carry the same wrong-looking code from different sources.
WD = [
    wikidata_row("Q11", ["M01AE03", "D01AC08"], {"en": "alfazin"}),
    wikidata_row("Q12", ["M01AE03", "C08CA01"], {"en": "betarol"}),
    wikidata_row("Q13", ["N02AX02"], {"en": "gammacil"}),
]
TR = [
    titck_row(barcode13(1), "ALFAZIN ONE", ["alfazin"], "M01AE03"),
    titck_row(barcode13(2), "ALFAZIN TWO", ["alfazin"], "D01AC08"),
    titck_row(barcode13(3), "BETAROL ONE", ["betarol"], "C08CA01"),
    titck_row(barcode13(4), "GAMMACIL ONE", ["gammacil"], "N02AX02"),
]
CARRIED = [
    ("Q11", "M01AE03", "wikidata"),
    ("Q11", "D01AC08", "wikidata"),
    ("Q12", "M01AE03", "wikidata"),
    ("Q12", "C08CA01", "wikidata"),
    ("Q13", "N02AX02", "wikidata"),
    ("Q11", "M01AE03", "titck"),
    ("Q11", "D01AC08", "titck"),
    ("Q12", "C08CA01", "titck"),
    ("Q13", "N02AX02", "titck"),
]


def exclusion(key: str, code: str, source: str) -> CodeExclusion:
    return CodeExclusion(key, code, source, "wrong_substance", "e", URL, "2026-11-08", "n")


def build(exclusions: list[CodeExclusion]) -> PreparedDataset:
    return prepare_dataset(TR, [], WD, RULES, ROUTES, code_exclusions=exclusions)


def codes(ds: PreparedDataset) -> dict[str, set[str]]:
    return {q: {a.code for a in r.ingredient_atc} for q, r in ds.ingredients.items()}


BASELINE = build([])


def expected(chosen: set[tuple[str, str, str]]) -> dict[str, set[str]]:
    """Codes per key after the exclusions, for sets that keep every key in the index."""
    out: dict[str, set[str]] = {}
    for q in ("Q11", "Q12", "Q13"):
        out[q] = {
            c
            for k, c, src in CARRIED
            if k == q and src in ("wikidata", "titck") and (k, c, src) not in chosen
        }
    return out


def stays(chosen: set[tuple[str, str, str]]) -> bool:
    """Every key keeps a Wikidata code, so it stays eligible (a key without one leaves the index
    and the TİTCK name bridge may re-map its product names: tested on its own below)."""
    return all(
        any(k == q and s == "wikidata" and (k, c, s) not in chosen for k, c, s in CARRIED)
        for q in ("Q11", "Q12", "Q13")
    )


@given(chosen=st.sets(st.sampled_from(CARRIED)).filter(stays))
def test_p50_only_the_excluded_codes_leave(chosen: set[tuple[str, str, str]]) -> None:
    """Feature: drug-resolution, Property P50. Validates Req 15.3, 15.4."""
    want = expected(chosen)
    ds = build([exclusion(*t) for t in sorted(chosen)])
    assert codes(ds) == want
    assert [(p.candidate_id, p.published_atc) for p in ds.products] == [
        (p.candidate_id, p.published_atc) for p in BASELINE.products
    ]
    for p in ds.products:  # no product ingredient carries a code its key no longer has
        for ing in p.ingredients:
            if ing.qid is not None:
                assert {a.code for a in ing.atc} <= want[ing.qid]


def test_p50_a_key_without_a_code_leaves_the_index() -> None:
    """The research-chemical case: the only code goes, the item is no longer an ingredient."""
    ds = prepare_dataset(
        [], [], WD, RULES, ROUTES, code_exclusions=[exclusion("Q13", "N02AX02", "wikidata")]
    )
    assert "Q13" not in ds.ingredients and {"Q11", "Q12"} <= set(ds.ingredients)
    assert not any(n.ref == "Q13" for n in ds.names)


def test_p50_the_published_code_of_a_product_does_not_become_the_ingredients_code() -> None:
    """The ketoconazole case: a single-ingredient product publishes another substance's code."""
    ds = build([exclusion("Q11", "M01AE03", "titck"), exclusion("Q11", "M01AE03", "wikidata")])
    assert codes(ds)["Q11"] == {"D01AC08"}
    one = next(p for p in ds.products if p.product_name == "ALFAZIN ONE")
    assert one.published_atc == "M01AE03"  # as published
    assert [a.code for a in one.ingredients[0].atc] == ["D01AC08"]
    assert (
        one.ingredients[0].atc_selection == "anatomical_group"
        or one.ingredients[0].atc_selection == "all_codes"
    )
    other = next(p for p in ds.products if p.product_name == "BETAROL ONE")
    assert [a.code for a in other.ingredients[0].atc] == ["C08CA01"]


def test_p50_a_stale_entry_refuses_the_build() -> None:
    for stale in (
        exclusion("Q11", "M01AE03", "titck").__class__(
            "Q99", "M01AE03", "wikidata", "wrong_substance", "e", URL, "2026-11-08", "n"
        ),
        exclusion("Q12", "M01AE03", "titck"),  # carried by Wikidata only
        exclusion("Q11", "A02BC05", "wikidata"),
    ):
        with pytest.raises(RulesFileError, match="does not give"):
            build([stale])


def test_p50_rows_without_exclusions_are_untouched_and_the_input_is_not_changed() -> None:
    rows = list(WD)
    assert apply_to_rows(rows, []) == rows
    out = apply_to_rows(rows, [exclusion("Q11", "M01AE03", "wikidata")])
    assert [r["atc_codes"] for r in out] == [["D01AC08"], ["M01AE03", "C08CA01"], ["N02AX02"]]
    assert WD[0]["atc_codes"] == ["M01AE03", "D01AC08"]
    assert replace(exclusion("Q11", "M01AE03", "wikidata"), note="x") != exclusion(
        "Q11", "M01AE03", "wikidata"
    )


def test_the_committed_file_is_in_the_data_readme() -> None:
    readme = (Path(__file__).resolve().parents[3] / "data" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "atc_code_exclusions.csv" in readme
