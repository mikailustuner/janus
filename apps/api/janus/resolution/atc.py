"""ATC codes for ingredients (drug-resolution design §5.4, §5.5; Req 5.1, 5.2). Pure.

- Only 7-character codes (`^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$`) can be ingredient codes.
- Combination codes are decided by one function, `CombinationCheck.reason`, from the reviewed
  rule file `data/atc_combination_rules.csv`, the WHO numbering convention and the codes
  observed on TİTCK multi-ingredient products.
- `select_codes` picks the codes of one ingredient that fit its product: the product's own code
  for a single-ingredient product, else by the product code's group, else by route (US,
  `data/route_atc_groups.csv`), else all codes (not confirmed).
- A combination code is never emitted; `assert_no_combination` fails loudly if one would be.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

INGREDIENT_LEVEL = re.compile(r"^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$")
ATC_PREFIX = re.compile(r"^[A-Z](?:[0-9]{2}(?:[A-Z](?:[A-Z](?:[0-9]{2})?)?)?)?$")
_THERAPEUTIC = re.compile(r"^[A-Z][0-9]{2}")
_ANATOMICAL = re.compile(r"^[A-Z]")

# WHO convention: combinations within one 4th-level group use 5th level 20 or 30; combinations
# outside it use the 50-series (and 70-series in some groups).
NUMBERING_SERIES: frozenset[int] = frozenset({20, 30, *range(50, 80)})

DATA_DIR = Path(__file__).resolve().parents[4] / "data"
COMBINATION_RULES_FILE = DATA_DIR / "atc_combination_rules.csv"
ROUTE_MAP_FILE = DATA_DIR / "route_atc_groups.csv"


def is_ingredient_level(code: str | None) -> bool:
    return code is not None and INGREDIENT_LEVEL.match(code) is not None


class RulesFileError(ValueError):
    """A curated rule file is malformed (names the row number, not its content)."""


class RuleKind(StrEnum):
    COMBINATION_GROUP = "combination_group"
    COMBINATION_CODE = "combination_code"
    EXCEPTION = "exception"


class CombinationReason(StrEnum):
    RULE_GROUP = "rule_group"
    RULE_CODE = "rule_code"
    NUMBERING = "numbering"
    OBSERVED = "observed_on_multi_ingredient_product"


def _rows(text: str, header: list[str]) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != header:
        raise RulesFileError(f"header must be {','.join(header)}")
    return list(reader)


@dataclass(frozen=True)
class CombinationRules:
    groups: frozenset[str]
    codes: frozenset[str]
    exceptions: frozenset[str]
    version: str

    @classmethod
    def from_csv_text(cls, text: str) -> CombinationRules:
        groups: set[str] = set()
        codes: set[str] = set()
        exceptions: set[str] = set()
        seen: set[str] = set()
        for n, row in enumerate(_rows(text, ["pattern", "kind", "note"]), start=2):
            pattern, kind = (row["pattern"] or "").strip(), (row["kind"] or "").strip()
            if pattern in seen:
                raise RulesFileError(f"row {n}: duplicate pattern")
            seen.add(pattern)
            if kind == RuleKind.COMBINATION_GROUP:
                if not (3 <= len(pattern) <= 5 and ATC_PREFIX.match(pattern)):
                    raise RulesFileError(f"row {n}: group must be a 3-5 character ATC prefix")
                groups.add(pattern)
            elif kind == RuleKind.COMBINATION_CODE:
                if not is_ingredient_level(pattern):
                    raise RulesFileError(f"row {n}: code must have 7 characters")
                codes.add(pattern)
            elif kind == RuleKind.EXCEPTION:
                if not (len(pattern) in (5, 7) and ATC_PREFIX.match(pattern)):
                    raise RulesFileError(f"row {n}: exception must be a 5- or 7-character code")
                exceptions.add(pattern)
            else:
                raise RulesFileError(f"row {n}: unknown kind")
        version = hashlib.sha256(text.encode()).hexdigest()
        return cls(frozenset(groups), frozenset(codes), frozenset(exceptions), version)

    @classmethod
    def load(cls, path: Path = COMBINATION_RULES_FILE) -> CombinationRules:
        return cls.from_csv_text(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class CombinationCheck:
    """Everything the combination decision depends on (design §5.4)."""

    rules: CombinationRules
    observed: frozenset[str] = frozenset()  # codes of TİTCK products with >= 2 distinct keys
    wikidata_codes: frozenset[str] = frozenset()  # codes of any Wikidata item

    def reason(self, code: str) -> CombinationReason | None:
        """Why `code` is a combination code, or None if it is not one."""
        if not is_ingredient_level(code):
            return None
        if code in self.rules.exceptions or code[:5] in self.rules.exceptions:
            return None
        if any(code.startswith(g) for g in self.rules.groups):
            return CombinationReason.RULE_GROUP
        if code in self.rules.codes:
            return CombinationReason.RULE_CODE
        if int(code[5:]) in NUMBERING_SERIES:
            return CombinationReason.NUMBERING
        if code in self.observed and code not in self.wikidata_codes:
            return CombinationReason.OBSERVED
        return None

    def is_combination(self, code: str) -> bool:
        return self.reason(code) is not None


class CombinationCodeLeakError(AssertionError):
    """A combination code was about to be emitted as an ingredient code (Req 5.2)."""


def assert_no_combination(codes: Iterable[str], check: CombinationCheck) -> None:
    for code in codes:
        if check.is_combination(code) or not is_ingredient_level(code):
            raise CombinationCodeLeakError("combination or non-ingredient code in output")


@dataclass(frozen=True)
class RouteMap:
    allow: Mapping[str, tuple[str, ...]]
    version: str

    @classmethod
    def from_csv_text(cls, text: str) -> RouteMap:
        allow: dict[str, tuple[str, ...]] = {}
        for n, row in enumerate(_rows(text, ["route", "allow", "note"]), start=2):
            route = (row["route"] or "").strip()
            prefixes = tuple(sorted({p.strip() for p in (row["allow"] or "").split(";")} - {""}))
            if not route or route in allow:
                raise RulesFileError(f"row {n}: empty or duplicate route")
            if not prefixes or not all(ATC_PREFIX.match(p) and len(p) <= 5 for p in prefixes):
                raise RulesFileError(f"row {n}: allow must list ATC prefixes of 1-5 characters")
            allow[route] = prefixes
        return cls(allow, hashlib.sha256(text.encode()).hexdigest())

    @classmethod
    def load(cls, path: Path = ROUTE_MAP_FILE) -> RouteMap:
        return cls.from_csv_text(path.read_text(encoding="utf-8"))

    def mapped(self, routes: Iterable[str]) -> tuple[str, ...]:
        return tuple(sorted({r for r in routes if r in self.allow}))

    def allowed(self, code: str, routes: Iterable[str]) -> bool:
        return any(code.startswith(p) for r in self.mapped(routes) for p in self.allow[r])


@dataclass(frozen=True)
class AtcCode:
    """One ingredient-level code and where it came from."""

    code: str
    source_id: str  # "wikidata" or the product's source id, e.g. "titck"
    product_ref: str | None = None  # the product it was observed on (TİTCK single-ingredient)

    def sort_key(self) -> tuple[str, str, str]:
        # Not dataclass ordering: product_ref may be None (P17 counterexample).
        return (self.code, self.source_id, self.product_ref or "")


def _sorted(codes: Iterable[AtcCode]) -> tuple[AtcCode, ...]:
    return tuple(sorted(set(codes), key=AtcCode.sort_key))


def ingredient_codes(
    wikidata: Iterable[str],
    observed_single: Iterable[tuple[str, str, str]],
    check: CombinationCheck,
) -> tuple[AtcCode, ...]:
    """Ingredient-level, non-combination codes of one ingredient key (design §5.4).

    `wikidata`: the item's codes; `observed_single`: (code, source id, product ref) from
    single-ingredient products mapped unambiguously to the item.
    """
    out = {AtcCode(c, "wikidata") for c in wikidata}
    out |= {AtcCode(c, s, ref) for c, s, ref in observed_single}
    return _sorted(
        a for a in out if is_ingredient_level(a.code) and not check.is_combination(a.code)
    )


Selection = Literal[
    "single_ingredient_product", "therapeutic_group", "anatomical_group", "route_group", "all_codes"
]
UnmappedReason = Literal["no_ingredient_atc", "no_ingredient_atc_for_route"]


@dataclass(frozen=True)
class ProductContext:
    published_atc: str | None
    ingredient_count: int
    routes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Selected:
    codes: tuple[AtcCode, ...]
    selection: Selection | None
    reason: UnmappedReason | None


def select_codes(
    candidates: tuple[AtcCode, ...],
    product: ProductContext,
    check: CombinationCheck,
    route_map: RouteMap,
) -> Selected:
    """Pick the ingredient's codes that fit the product (design §5.5)."""
    s = _sorted(
        a for a in candidates if is_ingredient_level(a.code) and not check.is_combination(a.code)
    )
    result = _select(s, product, check, route_map)
    assert_no_combination((a.code for a in result.codes), check)
    return result


def _select(
    s: tuple[AtcCode, ...], product: ProductContext, check: CombinationCheck, route_map: RouteMap
) -> Selected:
    if not s:
        return Selected((), None, "no_ingredient_atc")
    p = product.published_atc
    if p is not None:
        if product.ingredient_count == 1 and is_ingredient_level(p) and not check.is_combination(p):
            own = tuple(a for a in s if a.code == p)
            if own:
                return Selected(own, "single_ingredient_product", None)
        m = _THERAPEUTIC.match(p)
        if m:
            same = tuple(a for a in s if a.code.startswith(m.group(0)))
            if same:
                return Selected(same, "therapeutic_group", None)
        m = _ANATOMICAL.match(p)
        if m:
            same = tuple(a for a in s if a.code.startswith(m.group(0)))
            if same:
                return Selected(same, "anatomical_group", None)
        return Selected(s, "all_codes", None)
    if route_map.mapped(product.routes):
        allowed = tuple(a for a in s if route_map.allowed(a.code, product.routes))
        if allowed:
            return Selected(allowed, "route_group", None)
        return Selected((), None, "no_ingredient_atc_for_route")
    return Selected(s, "all_codes", None)
