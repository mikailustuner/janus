"""Resolution service (drug-resolution design §4). Reads only; no external calls (DP6).

The request path parses the input (pure), asks the region adapters for product keys, looks the
keys up in one read-only transaction and assembles a `ResolutionResult` with provenance for
every field. All mapping decisions were made at load time (`prepare.py`).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, cast

import psycopg

from janus.integrity.freshness import is_stale, parse_snapshot_date
from janus.passport.forms import FormTable
from janus.passport.strength import strength_code
from janus.regions.base import (
    Country,
    ProductKey,
    Region,
    RegionAdapter,
    gs1_prefix_region,
    no_open_database_country,
)
from janus.regions.eu_es.adapter import EsNomenclatorAdapter
from janus.regions.eu_fr.adapter import FrCip13Adapter
from janus.regions.eu_name.adapter import EuNameAdapter
from janus.regions.tr.adapter import TitckAdapter
from janus.regions.us.adapter import OpenFdaNdcAdapter
from janus.resolution import repository
from janus.resolution.gs1 import parse_element_string
from janus.resolution.model import (
    AtcCodeOut,
    IngredientCandidate,
    IngredientKey,
    Notice,
    Package,
    ProductCandidate,
    ResolutionResult,
    ResolvedIngredient,
    ScanInfo,
    SourceRef,
    StrengthCodeOut,
    is_homeopathic_product,
)
from janus.resolution.names import fold
from janus.resolution.ndc import parse_ndc_input
from janus.resolution.prepare_eu import is_homeopathic_name

# A new country is one adapter and one line here (Req 4.5, 10).
ADAPTERS: tuple[RegionAdapter, ...] = (
    TitckAdapter(),
    OpenFdaNdcAdapter(),
    FrCip13Adapter(),
    EsNomenclatorAdapter(),
    EuNameAdapter(),
)
WIKIDATA = "wikidata"
JANUS_CURATED = "janus_curated"  # curated Janus ingredient keys (J<n>)
# Staleness follows the shared freshness rule (twice the cadence, evidence-integrity DP17).
STALENESS_SOURCES = ("titck", "openfda_ndc", "eu_fr_bdpm", "eu_es_cima")
REGION_SOURCES: dict[Region, tuple[str, ...]] = {
    "TR": ("titck",),
    "US": ("openfda_ndc",),
    "EU": ("eu_fr_bdpm", "eu_es_cima"),
}
# The EU sources are optional at load time (Req 9.7); a default search or scan uses them only if
# they are loaded, while a request that names region EU needs both.
OPTIONAL_SOURCES: frozenset[str] = frozenset({"eu_fr_bdpm", "eu_es_cima"})
COUNTRY_OF_SOURCE: dict[str, Country] = {
    a.source_id: a.country for a in ADAPTERS if a.source_id is not None and a.country is not None
}
# Region hints for which no adapter exists yet (none today: FR, ES and DE have adapters).
NOT_YET: tuple[str, ...] = ()


class ResolutionUnavailableError(RuntimeError):
    """No current dataset, or a needed source is not loaded (Req 6.2). Never "not found"."""


def choose_adapters(
    adapters: Sequence[RegionAdapter], gtin14: str, override: Region | None
) -> list[RegionAdapter]:
    """With an override only that region's adapter; else every accepting adapter, hinted first."""
    if override is not None:
        return [a for a in adapters if a.region == override]
    accepting = [a for a in adapters if a.accepts_gtin(gtin14)]
    return sorted(
        accepting, key=lambda a: (not a.structural_hint(gtin14), a.region, a.country or "")
    )


@dataclass(frozen=True)
class RankedHit:
    kind: str
    ref: str
    score: float


