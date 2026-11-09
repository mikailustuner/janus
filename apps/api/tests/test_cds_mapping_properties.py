"""Code mapping of the CDS Hooks service: P6 and examples (cds-hooks task 2). Pure."""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from hypothesis import given
from hypothesis import strategies as st

from janus.cds import mapping
from janus.cds.fhir import Coding
from janus.cds.mapping import ATC, NDC, RXNORM, IngredientItem, NotMapped, ProductItem
from janus.resolution.model import (
    AtcCodeOut,
    IngredientKey,
    ProductCandidate,
    ResolvedIngredient,
    SourceRef,
)

SRC = SourceRef(source_id="openfda_ndc", run_id="r", region="US", snapshot_date="2026-11-06")


def product(
    pid: int, qid: str | None, codes: Sequence[str], status: str = "mapped"
) -> ProductCandidate:
    ing = ResolvedIngredient(
        position=0,
        published_name="X",
        strength=None,
        status=status,  # pyright: ignore[reportArgumentType]
        reason=None,
        ingredient_key=None if qid is None else IngredientKey(qid=qid, label_en=None, labels={}),
        key_candidates=[],
        match_step=None,
        atc_codes=[AtcCodeOut(code=c, source=SRC) for c in codes],
        atc_selection="single_ingredient_product",
        rxcuis=[],
        rxcui_status=None,
        source=SRC,
    )
    return ProductCandidate(
        candidate_id=f"US:openfda_ndc:{pid}",
        region="US",
        matched_by="candidate_id",
        product_name=None,
        brand_name=None,
        generic_name=None,
        ingredient_text=None,
        published_atc=None,
        product_type=None,
        routes=["ORAL"],
        dosage_form=None,
        marketing_end_date=None,
        suspension_status=None,
        name_only=False,
        product_rxcuis=[],
        packages=[],
        ingredients=[ing],
        source=SRC,
    )


@dataclass
class FakeLookup:
    ndc: Mapping[str, list[ProductCandidate]] = field(
        default_factory=dict[str, list[ProductCandidate]]
    )
    rx_products: Mapping[str, list[ProductCandidate]] = field(
        default_factory=dict[str, list[ProductCandidate]]
    )
    rx_keys: Mapping[str, list[str]] = field(default_factory=dict[str, list[str]])
    atc_keys: Mapping[str, list[str]] = field(default_factory=dict[str, list[str]])
    codes: Mapping[str, list[str]] = field(default_factory=dict[str, list[str]])
    too_many: frozenset[str] = frozenset()
    combination: frozenset[str] = frozenset()
    calls: list[str] = field(default_factory=list[str])

    def products_by_ndc(self, code: str) -> Sequence[ProductCandidate]:
        self.calls.append(f"ndc:{code}")
        return self.ndc.get(code, [])

    def products_by_rxcui(self, code: str) -> Sequence[ProductCandidate] | None:
        self.calls.append(f"rxp:{code}")
        return None if code in self.too_many else self.rx_products.get(code, [])

    def qids_by_rxcui(self, code: str) -> Sequence[str]:
        self.calls.append(f"rxk:{code}")
        return self.rx_keys.get(code, [])

    def qids_by_atc(self, code: str) -> Sequence[str]:
        self.calls.append(f"atc:{code}")
        return self.atc_keys.get(code, [])

    def key_codes(self, qid: str) -> Sequence[str]:
        return self.codes.get(qid, [])

    def is_combination_code(self, code: str) -> bool:
        return code in self.combination


