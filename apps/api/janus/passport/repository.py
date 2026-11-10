"""Read-only queries of the presence endpoint (medication-passport design §4.2). Parameterised SQL.

Every function takes a connection inside `read_only_tx()`. Per request: the statement timeout,
`resolution.repository.current` (two statements), `known_keys` and `presence_rows`; the number of
statements does not depend on the number of items (Req 13.2, P15). The statement text is fixed and
every value is bound.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import LiteralString

import psycopg

from janus.passport.listing import ListingRow
from janus.passport.presence import PresenceRow

STATEMENT_TIMEOUT: LiteralString = "3s"  # Req 5.3

# The `hp_strength` pattern is `HOMEOPATHIC_UNIT` of `resolution/model.py` (P8 checks that POSIX
# `~*` and Python agree). `hp_names` is a superset pre-filter; `is_homeopathic_name` decides.
PRESENCE_SQL: LiteralString = r"""
WITH hit AS (
  SELECT DISTINCT source_id, product_id
  FROM res_product_ingredient
  WHERE dataset_id = %(d)s AND status = 'mapped' AND qid = ANY(%(keys)s::text[])
), prod AS (
  SELECT i.source_id, i.product_id,
         array_agg(i.qid      ORDER BY i.qid, i.position) FILTER (WHERE i.status = 'mapped')
           AS keys,
         array_agg(i.strength ORDER BY i.qid, i.position) FILTER (WHERE i.status = 'mapped')
           AS strengths,
         bool_and(i.status = 'mapped') AS complete,
         coalesce(bool_or(i.strength ~* '\[(hp|kp)_[a-z]+\]'), false) AS hp_strength,
         array_agg(i.published_name) FILTER (WHERE i.published_name ILIKE '%%pathiques%%')
           AS hp_names
  FROM hit h
  JOIN res_product_ingredient i
    ON i.dataset_id = %(d)s AND i.source_id = h.source_id AND i.product_id = h.product_id
  GROUP BY i.source_id, i.product_id
)
SELECT p.source_id, p.keys, p.strengths, p.complete, p.hp_strength, p.hp_names, r.region,
       r.dosage_form, r.routes, count(*) AS products
FROM prod p
JOIN res_product r ON r.dataset_id = %(d)s AND r.source_id = p.source_id
                  AND r.product_id = p.product_id
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
"""


def set_timeout(conn: psycopg.Connection) -> None:
    conn.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")


def presence_rows(conn: psycopg.Connection, dataset: str, keys: Sequence[str]) -> list[PresenceRow]:
    rows = conn.execute(PRESENCE_SQL, {"d": dataset, "keys": list(keys)}).fetchall()
    return [
        PresenceRow(
            source_id=str(r[0]),
            keys=list(r[1]),
            strengths=list(r[2]),
            complete=bool(r[3]),
            hp_strength=bool(r[4]),
            hp_names=list(r[5] or []),
            region=str(r[6]),
            dosage_form=r[7],
            routes=list(r[8]),
            products=int(r[9]),
        )
        for r in rows
    ]


def known_keys(conn: psycopg.Connection, dataset: str, keys: Sequence[str]) -> set[str]:
    rows = conn.execute(
        "SELECT qid FROM res_ingredient WHERE dataset_id = %s AND qid = ANY(%s)",
        (dataset, list(keys)),
    ).fetchall()
    return {str(r[0]) for r in rows}


# One target source, grouped by everything the listing shows (design §15.3). Same ingredient
# aggregation and homeopathic pre-filters as `PRESENCE_SQL`; the display name is the published
# product name (brand or generic name where a source has no product name).
LISTING_SQL: LiteralString = r"""
WITH hit AS (
  SELECT DISTINCT product_id
  FROM res_product_ingredient
  WHERE dataset_id = %(d)s AND status = 'mapped' AND source_id = %(s)s
    AND qid = ANY(%(keys)s::text[])
), prod AS (
  SELECT i.product_id,
         array_agg(i.qid      ORDER BY i.qid, i.position) FILTER (WHERE i.status = 'mapped')
           AS keys,
         array_agg(i.strength ORDER BY i.qid, i.position) FILTER (WHERE i.status = 'mapped')
           AS strengths,
         bool_and(i.status = 'mapped') AS complete,
         coalesce(bool_or(i.strength ~* '\[(hp|kp)_[a-z]+\]'), false) AS hp_strength,
         array_agg(i.published_name) FILTER (WHERE i.published_name ILIKE '%%pathiques%%')
           AS hp_names
  FROM hit h
  JOIN res_product_ingredient i
    ON i.dataset_id = %(d)s AND i.source_id = %(s)s AND i.product_id = h.product_id
  GROUP BY i.product_id
)
SELECT p.keys, p.strengths, p.complete, p.hp_strength, p.hp_names, r.region, r.dosage_form,
       r.routes, coalesce(r.product_name, r.brand_name, r.generic_name) AS name, r.product_type,
       r.marketing_end_date, r.status_published, count(*) AS products
FROM prod p
JOIN res_product r ON r.dataset_id = %(d)s AND r.source_id = %(s)s
                  AND r.product_id = p.product_id
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
"""


def listing_rows(
    conn: psycopg.Connection, dataset: str, source_id: str, keys: Sequence[str]
) -> list[ListingRow]:
    rows = conn.execute(LISTING_SQL, {"d": dataset, "s": source_id, "keys": list(keys)}).fetchall()
    return [
        ListingRow(
            row=PresenceRow(
                source_id=source_id,
                keys=list(r[0] or []),
                strengths=list(r[1] or []),
                complete=bool(r[2]),
                hp_strength=bool(r[3]),
                hp_names=list(r[4] or []),
                region=str(r[5]),
                dosage_form=r[6],
                routes=list(r[7]),
                products=int(r[12]),
            ),
            name=r[8],
            product_type=r[9],
            marketing_end_date=r[10],
            status_published=list(r[11]),
        )
        for r in rows
    ]