def rank(key: str, hits: Iterable[repository.NameHit], limit: int) -> list[RankedHit]:
    """Pure ranking: exact, prefix, word prefix, similarity, products first; one entry per ref."""

    def sort_key(h: repository.NameHit) -> tuple[Any, ...]:
        words = h.name_key.split()
        return (
            h.name_key != key,
            not h.name_key.startswith(key),
            not any(w.startswith(key) for w in words),
            -round(h.similarity, 6),
            h.kind != "product",
            h.region,
            h.ref,
            h.name_key,
        )

    out: list[RankedHit] = []
    seen: set[tuple[str, str]] = set()
    for h in sorted(hits, key=sort_key):
        if (h.kind, h.ref) in seen:
            continue
        seen.add((h.kind, h.ref))
        out.append(RankedHit(h.kind, h.ref, round(h.similarity, 4)))
        if len(out) == limit:
            break
    return out


class _Builder:
    """Turns repository rows into result models with provenance."""

    def __init__(
        self, conn: psycopg.Connection, cur: repository.Current, forms: FormTable | None = None
    ) -> None:
        self.conn = conn
        self.cur = cur
        self.keys: dict[str, dict[str, Any]] = {}
        # Only a table the owner accepted names groups in answers (medication-passport task 4).
        self.forms = forms if forms is not None and forms.reviewed else None

    def _strength(
        self, source_id: str, strength: str | None, group: str | None
    ) -> StrengthCodeOut | None:
        code = strength_code(source_id, strength, group)
        return None if code is None else StrengthCodeOut(**vars(code))

    def source(self, source_id: str) -> SourceRef:
        s = self.cur.sources.get(source_id)
        if s is None:
            raise ResolutionUnavailableError(source_id)
        return SourceRef(
            source_id=s.source_id, run_id=s.run_id, region=s.region, snapshot_date=s.snapshot_date
        )

    def _key(self, qid: str | None) -> IngredientKey | None:
        if qid is None:
            return None
        rec = self.keys.get(qid)
        labels = cast(dict[str, str | None], rec["labels"]) if rec else {}
        return IngredientKey(
            qid=qid, label_en=labels.get("en"), labels=dict(sorted(labels.items()))
        )

    def _codes(self, raw: Iterable[dict[str, Any]]) -> list[AtcCodeOut]:
        return [
            AtcCodeOut(code=a["code"], source=self.source(a["source_id"]), product=a["product_ref"])
            for a in raw
        ]

    def products(
        self,
        refs: Sequence[repository.ProductRef],
        matched_by: str,
        scores: dict[Any, float] | None = None,
    ) -> list[ProductCandidate]:
        rows = repository.products(self.conn, self.cur.dataset_id, refs)
        qids = {i["qid"] for r in rows for i in r.ingredients if i["qid"]}
        self.keys.update(repository.ingredients(self.conn, self.cur.dataset_id, qids))
        out: list[ProductCandidate] = []
        for r in rows:
            f = r.fields
            src = self.source(r.source_id)
            cid = f"{f['region']}:{r.source_id}:{r.product_id}"
            group = (
                None
                if self.forms is None
                else self.forms.group(r.source_id, f["dosage_form"], f["routes"])
            )
            out.append(
                ProductCandidate(
                    candidate_id=cid,
                    region=f["region"],
                    country=COUNTRY_OF_SOURCE.get(r.source_id),
                    matched_by=matched_by,  # pyright: ignore[reportArgumentType]
                    score=(scores or {}).get(cid),
                    product_name=f["product_name"],
                    brand_name=f["brand_name"],
                    generic_name=f["generic_name"],
                    ingredient_text=f["ingredient_text"],
                    published_atc=f["published_atc"],
                    product_type=f["product_type"],
                    routes=list(f["routes"]),
                    dosage_form=f["dosage_form"],
                    marketing_end_date=f["marketing_end_date"],
                    suspension_status=f["suspension_status"],
                    name_only=f["name_only"],
                    homeopathic=is_homeopathic_product(i["strength"] for i in r.ingredients)
                    or (
                        f["region"] == "EU"
                        and any(is_homeopathic_name(i["published_name"]) for i in r.ingredients)
                    ),
                    status_published=list(f["status_published"]),
                    product_rxcuis=list(f["product_rxcuis"]),
                    packages=[Package(ndc_published=p, ndc11=c) for p, c in r.packages],
                    ingredients=[
                        ResolvedIngredient(
                            position=i["position"],
                            published_name=i["published_name"],
                            strength=i["strength"],
                            status=i["status"],
                            reason=i["reason"],
                            ingredient_key=self._key(i["qid"]),
                            key_candidates=list(i["key_candidates"]),
                            match_step=i["match_step"],
                            atc_codes=self._codes(i["atc"]),
                            atc_selection=i["atc_selection"],
                            rxcuis=list(i["rxcuis"]),
                            rxcui_status=i["rxcui_status"],
                            source=src,
                            strength_code=self._strength(r.source_id, i["strength"], group),
                        )
                        for i in r.ingredients
                    ],
                    source=src,
                    dose_form_group=group,
                )
            )
        return out

    def ingredient_candidates(
        self, qids: Sequence[str], scores: dict[str, float]
    ) -> list[IngredientCandidate]:
        self.keys.update(repository.ingredients(self.conn, self.cur.dataset_id, qids))
        out: list[IngredientCandidate] = []
        for qid in qids:
            rec = self.keys.get(qid)
            if rec is None:
                continue
            key = self._key(qid)
            assert key is not None  # noqa: S101 (rec exists, so the key does)
            codes = self._codes(rec["ingredient_atc"])
            out.append(
                IngredientCandidate(
                    score=scores.get(qid),
                    ingredient_key=key,
                    atc_codes=codes,
                    atc_selection="all_codes" if codes else None,
                    rxcuis=rec["rxcuis"],
                    rxcui_status="from_wikidata" if rec["rxcuis"] else "not_in_wikidata",
                    source=self.source(JANUS_CURATED if qid.startswith("J") else WIKIDATA),
                )
            )
        return out


