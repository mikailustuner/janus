"""Identity checks across sources and their classification (data-quality design §3-§5). Pure.

Inputs are counts reduced from the prepared resolution dataset (`observations`), never product
rows: a finding carries an ingredient key, a code, the codes it was compared with and how many
products showed it. No product name, barcode or national code reaches a finding, so nothing of
the TİTCK list can be republished from here (data-sources.md: TİTCK terms unclear).

Checks (an ATC "level-4 group" is the first five characters, e.g. `R06AE`):

* `exclusion_status`: each reviewed row of `data/atc_code_exclusions.csv` (a confirmed error),
  and whether its source still publishes the code (`persisting`) or no longer does
  (`resolved_upstream`: the row is stale and the resolution loader will refuse it).
* `item_group`: a regulator's code on a single-ingredient product (TİTCK, AEMPS CIMA) that shares
  no level-4 group with any code of the ingredient key's item (Wikidata, or a curated Janus key).
* `regulator_group`: a key with single-ingredient products in both regulators whose codes share
  no level-4 group between the two regulators.
* `substance_code_keys`: one substance code of a source (BDPM, CIMA) whose names map to two or
  more ingredient keys.

Classes: `confirmed_error` (a reviewed exclusion row), `benign_difference` (a deterministic rule
says the difference is expected, e.g. both regulators publish the code), `needs_pharmacist`
(everything else). The rules never call anything an error that a person has not confirmed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from janus.resolution.atc import is_ingredient_level

TITCK: Final = "titck"
CIMA: Final = "eu_es_cima"
BDPM: Final = "eu_fr_bdpm"
OPENFDA: Final = "openfda_ndc"
WIKIDATA: Final = "wikidata"
REGULATORS: Final = (TITCK, CIMA)
SUBSTANCE_SOURCES: Final = (BDPM, CIMA)
GROUP_CHARS: Final = 5  # ATC level 4 (chemical/therapeutic/pharmacological subgroup)
LEVEL2_CHARS: Final = 3


class Check(StrEnum):
    exclusion_status = "exclusion_status"
    item_group = "item_group"
    regulator_group = "regulator_group"
    substance_code_keys = "substance_code_keys"


class Klass(StrEnum):
    confirmed_error = "confirmed_error"
    needs_pharmacist = "needs_pharmacist"
    benign_difference = "benign_difference"


class Reason(StrEnum):
    # exclusion_status
    wrong_substance = "wrong_substance"
    old_code = "old_code"
    not_a_medicine = "not_a_medicine"
    still_published = "still_published"
    no_longer_published = "no_longer_published"
    # item_group
    code_of_other_substance = "code_of_other_substance"
    combination_code_on_single_ingredient_product = "combination_code_on_single_ingredient_product"
    both_regulators_publish_it = "both_regulators_publish_it"
    same_level2_group = "same_level2_group"
    group_differs = "group_differs"
    # regulator_group
    regulators_differ = "regulators_differ"
    item_agrees_with_titck = "item_agrees_with_titck"
    item_agrees_with_cima = "item_agrees_with_cima"
    # substance_code_keys
    one_substance_code_two_keys = "one_substance_code_two_keys"


class Upstream(StrEnum):
    persisting = "persisting"
    resolved_upstream = "resolved_upstream"


@dataclass(frozen=True)
class Observation:
    """A code seen on `products` single-ingredient products of `source` mapped to `key`."""

    source: str
    key: str
    code: str
    products: int


@dataclass(frozen=True)
class Item:
    """An ingredient key: its English label and the codes its item gives (before exclusions)."""

    key: str
    label: str | None
    codes: tuple[str, ...]
    origin: str = WIKIDATA  # wikidata | janus_curated


@dataclass(frozen=True)
class Exclusion:
    key: str
    code: str
    source: str  # wikidata | titck
    reason: str
    whocc_url: str
    whocc_date: str

    @property
    def triple(self) -> tuple[str, str, str]:
        return (self.key, self.code, self.source)


@dataclass(frozen=True)
class SubstanceCode:
    source: str
    code: str
    keys: tuple[str, ...]


@dataclass(frozen=True)
class Inputs:
    observations: tuple[Observation, ...]
    items: Mapping[str, Item]
    exclusions: tuple[Exclusion, ...] = ()
    substance_codes: tuple[SubstanceCode, ...] = ()
    combination_codes: frozenset[str] = frozenset()  # observed codes that are combination codes
    # key -> source -> number of products with the key as an ingredient (any number of them)
    presence: Mapping[str, Mapping[str, int]] = field(default_factory=dict[str, Mapping[str, int]])


@dataclass(frozen=True)
class Finding:
    check: Check
    source: str
    key: str
    code: str
    klass: Klass
    reasons: tuple[Reason, ...]
    compared_codes: tuple[str, ...] = ()
    products: int = 0
    other_keys: tuple[str, ...] = ()
    upstream: Upstream | None = None

    @property
    def id(self) -> str:
        """Stable across runs: the same question about the same key and code."""
        return f"{self.check.value}:{self.source}:{self.key}:{self.code}"


def group(code: str) -> str:
    return code[:GROUP_CHARS]


def shares_group(code: str, others: Iterable[str]) -> bool:
    return any(group(code) == group(o) for o in others)


def _sorted(findings: Iterable[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: f.id)


def exclusion_findings(inp: Inputs) -> list[Finding]:
    seen = {(o.key, o.code, o.source): o.products for o in inp.observations}
    out: list[Finding] = []
    for e in inp.exclusions:
        item = inp.items.get(e.key)
        if e.source == WIKIDATA:
            published = item is not None and e.code in item.codes
            products = 0
        else:
            products = seen.get(e.triple, 0)
            published = products > 0
        out.append(
            Finding(
                Check.exclusion_status,
                e.source,
                e.key,
                e.code,
                Klass.confirmed_error,
                (
                    Reason(e.reason),
                    Reason.still_published if published else Reason.no_longer_published,
                ),
                compared_codes=tuple(sorted(item.codes)) if item is not None else (),
                products=products,
                upstream=Upstream.persisting if published else Upstream.resolved_upstream,
            )
        )
    return _sorted(out)


def _holders(inp: Inputs, excluded: frozenset[tuple[str, str, str]]) -> dict[str, set[str]]:
    """code -> keys that carry it (item codes and regulator observations), minus exclusions."""
    holders: dict[str, set[str]] = defaultdict(set)
    for item in inp.items.values():
        for c in item.codes:
            if (item.key, c, WIKIDATA) not in excluded:
                holders[c].add(item.key)
    for o in inp.observations:
        if (o.key, o.code, o.source) not in excluded:
            holders[o.code].add(o.key)
    return holders


def item_group_findings(inp: Inputs) -> list[Finding]:
    excluded = frozenset(e.triple for e in inp.exclusions)
    holders = _holders(inp, excluded)
    by_source: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for o in inp.observations:
        by_source[o.source].add((o.key, o.code))
    out: list[Finding] = []
    for o in inp.observations:
        if o.source not in REGULATORS or (o.key, o.code, o.source) in excluded:
            continue
        item = inp.items.get(o.key)
        if item is None or not item.codes or shares_group(o.code, item.codes):
            continue
        others = tuple(sorted(holders.get(o.code, set()) - {o.key}))
        reasons: list[Reason] = []
        if others:
            reasons.append(Reason.code_of_other_substance)
        if o.code in inp.combination_codes:
            reasons.append(Reason.combination_code_on_single_ingredient_product)
        corroborated = any(
            (o.key, o.code) in by_source[s] for s in REGULATORS if s != o.source
        ) and not any((o.key, o.code, s) in excluded for s in REGULATORS)
        if corroborated:
            reasons.append(Reason.both_regulators_publish_it)
        if any(o.code[:LEVEL2_CHARS] == c[:LEVEL2_CHARS] for c in item.codes):
            reasons.append(Reason.same_level2_group)
        if not (others or o.code in inp.combination_codes or corroborated):
            reasons.append(Reason.group_differs)
        klass = (
            Klass.benign_difference
            if corroborated and not others and o.code not in inp.combination_codes
            else Klass.needs_pharmacist
        )
        out.append(
            Finding(
                Check.item_group,
                o.source,
                o.key,
                o.code,
                klass,
                tuple(reasons),
                compared_codes=tuple(sorted(item.codes)),
                products=o.products,
                other_keys=others,
            )
        )
    return _sorted(out)


def regulator_group_findings(inp: Inputs) -> list[Finding]:
    excluded = frozenset(e.triple for e in inp.exclusions)
    codes: dict[str, dict[str, set[str]]] = {s: defaultdict(set) for s in REGULATORS}
    products: dict[str, int] = defaultdict(int)
    for o in inp.observations:
        if o.source in REGULATORS and (o.key, o.code, o.source) not in excluded:
            codes[o.source][o.key].add(o.code)
            products[o.key] += o.products
    out: list[Finding] = []
    for key in sorted(set(codes[TITCK]) & set(codes[CIMA])):
        tr, es = codes[TITCK][key], codes[CIMA][key]
        if any(shares_group(c, es) for c in tr):
            continue
        item = inp.items.get(key)
        item_codes = item.codes if item is not None else ()
        reasons = [Reason.regulators_differ]
        if any(shares_group(c, item_codes) for c in tr):
            reasons.append(Reason.item_agrees_with_titck)
        if any(shares_group(c, item_codes) for c in es):
            reasons.append(Reason.item_agrees_with_cima)
        out.append(
            Finding(
                Check.regulator_group,
                f"{TITCK}+{CIMA}",
                key,
                "|".join(sorted(tr)),
                Klass.needs_pharmacist,
                tuple(reasons),
                compared_codes=tuple(sorted(es)),
                products=products[key],
            )
        )
    return _sorted(out)


def substance_code_findings(inp: Inputs) -> list[Finding]:
    out = [
        Finding(
            Check.substance_code_keys,
            s.source,
            "|".join(sorted(s.keys)),
            s.code,
            Klass.needs_pharmacist,
            (Reason.one_substance_code_two_keys,),
            other_keys=tuple(sorted(s.keys)),
        )
        for s in inp.substance_codes
        if len(set(s.keys)) >= 2
    ]
    return _sorted(out)


def run_checks(inp: Inputs) -> list[Finding]:
    """Every finding of one run, sorted by id (the order of the inputs does not matter)."""
    found = [
        *exclusion_findings(inp),
        *item_group_findings(inp),
        *regulator_group_findings(inp),
        *substance_code_findings(inp),
    ]
    ids = [f.id for f in found]
    if len(set(ids)) != len(ids):
        raise ValueError("two findings share an id")
    return _sorted(found)


# --- reduction of the prepared dataset to counts -----------------------------------------


@dataclass(frozen=True)
class ProductView:
    """What a check may know about a product: its source, published code and mapped keys."""

    source: str
    published_atc: str | None
    keys: tuple[str | None, ...]  # one entry per ingredient; None when not mapped


def reduce_products(
    products: Iterable[ProductView],
) -> tuple[tuple[Observation, ...], dict[str, dict[str, int]]]:
    """Observations (single-ingredient products with one mapped key and an ingredient-level
    published code) and the number of products of every key per source."""
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    presence: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for p in products:
        for k in {k for k in p.keys if k is not None}:
            presence[k][p.source] += 1
        code, keys = p.published_atc, p.keys
        if len(keys) == 1 and keys[0] is not None and code and is_ingredient_level(code):
            counts[(p.source, keys[0], code)] += 1
    obs = tuple(Observation(s, k, c, n) for (s, k, c), n in sorted(counts.items()))
    return obs, {k: dict(v) for k, v in sorted(presence.items())}


def substance_codes(
    lines: Iterable[tuple[str, str, str]], name_keys: Mapping[tuple[str, str], Sequence[str]]
) -> tuple[SubstanceCode, ...]:
    """(source, substance code, published name) lines and the keys each (source, name) maps
    to -> one entry per (source, code) with every key its names reach."""
    keys: dict[tuple[str, str], set[str]] = defaultdict(set)
    for source, code, name in lines:
        keys[(source, code)].update(name_keys.get((source, name), ()))
    return tuple(
        SubstanceCode(s, c, tuple(sorted(ks))) for (s, c), ks in sorted(keys.items()) if ks
    )
