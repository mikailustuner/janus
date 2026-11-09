"""The `janus-cascade` CDS service: map, evaluate, build cards (cds-hooks design §5, §6).

One read-only transaction for the mapping and the evaluation. Nothing is written, nothing of
the request is logged, no external service is called.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import Any, Final

import psycopg

from janus.cascades import service as cascades
from janus.cascades.schemas import MAX_ITEMS, EvaluateIn
from janus.cds import cards, mapping
from janus.cds.fhir import Extracted, Origin
from janus.resolution import repository
from janus.resolution import service as resolution
from janus.resolution.model import ProductCandidate, Region
from janus.resolution.ndc import NdcError

SOURCE_REGION: Final[Mapping[str, Region]] = {
    s: r for r, sources in resolution.REGION_SOURCES.items() for s in sources
}


class TooManyMedicationsError(ValueError):
    """More distinct medicines than the engine accepts (design DP12)."""


class DbLookup:
    """`mapping.Lookup` over the current dataset, inside the caller's read-only transaction."""

    def __init__(self, conn: psycopg.Connection, dataset: str, today: dt.date) -> None:
        self.conn = conn
        self.dataset = dataset
        self.today = today
        self._combination = repository.combination_codes(conn, dataset)

    def products_by_ndc(self, code: str) -> Sequence[ProductCandidate]:
        try:
            found = resolution.resolve_ndc(self.conn, code, self.today)
        except (NdcError, resolution.ResolutionUnavailableError):
            return []  # malformed, or no US source in this dataset: nothing found
        return [c for c in found.candidates if isinstance(c, ProductCandidate)]

    def products_by_rxcui(self, code: str) -> Sequence[ProductCandidate] | None:
        refs = repository.refs_by_product_rxcui(self.conn, self.dataset, code)
        ids = [f"{SOURCE_REGION[s]}:{s}:{p}" for s, p in refs if s in SOURCE_REGION]
        if not ids:
            return []
        if len(ids) > mapping.MAX_PRODUCTS:
            return None  # too many to compare: never a partial comparison (review P3)
        try:
            found = resolution.resolve_products(self.conn, ids, self.today)
        except resolution.ResolutionUnavailableError:
            return []
        return [c for c in found.candidates if isinstance(c, ProductCandidate)]

    def qids_by_rxcui(self, code: str) -> Sequence[str]:
        return repository.qids_by_rxcui(self.conn, self.dataset, code)

    def qids_by_atc(self, code: str) -> Sequence[str]:
        return repository.qids_by_atc(self.conn, self.dataset, code)

    def key_codes(self, qid: str) -> Sequence[str]:
        rec = repository.ingredients(self.conn, self.dataset, [qid]).get(qid)
        return [] if rec is None else [str(a["code"]) for a in rec["ingredient_atc"]]

    def is_combination_code(self, code: str) -> bool:
        return code in self._combination


def items_of(
    extracted: Extracted, lookup: mapping.Lookup
) -> tuple[list[dict[str, Any]], list[frozenset[Origin]], int]:
    """Engine items (de-duplicated by product or key), their origins, and the count of
    medicines that could not be mapped."""
    keys: dict[tuple[str, str], int] = {}
    items: list[dict[str, Any]] = []
    origins: list[set[Origin]] = []
    not_checked = 0
    for med in extracted.medicines:
        m = mapping.map_medicine(med.codings, lookup)
        if isinstance(m, mapping.NotMapped):
            not_checked += 1
            continue
        key = (
            ("product", m.candidate_id)
            if isinstance(m, mapping.ProductItem)
            else ("ingredient", m.qid)
        )
        if key not in keys:
            keys[key] = len(items)
            items.append({key[0]: key[1]})
            origins.append(set())
        origins[keys[key]].add(med.origin)
    if len(items) > MAX_ITEMS:
        raise TooManyMedicationsError
    return items, [frozenset(o) for o in origins], not_checked


def evaluate(
    conn: psycopg.Connection,
    extracted: Extracted,
    today: dt.date,
    faers_event_keys: Mapping[int, str] | None = None,
) -> cards.CardsOut:
    dataset = resolution.current_dataset_id(conn)
    if dataset is None:
        raise cascades.CascadesUnavailableError
    items, origins, not_checked = items_of(extracted, DbLookup(conn, dataset, today))
    if not any(o & extracted.focus for o in origins):
        return cards.CardsOut(cards=[])  # nothing in focus: no finding could become a card
    body = EvaluateIn.model_validate({"dataset_version": dataset, "items": items})
    result = cascades.derive(conn, body, today, faers_event_keys).result
    return cards.build(result, origins, extracted.focus, not_checked, extracted.not_provided)
