"""Reference data and the result type shared by the two formulation resolvers (spec model-kit, milestone M3).

The resolvers A (`formulation_a`) and B (`formulation_b`) work independently on a study record; they share only this
module: the result type, the vocabulary and the table of marketed products (dosage form class of a brand name, from
the public US product directory, `data/modelkit/product_forms.csv`). Pure functions; no network. Research use only.
Not for clinical decisions.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from typing import Final

FORMULATIONS: Final = (
    "immediate_release",
    "solution",
    "modified_release",
    "fixed_dose_combination",
    "other_route",
    "unspecified",
)
ROUTES: Final = ("oral", "iv", "unknown")
RULE_VERSION: Final = "formulation-1"

# Evidence classes both resolvers use. "ir_weak" is a bare tablet or capsule word (weakest evidence for
# immediate release); "ir" is an explicit immediate-release word or a marketed product known as an
# immediate-release form. The final formulation of a set of evidence classes is decided by `decide`.
EVIDENCE: Final = ("fdc", "other_route", "mr", "special", "solution", "ir", "ir_weak")
_TO_FORMULATION: Final = {
    "fdc": "fixed_dose_combination",
    "other_route": "other_route",
    "mr": "modified_release",
    "solution": "solution",
    "ir": "immediate_release",
    "ir_weak": "immediate_release",
}


@dataclass(frozen=True, slots=True)
class Resolution:
    """What one resolver found for one value: a formulation and a route from the study record."""

    formulation: str = "unspecified"
    route: str = "unknown"
    why: str = ""  # short code of the deciding evidence, kept in the row note


UNRESOLVED: Final = Resolution()


def decide(classes: frozenset[str], routes: frozenset[str]) -> Resolution:
    """The formulation and route of the evidence classes and route words found in the evidence of one
    layer (shared rule, fixed in advance, see the pre-registration of M3).

    - nothing stated -> unspecified (never immediate release by assumption);
    - a fixed-dose-combination word wins, then a non-oral route word, then a modified-release word;
    - a bare tablet or capsule word loses against every other evidence;
    - intravenous administration is a solution; an explicit immediate-release word together with
      solution or intravenous evidence is a conflict -> unresolved;
    - oral and intravenous words in one layer are a conflict -> unresolved (route unknown)."""
    if "iv" in routes and "oral" in routes:
        return Resolution(why="conflict:iv_and_oral")
    route = "iv" if "iv" in routes else "oral" if "oral" in routes else "unknown"
    cls = set(classes)
    if "iv" in routes and not cls & {"fdc", "other_route", "mr"}:
        cls.add("solution")
    for winner in ("fdc", "other_route", "mr"):
        if winner in cls:
            return Resolution(
                _TO_FORMULATION[winner], "unknown" if winner == "other_route" else route, winner
            )
    if "special" in cls:  # chewable, dispersible, orally disintegrating: no class of the vocabulary
        return Resolution("unspecified", route, "special_oral_form")
    if "solution" in cls and "ir" in cls:
        return Resolution("unspecified", route, "conflict:solution_and_immediate_release")
    for winner in ("solution", "ir", "ir_weak"):
        if winner in cls:
            return Resolution(_TO_FORMULATION[winner], route, winner)
    return Resolution("unspecified", route, "")


@dataclass(frozen=True, slots=True)
class Product:
    brand: str  # normalised
    form_class: str  # a formulation of the vocabulary
    route: str  # oral, iv or ""


class BrandTable:
    """Marketed products of the pool drugs by drug key."""

    def __init__(self, products: dict[str, list[Product]]) -> None:
        self.by_drug = products

    @classmethod
    def from_csv(cls, text: str) -> BrandTable:
        out: dict[str, list[Product]] = defaultdict(list)
        for r in csv.DictReader(io.StringIO(text)):
            out[r["drug_key"]].append(Product(r["brand"], r["form_class"], r["route"]))
        return cls(dict(out))

    @classmethod
    def empty(cls) -> BrandTable:
        return cls({})

    def products(self, drug_key: str) -> list[Product]:
        return self.by_drug.get(drug_key, [])
