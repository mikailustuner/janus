"""Property tests for dataset preparation (drug-resolution design §8: P5, P7, P18, P17)."""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from janus.resolution.atc import (
    CombinationCheck,
    CombinationRules,
    RouteMap,
    is_ingredient_level,
)
from janus.resolution.canonical import GOLDEN_ROWS, GOLDEN_SCHEMA, content_hash
from janus.resolution.prepare import PreparedDataset, prepare_dataset
from tests.resolution_strategies import (
    SALTS,
    SYN_CODES,
    WORDS,
    titck_row,
    us_row,
    wikidata_row,
    with_check_digit,
)

RULES = CombinationRules(frozenset({"C09B", "A10BD"}), frozenset({"J01CA51"}), frozenset(), "t")
ROUTES = RouteMap({"ORAL": ("A", "C", "J", "N"), "TOPICAL": ("D",)}, "t")
COMBO_CODES = st.sampled_from(["C09BB03", "A10BD05", "J01CA51", "N01AA20", "C08CA51"])


def _barcode(i: int) -> str:
    return with_check_digit(f"869{i:09d}")


@st.composite
def sources(draw: st.DrawFn) -> tuple[list[Any], list[Any], list[Any]]:
    """Synthetic Wikidata items and TİTCK/openFDA products built from them."""
    n = draw(st.integers(2, len(WORDS)))
    words = WORDS[:n]
    wd: list[Any] = []
    for i, w in enumerate(words, start=1):
        codes = draw(st.lists(st.one_of(SYN_CODES, COMBO_CODES), min_size=1, max_size=3))
        lang = draw(st.sampled_from(["en", "tr"]))
        wd.append(wikidata_row(f"Q{i}", codes, {lang: w}))
    name = st.one_of(
        st.sampled_from(words),
        st.tuples(st.sampled_from(words), st.sampled_from(SALTS)).map(" ".join),
        st.just("bilinmeyen madde"),
        st.tuples(st.sampled_from(words), st.sampled_from(words)).map(" ".join),  # unsplit
    )
    published = st.one_of(st.none(), SYN_CODES, COMBO_CODES, st.sampled_from(["B05D", "S03CA0l"]))
    tr: list[Any] = []
    for i in range(draw(st.integers(1, 12))):
        ings = draw(st.lists(name, min_size=0, max_size=3))
        barcode = _barcode(draw(st.integers(1, 6))) if draw(st.integers(0, 5)) else None
        tr.append(titck_row(barcode, f"URUN {i}", ings, draw(published)))
    us: list[Any] = []
    for i in range(draw(st.integers(0, 6))):
        ings = draw(st.lists(st.sampled_from(words), min_size=1, max_size=2))
        routes = draw(st.lists(st.sampled_from(["ORAL", "TOPICAL", "NASAL"]), max_size=2))
        us.append(us_row(f"1234{i}-678", [f"1234{i}-678-90"], ings, routes))
    return tr, us, wd


def _full_check(ds: PreparedDataset) -> set[str]:
    return set(ds.combination_audit)


@given(src=sources())
def test_no_combination_code_in_prepared_dataset(
    src: tuple[list[Any], list[Any], list[Any]],
) -> None:
    """Feature: drug-resolution, Property P7 (prepare part). Validates Req 5.2.

    No ingredient of any product carries a combination code (rule file, numbering rule or
    observation), including single-ingredient rows whose published code is a combination code
    and names that look like two substances.
    """
    tr, us, wd = src
    ds = prepare_dataset(tr, us, wd, RULES, ROUTES)
    combo = _full_check(ds)
    base = CombinationCheck(RULES)
    for p in ds.products:
        for ing in p.ingredients:
            for code in ing.rule_input():
                assert code not in combo and not base.is_combination(code)
                assert is_ingredient_level(code)
            if ing.reason == "possible_unsplit_combination":
                assert ing.atc == ()


@given(src=sources())
def test_unmapped_stay_visible(src: tuple[list[Any], list[Any], list[Any]]) -> None:
    """Feature: drug-resolution, Property P18. Validates Req 5.4.

    Every product keeps one entry per published ingredient, in published order; every entry
    that is not `mapped` has a reason (or, if ambiguous, its candidate keys) and contributes
    nothing to `rule_input`.
    """
    tr, us, wd = src
    ds = prepare_dataset(tr, us, wd, RULES, ROUTES)
    by_name = {p.product_name: p for p in ds.products if p.source_id == "titck"}
    for row in tr:
        p = by_name[row["product_name"]]
        assert [i.published_name for i in p.ingredients] == row["ingredients"]
        assert [i.position for i in p.ingredients] == list(range(len(row["ingredients"])))
    for p in ds.products:
        for ing in p.ingredients:
            if ing.status == "mapped":
                assert ing.qid and ing.atc and ing.reason is None
            else:
                assert ing.rule_input() == ()
                if ing.status == "ambiguous":
                    assert len(ing.key_candidates) >= 2
                else:
                    assert ing.reason is not None


