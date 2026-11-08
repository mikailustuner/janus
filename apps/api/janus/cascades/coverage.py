"""PIPC coverage report (cascade-engine design §7, Req 8). Pure.

For every rule and role: how many TİTCK, US and EU (French and Spanish) products resolve to an
ingredient in the class, which class members have no product, and which unmapped or ambiguous
ingredient names probably belong to the class. Hints are a curation aid for the synonym file;
they never make findings.
Class membership uses `class_match`, the engine's only matcher.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from janus.cascades.model import AtcClass, RuleBase
from janus.cascades.patterns import class_match
from janus.resolution.names import fold, strip_salts

BUCKETS = ("TR", "US_RX", "US_OTC", "US_OTHER", "EU")
REGIONS = ("TR", "US", "EU")
MIN_PART_CHARS = 5  # a member name shorter than this is never matched as a part of another name
OTC_SHARE_MARK = 0.5
_WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class ProductRow:
    source_id: str
    product_id: int
    region: str
    product_type: str | None
    published_atc: str | None
    homeopathic: bool = False  # never counted and never hinted (owner decision 2026-11-07)


@dataclass(frozen=True)
class IngredientRow:
    source_id: str
    product_id: int
    published_name: str
    status: str  # mapped | ambiguous | unmapped
    qid: str | None
    key_candidates: tuple[str, ...]
    codes: tuple[str, ...]  # rule-input codes (mapped only)


@dataclass(frozen=True)
class KeyRow:
    qid: str
    label_en: str | None
    codes: tuple[str, ...]  # all ingredient-level codes of the key
    names: tuple[str, ...]  # folded labels and aliases


def name_key(text: str) -> str:
    """Folded, salt-stripped name: hints group salt forms of one name (drug-resolution §5.2)."""
    return strip_salts(fold(text))


def bucket(p: ProductRow) -> str:
    if p.region == "TR":
        return "TR"
    if p.region == "EU":
        return "EU"
    if p.product_type == "HUMAN PRESCRIPTION DRUG":
        return "US_RX"
    if p.product_type == "HUMAN OTC DRUG":
        return "US_OTC"
    return "US_OTHER"


def trigrams(text: str) -> frozenset[str]:
    """pg_trgm's trigrams: each word padded with two spaces in front and one behind."""
    out: set[str] = set()
    for w in _WORD.findall(name_key(text)):
        padded = f"  {w} "
        out.update(padded[i : i + 3] for i in range(len(padded) - 2))
    return frozenset(out)


def trigram_similarity(a: str, b: str) -> float:
    ta, tb = trigrams(a), trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class _SimilarityIndex:
    """Unmapped names as trigram sets with an inverted index; a lookup scans candidates only."""

    def __init__(self, names: Iterable[str]) -> None:
        self.grams: dict[str, frozenset[str]] = {}
        self.posting: dict[str, list[str]] = defaultdict(list)
        for n in sorted(set(names)):
            g = trigrams(n)
            if g:
                self.grams[n] = g
                for t in g:
                    self.posting[t].append(n)

    def similar(self, name: str, threshold: float) -> dict[str, float]:
        g = trigrams(name)
        if not g:
            return {}
        shared: Counter[str] = Counter()
        for t in g:
            shared.update(self.posting.get(t, ()))
        out: dict[str, float] = {}
        for cand, inter in shared.items():
            union = len(g) + len(self.grams[cand]) - inter
            sim = inter / union
            if sim >= threshold:
                out[cand] = sim
        return out


def tokens(text: str) -> tuple[str, ...]:
    """Folded, salt-stripped words of a name."""
    return tuple(_WORD.findall(name_key(text)))


def member_sequences(members: dict[str, KeyRow]) -> dict[tuple[str, ...], str]:
    """Word sequences of the class members' labels and aliases that belong to exactly one member
    and have at least `MIN_PART_CHARS` characters (design §16.4)."""
    owner: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for q, k in members.items():
        for n in k.names:
            seq = tokens(n)
            if seq and len(" ".join(seq)) >= MIN_PART_CHARS:
                owner[seq].add(q)
    return {seq: next(iter(qs)) for seq, qs in owner.items() if len(qs) == 1}


