"""Map FHIR medication codings to Janus list items (cds-hooks design §5). Pure.

The lookups (`Lookup`) read the current resolution dataset; this module decides only which
coding is used and whether the answer is unambiguous. Codes reach the engine solely through the
resolution layer (`rule_input`), never from the request: an ATC code from an order is used only
to find the one ingredient key that carries it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, Protocol

from janus.cds.fhir import Coding
from janus.resolution.atc import is_ingredient_level
from janus.resolution.model import ProductCandidate, rule_input

NDC: Final = "http://hl7.org/fhir/sid/ndc"
RXNORM: Final = "http://www.nlm.nih.gov/research/umls/rxnorm"
ATC: Final = "http://www.whocc.no/atc"
ORDER: Final = (NDC, RXNORM, ATC)  # most to least specific (design DP3)

_SHAPES: Final = {
    NDC: re.compile(r"^(?=.{1,13}$)[0-9]+(-[0-9]+){0,2}$"),
    RXNORM: re.compile(r"^[1-9][0-9]{0,9}$"),
    ATC: re.compile(r"^[A-Z]([0-9]{2}([A-Z]([A-Z]([0-9]{2})?)?)?)?$"),
}
# Products considered for one code; more are not compared (the answer is "ambiguous").
MAX_PRODUCTS: Final = 500

Reason = Literal[
    "no_supported_coding", "unmapped_code", "ambiguous_code", "combination_code", "form_mismatch"
]


@dataclass(frozen=True)
class ProductItem:
    candidate_id: str
    system: str


@dataclass(frozen=True)
class IngredientItem:
    qid: str
    system: str


@dataclass(frozen=True)
class NotMapped:
    reason: Reason


Mapped = ProductItem | IngredientItem | NotMapped


class Lookup(Protocol):
    """Read-only lookups over the current resolution dataset."""

    def products_by_ndc(self, code: str) -> Sequence[ProductCandidate]: ...
    # None: more than MAX_PRODUCTS products carry the code (not compared: "ambiguous").
    def products_by_rxcui(self, code: str) -> Sequence[ProductCandidate] | None: ...
    def qids_by_rxcui(self, code: str) -> Sequence[str]: ...
    def qids_by_atc(self, code: str) -> Sequence[str]: ...
    def key_codes(self, qid: str) -> Sequence[str]: ...
    def is_combination_code(self, code: str) -> bool: ...


def supported(codings: Sequence[Coding]) -> list[Coding]:
    """Codings of the three systems with a well-formed code, NDC first, then RxNorm, then ATC;
    the order within one system is kept."""
    kept = [c for c in codings if c.system in _SHAPES and _SHAPES[c.system].fullmatch(c.code)]
    return sorted(kept, key=lambda c: ORDER.index(c.system))


def signature(p: ProductCandidate) -> tuple[object, ...]:
    """What the engine reads from a product: per ingredient, status, key, rule codes and how the
    codes were selected (form-confirmed or not), as a sorted multiset so that the order in which
    a register lists the ingredients does not matter (pharmacologist review P4)."""
    return (
        p.homeopathic,
        tuple(
            sorted(
                (
                    i.status,
                    "" if i.ingredient_key is None else i.ingredient_key.qid,
                    rule_input(i),
                    i.atc_selection or "",
                )
                for i in p.ingredients
            )
        ),
    )


def pick_product(products: Sequence[ProductCandidate] | None, system: str) -> Mapped | None:
    """The product item when every product reads the same for the engine; None when nothing is
    found. Products without any published ingredient (kits, bulk entries) carry nothing for the
    engine and are left out of the comparison (live check 2026-11-09: 2 of 92 products of one
    furosemide RxCUI). `None` (too many products to compare) is ambiguous."""
    if products is None:
        return NotMapped("ambiguous_code")
    informative = [p for p in products if p.ingredients]
    if not informative:
        return None
    if len(informative) > MAX_PRODUCTS or len({signature(p) for p in informative}) != 1:
        return NotMapped("ambiguous_code")
    return ProductItem(min(p.candidate_id for p in informative), system)


def _one_key(qids: Sequence[str], system: str) -> Mapped | None:
    unique = sorted(set(qids))
    if not unique:
        return None
    if len(unique) > 1:
        return NotMapped("ambiguous_code")
    return IngredientItem(unique[0], system)


def _one_key_for_form(code: str, lookup: Lookup) -> Mapped | None:
    """An ATC code names a form (S01ED01 timolol eye drops), but an ingredient key carries all
    its forms' codes (C07AA06 oral timolol too) and the engine reads them all. When the key's
    codes span more than one anatomical group, the order's form cannot be kept: not guessed
    (pharmacologist review P1)."""
    found = _one_key(lookup.qids_by_atc(code), ATC)
    if not isinstance(found, IngredientItem):
        return found
    if len({c[0] for c in lookup.key_codes(found.qid)} | {code[0]}) > 1:
        return NotMapped("form_mismatch")
    return found


def map_coding(coding: Coding, lookup: Lookup) -> Mapped | None:
    """One coding → an item, a reason, or None (nothing found for this coding)."""
    if coding.system == NDC:
        return pick_product(lookup.products_by_ndc(coding.code), NDC)
    if coding.system == RXNORM:
        found = pick_product(lookup.products_by_rxcui(coding.code), RXNORM)
        return found if found is not None else _one_key(lookup.qids_by_rxcui(coding.code), RXNORM)
    if not is_ingredient_level(coding.code) or lookup.is_combination_code(coding.code):
        return NotMapped("combination_code")  # never matched (tech.md)
    return _one_key_for_form(coding.code, lookup)


def map_medicine(codings: Sequence[Coding], lookup: Lookup) -> Mapped:
    """The first supported coding that maps wins (NDC, RxNorm, ATC). Without a mapping, the
    most telling reason: ambiguous or combination before unmapped."""
    usable = supported(codings)
    if not usable:
        return NotMapped("no_supported_coding")
    reasons: list[Reason] = []
    for c in usable:
        m = map_coding(c, lookup)
        if isinstance(m, ProductItem | IngredientItem):
            return m
        if isinstance(m, NotMapped):
            reasons.append(m.reason)
    for reason in ("ambiguous_code", "form_mismatch", "combination_code"):
        if reason in reasons:
            return NotMapped(reason)
    return NotMapped("unmapped_code")
