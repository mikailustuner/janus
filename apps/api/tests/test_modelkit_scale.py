"""The model kit at the size of the pool (milestone M2): hundreds of drugs, the release is built
once, the list and the drug routes stay fast, the list is paged."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from janus.main import create_app
from janus.modelkit.store import ModelkitHolder
from tests.modelkit_helpers import seed_dicts, write_run

N = 600


@pytest.fixture(scope="module")
def big(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[TestClient, float]]:
    base = seed_dicts()
    rows: list[dict[str, Any]] = []
    for i in range(N // 6):  # the six seed drugs, copied under new names
        for r in base:
            rows.append({**r, "drug_key": f"{r['drug_key']}_{i:03d}"[:32]})
    data_dir: Path = tmp_path_factory.mktemp("big")
    write_run(data_dir, rows)
    app: FastAPI = create_app(configure_logs=False)
    app.state.modelkit = ModelkitHolder(data_dir)
    with TestClient(app) as cl:
        t0 = time.perf_counter()
        assert cl.get("/modelkit/drugs").status_code == 200  # first call builds the release
        yield cl, time.perf_counter() - t0


def test_the_release_builds_once_and_holds_the_pool(big: tuple[TestClient, float]) -> None:
    cl, build_s = big
    body = cl.get("/modelkit/drugs", params={"limit": 200}).json()
    assert body["total"] == body["counts"]["all"] == N
    assert len(body["drugs"]) == 200
    assert build_s < 60  # one-time cost of building 600 drugs


def test_list_and_detail_routes_are_fast_at_scale(big: tuple[TestClient, float]) -> None:
    cl, _ = big
    key = cl.get("/modelkit/drugs", params={"q": "sunitinib", "limit": 1}).json()["drugs"][0]["key"]
    for path in ("/modelkit/drugs?limit=50", f"/modelkit/drugs/{key}", "/modelkit/validation"):
        cl.get(path)
        t0 = time.perf_counter()
        for _ in range(5):
            assert cl.get(path).status_code == 200
        assert (time.perf_counter() - t0) / 5 < 0.3, path  # plan section 11: p95 under 300 ms


def test_search_pages_cover_the_whole_list_once(big: tuple[TestClient, float]) -> None:
    cl, _ = big
    seen: list[str] = []
    offset = 0
    while True:
        page = cl.get("/modelkit/drugs", params={"limit": 200, "offset": offset}).json()
        seen += [d["key"] for d in page["drugs"]]
        offset += 200
        if offset >= page["total"]:
            break
    assert len(seen) == len(set(seen)) == N
