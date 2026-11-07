"""Helpers for database-backed resolution tests: synthetic artifacts and loads."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import psycopg

from janus.resolution.canonical import content_hash
from janus.resolution.load import Artifact, Inputs
from janus.resolution.prepare import OPENFDA, TITCK, WIKIDATA
from tests.resolution_strategies import ROUTES, RULES

_META = {
    TITCK: ("titck-2", "TR", "2026-11-06", "Redistribution terms unclear"),
    OPENFDA: ("us_ndc-2", "US", "2026-11-06", "CC0 1.0 (public domain)"),
    WIKIDATA: ("wikidata_ingredients-1", None, "2026-11-07T16:39:17+00:00", "CC0 1.0"),
}


def artifact(source_id: str, rows: Sequence[Any], run: str = "run-1") -> Artifact:
    schema, region, snapshot, licence = _META[source_id]
    manifest = {
        "run_id": f"{source_id}-{run}",
        "source_id": source_id,
        "schema_version": schema,
        "region": region,
        "snapshot_date": snapshot,
        "snapshot_date_is_retrieval_time": source_id == WIKIDATA,
        "outcome": "succeeded",
        "content_sha256": content_hash(rows, schema),
        "license": licence,
    }
    evidence = {"source_url": f"https://example.org/{source_id}", "license": licence}
    return Artifact(source_id, manifest, evidence, list(rows))


def inputs(tr: Sequence[Any], us: Sequence[Any], wd: Sequence[Any], run: str = "run-1") -> Inputs:
    return Inputs(
        {
            TITCK: artifact(TITCK, tr, run),
            OPENFDA: artifact(OPENFDA, us, run),
            WIKIDATA: artifact(WIKIDATA, wd, run),
        },
        RULES,
        ROUTES,
        (),
        "test-code",
    )


def reset(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM res_current")
    conn.execute("DELETE FROM res_dataset")


RES_TABLES = (
    "res_source_version",
    "res_product",
    "res_product_code",
    "res_product_ingredient",
    "res_ingredient",
    "res_name",
    "res_combination_atc",
    "res_coverage",
)


def datasets_of_rows(conn: psycopg.Connection) -> dict[str, set[str]]:
    """For every resolution table, the dataset ids its rows belong to."""
    out: dict[str, set[str]] = {}
    for table in RES_TABLES:
        rows = conn.execute(f"SELECT DISTINCT dataset_id FROM {table}").fetchall()  # noqa: S608 (fixed names)
        out[table] = {str(r[0]) for r in rows}
    return out


def dump(conn: psycopg.Connection, dataset: str) -> dict[str, list[tuple[Any, ...]]]:
    out: dict[str, list[tuple[Any, ...]]] = {}
    for table in RES_TABLES:
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE dataset_id = %s",  # noqa: S608 (fixed names)
            (dataset,),
        ).fetchall()
        out[table] = sorted(tuple(str(v) for v in r) for r in rows)
    return out
