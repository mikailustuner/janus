"""Names of the list's ingredients for the label check (safety-check design §6). Read-only."""

from __future__ import annotations

from collections.abc import Sequence

import psycopg

US_SOURCE = "openfda_ndc"


def us_substance_names(
    conn: psycopg.Connection, dataset: str, keys: Sequence[str]
) -> dict[str, set[str]]:
    """The US substance names (as published in the NDC directory) that drug resolution mapped
    to each key."""
    rows = conn.execute(
        "SELECT DISTINCT qid, published_name FROM res_product_ingredient "
        "WHERE dataset_id = %s AND source_id = %s AND status = 'mapped' AND qid = ANY(%s)",
        (dataset, US_SOURCE, list(keys)),
    ).fetchall()
    out: dict[str, set[str]] = {}
    for qid, name in rows:
        out.setdefault(str(qid), set()).add(str(name))
    return out


def keys_of_names(
    conn: psycopg.Connection, dataset: str, name_keys: Sequence[str]
) -> dict[str, set[str]]:
    """For each folded name, the ingredient keys the dataset knows it for."""
    rows = conn.execute(
        "SELECT name_key, ref FROM res_name "
        "WHERE dataset_id = %s AND kind = 'ingredient' AND name_key = ANY(%s)",
        (dataset, list(name_keys)),
    ).fetchall()
    out: dict[str, set[str]] = {}
    for name, ref in rows:
        out.setdefault(str(name), set()).add(str(ref))
    return out
