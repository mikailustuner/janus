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
from janus.passport.presence import SOURCE_ORDER, evaluate, signature
from janus.passport.schemas import CanCompare, Notice, PresenceIn, PresenceOut, SourceOut
from janus.passport.strength import CODED_SOURCES
from janus.resolution import repository as resolution_repository

ATTRIBUTION = {
    "titck": "titck",
    "eu_fr_bdpm": "bdpm",
    "eu_es_cima": "cima",
    "openfda_ndc": "openfda",
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