AMLO = product(1, "Q411347", ["C08CA01"])
AMLO2 = product(2, "Q411347", ["C08CA01"])
FURO = product(3, "Q900001", ["C03CA01"])
LOOKUP = FakeLookup(
    ndc={"11111-111-11": [AMLO]},
    rx_products={"308135": [AMLO2, AMLO], "999": [AMLO, FURO]},
    rx_keys={"17767": ["Q411347"], "555": ["Q1", "Q2"]},
    atc_keys={"C03CA01": ["Q900001"], "N02BE01": ["Q1", "Q2"], "S01ED01": ["Q_timolol"]},
    codes={"Q900001": ["C03CA01"], "Q_timolol": ["C07AA06", "S01ED01"]},
    combination=frozenset({"C09DA01"}),
    too_many=frozenset({"7777"}),
)


def test_each_system_maps() -> None:
    assert mapping.map_medicine([Coding(NDC, "11111-111-11")], LOOKUP) == ProductItem(
        "US:openfda_ndc:1", NDC
    )
    # Products with the same signature: the lowest candidate id.
    assert mapping.map_medicine([Coding(RXNORM, "308135")], LOOKUP) == ProductItem(
        "US:openfda_ndc:1", RXNORM
    )
    assert mapping.map_medicine([Coding(RXNORM, "17767")], LOOKUP) == IngredientItem(
        "Q411347", RXNORM
    )
    assert mapping.map_medicine([Coding(ATC, "C03CA01")], LOOKUP) == IngredientItem("Q900001", ATC)


def test_form_of_an_atc_code_is_not_lost() -> None:
    """Review P1: eye-drop timolol (S01ED01) must not reach the engine as oral timolol."""
    assert mapping.map_medicine([Coding(ATC, "S01ED01")], LOOKUP) == NotMapped("form_mismatch")


def test_too_many_products_are_not_compared() -> None:
    """Review P3: more products than can be compared is ambiguous, never a partial look."""
    assert mapping.map_medicine([Coding(RXNORM, "7777")], LOOKUP) == NotMapped("ambiguous_code")


def test_signature_ignores_ingredient_order() -> None:
    """Review P4: the same ingredients listed in another order read the same."""
    a = product(1, "Q1", ["C08CA01"])
    b = product(2, "Q2", ["C09AA03"])
    combo1 = a.model_copy(update={"ingredients": [a.ingredients[0], b.ingredients[0]]})
    combo2 = a.model_copy(update={"ingredients": [b.ingredients[0], a.ingredients[0]]})
    assert mapping.signature(combo1) == mapping.signature(combo2)
    other = a.ingredients[0].model_copy(update={"atc_selection": "all_codes"})
    assert mapping.signature(a) != mapping.signature(a.model_copy(update={"ingredients": [other]}))


def test_not_guessed_and_combination_never_matched() -> None:
    assert mapping.map_medicine([Coding(RXNORM, "999")], LOOKUP) == NotMapped("ambiguous_code")
    assert mapping.map_medicine([Coding(RXNORM, "555")], LOOKUP) == NotMapped("ambiguous_code")
    assert mapping.map_medicine([Coding(ATC, "N02BE01")], LOOKUP) == NotMapped("ambiguous_code")
    for code in ("C09DA01", "C08CA", "C08"):
        assert mapping.map_medicine([Coding(ATC, code)], LOOKUP) == NotMapped("combination_code")
    assert mapping.map_medicine([Coding(ATC, "A01AA01")], LOOKUP) == NotMapped("unmapped_code")
    assert mapping.map_medicine([Coding("http://snomed.info/sct", "1")], LOOKUP) == NotMapped(
        "no_supported_coding"
    )
    assert mapping.map_medicine([Coding(RXNORM, "12a")], LOOKUP) == NotMapped("no_supported_coding")


SYSTEM_CODES = st.sampled_from(
    [
        Coding(NDC, "11111-111-11"),
        Coding(NDC, "00000-000-00"),
        Coding(RXNORM, "308135"),
        Coding(RXNORM, "17767"),
        Coding(RXNORM, "999"),
        Coding(RXNORM, "1"),
        Coding(ATC, "C03CA01"),
        Coding(ATC, "C09DA01"),
        Coding(ATC, "N02BE01"),
        Coding(ATC, "S01ED01"),
        Coding(RXNORM, "7777"),
        Coding("http://snomed.info/sct", "123"),
    ]
)


