"""Presence service (medication-passport design §3, §4.2, §5.3). Reads only, one transaction.

Statements per request (constant, Req 13.2): `SET LOCAL statement_timeout`, the current dataset and
its source versions, the known keys, the grouped presence statement. Nothing is written and nothing
is logged; the answer holds codes and numbers only.
"""

from __future__ import annotations

import datetime as dt

import psycopg

from janus.integrity.freshness import is_stale, parse_snapshot_date
from janus.passport import repository
from janus.passport.forms import FormTable
from janus.passport.listing import listing
from janus.passport.presence import SOURCE_ORDER, ItemQuery, evaluate, signature
from janus.passport.schemas import (
    CanCompare,
    ItemIn,
    LevelCounts,
    ListingCounts,
    ListingNotice,
    Notice,
    PresenceIn,
    PresenceOut,
    ProductsIn,
    ProductsOut,
    SourceOut,
)
from janus.passport.strength import CODED_SOURCES
from janus.resolution import repository as resolution_repository

ATTRIBUTION = {
    "titck": "titck",
    "eu_fr_bdpm": "bdpm",
    "eu_es_cima": "cima",
    "openfda_ndc": "openfda",
    "eu_it_aifa": "aifa",
    "ca_dpd": "dpd",
}


class PassportUnavailableError(RuntimeError):
    """No current resolution dataset (Req 5.3). Never "not found"."""


def _sources(
    cur: resolution_repository.Current, forms: FormTable, today: dt.date
) -> list[SourceOut]:
    out: list[SourceOut] = []
    for i, (sid, region, country) in enumerate(SOURCE_ORDER):
        row = None if sid is None else cur.sources.get(sid)
        if sid is None or row is None:
            out.append(
                SourceOut(
                    source=i,
                    source_id=sid,  # pyright: ignore[reportArgumentType]
                    region=region,  # pyright: ignore[reportArgumentType]
                    country=country,  # pyright: ignore[reportArgumentType]
                    status="source_unavailable",
                    reason="no_open_product_database" if sid is None else "not_loaded",
                    snapshot_date=None,
                    stale=False,
                    attribution=None if sid is None else ATTRIBUTION[sid],  # pyright: ignore[reportArgumentType]
                    as_published=sid == "eu_fr_bdpm",
                    can_compare=CanCompare(strength=False, dose_form=False),
                )
            )
            continue
        snap = parse_snapshot_date(row.snapshot_date)
        out.append(
            SourceOut(
                source=i,
                source_id=sid,  # pyright: ignore[reportArgumentType]
                region=region,  # pyright: ignore[reportArgumentType]
                country=country,  # pyright: ignore[reportArgumentType]
                status="loaded",
                reason=None,
                snapshot_date=snap.isoformat(),
                # Same rule as the resolution notice `source_may_be_outdated`.
                stale=row.cadence_days is None or is_stale(snap, today, row.cadence_days),
                attribution=ATTRIBUTION[sid],  # pyright: ignore[reportArgumentType]
                as_published=sid == "eu_fr_bdpm",
                can_compare=CanCompare(
                    strength=sid in CODED_SOURCES, dose_form=sid in forms.sources
                ),
            )
        )
    return out


def presence(
    conn: psycopg.Connection, body: PresenceIn, forms: FormTable, today: dt.date
) -> PresenceOut:
    repository.set_timeout(conn)
    cur = resolution_repository.current(conn)
    if cur is None:
        raise PassportUnavailableError("no current dataset")
    keys = sorted({i.key for item in body.items for i in item.ingredients})
    known = repository.known_keys(conn, cur.dataset_id, keys)
    rows = repository.presence_rows(conn, cur.dataset_id, keys)
    sigs = [signature(r, forms) for r in rows]
    loaded = {sid for sid, _, _ in SOURCE_ORDER if sid is not None and sid in cur.sources}
    items = evaluate(body.items, sigs, loaded, known)
    notices: list[Notice] = ["presence_is_lower_bound"]
    if any(i.unknown_keys for i in items):
        notices.append("unknown_ingredient_keys")
    return PresenceOut(
        dataset_version=cur.dataset_id,
        form_table_version=forms.version,
        sources=_sources(cur, forms, today),
        items=items,
        notices=notices,
    )


def products(
    conn: psycopg.Connection, body: ProductsIn, forms: FormTable, today: dt.date
) -> ProductsOut:
    """The products of one listable source with exactly the medicine's ingredients (design §15).
    Statements per request (constant): the timeout, the current dataset and its source versions,
    the known keys, the grouped listing statement. A source that is not loaded is answered
    `source_unavailable` with nothing listed, as in `presence` (Req 5.4)."""
    repository.set_timeout(conn)
    cur = resolution_repository.current(conn)
    if cur is None:
        raise PassportUnavailableError("no current dataset")
    item = ItemQuery.of(ItemIn(ingredients=body.ingredients, dose_form=body.dose_form))
    keys = sorted(item.keys)
    index = next(i for i, (sid, _, _) in enumerate(SOURCE_ORDER) if sid == body.target)
    source = _sources(cur, forms, today)[index]
    known = repository.known_keys(conn, cur.dataset_id, keys)
    unknown = sorted(item.keys - known)
    notices: list[ListingNotice] = ["listing_is_lower_bound"]
    if unknown:
        notices.append("unknown_ingredient_keys")
    zero = LevelCounts(same=0, different=0, unknown=0)
    if source.status != "loaded":
        return ProductsOut(
            dataset_version=cur.dataset_id,
            form_table_version=forms.version,
            source=source,
            keys=keys,
            unknown_keys=unknown,
            status="source_unavailable",
            total=0,
            listings=0,
            counts=ListingCounts(strength=zero, dose_form=zero),
            with_other_ingredients=0,
            keys_found=[],
            homeopathic_left_out=0,
            not_finished_left_out=0,
            offset=body.offset,
            limit=body.limit,
            products=[],
            notices=notices,
        )
    rows = repository.listing_rows(conn, cur.dataset_id, body.target, keys)
    out = listing(item, rows, forms, today)
    return ProductsOut(
        dataset_version=cur.dataset_id,
        form_table_version=forms.version,
        source=source,
        keys=keys,
        unknown_keys=unknown,
        status=out.answer.status,
        total=len(out.products),
        listings=out.answer.products,
        counts=out.counts,
        with_other_ingredients=out.answer.with_other_ingredients,
        keys_found=out.answer.keys_found,
        homeopathic_left_out=out.answer.homeopathic_left_out,
        not_finished_left_out=out.not_finished_left_out,
        offset=body.offset,
        limit=body.limit,
        products=out.products[body.offset : body.offset + body.limit],
        notices=notices,
    )
