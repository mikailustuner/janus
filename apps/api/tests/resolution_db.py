"""Helpers for database-backed resolution tests: synthetic artifacts and loads."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import psycopg

from janus.resolution.canonical import content_hash
from janus.resolution.load import Artifact, Inputs
from janus.resolution.prepare import OPENFDA, TITCK, WIKIDATA
from janus.resolution.prepare_eu import ES_CIMA, FR_BDPM
from janus.resolution.prepare_national import CA_DPD, IT_AIFA
from tests.resolution_strategies import ROUTES, RULES

CADENCES = {TITCK: 7, OPENFDA: 7, WIKIDATA: 30, FR_BDPM: 30, ES_CIMA: 7, CA_DPD: 30, IT_AIFA: 7}
_META = {
    TITCK: ("titck-2", "TR", "2026-11-06", "Redistribution terms unclear"),
    OPENFDA: ("us_ndc-2", "US", "2026-11-06", "CC0 1.0 (public domain)"),
    WIKIDATA: ("wikidata_ingredients-1", None, "2026-11-07T16:39:17+00:00", "CC0 1.0"),
    FR_BDPM: ("eu_fr_bdpm-1", "EU", "2026-11-03", "Licence Ouverte (Etalab)"),
    ES_CIMA: ("eu_es_cima-1", "EU", "2026-11-07", "Reuse with attribution (Ley 37/2007)"),
    CA_DPD: ("ca_dpd-1", None, "2026-11-02", "Open Government Licence \u2013 Canada (version 2.0)"),
    IT_AIFA: ("eu_it_aifa-1", "EU", "2026-11-10", "CC BY 4.0"),
}
# The pipelines' manifests name these sources by their registry ids.
MANIFEST_ID = {FR_BDPM: "bdpm", ES_CIMA: "cima", CA_DPD: "dpd", IT_AIFA: "aifa"}


def artifact(source_id: str, rows: Sequence[Any], run: str = "run-1") -> Artifact:
    schema, region, snapshot, licence = _META[source_id]
    manifest = {
        "run_id": f"{source_id}-{run}",
        "source_id": MANIFEST_ID.get(source_id, source_id),
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


def inputs(
    tr: Sequence[Any],
    us: Sequence[Any],
    wd: Sequence[Any],
    run: str = "run-1",
    fr: Sequence[Any] | None = None,
    es: Sequence[Any] | None = None,
    ca: Sequence[Any] | None = None,
    it: Sequence[Any] | None = None,
) -> Inputs:
    """`fr`, `es`, `ca` and `it` are the BDPM, Nomenclátor, DPD and AIFA rows; `None` leaves the
    source out."""
    artifacts = {
        TITCK: artifact(TITCK, tr, run),
        OPENFDA: artifact(OPENFDA, us, run),
        WIKIDATA: artifact(WIKIDATA, wd, run),
    }
    if fr is not None:
        artifacts[FR_BDPM] = artifact(FR_BDPM, fr, run)
    if es is not None:
        artifacts[ES_CIMA] = artifact(ES_CIMA, es, run)
    if ca is not None:
        artifacts[CA_DPD] = artifact(CA_DPD, ca, run)
    if it is not None:
        artifacts[IT_AIFA] = artifact(IT_AIFA, it, run)
    return Inputs(
        artifacts,
        RULES,
        ROUTES,
        (),
        "test-code",
        CADENCES,
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
    "res_component_code",
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