@given(st.lists(SYSTEM_CODES, max_size=8), st.randoms(use_true_random=False))
def test_p6_system_order_and_stability(codings: list[Coding], rnd: random.Random) -> None:
    """P6: NDC before RxNorm before ATC; shuffling codings of other systems does not change the
    result; the result is the first coding (in that order) that maps."""
    result = mapping.map_medicine(codings, LOOKUP)
    by_system = {s: [c for c in codings if c.system == s] for s in mapping.ORDER}
    shuffled = list(codings)
    rnd.shuffle(shuffled)
    # Keep the order inside each system (it is meaningful), change it across systems.
    reordered: list[Coding] = []
    iters = {s: iter(by_system[s]) for s in mapping.ORDER}
    for c in shuffled:
        if c.system in iters:
            reordered.append(next(iters[c.system]))
        else:
            reordered.append(c)
    assert mapping.map_medicine(reordered, LOOKUP) == result
    expected: mapping.Mapped | None = None
    for c in mapping.supported(codings):
        m = mapping.map_coding(c, LOOKUP)
        if isinstance(m, ProductItem | IngredientItem):
            expected = m
            break
    if expected is not None:
        assert result == expected
    else:
        assert isinstance(result, NotMapped)


@given(st.text(alphabet="ABCDEFGHNXZ0123456789", min_size=1, max_size=8))
def test_p6_atc_only_ingredient_level_reaches_the_lookup(code: str) -> None:
    lookup = FakeLookup(atc_keys={code: ["Q1"]}, codes={"Q1": [code]})
    result = mapping.map_medicine([Coding(ATC, code)], lookup)
    if isinstance(result, IngredientItem):
        assert len(code) == 7
        assert lookup.calls == [f"atc:{code}"]
    else:
        assert all(not c.startswith("atc:") or len(code) == 7 for c in lookup.calls)


EMPTY = product(9, None, []).model_copy(update={"ingredients": []})


@given(st.lists(st.sampled_from([AMLO, AMLO2, FURO, EMPTY]), min_size=1, max_size=5))
def test_p6_products_are_picked_only_when_they_read_the_same(
    products: list[ProductCandidate],
) -> None:
    """Products without ingredients are left out; the rest must read the same."""
    picked = mapping.pick_product(products, RXNORM)
    informative = [p for p in products if p.ingredients]
    signatures = {mapping.signature(p) for p in informative}
    if not informative:
        assert picked is None
    elif len(signatures) == 1:
        assert picked == ProductItem(min(p.candidate_id for p in informative), RXNORM)
    else:
        assert picked == NotMapped("ambiguous_code")


def test_more_than_fifty_distinct_medicines_is_refused() -> None:
    from janus.cascades.schemas import MAX_ITEMS
    from janus.cds.fhir import Extracted, Medicine
    from janus.cds.service import TooManyMedicationsError, items_of

    codes = [f"A01AA{i:02d}" for i in range(MAX_ITEMS + 1)]
    lookup = FakeLookup(
        atc_keys={c: [f"Q{i + 1}"] for i, c in enumerate(codes)},
        codes={f"Q{i + 1}": [c] for i, c in enumerate(codes)},
    )
    meds = tuple(Medicine("active", (Coding(ATC, c),)) for c in codes)
    ok = Extracted(meds[:MAX_ITEMS] + meds[:3], frozenset({"draft"}), (), 0)
    items, origins, not_checked = items_of(ok, lookup)
    assert len(items) == MAX_ITEMS  # duplicates are one item
    assert origins[0] == frozenset({"active"}) and not_checked == 0
    try:
        items_of(Extracted(meds, frozenset({"draft"}), (), 0), lookup)
    except TooManyMedicationsError:
        pass
    else:
        raise AssertionError("expected TooManyMedicationsError")