def part_member(name_tokens: tuple[str, ...], seqs: dict[tuple[str, ...], str]) -> str | None:
    """The member whose name is a contiguous whole-word part of the name: the longest match
    wins, the smallest key breaks ties; `None` if no member name is part of it."""
    best: tuple[int, str] | None = None
    n = len(name_tokens)
    for i in range(n):
        for j in range(i + 1, n + 1):
            q = seqs.get(name_tokens[i:j])
            if q is None:
                continue
            length = j - i
            if best is None or length > best[0] or (length == best[0] and q < best[1]):
                best = (length, q)
    return None if best is None else best[1]


def _class_report(
    cls: AtcClass,
    products: dict[tuple[str, int], ProductRow],
    ingredients: Sequence[IngredientRow],
    keys: Sequence[KeyRow],
    index: _SimilarityIndex,
    threshold: float,
    top: int,
) -> dict[str, Any]:
    active = cls.extension_ids
    members = {
        k.qid: k for k in keys if any(class_match(c, cls, active) is not None for c in k.codes)
    }
    extension_only = sorted(
        q for q, k in members.items() if not any(class_match(c, cls) is not None for c in k.codes)
    )
    by_bucket: dict[str, set[tuple[str, int]]] = {b: set() for b in BUCKETS}
    present: dict[str, set[str]] = {r: set() for r in REGIONS}
    seqs = member_sequences(members)
    part_cache: dict[str, str | None] = {}
    hint_rows: dict[str, dict[str, Any]] = {}

    def hint(name: str, kind: str, row: IngredientRow, member: str | None) -> None:
        h = hint_rows.setdefault(
            name,
            {
                "name": name,
                "kinds": set(),
                "members": set(),
                "products": {b: set() for b in BUCKETS},
            },
        )
        h["kinds"].add(kind)
        if member:
            h["members"].add(member)
        p = products.get((row.source_id, row.product_id))
        if p is not None:
            h["products"][bucket(p)].add((row.source_id, row.product_id))

    similar_cache: dict[str, dict[str, float]] = {}
    member_names = {q: k.names for q, k in members.items()}
    near: dict[str, str] = {}  # unmapped folded name -> best member qid
    best: dict[str, float] = {}
    for q, names in sorted(member_names.items()):
        for n in names:
            if n not in similar_cache:
                similar_cache[n] = index.similar(n, threshold)
            for cand, sim in similar_cache[n].items():
                if sim > best.get(cand, 0.0) or (sim == best.get(cand) and q < near[cand]):
                    best[cand], near[cand] = sim, q

    for row in ingredients:
        p = products.get((row.source_id, row.product_id))
        if p is None or p.homeopathic:
            continue
        if row.status == "mapped":
            if row.qid in members and any(
                class_match(c, cls, active) is not None for c in row.codes
            ):
                by_bucket[bucket(p)].add((row.source_id, row.product_id))
                present[p.region if p.region in ("TR", "EU") else "US"].add(row.qid)
            continue
        name = name_key(row.published_name)
        if p.region == "TR" and p.published_atc and class_match(p.published_atc, cls, active):
            hint(name, "titck_product_code", row, None)
        if row.status == "ambiguous":
            hit = sorted(set(row.key_candidates) & set(members))
            if hit:
                hint(name, "ambiguous_member", row, hit[0])
        elif name in near:
            hint(name, "similar_name", row, near[name])
        if row.status == "unmapped" and seqs:
            if name not in part_cache:
                part_cache[name] = part_member(tokens(row.published_name), seqs)
            owner = part_cache[name]
            if owner is not None:
                hint(name, "member_name_part", row, owner)

    hint_list: list[dict[str, Any]] = [
        {
            "name": h["name"],
            "kinds": sorted(h["kinds"]),
            "members": sorted(h["members"]),
            "products": {b: len(v) for b, v in h["products"].items()},
            "total": sum(len(v) for v in h["products"].values()),
        }
        for h in hint_rows.values()
    ]
    hints = sorted(hint_list, key=lambda h: (-int(h["total"]), str(h["name"])))
    rx, otc = len(by_bucket["US_RX"]), len(by_bucket["US_OTC"])
    return {
        "members": len(members),
        "extension_only_members": extension_only,
        "products": {b: len(v) for b, v in by_bucket.items()},
        "otc_share": None if rx + otc == 0 else round(otc / (rx + otc), 4),
        "members_without_products": {
            r: sorted(
                ({"qid": q, "label_en": members[q].label_en} for q in set(members) - present[r]),
                key=lambda m: str(m["qid"]),
            )
            for r in REGIONS
        },
        "hints_total": len(hints),
        "hints": hints[:top],
    }


