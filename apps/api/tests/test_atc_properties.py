"""Property tests for ATC code handling (drug-resolution design §8: P7 pure part, P17, P24)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.resolution.atc import (
    AtcCode,
    CombinationCheck,
    CombinationCodeLeakError,
    CombinationRules,
    ProductContext,
    RouteMap,
    RulesFileError,
    assert_no_combination,
    ingredient_codes,
    is_ingredient_level,
    select_codes,
)

# Small alphabets so that generated codes share groups often.
CODES = st.tuples(
    st.sampled_from("ACDHNRS"),
    st.sampled_from(["01", "02", "07", "09"]),
    st.sampled_from(["AA", "AB", "BB", "CA"]),
    st.sampled_from(["01", "02", "03", "06", "20", "51", "86"]),
).map("".join)
MALFORMED = st.sampled_from(["B05D", "R05X", "A12AX", "S03CA0l", "C09", "c08ca01", "", "C08CA1"])
PUBLISHED = st.one_of(st.none(), CODES, MALFORMED)
ROUTES = ["ORAL", "TOPICAL", "OPHTHALMIC", "INTRAVENOUS", "NASAL"]


@st.composite
def checks(draw: st.DrawFn) -> CombinationCheck:
    prefixes = st.one_of(
        CODES.map(lambda c: c[:4]), CODES.map(lambda c: c[:5]), CODES.map(lambda c: c[:3])
    )
    groups = draw(st.frozensets(prefixes, max_size=3))
    codes = draw(st.frozensets(CODES, max_size=3))
    exceptions = draw(st.frozensets(st.one_of(CODES, CODES.map(lambda c: c[:5])), max_size=2))
    rules = CombinationRules(groups, codes, exceptions, "test")
    return CombinationCheck(
        rules,
        observed=draw(st.frozensets(CODES, max_size=4)),
        wikidata_codes=draw(st.frozensets(CODES, max_size=4)),
    )


@st.composite
def route_maps(draw: st.DrawFn) -> RouteMap:
    allow = draw(
        st.dictionaries(
            st.sampled_from(ROUTES),
            st.lists(
                st.one_of(CODES.map(lambda c: c[:1]), CODES.map(lambda c: c[:3])),
                min_size=1,
                max_size=3,
            ).map(lambda ps: tuple(sorted(set(ps)))),
            max_size=4,
        )
    )
    return RouteMap(allow, "test")


CANDIDATES = st.lists(
    st.builds(
        AtcCode,
        st.one_of(CODES, CODES, MALFORMED),
        st.sampled_from(["wikidata", "titck"]),
        st.one_of(st.none(), st.sampled_from(["TR:titck:1", "TR:titck:2"])),
    ),
    max_size=6,
).map(lambda xs: tuple(sorted(set(xs), key=AtcCode.sort_key)))

CONTEXTS = st.builds(
    ProductContext,
    PUBLISHED,
    st.integers(1, 4),
    st.lists(st.sampled_from([*ROUTES, "UNKNOWN ROUTE"]), max_size=3).map(tuple),
)


@given(candidates=CANDIDATES, product=CONTEXTS, check=checks(), route_map=route_maps())
def test_selected_codes_are_well_formed_and_belong_to_the_ingredient(
    candidates: tuple[AtcCode, ...],
    product: ProductContext,
    check: CombinationCheck,
    route_map: RouteMap,
) -> None:
    """Feature: drug-resolution, Property P17. Validates Req 5.1.

    Every selected code is a 7-character code taken from the ingredient's own candidates;
    malformed published codes are never selected; the selection is recorded.
    """
    result = select_codes(candidates, product, check, route_map)
    assert set(result.codes) <= set(candidates)
    assert all(is_ingredient_level(a.code) for a in result.codes)
    if product.published_atc is not None and not is_ingredient_level(product.published_atc):
        assert product.published_atc not in {a.code for a in result.codes}
    if result.codes:
        assert result.selection is not None and result.reason is None
    else:
        assert result.selection is None and result.reason is not None
    if result.selection == "single_ingredient_product":
        assert product.ingredient_count == 1
        assert {a.code for a in result.codes} == {product.published_atc}


@given(
    wikidata=st.lists(st.one_of(CODES, MALFORMED), max_size=4),
    observed=st.lists(
        st.tuples(st.one_of(CODES, MALFORMED), st.just("titck"), st.just("TR:titck:9")),
        max_size=3,
    ),
    product=CONTEXTS,
    check=checks(),
    route_map=route_maps(),
)
def test_no_combination_code_is_selected(
    wikidata: list[str],
    observed: list[tuple[str, str, str]],
    product: ProductContext,
    check: CombinationCheck,
    route_map: RouteMap,
) -> None:
    """Feature: drug-resolution, Property P7 (pure part). Validates Req 5.2.

    Neither `ingredient_codes` nor `select_codes` ever yields a combination code, even when the
    product's own code is one; the product's combination code never becomes an ingredient code.
    """
    s = ingredient_codes(wikidata, observed, check)
    assert not any(check.is_combination(a.code) for a in s)
    result = select_codes(s, product, check, route_map)
    assert not any(check.is_combination(a.code) for a in result.codes)
    if product.published_atc and check.is_combination(product.published_atc):
        assert product.published_atc not in {a.code for a in result.codes}


@given(check=checks(), code=CODES)
def test_forced_leak_raises(check: CombinationCheck, code: str) -> None:
    """Feature: drug-resolution, Property P7 (guard). A combination code makes the guard fail."""
    if check.is_combination(code):
        with pytest.raises(CombinationCodeLeakError):
            assert_no_combination([code], check)
    else:
        assert_no_combination([code], check)
    with pytest.raises(CombinationCodeLeakError):
        assert_no_combination(["C09"], check)


@given(
    candidates=CANDIDATES,
    routes=st.lists(st.sampled_from([*ROUTES, "UNKNOWN ROUTE"]), max_size=3),
    route_map=route_maps(),
)
def test_route_based_selection(
    candidates: tuple[AtcCode, ...], routes: list[str], route_map: RouteMap
) -> None:
    """Feature: drug-resolution, Property P24. Validates Req 5.1, 5.4 (owner decision DP20).

    For a product without a published code: with a mapped route every selected code is allowed
    for one of its routes, and with none allowed the ingredient is unmapped (no fallback);
    without a mapped route all codes are kept as `all_codes`; route order does not matter.
    """
    check = CombinationCheck(CombinationRules(frozenset(), frozenset(), frozenset(), "none"))
    s = tuple(
        a for a in candidates if is_ingredient_level(a.code) and not check.is_combination(a.code)
    )
    product = ProductContext(None, 1, tuple(routes))
    result = select_codes(candidates, product, check, route_map)
    reordered = select_codes(
        candidates, ProductContext(None, 1, tuple(reversed(routes))), check, route_map
    )
    assert result == reordered
    if not s:
        assert result.reason == "no_ingredient_atc"
    elif route_map.mapped(routes):
        allowed = [a for a in s if route_map.allowed(a.code, routes)]
        if allowed:
            assert result.selection == "route_group"
            assert list(result.codes) == allowed
        else:
            assert (result.codes, result.reason) == ((), "no_ingredient_atc_for_route")
    else:
        assert (result.codes, result.selection) == (s, "all_codes")


def test_rule_file_validation() -> None:
    ok = "pattern,kind,note\nC09B,combination_group,ACE inhibitor combinations\n"
    assert CombinationRules.from_csv_text(ok).groups == {"C09B"}
    for bad in (
        "pattern,kind\nC09B,combination_group\n",
        "pattern,kind,note\nC09B,group,x\n",
        "pattern,kind,note\nC0,combination_group,x\n",
        "pattern,kind,note\nC09BB3,combination_code,x\n",
        "pattern,kind,note\nC09B,combination_group,x\nC09B,combination_group,y\n",
    ):
        with pytest.raises(RulesFileError):
            CombinationRules.from_csv_text(bad)
    with pytest.raises(RulesFileError):
        RouteMap.from_csv_text("route,allow,note\nORAL,c0,x\n")


# --- examples with the reviewed rule files (data/, owner review 2026-11-07) -----------------

BETAMETHASONE = (
    "A07EA04 C05AA05 D07AC01 D07XC01 H02AB01 R01AD06 R03BA04 S01BA06 S02BA07 S03BA03".split()
)


def test_amlipin_and_topical_betamethasone_with_reviewed_files() -> None:
    """Validates Req 5.1, 5.2 (task 7.4). Wikidata codes as in the CC0 extract of 2026-11-07."""
    check = CombinationCheck(CombinationRules.load())
    routes = RouteMap.load()
    assert check.is_combination("C09BB03")
    assert not check.is_combination("C08CA01") and not check.is_combination("C09AA03")
    amlipin = ProductContext("C09BB03", 2)
    amlodipine = select_codes(ingredient_codes(["C08CA01"], [], check), amlipin, check, routes)
    lisinopril = select_codes(ingredient_codes(["C09AA03"], [], check), amlipin, check, routes)
    assert [a.code for a in amlodipine.codes] == ["C08CA01"]
    assert amlodipine.selection == "anatomical_group"
    assert [a.code for a in lisinopril.codes] == ["C09AA03"]
    assert lisinopril.selection == "therapeutic_group"

    s = ingredient_codes(BETAMETHASONE, [], check)
    assert "D07XC01" not in {a.code for a in s}  # D07X is a combination group
    cream = select_codes(s, ProductContext(None, 1, ("TOPICAL",)), check, routes)
    codes = {a.code for a in cream.codes}
    assert "D07AC01" in codes and "H02AB01" not in codes
    assert cream.selection == "route_group"
    tablet = select_codes(s, ProductContext(None, 1, ("ORAL",)), check, routes)
    assert "H02AB01" in {a.code for a in tablet.codes}
    assert not {a.code for a in tablet.codes} & {"D07AC01", "S01BA06"}


def test_reviewed_exceptions() -> None:
    """Rows verified against the WHOCC index on 2026-11-07 (owner condition)."""
    check = CombinationCheck(CombinationRules.load())
    assert not check.is_combination("J01CR04")  # sultamicillin: one substance
    assert not check.is_combination("G03CA57")  # conjugated estrogens: plain-estrogen group
    assert all(check.is_combination(c) for c in ("N04BA02", "N04BA05", "N04BA06", "N04BA07"))
    assert not check.is_combination("L01XX52")  # exception group L01XX