def _current(conn: psycopg.Connection, needed: Iterable[str]) -> repository.Current:
    cur = repository.current(conn)
    if cur is None or any(s not in cur.sources for s in (*needed, WIKIDATA)):
        raise ResolutionUnavailableError("dataset not loaded")
    return cur


def _notices(
    b: _Builder,
    sources: Sequence[str],
    candidates: Sequence[ProductCandidate | IngredientCandidate],
    today: dt.date,
) -> list[Notice]:
    out: list[Notice] = []
    for s in sources:
        if s in STALENESS_SOURCES:
            row = b.cur.sources[s]
            snap = parse_snapshot_date(row.snapshot_date)
            # A missing cadence cannot be judged, so the notice is shown.
            if row.cadence_days is None or is_stale(snap, today, row.cadence_days):
                out.append(
                    Notice(code="source_may_be_outdated", source_id=s, date=snap.isoformat())
                )
    if any(
        i.status != "mapped"
        for c in candidates
        if isinstance(c, ProductCandidate)
        for i in c.ingredients
    ):
        out.append(Notice(code="unmapped_ingredients"))
    return out


def _result(
    b: _Builder,
    regions: Sequence[Region],
    sources: Iterable[str],
    candidates: Sequence[ProductCandidate | IngredientCandidate],
    today: dt.date,
    scan: ScanInfo | None = None,
    extra: Sequence[Notice] = (),
) -> ResolutionResult:
    searched = sorted({*sources, WIKIDATA})
    return ResolutionResult(
        dataset_version=b.cur.dataset_id,
        regions_searched=list(dict.fromkeys(regions)),
        sources=[b.source(s) for s in searched],
        scan=scan,
        notices=[*extra, *_notices(b, searched, candidates, today)],
        candidates=list(candidates),
    )


