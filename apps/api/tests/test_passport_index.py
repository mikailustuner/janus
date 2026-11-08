"""Migration 0012: the presence index (medication-passport task 1.1, design §4.1, §4.2).

Validates Req 13.1: upgrade -> downgrade -> upgrade; the index exists only after the upgrade; the
plan of the §4.2 statement uses it on a synthetic dataset (sentinel keys, invented names).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, cast

import psycopg
import pytest
from alembic import command

from tests.conftest import alembic_config

INDEX = "res_product_ingredient_key"
DATASET = "e" * 64  # synthetic dataset id; never current

# The statement of design §4.2. Task 6 moves it into `passport/repository.py`; this test then
# imports it from there.
PRESENCE_SQL = r"""
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
         bool_or(i.strength ~* '\[(hp|kp)_[a-z]+\]') AS hp_strength,
         array_agg(i.published_name) FILTER (WHERE i.published_name ILIKE '%%pathiques%%')
           AS hp_names
  FROM hit h
  JOIN res_product_ingredient i
    ON i.dataset_id = %(d)s AND i.source_id = h.source_id AND i.product_id = h.product_id
  GROUP BY i.source_id, i.product_id
)
SELECT p.source_id, p.keys, p.strengths, p.complete, p.hp_strength, p.hp_names, r.region,
       r.dosage_form, count(*) AS products
FROM prod p
JOIN res_product r ON r.dataset_id = %(d)s AND r.source_id = p.source_id
                  AND r.product_id = p.product_id
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8
"""


def _index_exists(conn: psycopg.Connection) -> bool:
    row = conn.execute("SELECT to_regclass(%s) IS NOT NULL", (f"public.{INDEX}",)).fetchone()
    return bool(row and row[0])


def _index_def(conn: psycopg.Connection) -> str:
    row = conn.execute("SELECT indexdef FROM pg_indexes WHERE indexname = %s", (INDEX,)).fetchone()
    assert row is not None
    return str(row[0])


def _drop_synthetic(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM res_dataset WHERE id = %s", (DATASET,))


@pytest.fixture
def synthetic(db_conn: psycopg.Connection) -> Iterator[psycopg.Connection]:
    """40,000 products in two sources, one to three ingredients each, 2,000 sentinel keys;
    a fifth of the rows unmapped. Built in SQL so that the planner sees a realistic size."""
    _drop_synthetic(db_conn)
    db_conn.execute(
        "INSERT INTO res_dataset (id, status, inputs) VALUES (%s, 'ready', '{}'::jsonb)",
        (DATASET,),
    )
    for source, region in (("openfda_ndc", "US"), ("eu_fr_bdpm", "EU")):
        db_conn.execute(
            "INSERT INTO res_source_version (dataset_id, source_id, run_id, region, "
            "snapshot_date, snapshot_is_retrieval_time, content_sha256, schema_version, license, "
            "source_url) VALUES (%s, %s, 'run-1', %s, '2026-11-06', false, 'x', 'test-1', 'test', "
            "'https://example.org')",
            (DATASET, source, region),
        )
        db_conn.execute(
            "INSERT INTO res_product (dataset_id, source_id, product_id, region, routes, "
            "dosage_form, name_only, product_rxcuis) "
            "SELECT %s, %s, g, %s, '{}', 'TEST FORM', false, '{}' "
            "FROM generate_series(1, 20000) g",
            (DATASET, source, region),
        )
        db_conn.execute(
            "INSERT INTO res_product_ingredient (dataset_id, source_id, product_id, position, "
            "published_name, strength, status, qid, key_candidates, atc, rxcuis) "
            "SELECT %s, %s, g, p, 'TESTNAME', '5 mg/1', "
            "  CASE WHEN (g * 7 + p) %% 5 = 0 THEN 'unmapped' ELSE 'mapped' END, "
            "  CASE WHEN (g * 7 + p) %% 5 = 0 THEN NULL "
            "       ELSE 'Q99999' || lpad(((g * 31 + p * 17) %% 2000)::text, 4, '0') END, "
            "  '{}', "
            "  CASE WHEN (g * 7 + p) %% 5 = 0 THEN '[]'::jsonb "
            '       ELSE \'[{"code": "A01AA01"}]\'::jsonb END, '
            "  '{}' "
            "FROM generate_series(1, 20000) g, generate_series(0, 2) p WHERE p <= g %% 3",
            (DATASET, source),
        )
    db_conn.execute("ANALYZE res_product_ingredient")
    db_conn.execute("ANALYZE res_product")
    try:
        yield db_conn
    finally:
        _drop_synthetic(db_conn)


def _plan_nodes(plan: dict[str, Any]) -> Iterator[dict[str, Any]]:
    yield plan
    for child in plan.get("Plans", []):
        yield from _plan_nodes(child)


@pytest.mark.db
def test_migration_0012_is_reversible(db_url: str, db_conn: psycopg.Connection) -> None:
    """Feature: medication-passport, task 1.1. Validates Req 13.1."""
    assert _index_exists(db_conn)
    before = _index_def(db_conn)
    assert "WHERE (status = 'mapped'::text)" in before
    assert "(dataset_id, qid, source_id, product_id)" in before
    cfg = alembic_config(db_url)
    command.downgrade(cfg, "0011")
    assert not _index_exists(db_conn)
    command.upgrade(cfg, "head")
    assert _index_def(db_conn) == before


@pytest.mark.db
def test_presence_statement_uses_the_index(synthetic: psycopg.Connection) -> None:
    """Feature: medication-passport, task 1.1. Validates Req 13.1: the key lookup of §4.2 is an
    index scan of `res_product_ingredient_key`, not a sequential scan."""
    keys = [f"Q99999{n:04d}" for n in (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610)]
    row = synthetic.execute(
        ("EXPLAIN (FORMAT JSON) " + PRESENCE_SQL).encode(),
        {"d": DATASET, "keys": keys},
    ).fetchone()
    assert row is not None
    raw: Any = row[0]
    plan = cast(list[dict[str, Any]], raw if isinstance(raw, list) else json.loads(raw))
    nodes = list(_plan_nodes(plan[0]["Plan"]))
    used = {n.get("Index Name") for n in nodes}
    assert INDEX in used, [n["Node Type"] for n in nodes]
    assert not any(
        n["Node Type"] in ("Seq Scan", "Parallel Seq Scan")
        and n.get("Relation Name") == "res_product_ingredient"
        for n in nodes
    )