def build_coverage(
    rb: RuleBase,
    products: Sequence[ProductRow],
    ingredients: Sequence[IngredientRow],
    keys: Sequence[KeyRow],
    threshold: float = 0.6,
    top: int = 50,
) -> dict[str, Any]:
    by_id = {(p.source_id, p.product_id): p for p in products}
    index = _SimilarityIndex(
        name_key(r.published_name) for r in ingredients if r.status == "unmapped"
    )
    # EU is judged only if the dataset holds EU products; otherwise "cannot fire" would say
    # nothing but "the EU sources are not loaded".
    regions: list[tuple[str, tuple[str, ...]]] = [("TR", ("TR",)), ("US", ("US_RX", "US_OTC"))]
    if any(p.region == "EU" for p in products):
        regions.append(("EU", ("EU",)))
    classes: dict[str, dict[str, Any]] = {}
    for cid in sorted(rb.classes):
        classes[cid] = _class_report(
            rb.classes[cid], by_id, ingredients, keys, index, threshold, top
        )
    rules: list[dict[str, Any]] = []
    for r in rb.rules:
        entry: dict[str, Any] = {
            "rule_id": r.rule_id,
            "drug_a": r.drug_a,
            "adverse_event": r.adverse_event,
            "drug_b": r.drug_b,
            "index_class": r.index_class,
            "marker_class": r.marker_class,
            "matchable": r.matchable,
            "unmatchable": list(r.unmatchable) if r.unmatchable else None,
        }
        cannot: list[str] = []
        for region, bs in regions:
            for cid in (r.index_class, r.marker_class):
                if cid is None or sum(classes[cid]["products"][b] for b in bs) == 0:
                    cannot.append(region)
                    break
        entry["cannot_fire_in"] = sorted(set(cannot))
        rules.append(entry)
    marker_ids = sorted({r.marker_class for r in rb.rules if r.marker_class})
    otc_list: list[dict[str, Any]] = [
        {
            "class_id": c,
            "otc_share": classes[c]["otc_share"],
            "us_otc_products": classes[c]["products"]["US_OTC"],
        }
        for c in marker_ids
        if (classes[c]["otc_share"] or 0) >= OTC_SHARE_MARK
    ]
    otc_markers = sorted(otc_list, key=lambda m: (-int(m["us_otc_products"]), str(m["class_id"])))
    return {
        "rule_base_version": rb.version,
        "similarity_threshold": threshold,
        "summary": {
            "rules": len(rb.rules),
            "not_matchable": [r["rule_id"] for r in rules if not r["matchable"]],
            "cannot_fire_in_tr": [r["rule_id"] for r in rules if "TR" in r["cannot_fire_in"]],
            "cannot_fire_in_us": [r["rule_id"] for r in rules if "US" in r["cannot_fire_in"]],
            "cannot_fire_in_eu": [r["rule_id"] for r in rules if "EU" in r["cannot_fire_in"]],
            "otc_marker_classes": otc_markers,
        },
        "rules": rules,
        "classes": classes,
    }