def _needs_source(a: RegionAdapter, gtin14: str, override: Region | None) -> bool:
    """Whether a missing source of this adapter is an error (design §13.2). An EU adapter that
    merely accepts the code (Spain accepts any valid GTIN) is asked only if its source is loaded."""
    return override is not None or a.region != "EU" or a.structural_hint(gtin14)


def resolve_scan(
    conn: psycopg.Connection,
    content: str,
    override: Region | None,
    today: dt.date,
    adapters: Sequence[RegionAdapter] = ADAPTERS,
    *,
    forms: FormTable | None = None,
) -> ResolutionResult:
    data = parse_element_string(content, today)  # Gs1Error → 422 in the router
    chosen = choose_adapters(adapters, data.gtin14, override)
    cur = _current(
        conn,
        [
            a.source_id
            for a in chosen
            if a.source_id is not None and _needs_source(a, data.gtin14, override)
        ],
    )
    searched = [a for a in chosen if a.source_id is not None and a.source_id in cur.sources]
    b = _Builder(conn, cur, forms)
    hint = gs1_prefix_region(data.gtin14)
    extra: list[Notice] = []
    if override is None and hint in NOT_YET:
        extra.append(Notice(code="region_adapter_not_available", region=hint))
    country = no_open_database_country(data.gtin14)
    if (
        country is not None
        and override in (None, "EU")
        and any(a.source_id is None and a.accepts_gtin(data.gtin14) for a in chosen)
    ):
        # No open product-code database for this country: no candidate, the client offers name
        # search and on-device text recognition (Req 4.3).
        extra.append(Notice(code="no_open_product_database", region="EU", country=country))
    candidates: list[ProductCandidate | IngredientCandidate] = []
    for a in searched:
        # Key groups in order of trust: the first group that finds a product wins (design §13.1).
        for group in a.key_groups(data):
            refs: list[repository.ProductRef] = []
            by_kind: dict[str, list[str]] = {}
            for k in group.keys:
                by_kind.setdefault(k.kind, []).append(k.code)
            for kind, codes in sorted(by_kind.items()):
                refs += [
                    r
                    for r in repository.refs_by_codes(conn, cur.dataset_id, kind, codes)
                    if r[0] == a.source_id
                ]
            if refs:
                candidates += b.products(sorted(set(refs)), group.matched_by)
                break
    scan = ScanInfo(
        gtin=data.gtin14,
        expiry=data.expiry,
        expiry_status=data.expiry_status,
        serial_present=data.serial_present,
        lot_present=data.lot_present,
        structural_hint=hint,
    )
    return _result(
        b,
        [a.region for a in searched],
        [a.source_id for a in searched if a.source_id is not None],
        candidates,
        today,
        scan,
        extra,
    )


def resolve_ndc(
    conn: psycopg.Connection, ndc: str, today: dt.date, *, forms: FormTable | None = None
) -> ResolutionResult:
    keys = sorted(ProductKey(k.kind, k.code) for k in parse_ndc_input(ndc))  # NdcError → 422
    cur = _current(conn, ["openfda_ndc"])
    b = _Builder(conn, cur, forms)
    refs: set[repository.ProductRef] = set()
    for kind in sorted({k.kind for k in keys}):
        refs |= set(
            repository.refs_by_codes(
                conn, cur.dataset_id, kind, [k.code for k in keys if k.kind == kind]
            )
        )
    return _result(b, ["US"], ["openfda_ndc"], b.products(sorted(refs), "ndc"), today)


