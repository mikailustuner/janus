"""Local latency benchmark against the real counts file (collective-memory Req 9).

`python -m janus.memory.bench [--data-dir PATH] [--n N]` prints percentiles for the database part
and for the HTTP routes (in-process ASGI client). Skipped (exit 1) when no counts file exists.
Not run in CI (shared runners); CI asserts the statement budget instead.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import duckdb
from fastapi.testclient import TestClient

from janus.main import create_app
from janus.memory.faers_build import COUNTS_DB, counts_root
from janus.memory.reader import CountsHolder
from janus.settings import Settings

TARGETS_MS = {
    "pair (database)": 10,
    "pair (route)": 25,
    "regions (database)": 15,
    "regions (route)": 40,
    "janus key, 6 PTs (route)": 100,
    "combination 20 (route)": 250,
}


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * q))]


def timed(fn: Callable[[], Any], n: int) -> list[float]:
    out: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000)
    return out


def line(label: str, values: list[float]) -> str:
    target = TARGETS_MS.get(label)
    mark = (
        ""
        if target is None
        else f"  target p95 <= {target} ms: {'OK' if pct(values, 0.95) <= target else 'MISSED'}"
    )
    return (
        f"{label:34} n={len(values):4} p50 {statistics.median(values):7.1f}  "
        f"p95 {pct(values, 0.95):7.1f}  max {max(values):7.1f} ms{mark}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m janus.memory.bench")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--n", type=int, default=200)
    args = parser.parse_args(argv)
    db = counts_root(args.data_dir) / "current" / COUNTS_DB
    if not db.exists():
        print("no current counts file; benchmark skipped", file=sys.stderr)
        return 1
    holder = CountsHolder(args.data_dir)
    reader = holder.current()
    probe = duckdb.connect(str(db), read_only=True)
    sample = probe.execute(
        "SELECT ingredient_key, pt FROM (SELECT * FROM faers_pair_counts "  # noqa: S608
        "WHERE region = 'ALL' AND scope = 'suspect') "
        f"USING SAMPLE {int(args.n)} ROWS (reservoir, 7)"
    ).fetchall()
    top = [
        str(r[0])
        for r in probe.execute(
            "SELECT ingredient_key FROM faers_ingredient_counts WHERE region = 'ALL' "
            "AND scope = 'any' ORDER BY reports DESC LIMIT 20"
        ).fetchall()
    ]
    common = [
        str(r[0])
        for r in probe.execute(
            "SELECT pt FROM faers_event_counts WHERE region = 'ALL' "
            "ORDER BY reports_mapped DESC LIMIT 6"
        ).fetchall()
    ]
    probe.close()
    print(f"build {reader.meta.build_id}; {len(sample)} sampled pairs; top ingredients {len(top)}")

    def db_pair() -> None:
        with reader.session() as s:
            k, pt = sample[i[0] % len(sample)]
            i[0] += 1
            s.cells([k], [pt], "suspect", ["ALL"])

    def db_regions() -> None:
        with reader.session() as s:
            k, pt = sample[i[0] % len(sample)]
            i[0] += 1
            s.cells([k], [pt], "suspect", ["TR", "EU", "US", "OTHER", "UNKNOWN", "ALL"])

    i = [0]
    first = time.perf_counter()
    db_pair()
    print(f"first lookup after open: {(time.perf_counter() - first) * 1000:.1f} ms")
    print(line("pair (database)", timed(db_pair, args.n)))
    print(line("regions (database)", timed(db_regions, args.n)))

    app = create_app(
        Settings.from_env({"JANUS_DATA_DIR": str(args.data_dir)}), configure_logs=False
    )
    client = TestClient(app)

    def route_pair() -> None:
        k, pt = sample[i[0] % len(sample)]
        i[0] += 1
        client.post(
            "/memory/pair",
            json={"ingredient": k, "event": {"pt": pt}, "region": "ALL", "scope": "suspect"},
        ).raise_for_status()

    def route_regions() -> None:
        k, pt = sample[i[0] % len(sample)]
        i[0] += 1
        client.post(
            "/memory/regions", json={"ingredients": [k], "event": {"pt": pt}}
        ).raise_for_status()

    print(line("pair (route)", timed(route_pair, args.n)))
    print(line("regions (route)", timed(route_regions, args.n)))

    # Janus key with up to 6 PTs: a throw-away vocabulary entry is not available here, so the
    # report-level path is timed directly with the commonest PTs and the largest ingredient.
    def key_path() -> None:
        with reader.session() as s:
            s.cells([top[0]], common, "suspect", ["ALL"], force_report_level=True)

    print(line("janus key, 6 PTs (database)", timed(key_path, max(20, args.n // 10))))
    for n in (2, 5, 10, 20):
        body = {"ingredients": top[:n], "region": "ALL", "scope": "any", "top_events": 50}

        def combo(body: dict[str, Any] = body) -> None:
            client.post("/memory/combination", json=body).raise_for_status()

        label = f"combination {n} (route)"
        print(line(label, timed(combo, max(10, args.n // 20))))

    # 8 concurrent clients on the pair route
    def burst(_: int) -> float:
        t0 = time.perf_counter()
        route_pair()
        return (time.perf_counter() - t0) * 1000

    with ThreadPoolExecutor(8) as pool:
        values = list(pool.map(burst, range(args.n)))
    print(line("pair (route, 8 concurrent)", values))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
