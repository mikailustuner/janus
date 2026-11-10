"""Synthetic resolution datasets for the Passport database properties (medication-passport §10).

Rows are written straight into the `res_*` tables (the loader's matching is not under test here),
with sentinel keys `Q9999999xx`, invented names and the published dose forms of the committed table.
`install()` makes the dataset current; `reset()` (from `resolution_db`) removes it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import psycopg
from hypothesis import strategies as st

from tests.resolution_db import reset

KEYS = tuple(f"Q9999999{n:02d}" for n in range(1, 7))
UNKNOWN_KEY = "Q999999990"  # never an ingredient of any synthetic dataset
REGION = {
    "titck": "TR",
    "openfda_ndc": "US",
    "eu_fr_bdpm": "EU",
    "eu_es_cima": "EU",
    "eu_it_aifa": "EU",
    "ca_dpd": "CA",
}
PRODUCT_SOURCES = tuple(REGION)
HOMEOPATHIC_NAME = "TESTNAME POUR PRÉPARATIONS HOMÉOPATHIQUES"
STRENGTHS = {
    "titck": [None],
    "openfda_ndc": [
        "5 mg/1",
        "5000 ug/1",
        "10 mg/1",
        "250 mg/5mL",
        "50 mg/mL",
        "6 [hp_X]/mL",
        None,
    ],
    "eu_fr_bdpm": ["5 mg", "5000 microgrammes", "10 mg", "2 CH", None],
    "eu_es_cima": ["5 mg", None],
    "eu_it_aifa": [
        "5 milligrammi",
        "5000 microgrammi",
        "50 milligram(s)/millilitre",
        "50 gram(s)/litre",
        "5 percent",
        None,
    ],
    "ca_dpd": [
        "5 MG",
        "5000 MCG",
        "250 MG / 5 ML",
        "50 MG / ML",
        "50 G / L",
        "100 UNIT / ML",
        "5 % / W/W",
        None,
    ],
}
FORMS: dict[str, list[tuple[str | None, tuple[str, ...]]]] = {
    "titck": [(None, ())],
    "openfda_ndc": [
        ("TABLET, FILM COATED", ("ORAL",)),
        ("TABLET", ("ORAL",)),
        ("TABLET", ()),
        ("TABLET", ("SUBLINGUAL",)),
        ("CAPSULE, EXTENDED RELEASE", ("ORAL",)),
        ("SOLUTION", ("ORAL",)),
        ("SOLUTION", ("OPHTHALMIC",)),
        (None, ()),
    ],
    "eu_fr_bdpm": [
        ("comprimé pelliculé", ("orale",)),
        ("gélule", ("orale",)),
        ("solution buvable", ("orale",)),
        ("comprimé à sucer", ("orale",)),
        (None, ()),
    ],
    "eu_es_cima": [(None, ())],
    # No row of the committed table names these sources yet, so their group is unknown.
    "eu_it_aifa": [("Compressa", ()), ("Soluzione orale", ()), (None, ())],
    "ca_dpd": [("TABLET", ("ORAL",)), ("SOLUTION", ("ORAL",)), (None, ())],
}


@dataclass(frozen=True)
class Ing:
    status: str  # mapped, ambiguous, unmapped
    qid: str | None
    strength: str | None
    name: str


@dataclass(frozen=True)
class Product:
    source_id: str
    dosage_form: str | None
    routes: tuple[str, ...]
    ingredients: tuple[Ing, ...]
    # Listing fields (design §15); the defaults keep the presence datasets as they were.
    name: str = "TESTPRODUCT"
    product_type: str | None = None
    status_published: tuple[str, ...] = ()
    marketing_end_date: str | None = None


@st.composite
def ingredients(draw: st.DrawFn, source: str) -> Ing:
    status = draw(st.sampled_from(["mapped"] * 8 + ["unmapped", "ambiguous"]))
    qid = draw(st.sampled_from(KEYS[:3] * 3 + KEYS[3:])) if status == "mapped" else None
    name = draw(st.sampled_from(["TESTNAME A", "testname b", HOMEOPATHIC_NAME]))
    if source != "eu_fr_bdpm" and name == HOMEOPATHIC_NAME:
        name = "TESTNAME C"
    return Ing(status, qid, draw(st.sampled_from(STRENGTHS[source])), name)


@st.composite
def products(draw: st.DrawFn, source: str | None = None) -> Product:
    s = source or draw(
        st.sampled_from(
            ["openfda_ndc", "eu_fr_bdpm"] * 3
            + ["eu_it_aifa", "ca_dpd"] * 2
            + ["titck", "eu_es_cima"]
        )
    )
    form, routes = draw(st.sampled_from(FORMS[s]))
    ings = draw(
        st.lists(ingredients(s), min_size=1, max_size=3).filter(
            lambda x: len(x) < 3 or draw(st.booleans())
        )
    )
    return Product(s, form, routes, tuple(ings))


def datasets() -> st.SearchStrategy[list[Product]]:
    return st.lists(products(), min_size=0, max_size=40)


SOURCE_DATES = {
    "titck": ("TR", "2026-11-06", 7),
    "openfda_ndc": ("US", "2026-11-06", 7),
    "eu_fr_bdpm": ("EU", "2026-11-03", 30),
    "eu_es_cima": ("EU", "2026-11-07", 7),
    "eu_it_aifa": ("EU", "2026-11-10", 7),
    "ca_dpd": (None, "2026-11-02", 30),
    "wikidata": (None, "2026-11-07", 30),
}


def install(
    conn: psycopg.Connection,
    items: Sequence[Product],
    sources: Iterable[str] = PRODUCT_SOURCES,
    dates: dict[str, str] | None = None,
) -> str:
    """Write `items` as the current dataset (only products of `sources`); return its id."""
    loaded = [*dict.fromkeys(sources), "wikidata"]
    payload = (
        json.dumps(
            [
                [
                    p.source_id,
                    p.dosage_form,
                    p.routes,
                    p.ingredients,
                    p.name,
                    p.product_type,
                    p.status_published,
                    p.marketing_end_date,
                ]
                for p in items
            ],
            default=str,
        )
        + repr(loaded)
        + repr(dates)
    )
    dataset = hashlib.sha256(payload.encode()).hexdigest()
    reset(conn)
    with conn.transaction():
        conn.execute(
            "INSERT INTO res_dataset (id, status, inputs) VALUES (%s, 'ready', '{}'::jsonb)",
            (dataset,),
        )
        for s in loaded:
            region, snap, cadence = SOURCE_DATES[s]
            conn.execute(
                "INSERT INTO res_source_version (dataset_id, source_id, run_id, region, "
                "snapshot_date, snapshot_is_retrieval_time, content_sha256, schema_version, "
                "license, source_url, cadence_days) "
                "VALUES (%s, %s, %s, %s, %s, false, 'x', 'test-1', 'test', "
                "'https://example.org', %s)",
                (dataset, s, f"{s}-run", region, (dates or {}).get(s, snap), cadence),
            )
        mapped: set[str] = set()
        for pid, p in enumerate(items, start=1):
            if p.source_id not in loaded:
                continue
            conn.execute(
                "INSERT INTO res_product (dataset_id, source_id, product_id, region, product_name, "
                "routes, dosage_form, name_only, product_rxcuis, product_type, status_published, "
                "marketing_end_date) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, false, '{}', %s, %s, %s)",
                (
                    dataset,
                    p.source_id,
                    pid,
                    REGION[p.source_id],
                    p.name,
                    list(p.routes),
                    p.dosage_form,
                    p.product_type,
                    list(p.status_published),
                    p.marketing_end_date,
                ),
            )
            for pos, i in enumerate(p.ingredients):
                atc = '[{"code": "A01AA01", "source_id": "wikidata", "product_ref": null}]'
                conn.execute(
                    "INSERT INTO res_product_ingredient (dataset_id, source_id, product_id, "
                    "position, published_name, strength, status, qid, key_candidates, atc, rxcuis) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, '{}', %s::jsonb, '{}')",
                    (
                        dataset,
                        p.source_id,
                        pid,
                        pos,
                        i.name,
                        i.strength,
                        i.status,
                        i.qid,
                        atc if i.status == "mapped" else "[]",
                    ),
                )
                if i.qid:
                    mapped.add(i.qid)
        for q in sorted(mapped):
            conn.execute(
                "INSERT INTO res_ingredient (dataset_id, qid, labels, ingredient_atc, rxcuis) "
                "VALUES (%s, %s, '{\"en\": \"testname\"}'::jsonb, '[]'::jsonb, '{}')",
                (dataset, q),
            )
        conn.execute(
            "INSERT INTO res_current (one, dataset_id) VALUES (true, %s) "
            "ON CONFLICT (one) DO UPDATE SET dataset_id = excluded.dataset_id",
            (dataset,),
        )
    return dataset


def product_ids(items: Sequence[Product], sources: Iterable[str]) -> list[tuple[int, Product]]:
    loaded = set(sources)
    return [(pid, p) for pid, p in enumerate(items, start=1) if p.source_id in loaded]