def search(
    conn: psycopg.Connection,
    query: str,
    region: Region | None,
    limit: int,
    today: dt.date,
    *,
    forms: FormTable | None = None,
) -> ResolutionResult:
    key = fold(query)
    if len(key) < 2:
        raise ValueError("query_too_short")
    # Without a region: Türkiye and the US always, the EU sources if the dataset holds them. A
    # request that names a region needs all of that region's sources (Req 6.2).
    wanted: list[Region] = [region] if region else ["TR", "US", "EU"]
    required = REGION_SOURCES[region] if region else (*REGION_SOURCES["TR"], *REGION_SOURCES["US"])
    cur = _current(conn, required)
    sources = [s for r in wanted for s in REGION_SOURCES[r] if s in cur.sources]
    regions: list[Region] = [r for r in wanted if any(s in sources for s in REGION_SOURCES[r])]
    b = _Builder(conn, cur, forms)
    hits = rank(key, repository.search_names(conn, cur.dataset_id, key, wanted), limit)
    candidates: list[ProductCandidate | IngredientCandidate] = []
    for h in hits:  # keep rank order
        if h.kind == "product":
            region_s, source_id, pid = h.ref.split(":")
            del region_s
            candidates += b.products([(source_id, int(pid))], "name", {h.ref: h.score})
        else:
            candidates += b.ingredient_candidates([h.ref], {h.ref: h.score})
    return _result(b, regions, sources, candidates, today)


def resolve_products(
    conn: psycopg.Connection,
    candidate_ids: Sequence[str],
    today: dt.date,
    *,
    forms: FormTable | None = None,
) -> ResolutionResult:
    refs: list[repository.ProductRef] = []
    regions: list[Region] = []
    for cid in dict.fromkeys(candidate_ids):
        region, source_id, pid = cid.split(":")
        if source_id not in REGION_SOURCES.get(cast(Region, region), ()):
            continue
        refs.append((source_id, int(pid)))
        if region not in regions:
            regions.append(cast(Region, region))
    regions.sort()
    sources = sorted({source_id for source_id, _ in refs})
    cur = _current(conn, sources)
    b = _Builder(conn, cur, forms)
    found = b.products(refs, "candidate_id")
    extra = (
        []
        if len(found) == len(refs) == len(set(candidate_ids))
        else [Notice(code="unknown_candidate_ids")]
    )
    return _result(b, regions, sources, found, today, extra=extra)


# --- Read-only helpers for the cascade engine (cascade-engine design §6.2) -----------------------


@dataclass(frozen=True)
class RuleInputs:
    """Products and ingredients of the current dataset, for `janus.cascades.inputs`."""

    dataset_id: str
    products: dict[str, ProductCandidate]  # by candidate id; unknown ids are absent
    ingredients: dict[str, IngredientCandidate]  # by QID; unknown QIDs are absent
    combination_codes: frozenset[str]
    # Reviewed (key, combination code) pairs: the only combination codes the engine may accept.
    component_pairs: frozenset[tuple[str, str]] = frozenset()


def current_dataset_id(conn: psycopg.Connection) -> str | None:
    cur = repository.current(conn)
    return None if cur is None else cur.dataset_id


def rule_inputs(
    conn: psycopg.Connection, candidate_ids: Sequence[str], qids: Sequence[str]
) -> RuleInputs:
    """Re-resolve list items in the request's read-only transaction (codes via `rule_input`).

    Needs the sources of the regions that occur in `candidate_ids` (plus Wikidata): a list of
    Turkish boxes works on a dataset without EU data (Req 9.7); 503 still means "a needed source
    is missing"."""
    refs: list[repository.ProductRef] = []
    for cid in dict.fromkeys(candidate_ids):
        region, source_id, pid = cid.split(":")
        if source_id in REGION_SOURCES.get(cast(Region, region), ()):
            refs.append((source_id, int(pid)))
    cur = _current(conn, sorted({source_id for source_id, _ in refs}))
    b = _Builder(conn, cur)
    products = {p.candidate_id: p for p in b.products(refs, "candidate_id")}
    wanted = sorted(set(qids))
    ingredients = {c.ingredient_key.qid: c for c in b.ingredient_candidates(wanted, {})}
    return RuleInputs(
        cur.dataset_id,
        products,
        ingredients,
        repository.combination_codes(conn, cur.dataset_id),
        repository.component_pairs(conn, cur.dataset_id),
    )