@given(src=sources())
def test_codes_belong_to_their_ingredient(src: tuple[list[Any], list[Any], list[Any]]) -> None:
    """Feature: drug-resolution, Property P17 (prepare part). Validates Req 5.1.

    Every emitted code is one of the ingredient key's own ingredient codes; malformed published
    codes are never emitted.
    """
    tr, us, wd = src
    ds = prepare_dataset(tr, us, wd, RULES, ROUTES)
    for p in ds.products:
        for ing in p.ingredients:
            if ing.status != "mapped":
                continue
            assert ing.qid is not None
            own = {a.code for a in ds.ingredients[ing.qid].ingredient_atc}
            assert {a.code for a in ing.atc} <= own


SINGLE_CODES = SYN_CODES.filter(lambda c: not CombinationCheck(RULES).is_combination(c))


@given(
    a_codes=st.lists(SINGLE_CODES, min_size=1, max_size=3, unique=True),
    b_codes=st.lists(SINGLE_CODES, min_size=1, max_size=3, unique=True),
    combo=st.sampled_from(["C09BB03", "C09DA01", "A10BD07", "J01CA51"]),
    a_pick=st.one_of(st.none(), st.integers(0, 2)),
    b_pick=st.one_of(st.none(), st.integers(0, 2)),
    salt=st.sampled_from(["", " hidroklorur", " besilat"]),
)
def test_decomposition_invariance(
    a_codes: list[str],
    b_codes: list[str],
    combo: str,
    a_pick: int | None,
    b_pick: int | None,
    salt: str,
) -> None:
    """Feature: drug-resolution, Property P5. Validates Req 5.1.

    A combination product A + B has the same ingredient keys as the single products A and B;
    each ingredient's codes in A + B are among its own ingredient codes; when an ingredient has
    exactly one code, A + B and the single product give that same code. (A and B are known
    ingredients: each has a non-combination code, and a single product's code is one of them.)
    """
    a_mono = None if a_pick is None else a_codes[a_pick % len(a_codes)]
    b_mono = None if b_pick is None else b_codes[b_pick % len(b_codes)]
    wd = [
        wikidata_row("Q1", a_codes, {"en": "alfazin"}),
        wikidata_row("Q2", b_codes, {"tr": "betorol"}),
    ]
    tr = [
        titck_row(_barcode(1), "KOMBI", ["alfazin" + salt, "betorol"], combo),
        titck_row(_barcode(2), "TEK A", ["alfazin"], a_mono),
        titck_row(_barcode(3), "TEK B", ["betorol" + salt], b_mono),
    ]
    ds = prepare_dataset(tr, [], wd, RULES, ROUTES)
    p = {x.product_name: x for x in ds.products}
    combo_p, a, b = p["KOMBI"], p["TEK A"], p["TEK B"]
    assert [i.qid for i in combo_p.ingredients] == [a.ingredients[0].qid, b.ingredients[0].qid]
    assert [i.qid for i in combo_p.ingredients] == ["Q1", "Q2"]
    for ing, single in zip(combo_p.ingredients, (a, b), strict=True):
        assert ing.qid is not None
        own = ds.ingredients[ing.qid].ingredient_atc
        assert {x.code for x in ing.atc} <= {x.code for x in own}
        assert combo not in ing.rule_input()
        if len({x.code for x in own}) == 1:
            assert ing.rule_input() == single.ingredients[0].rule_input()


def test_amlipin_example() -> None:
    """Req 5.2 example with the reviewed rule files and the real Wikidata codes."""
    wd = [
        wikidata_row("Q411347", ["C08CA01"], {"en": "amlodipine", "tr": "amlodipin"}),
        wikidata_row("Q412208", ["C09AA03"], {"en": "lisinopril"}),
    ]
    tr = [
        titck_row(
            "8680199094206",
            "AMLIPIN 10 / 10 MG FILM TABLET, 30 ADET",
            ["amlodipin besilat", "lisinopril dihidrat"],
            "C09BB03",
        )
    ]
    ds = prepare_dataset(tr, [], wd, CombinationRules.load(), RouteMap.load())
    (p,) = ds.products
    assert p.published_atc == "C09BB03"
    assert [(i.qid, i.rule_input()) for i in p.ingredients] == [
        ("Q411347", ("C08CA01",)),
        ("Q412208", ("C09AA03",)),
    ]


def test_golden_hash_vector() -> None:
    """Same value as pipelines/tests/test_canonical_properties.py (design §6.2)."""
    assert (
        content_hash(GOLDEN_ROWS, GOLDEN_SCHEMA)
        == "a7b073198be149895d161e694542975078a69999dd7fb1c284f8dcf1b6c5ec8b"
    )
