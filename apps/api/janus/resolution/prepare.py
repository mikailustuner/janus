"""Load-time preparation of the resolution dataset (drug-resolution design §5). Pure.

Takes the rows of the `titck`, `us_ndc` and `wikidata_ingredients` artifacts and the curated
rule files, and decides, once for the whole dataset: each published ingredient's key, its
ingredient-level ATC codes, and which codes are combination codes. The request path only reads
the result. A final guard raises if any combination code would be emitted (Req 5.2).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from janus.resolution.anion_acid import AnionAcidTable
from janus.resolution.atc import (
    AtcCode,
    CombinationCheck,
    CombinationRules,
    ProductContext,
    RouteMap,
    Selection,
    assert_no_combination,
    ingredient_codes,
    is_ingredient_level,
    select_codes,
)
from janus.resolution.canonical import canonical_line
from janus.resolution.matching import IndexItem, Match, NameIndex, label_keys, map_name
from janus.resolution.name_lists import Lang
from janus.resolution.names import fold
from janus.resolution.ndc import canonical_package, canonical_product
from janus.resolution.prepare_eu import (
    ES_CIMA,
    FR_BDPM,
    EuProduct,
    bdpm_products,
    cima_products,
    is_homeopathic_name,
)

TITCK = "titck"
OPENFDA = "openfda_ndc"
WIKIDATA = "wikidata"
JANUS_CURATED = "janus_curated"  # curated Janus ingredient keys, data/janus_ingredients.csv
LANGS = ("en", "tr", "de", "fr", "es")
SEARCH_LANGS = ("en", "tr")  # name entries of every region (region "")
EU_SEARCH_LANGS = ("de", "fr", "es")  # name entries of region EU (DP39)
FINISHED_TYPES = frozenset(
    {
        "HUMAN PRESCRIPTION DRUG",
        "HUMAN OTC DRUG",
        "VACCINE",
        "PLASMA DERIVATIVE",
        "CELLULAR THERAPY",
        "STANDARDIZED ALLERGENIC",
        "NON-STANDARDIZED ALLERGENIC",
    }
)

Status = Literal["mapped", "ambiguous", "unmapped"]
Reason = Literal[
    "no_ingredient_key",
    "possible_unsplit_combination",
    "no_ingredient_atc",
    "no_ingredient_atc_for_route",
]
type Row = Mapping[str, Any]


@dataclass(frozen=True)
class PreparedIngredient:
    position: int
    published_name: str
    strength: str | None
    status: Status
    reason: Reason | None
    qid: str | None
    key_candidates: tuple[str, ...]
    match_step: str | None
    atc: tuple[AtcCode, ...]
    atc_selection: Selection | None
    rxcuis: tuple[str, ...]
    rxcui_status: Literal["from_wikidata", "not_in_wikidata"] | None

    def rule_input(self) -> tuple[str, ...]:
        """Ingredient-level codes for rule matching: unique, sorted, only when mapped."""
        return tuple(sorted({a.code for a in self.atc})) if self.status == "mapped" else ()


@dataclass(frozen=True)
class PreparedProduct:
    source_id: str
    product_id: int
    region: Literal["TR", "US", "EU"]
    product_name: str | None
    brand_name: str | None
    generic_name: str | None
    ingredient_text: str | None
    published_atc: str | None
    product_type: str | None
    routes: tuple[str, ...]
    dosage_form: str | None
    marketing_end_date: str | None
    suspension_status: int | None
    name_only: bool
    product_rxcuis: tuple[str, ...]
    codes: tuple[tuple[str, str, str], ...]  # (kind, code, as published)
    ingredients: tuple[PreparedIngredient, ...]
    status_published: tuple[str, ...] = ()  # EU: statuses exactly as published (display only)

    @property
    def candidate_id(self) -> str:
        return f"{self.region}:{self.source_id}:{self.product_id}"


@dataclass(frozen=True)
class IngredientRecord:
    qid: str
    labels: Mapping[str, str | None]
    ingredient_atc: tuple[AtcCode, ...]
    rxcuis: tuple[str, ...]


@dataclass(frozen=True, order=True)
class NameEntry:
    name_key: str
    kind: Literal["product", "ingredient"]
    region: str  # "TR", "US", "EU" or "" for ingredients (all regions)
    ref: str  # candidate id or QID
    display: str


@dataclass(frozen=True)
class PreparedDataset:
    products: tuple[PreparedProduct, ...]
    ingredients: Mapping[str, IngredientRecord]
    names: tuple[NameEntry, ...]
    combination_audit: Mapping[str, str]
    coverage: Mapping[str, Any]


def _ordered(rows: Iterable[Row]) -> list[Row]:
    """Rows in canonical order, so product ids do not depend on file row order (§4.3)."""
    return sorted(rows, key=lambda r: canonical_line(r).encode("utf-8"))


def _strs(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(str(v) for v in value if v is not None)  # pyright: ignore[reportUnknownVariableType]


def _opt_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _item_names(row: Row) -> dict[str, tuple[str, ...]]:
    out: dict[str, tuple[str, ...]] = {}
    for lang in LANGS:
        label = row.get(f"label_{lang}")
        names = ((label,) if label else ()) + _strs(row.get(f"aliases_{lang}"))
        if names:
            out[lang] = names
    return out


def index_item(row: Row) -> IndexItem:
    labels = {lang: str(row[f"label_{lang}"]) for lang in LANGS if row.get(f"label_{lang}")}
    aliases = {lang: _strs(row.get(f"aliases_{lang}")) for lang in LANGS}
    return IndexItem(str(row["qid"]), labels, {k: v for k, v in aliases.items() if v})


@dataclass
class _Raw:
    """A product before ingredient decisions: name strings and context."""

    product: dict[str, Any]
    names: list[tuple[str, str | None]]  # (published name, strength)
    lang: Lang
    matches: list[Match] = field(default_factory=list[Match])


def _titck_products(rows: Sequence[Row]) -> list[_Raw]:
    out: list[_Raw] = []
    for i, r in enumerate(_ordered(rows), start=1):
        barcode = r.get("barcode")
        name_only = bool(r.get("name_only")) or barcode is None
        codes = () if name_only else (("tr_barcode", str(barcode), str(barcode)),)
        out.append(
            _Raw(
                {
                    "source_id": TITCK,
                    "product_id": i,
                    "region": "TR",
                    "product_name": r.get("product_name"),
                    "brand_name": None,
                    "generic_name": None,
                    "ingredient_text": r.get("ingredient_text"),
                    "published_atc": r.get("atc_code"),
                    "product_type": None,
                    "routes": (),
                    "dosage_form": None,
                    "marketing_end_date": None,
                    "suspension_status": r.get("suspension_status"),
                    "name_only": name_only,
                    "product_rxcuis": (),
                    "codes": codes,
                },
                [(str(n), None) for n in _strs(r.get("ingredients"))],
                lang="tr",
            )
        )
    return out


def _openfda_products(rows: Sequence[Row], stats: Counter[str]) -> list[_Raw]:
    out: list[_Raw] = []
    for i, r in enumerate(_ordered(rows), start=1):
        codes: list[tuple[str, str, str]] = []
        product = str(r.get("product_ndc") or "")
        p9 = canonical_product(product)
        if p9 is None:
            stats["malformed_product_ndc"] += 1
        else:
            codes.append(("ndc_product9", p9, product))
        for pkg in _strs(r.get("package_ndcs")):
            p11 = canonical_package(pkg)
            if p11 is None:
                stats["malformed_package_ndc"] += 1
            else:
                codes.append(("ndc_package11", p11, pkg))
        active: list[Mapping[str, Any]] = list(r.get("active_ingredients") or [])
        ingredients: list[tuple[str, str | None]] = [
            (str(a.get("name") or ""), _opt_str(a.get("strength"))) for a in active
        ]
        out.append(
            _Raw(
                {
                    "source_id": OPENFDA,
                    "product_id": i,
                    "region": "US",
                    "product_name": r.get("brand_name") or r.get("generic_name"),
                    "brand_name": r.get("brand_name"),
                    "generic_name": r.get("generic_name"),
                    "ingredient_text": None,
                    "published_atc": None,
                    "product_type": r.get("product_type"),
                    "routes": _strs(r.get("route")),
                    "dosage_form": r.get("dosage_form"),
                    "marketing_end_date": r.get("marketing_end_date"),
                    "suspension_status": None,
                    "name_only": False,
                    "product_rxcuis": _strs(r.get("rxcuis")),
                    "codes": tuple(codes),
                },
                ingredients,
                lang="en",
            )
        )
    return out


def _eu_raws(products: Sequence[EuProduct], stats: Counter[str]) -> list[_Raw]:
    out: list[_Raw] = []
    for p in products:
        if p.product["source_id"] == FR_BDPM:
            stats["bdpm_links"] += p.stats.links
            stats["bdpm_superseded_sa_lines"] += p.stats.superseded_sa_lines
            stats["bdpm_multi_ft_links"] += p.stats.multi_ft_links
        out.append(_Raw(p.product, list(p.names), lang=p.lang))
    return out


def eligible_items(
    wikidata_rows: Sequence[Row],
    rules: CombinationRules,
    curated_rows: Sequence[Row] = (),
) -> tuple[dict[str, Row], frozenset[str], CombinationCheck]:
    """Eligible ingredient keys: items with >= 1 ingredient-level, non-combination code, with
    the curated Janus keys added. Returns (items by key, all Wikidata codes, base check).

    The observation rule only flags codes that no Wikidata item carries, so eligibility is the
    same under the full check computed later in `prepare_dataset`.
    """
    all_rows = [*wikidata_rows, *curated_rows]
    wikidata_codes = frozenset(c for r in all_rows for c in _strs(r.get("atc_codes")))
    base = CombinationCheck(rules, frozenset(), wikidata_codes)
    items: dict[str, Row] = {}
    for r in all_rows:
        codes = _strs(r.get("atc_codes"))
        if any(is_ingredient_level(c) and not base.is_combination(c) for c in codes):
            items[str(r["qid"])] = r
    return items, wikidata_codes, base


def build_name_index(
    wikidata_rows: Sequence[Row],
    rules: CombinationRules,
    synonyms: Iterable[tuple[str, str]] = (),
    curated_rows: Sequence[Row] = (),
    acid: AnionAcidTable | None = None,
) -> NameIndex:
    """The name index of `prepare_dataset` without the TİTCK bridge (steps 0-5): what any
    caller that maps non-Turkish names (e.g. the FAERS count builder) needs."""
    items, _codes, _base = eligible_items(wikidata_rows, rules, curated_rows)
    index = NameIndex.build((index_item(r) for r in items.values()), synonyms, acid=acid)
    index.acid.check_acids(lambda label: label_keys(index, label))
    return index


def prepare_dataset(
    titck_rows: Sequence[Row],
    us_rows: Sequence[Row],
    wikidata_rows: Sequence[Row],
    rules: CombinationRules,
    route_map: RouteMap,
    synonyms: Iterable[tuple[str, str]] = (),
    curated_rows: Sequence[Row] = (),
    acid: AnionAcidTable | None = None,
    *,
    fr_rows: Sequence[Row] | None = None,
    es_rows: Sequence[Row] | None = None,
) -> PreparedDataset:
    """`fr_rows` and `es_rows` are the BDPM and Nomenclátor artifacts; `None` means the source
    is not loaded (no section, no products).

    `curated_rows` are Janus ingredient keys (`J<n>`) in the shape of Wikidata rows, for
    substances that no Wikidata item in the extract covers with a code (owner decision,
    2026-11-07: dimenhydrinate). They behave like items; their codes cite `janus_curated`."""
    curated_keys = frozenset(str(r["qid"]) for r in curated_rows)
    items, wikidata_codes, base = eligible_items(wikidata_rows, rules, curated_rows)
    code2q: defaultdict[str, set[str]] = defaultdict(set)
    for qid, r in items.items():
        for c in _strs(r.get("atc_codes")):
            if is_ingredient_level(c) and not base.is_combination(c):
                code2q[c].add(qid)

    stats: Counter[str] = Counter()
    raws = _titck_products(titck_rows) + _openfda_products(us_rows, stats)
    if fr_rows is not None:
        raws += _eu_raws(bdpm_products(fr_rows), stats)
    if es_rows is not None:
        raws += _eu_raws(cima_products(es_rows), stats)

    # TİTCK ATC bridge (step 6): single-ingredient rows whose valid code belongs to one item.
    bridge: defaultdict[str, set[str]] = defaultdict(set)
    for raw in raws:
        p = raw.product["published_atc"]
        if raw.lang == "tr" and len(raw.names) == 1 and is_ingredient_level(p):
            if not base.is_combination(p) and len(code2q.get(p, ())) == 1:
                bridge[raw.names[0][0]].update(code2q[p])

    index = NameIndex.build((index_item(r) for r in items.values()), synonyms, bridge, acid)
    index.acid.check_acids(lambda label: label_keys(index, label))  # Req 12.7: refuse a bad row
    cache: dict[tuple[str, Lang], Match] = {}
    for raw in raws:
        for name, _ in raw.names:
            key = (name, raw.lang)
            if key not in cache:
                cache[key] = map_name(name, index, lang=raw.lang)
            raw.matches.append(cache[key])

    # Observation rule input: codes of TİTCK and Nomenclátor products with >= 2 distinct mapped
    # keys (DP34: the Nomenclátor feeds only this check, never an ingredient's codes).
    observed: set[str] = set()
    for raw in raws:
        p = raw.product["published_atc"]
        if raw.lang in ("tr", "es") and is_ingredient_level(p):
            keys = {m.keys[0] for m in raw.matches if m.status == "mapped"}
            if len(keys) >= 2:
                observed.add(p)
    check = CombinationCheck(rules, frozenset(observed), wikidata_codes)

    # Codes observed on TİTCK single-ingredient products, per key (lowest product id as ref).
    single: dict[str, dict[str, int]] = defaultdict(dict)
    for raw in raws:
        p = raw.product["published_atc"]
        if raw.lang == "tr" and len(raw.matches) == 1 and raw.matches[0].status == "mapped":
            if is_ingredient_level(p) and not check.is_combination(p):
                qid = raw.matches[0].keys[0]
                pid = raw.product["product_id"]
                single[qid][p] = min(single[qid].get(p, pid), pid)

    records: dict[str, IngredientRecord] = {}
    for qid, r in items.items():
        observed_single = [(c, TITCK, f"TR:{TITCK}:{pid}") for c, pid in single[qid].items()]
        records[qid] = IngredientRecord(
            qid,
            {lang: r.get(f"label_{lang}") for lang in LANGS},
            _one_per_code(
                ingredient_codes(
                    _strs(r.get("atc_codes")),
                    observed_single,
                    check,
                    JANUS_CURATED if qid in curated_keys else WIKIDATA,
                )
            ),
            _strs(r.get("rxcuis")),
        )

    products: list[PreparedProduct] = []
    for raw in raws:
        ctx = ProductContext(
            raw.product["published_atc"], len(raw.names), tuple(raw.product["routes"])
        )
        ings = tuple(
            _ingredient(i, name, strength, match, records, ctx, check, route_map, raw)
            for i, ((name, strength), match) in enumerate(zip(raw.names, raw.matches, strict=True))
        )
        for ing in ings:
            assert_no_combination(ing.rule_input(), check)
        products.append(PreparedProduct(**raw.product, ingredients=ings))

    names = _name_entries(products, items)
    audit = _audit(products, wikidata_codes, check)
    coverage = _coverage(products, records, items, stats)
    return PreparedDataset(tuple(products), records, names, audit, coverage)


def _one_per_code(codes: Iterable[AtcCode]) -> tuple[AtcCode, ...]:
    """One entry per code; a code observed on a TİTCK product (the regulator's list) is cited
    before the same code from Wikidata."""
    best: dict[str, AtcCode] = {}
    for a in sorted(
        codes, key=lambda a: (a.code, a.source_id in (WIKIDATA, JANUS_CURATED), a.sort_key())
    ):
        best.setdefault(a.code, a)
    return tuple(best[c] for c in sorted(best))


def _ingredient(
    position: int,
    name: str,
    strength: str | None,
    match: Match,
    records: Mapping[str, IngredientRecord],
    ctx: ProductContext,
    check: CombinationCheck,
    route_map: RouteMap,
    raw: _Raw,
) -> PreparedIngredient:
    def unmapped(
        status: Status, reason: Reason | None, keys: tuple[str, ...] = ()
    ) -> PreparedIngredient:
        return PreparedIngredient(
            position, name, strength, status, reason, None, keys, match.step, (), None, (), None
        )

    if match.status == "ambiguous":
        return unmapped("ambiguous", None, match.keys)
    if match.status == "unsplit":
        return unmapped("unmapped", "possible_unsplit_combination", match.keys)
    if match.status == "none":
        return unmapped("unmapped", "no_ingredient_key")
    qid = match.keys[0]
    record = records[qid]
    chosen = select_codes(record.ingredient_atc, ctx, check, route_map)
    codes = _one_per_code(chosen.codes)
    if chosen.selection == "single_ingredient_product":
        own = f"{raw.product['region']}:{raw.product['source_id']}:{raw.product['product_id']}"
        codes = (AtcCode(codes[0].code, raw.product["source_id"], own),)
    status: Status = "mapped" if codes else "unmapped"
    return PreparedIngredient(
        position,
        name,
        strength,
        status,
        chosen.reason,
        qid,
        (qid,),
        match.step,
        codes,
        chosen.selection,
        record.rxcuis,
        "from_wikidata" if record.rxcuis else "not_in_wikidata",
    )


def _name_entries(
    products: Sequence[PreparedProduct], items: Mapping[str, Row]
) -> tuple[NameEntry, ...]:
    out: set[NameEntry] = set()
    for p in products:
        if p.region == "US" and p.product_type not in FINISHED_TYPES:
            continue
        for display in sorted(n for n in (p.product_name, p.brand_name, p.generic_name) if n):
            key = fold(display)
            if key:
                out.add(NameEntry(key, "product", p.region, p.candidate_id, display))
        for ing in p.ingredients:
            if ing.status == "mapped" and ing.qid and p.region in ("TR", "EU"):
                key = fold(ing.published_name)
                if key:
                    # TİTCK's ingredient names are searchable everywhere (Phase 1); the French
                    # and Spanish ones only with region EU (DP39).
                    region = "" if p.region == "TR" else "EU"
                    out.add(NameEntry(key, "ingredient", region, ing.qid, ing.published_name))
    for qid, r in items.items():
        names = _item_names(r)
        for langs, region in ((SEARCH_LANGS, ""), (EU_SEARCH_LANGS, "EU")):
            for lang in langs:
                for display in names.get(lang, ()):
                    key = fold(display)
                    if key:
                        out.add(NameEntry(key, "ingredient", region, qid, display))
    return tuple(sorted(out))


def _audit(
    products: Sequence[PreparedProduct], wikidata_codes: frozenset[str], check: CombinationCheck
) -> dict[str, str]:
    seen = set(wikidata_codes) | {p.published_atc for p in products if p.published_atc}
    out: dict[str, str] = {}
    for code in sorted(c for c in seen if is_ingredient_level(c)):
        reason = check.reason(code)
        if reason is not None:
            out[code] = reason.value
    return out


def _source_coverage(products: Sequence[PreparedProduct]) -> dict[str, Any]:
    names: Counter[str] = Counter()
    status_of: dict[str, PreparedIngredient] = {}
    for p in products:
        for ing in p.ingredients:
            names[ing.published_name] += 1
            status_of.setdefault(ing.published_name, ing)
    occ = sum(names.values())
    by_step: Counter[str] = Counter()
    by_step_occ: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    selections: Counter[str] = Counter()
    for p in products:
        for ing in p.ingredients:
            if ing.status == "mapped":
                by_step_occ[str(ing.match_step)] += 1
                selections[str(ing.atc_selection)] += 1
            else:
                reasons[ing.reason or ing.status] += 1
    mapped_names = 0
    ambiguous = unsplit = 0
    for name, ing in status_of.items():
        del name
        if ing.status == "mapped":
            mapped_names += 1
            by_step[str(ing.match_step)] += 1
        elif ing.status == "ambiguous":
            ambiguous += 1
        elif ing.reason == "possible_unsplit_combination":
            unsplit += 1
    with_ings = [p for p in products if p.ingredients]
    full = [p for p in with_ings if all(i.status == "mapped" for i in p.ingredients)]
    multi = [p for p in with_ings if len(p.ingredients) >= 2]
    multi_full = [p for p in multi if all(i.status == "mapped" for i in p.ingredients)]
    unmapped_top = Counter(
        {n: c for n, c in names.items() if status_of[n].status != "mapped"}
    ).most_common(50)

    def share(a: int, b: int) -> float:
        return round(a / b, 4) if b else 0.0

    return {
        "products": len(products),
        "products_with_ingredients": len(with_ings),
        "products_fully_mapped": len(full),
        "products_fully_mapped_share": share(len(full), len(with_ings)),
        "multi_ingredient_products": len(multi),
        "multi_ingredient_fully_mapped": len(multi_full),
        "multi_ingredient_fully_mapped_share": share(len(multi_full), len(multi)),
        "distinct_names": len(names),
        "names_mapped": mapped_names,
        "names_mapped_share": share(mapped_names, len(names)),
        "occurrences": occ,
        "occurrences_mapped": sum(by_step_occ.values()),
        "occurrences_mapped_share": share(sum(by_step_occ.values()), occ),
        "names_by_step": dict(sorted(by_step.items())),
        "occurrences_by_step": dict(sorted(by_step_occ.items())),
        "ambiguous_names": ambiguous,
        "unsplit_names": unsplit,
        "not_mapped_occurrences_by_reason": dict(sorted(reasons.items())),
        "atc_selection": dict(sorted(selections.items())),
        "unmapped_top": unmapped_top,  # local report only: contains source names
    }


def _coverage(
    products: Sequence[PreparedProduct],
    records: Mapping[str, IngredientRecord],
    items: Mapping[str, Row],
    stats: Counter[str],
) -> dict[str, Any]:
    tr = [p for p in products if p.source_id == TITCK]
    us = [p for p in products if p.source_id == OPENFDA]
    # Agreement of Wikidata codes with TİTCK single-ingredient codes (5-character group).
    checked = agree = 0
    for p in tr:
        code = p.published_atc
        qid = p.ingredients[0].qid if len(p.ingredients) == 1 else None
        if qid and code is not None and is_ingredient_level(code):
            checked += 1
            agree += any(c[:5] == code[:5] for c in _strs(items[qid].get("atc_codes")))
    tr_cov = _source_coverage(tr)
    tr_cov["wikidata_group_agreement"] = {
        "checked": checked,
        "agree": agree,
        "share": round(agree / checked, 4) if checked else 0.0,
    }
    by_type: dict[str, Any] = {
        "all": _source_coverage(us),
        "rx": _source_coverage([p for p in us if p.product_type == "HUMAN PRESCRIPTION DRUG"]),
        "rx_otc": _source_coverage(
            [p for p in us if p.product_type in ("HUMAN PRESCRIPTION DRUG", "HUMAN OTC DRUG")]
        ),
    }
    out: dict[str, Any] = {
        TITCK: tr_cov,
        OPENFDA: {**by_type, "malformed_ndcs": dict(stats)},
        "ingredient_keys": len(records),
    }
    fr = [p for p in products if p.source_id == FR_BDPM]
    if fr:
        # Homeopathic presentations are findable by name but never counted (Req 12.10, 5.11).
        plain = [
            p for p in fr if not any(is_homeopathic_name(i.published_name) for i in p.ingredients)
        ]
        out[FR_BDPM] = {
            **_source_coverage(plain),
            "homeopathic_presentations_left_out": len(fr) - len(plain),
            "link_lines": {k: v for k, v in sorted(stats.items()) if k.startswith("bdpm_")},
        }
    es = [p for p in products if p.source_id == ES_CIMA]
    if es:
        out[ES_CIMA] = _source_coverage(es)
    return out
