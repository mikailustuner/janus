"""Benchmark of `POST /passport/presence` (medication-passport design §13, task 7, Req 13.1).

Usage: `python -m janus.passport.bench [--runs 30]` with `DATABASE_URL` (a loaded database at
migration head). Times the full HTTP route in-process for three lists:

- **common** (Req 13.1, 15 items): fifteen ingredients common in older adults' medicine lists
  (`COMMON`, the English labels of the dataset: Wikidata spellings), one item each;
- **frequent** (stress, 15 items): the 15 keys with the most products in the dataset;
- **worst** (Req 13.1, 50 items): the 50 keys with the most products.

Prints p50 and p95 in milliseconds, the number of products behind each list and the targets; no
key is printed.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections.abc import Sequence

COMMON = (
    "metformin",
    "amlodipine",
    "lisinopril",
    "atorvastatin",
    "simvastatin",
    "(rs)-metoprolol",
    "omeprazole",
    "pantoprazole",
    "levothyroxine sodium",
    "furosemide",
    "hydrochlorothiazide",
    "losartan",
    "ramipril",
    "bisoprolol",
    "rac-warfarin",
)
COMMON_SQL = """
SELECT qid FROM res_ingredient
WHERE dataset_id = (SELECT dataset_id FROM res_current) AND lower(labels->>'en') = ANY(%s)
ORDER BY qid
"""
TOP_KEYS_SQL = """
SELECT qid FROM res_product_ingredient
WHERE dataset_id = (SELECT dataset_id FROM res_current) AND status = 'mapped'
GROUP BY qid ORDER BY count(DISTINCT (source_id, product_id)) DESC, qid LIMIT %s
"""
PRODUCTS_SQL = """
SELECT count(DISTINCT (source_id, product_id)) FROM res_product_ingredient
WHERE dataset_id = (SELECT dataset_id FROM res_current) AND status = 'mapped' AND qid = ANY(%s)
"""
TARGETS_MS = {"common": 500.0, "frequent": 500.0, "worst": 2000.0}


def percentile(values: Sequence[float], p: float) -> float:
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(p * (len(ordered) - 1))))
    return ordered[k]


def main(argv: Sequence[str] | None = None) -> int:
    import psycopg
    from fastapi.testclient import TestClient

    from janus.db.pool import Database
    from janus.main import create_app
    from janus.settings import Settings

    ap = argparse.ArgumentParser(prog="python -m janus.passport.bench")
    ap.add_argument("--runs", type=int, default=30)
    args = ap.parse_args(argv)
    settings = Settings.from_env()
    if not settings.database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    with psycopg.connect(settings.database_url) as conn:
        top = [str(r[0]) for r in conn.execute(TOP_KEYS_SQL, (50,)).fetchall()]
        common = [str(r[0]) for r in conn.execute(COMMON_SQL, (list(COMMON),)).fetchall()]
        lists = {"common": common, "frequent": top[:15], "worst": top}
        products = {
            name: int((conn.execute(PRODUCTS_SQL, (keys,)).fetchone() or (0,))[0])
            for name, keys in lists.items()
        }
        indexed = conn.execute(
            "SELECT to_regclass('public.res_product_ingredient_key') IS NOT NULL"
        ).fetchone()
    print(f"presence index present: {bool(indexed and indexed[0])}")
    database = Database(settings.database_url)
    database.open()
    try:
        app = create_app(settings, database=database, configure_logs=False)
        with TestClient(app) as client:
            for name, keys in lists.items():
                body = {"items": [{"ingredients": [{"key": k}]} for k in keys]}
                client.post("/passport/presence", json=body)  # warm-up
                times: list[float] = []
                status = 0
                for _ in range(args.runs):
                    t0 = time.perf_counter()
                    r = client.post("/passport/presence", json=body)
                    times.append((time.perf_counter() - t0) * 1000)
                    status = r.status_code
                p50, p95 = statistics.median(times), percentile(times, 0.95)
                print(  # log-guard: ignore (counts and timings only)
                    f"{name}: {len(keys)} items, {products[name]} products, status {status}, "
                    f"p50 {p50:.0f} ms, p95 {p95:.0f} ms "
                    f"(target p95 <= {TARGETS_MS[name]:.0f} ms, {args.runs} runs)"
                )
    finally:
        database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
