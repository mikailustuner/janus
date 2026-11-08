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
from janus.regions.base import ProductKey, Region, RegionAdapter, gs1_prefix_region
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
    is_homeopathic_product,
)
from janus.resolution.names import fold
from janus.resolution.ndc import parse_ndc_input

ADAPTERS: tuple[RegionAdapter, ...] = (TitckAdapter(), OpenFdaNdcAdapter())
WIKIDATA = "wikidata"
JANUS_CURATED = "janus_curated"  # curated Janus ingredient keys (J<n>)
# Staleness follows the shared freshness rule (twice the cadence, evidence-integrity DP17).
STALENESS_SOURCES = ("titck", "openfda_ndc")
REGION_SOURCES: dict[Region, str] = {"TR": "titck", "US": "openfda_ndc"}
NOT_YET: tuple[str, ...] = ("FR", "ES", "DE")  # Phase 2 adapters (eu_fr, eu_es, eu_name)


class ResolutionUnavailableError(RuntimeError):
    """No current dataset, or a needed source is not loaded (Req 6.2). Never "not found"."""


def choose_adapters(
    adapters: Sequence[RegionAdapter], gtin14: str, override: Region | None
) -> list[RegionAdapter]:
    """With an override only that region's adapter; else every accepting adapter, hinted first."""
    if override is not None:
        return [a for a in adapters if a.region == override]
    accepting = [a for a in adapters if a.accepts_gtin(gtin14)]
    return sorted(accepting, key=lambda a: (not a.structural_hint(gtin14), a.region))


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

    def __init__(self, conn: psycopg.Connection, cur: repository.Current) -> None:
        self.conn = conn
        self.cur = cur
        self.keys: dict[str, dict[str, Any]] = {}

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
            out.append(
                ProductCandidate(
                    candidate_id=cid,
                    region=f["region"],
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
                    homeopathic=is_homeopathic_product(i["strength"] for i in r.ingredients),
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
                        )
                        for i in r.ingredients
                    ],
                    source=src,
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
    candidates: Sequence[ProductCandidate | IngredientCandidate],
    today: dt.date,
    scan: ScanInfo | None = None,
    extra: Sequence[Notice] = (),
) -> ResolutionResult:
    sources = sorted({REGION_SOURCES[r] for r in regions} | {WIKIDATA})
    return ResolutionResult(
        dataset_version=b.cur.dataset_id,
        regions_searched=list(regions),
        sources=[b.source(s) for s in sources],
        scan=scan,
        notices=[*extra, *_notices(b, sources, candidates, today)],
        candidates=list(candidates),
    )


def resolve_scan(
    conn: psycopg.Connection,
    content: str,
    override: Region | None,
    today: dt.date,
    adapters: Sequence[RegionAdapter] = ADAPTERS,
) -> ResolutionResult:
    data = parse_element_string(content, today)  # Gs1Error → 422 in the router
    chosen = choose_adapters(adapters, data.gtin14, override)
    cur = _current(conn, [a.source_id for a in chosen if a.source_id is not None])
    b = _Builder(conn, cur)
    hint = gs1_prefix_region(data.gtin14)
    extra: list[Notice] = []
    if override is None and hint in NOT_YET:
        extra.append(Notice(code="region_adapter_not_available", region=hint))
    candidates: list[ProductCandidate | IngredientCandidate] = []
    for a in chosen:
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
    return _result(b, [a.region for a in chosen], candidates, today, scan, extra)


def resolve_ndc(conn: psycopg.Connection, ndc: str, today: dt.date) -> ResolutionResult:
    keys = sorted(ProductKey(k.kind, k.code) for k in parse_ndc_input(ndc))  # NdcError → 422
    cur = _current(conn, ["openfda_ndc"])
    b = _Builder(conn, cur)
    refs: set[repository.ProductRef] = set()
    for kind in sorted({k.kind for k in keys}):
        refs |= set(
            repository.refs_by_codes(
                conn, cur.dataset_id, kind, [k.code for k in keys if k.kind == kind]
            )
        )
    return _result(b, ["US"], b.products(sorted(refs), "ndc"), today)


def search(
    conn: psycopg.Connection, query: str, region: Region | None, limit: int, today: dt.date
) -> ResolutionResult:
    key = fold(query)
    if len(key) < 2:
        raise ValueError("query_too_short")
    regions: list[Region] = [region] if region else ["TR", "US"]
    cur = _current(conn, [REGION_SOURCES[r] for r in regions])
    b = _Builder(conn, cur)
    hits = rank(key, repository.search_names(conn, cur.dataset_id, key, regions), limit)
    candidates: list[ProductCandidate | IngredientCandidate] = []
    for h in hits:  # keep rank order
        if h.kind == "product":
            region_s, source_id, pid = h.ref.split(":")
            del region_s
            candidates += b.products([(source_id, int(pid))], "name", {h.ref: h.score})
        else:
            candidates += b.ingredient_candidates([h.ref], {h.ref: h.score})
    return _result(b, regions, candidates, today)


def resolve_products(
    conn: psycopg.Connection, candidate_ids: Sequence[str], today: dt.date
) -> ResolutionResult:
    refs: list[repository.ProductRef] = []
    regions: list[Region] = []
    for cid in dict.fromkeys(candidate_ids):
        region, source_id, pid = cid.split(":")
        if REGION_SOURCES.get(cast(Region, region)) != source_id:
            continue
        refs.append((source_id, int(pid)))
        if region not in regions:
            regions.append(cast(Region, region))
    regions.sort()
    cur = _current(conn, [REGION_SOURCES[r] for r in regions])
    b = _Builder(conn, cur)
    found = b.products(refs, "candidate_id")
    extra = (
        []
        if len(found) == len(refs) == len(set(candidate_ids))
        else [Notice(code="unknown_candidate_ids")]
    )
    return _result(b, regions, found, today, extra=extra)


# --- Read-only helpers for the cascade engine (cascade-engine design §6.2) -----------------------


@dataclass(frozen=True)
class RuleInputs:
    """Products and ingredients of the current dataset, for `janus.cascades.inputs`."""

    dataset_id: str
    products: dict[str, ProductCandidate]  # by candidate id; unknown ids are absent
    ingredients: dict[str, IngredientCandidate]  # by QID; unknown QIDs are absent
    combination_codes: frozenset[str]


def current_dataset_id(conn: psycopg.Connection) -> str | None:
    cur = repository.current(conn)
    return None if cur is None else cur.dataset_id


def rule_inputs(
    conn: psycopg.Connection, candidate_ids: Sequence[str], qids: Sequence[str]
) -> RuleInputs:
    """Re-resolve list items in the request's read-only transaction (codes via `rule_input`)."""
    cur = _current(conn, REGION_SOURCES.values())
    refs: list[repository.ProductRef] = []
    for cid in dict.fromkeys(candidate_ids):
        region, source_id, pid = cid.split(":")
        if REGION_SOURCES.get(cast(Region, region)) == source_id:
            refs.append((source_id, int(pid)))
    b = _Builder(conn, cur)
    products = {p.candidate_id: p for p in b.products(refs, "candidate_id")}
    wanted = sorted(set(qids))
    ingredients = {c.ingredient_key.qid: c for c in b.ingredient_candidates(wanted, {})}
    return RuleInputs(
        cur.dataset_id, products, ingredients, repository.combination_codes(conn, cur.dataset_id)
    )
