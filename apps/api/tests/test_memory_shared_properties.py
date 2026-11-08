"""User layers: release rules, sibling rule, interface for outcomes (design §10: P16-P19, P30).

Database tests run against real PostgreSQL 16 (`JANUS_TEST_DATABASE_URL`, after migrations).
"""

from __future__ import annotations

import base64
import datetime as dt
import os
from collections.abc import Iterator, Sequence
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.db.pool import Database
from janus.main import create_app
from janus.memory import messages
from janus.memory.disclosure import keyed_noise_source
from janus.memory.schemas import FaersCommon, SharedIn, SharedOut
from janus.memory.shared import (
    ContributionsSource,
    ContributorCell,
    UserLayerSource,
    shared,
    sibling_rule_count,
)
from janus.settings import Settings
from tests.conftest import DB_EXAMPLES
from tests.harness import assert_stateless, capture_logs, isolated_tempdir
from tests.memory_counts import mk
from tests.sentinels import leaked

POOL = ["Q11", "Q12", "Q13"]
EVENT = "cough"
KEY = b"k" * 32
NOISE = keyed_noise_source(KEY)
K = 20
EPS = Fraction(1)
MONDAY = dt.date(2026, 11, 2)
SOURCES: dict[str, UserLayerSource] = {"contributions": ContributionsSource()}

INSERT = (
    "INSERT INTO contributions (report_week, age_band, sex, region, ingredients, event, direction, "
    "consent_version, deletion_token_hash) VALUES (%s, 40, NULL, %s, %s, %s, %s, 'v1', %s)"
)


def reset(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM contributions")


def add(
    conn: psycopg.Connection,
    region: str,
    ingredients: Sequence[str],
    n: int,
    event: str = EVENT,
    direction: str = "adverse",
) -> None:
    rows = [
        (MONDAY, region, sorted(ingredients), event, direction, os.urandom(32)) for _ in range(n)
    ]
    with conn.cursor() as cur:
        cur.executemany(INSERT, rows)


def ask(
    conn: psycopg.Connection, ingredients: Sequence[str], *, layer: str = "contributions"
) -> SharedOut:
    req = mk(SharedIn, layer=layer, ingredients=list(ingredients), event=EVENT, direction="adverse")
    return shared(req, sources=SOURCES, conn=conn, noise_source=NOISE, k=K, epsilon=EPS)


def true_counts(conn: psycopg.Connection, ingredients: Sequence[str]) -> dict[str, int]:
    rows = conn.execute(
        "SELECT region, count(*) FROM contributions WHERE ingredients @> %s::text[] "
        "AND event = %s AND direction = 'adverse' GROUP BY region",
        (sorted(ingredients), EVENT),
    ).fetchall()
    return {str(r): int(n) for r, n in rows}


pytestmark = pytest.mark.db


@pytest.fixture
def conn(db_conn: psycopg.Connection) -> Iterator[psycopg.Connection]:
    reset(db_conn)
    yield db_conn
    reset(db_conn)


counts = st.integers(0, 45)


@st.composite
def donations(draw: st.DrawFn) -> list[tuple[str, tuple[str, ...], int]]:
    """(region, ingredient set of the donation, how many donations)."""
    out: list[tuple[str, tuple[str, ...], int]] = []
    for region in ("TR", "EU", "US"):
        for _ in range(draw(st.integers(0, 3))):
            ings = draw(st.lists(st.sampled_from(POOL), min_size=1, max_size=3, unique=True))
            out.append((region, tuple(sorted(ings)), draw(counts)))
    return out


# --- P16 ---------------------------------------------------------------------------------------


@settings(max_examples=DB_EXAMPLES, deadline=None)
@given(donations(), st.sampled_from([["Q11"], ["Q11", "Q12"], ["Q12"], ["Q11", "Q12", "Q13"]]))
def test_release_rules(
    db_conn: psycopg.Connection, plan: list[tuple[str, tuple[str, ...], int]], asked: list[str]
) -> None:
    """Feature: collective-memory, Property P16 — Validates: Req 4.5, 4.6, 5.1, 5.2, 5.4.
    Hidden cells carry no value; released values are integers >= 0 and repeat; the total is the sum
    of released values; a hidden cell's count changing (below 20) changes nothing in the answer.
    """
    reset(db_conn)
    for region, ings, n in plan:
        add(db_conn, region, ings, n)
    first = ask(db_conn, asked)
    assert first.status == "ok" and [c.region for c in first.cells] == ["TR", "EU", "US"]
    assert ask(db_conn, asked) == first  # deterministic: same cell, same contributors
    released = [c for c in first.cells if c.status == "released"]
    for c in first.cells:
        if c.status == "hidden":
            assert c.value is None
        else:
            assert isinstance(c.value, int) and c.value >= 0
    assert first.total_of_released == (sum(c.value or 0 for c in released) if released else None)
    truth = true_counts(db_conn, asked)
    for c in first.cells:
        if truth.get(c.region, 0) < K:
            assert c.status == "hidden"  # suppression is decided on the true count
    # a donation to a hidden cell (still below 20 afterwards) changes nothing visible
    hidden = [
        c.region for c in first.cells if c.status == "hidden" and truth.get(c.region, 0) < K - 1
    ]
    if hidden:
        add(db_conn, hidden[0], asked, 1)
        assert ask(db_conn, asked) == first
    # an unrelated event changes nothing
    add(db_conn, "US", asked, 3, event="insomnia")
    assert ask(db_conn, asked) == first
    reset(db_conn)


def test_hidden_looks_the_same_for_every_true_count_below_k(conn: psycopg.Connection) -> None:
    """Feature: collective-memory, Property P16 — Validates: Req 5.4."""
    answers: list[str] = []
    for n in range(0, K):
        reset(conn)
        add(conn, "TR", ["Q11"], n)
        answers.append(ask(conn, ["Q11"]).model_dump_json())
    assert len(set(answers)) == 1


def test_deleting_a_donation_changes_the_version_and_drops_it_from_the_count(
    conn: psycopg.Connection,
) -> None:
    """Feature: collective-memory, Property P16 — Validates: Req 4.6."""
    add(conn, "US", ["Q11"], 30)
    src = ContributionsSource()
    before = {c.region: c for c in src.cells(conn, ["Q11"], EVENT, "adverse")}["US"]
    conn.execute("DELETE FROM contributions WHERE id = (SELECT id FROM contributions LIMIT 1)")
    after = {c.region: c for c in src.cells(conn, ["Q11"], EVENT, "adverse")}["US"]
    assert after.n == before.n - 1 and after.version != before.version
    add(conn, "US", ["Q11"], 2, event="insomnia")  # another event: same version
    again = {c.region: c for c in src.cells(conn, ["Q11"], EVENT, "adverse")}["US"]
    assert again.version == after.version


# --- P30 ---------------------------------------------------------------------------------------


@settings(max_examples=300, deadline=None)
@given(
    st.integers(0, 80),
    st.dictionaries(st.sampled_from(["Q1", "Q2", "Q3", "Q4"]), st.integers(0, 80), max_size=4),
)
def test_sibling_rule_is_pure_and_exact(n: int, raw: dict[str, int]) -> None:
    """Feature: collective-memory, Property P30 (pure part) — Validates: Req 5.8."""
    siblings = {k: min(m, n) for k, m in raw.items()}
    cell = ContributorCell("US", n, "v", siblings)
    got = sibling_rule_count(cell, K)
    ok = n >= K and all(n - m == 0 or n - m >= K for m in siblings.values())
    assert got == (n if ok else 0)


@settings(max_examples=DB_EXAMPLES, deadline=None)
@given(donations())
def test_nested_released_cells_never_differ_by_a_small_group(
    db_conn: psycopg.Connection, plan: list[tuple[str, tuple[str, ...], int]]
) -> None:
    """Feature: collective-memory, Property P30 — Validates: Req 5.8.
    For any released S inside T (same event, direction, region), n_S - n_T is 0 or at least 20;
    an ineligible cell is answered exactly like a cell under k.
    """
    reset(db_conn)
    for region, ings, n in plan:
        add(db_conn, region, ings, n)
    sets = [list(c) for r in (1, 2, 3) for c in combinations(POOL, r)]
    answers = {tuple(s): ask(db_conn, s) for s in sets}
    truths = {tuple(s): true_counts(db_conn, s) for s in sets}
    for s, t in ((a, b) for a in sets for b in sets if set(a) < set(b)):
        for i, region in enumerate(("TR", "EU", "US")):
            if (
                answers[tuple(s)].cells[i].status == "released"
                and answers[tuple(t)].cells[i].status == "released"
            ):
                diff = truths[tuple(s)].get(region, 0) - truths[tuple(t)].get(region, 0)
                assert diff == 0 or diff >= K, (s, t, region)
    for s in sets:
        for i, region in enumerate(("TR", "EU", "US")):
            cell = answers[tuple(s)].cells[i]
            if truths[tuple(s)].get(region, 0) < K:
                assert cell.status == "hidden" and cell.value is None
    reset(db_conn)


def test_a_cell_next_to_a_small_sibling_is_hidden(conn: psycopg.Connection) -> None:
    """Feature: collective-memory, Property P30 — Validates: Req 5.8."""
    add(conn, "US", ["Q11"], 25)  # alone
    add(conn, "US", ["Q11", "Q12"], 25)  # 25 donations also name Q12: Q11 alone is 25 -> fine
    assert ask(conn, ["Q11"]).cells[2].status == "released"
    reset(conn)
    add(conn, "US", ["Q11"], 3)  # 3 donations name only Q11
    add(conn, "US", ["Q11", "Q12"], 30)  # Q11 has 33; Q11+Q12 has 30: they differ by 3
    assert ask(conn, ["Q11"]).cells[2].status == "hidden"  # n >= 20 but its sibling gap is 3
    assert ask(conn, ["Q11", "Q12"]).cells[2].status == "released"  # the nested cell is safe


# --- P17, P18, P19 -----------------------------------------------------------------------------


def test_no_cross_layer_number() -> None:
    """Feature: collective-memory, Property P17 — Validates: Req 4.3, 4.4."""
    user = set(SharedOut.model_fields)
    faers = set(FaersCommon.model_fields)
    assert not user & {"stats", "snapshot", "citation", "estimates", "cells_raw", "events"}
    assert not faers & {"value", "total_of_released", "disclosure"}
    assert "stats" not in SharedOut.model_fields


@settings(max_examples=40, deadline=None)
@given(st.sampled_from(["no_database", "no_key"]), st.sampled_from(["contributions"]))
def test_no_key_or_no_database_means_no_count(how: str, layer: str) -> None:
    """Feature: collective-memory, Property P18 — Validates: Req 5.5."""
    req = mk(SharedIn, layer=layer, ingredients=["Q11"], event=EVENT, direction="adverse")
    out = shared(
        req,
        sources=SOURCES,
        conn=None,
        noise_source=None if how == "no_key" else NOISE,
        k=K,
        epsilon=EPS,
    )
    assert out.status == "layer_unavailable" and out.cells == [] and out.total_of_released is None


def test_without_a_noise_key_nothing_is_released(conn: psycopg.Connection) -> None:
    add(conn, "US", ["Q11"], 60)
    req = mk(SharedIn, layer="contributions", ingredients=["Q11"], event=EVENT, direction="adverse")
    out = shared(req, sources=SOURCES, conn=conn, noise_source=None, k=K, epsilon=EPS)
    assert out.status == "layer_unavailable" and out.cells == []


class StubOutcomes:
    """A stand-in for the doctor-loop outcome store: same cells, same release rules."""

    def __init__(self, n: int) -> None:
        self.n = n

    def cells(
        self, conn: psycopg.Connection, ingredients: Sequence[str], event: str, direction: str
    ) -> list[ContributorCell]:
        return [ContributorCell("EU", self.n, "outcome-v1", {})]


def test_outcomes_interface(conn: psycopg.Connection) -> None:
    """Feature: collective-memory, Property P19 — Validates: Req 4.7."""
    req = mk(SharedIn, layer="outcomes", ingredients=["Q11"], event=EVENT, direction="adverse")
    none = shared(req, sources=SOURCES, conn=conn, noise_source=NOISE, k=K, epsilon=EPS)
    assert none.status == "not_available" and none.cells == [] and none.total_of_released is None
    for n, status in ((5, "hidden"), (40, "released")):
        out = shared(
            req,
            sources={**SOURCES, "outcomes": StubOutcomes(n)},
            conn=conn,
            noise_source=NOISE,
            k=K,
            epsilon=EPS,
        )
        assert out.status == "ok" and out.cells[1].status == status


# --- the route ---------------------------------------------------------------------------------


@pytest.fixture
def client(db_url: str) -> Iterator[TestClient]:
    key = base64.urlsafe_b64encode(KEY).decode()
    env = {"DATABASE_URL": db_url, "JANUS_NOISE_KEY": key}
    db = Database(db_url)
    db.open()
    app = create_app(Settings.from_env(env), database=db, configure_logs=False)
    yield TestClient(app, raise_server_exceptions=False)
    db.close()


def test_route_contract_and_statelessness(client: TestClient, conn: psycopg.Connection) -> None:
    add(conn, "US", ["Q11"], 40)
    body = {
        "layer": "contributions",
        "ingredients": ["Q11"],
        "event": EVENT,
        "direction": "adverse",
    }
    with isolated_tempdir() as tmp:
        r = assert_stateless(conn, tmp, lambda: client.post("/memory/shared", json=body))
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    out = r.json()
    assert out["status"] == "ok" and out["disclosure"] == {
        "k": 20,
        "epsilon": "1",
        "wording": "hidden_under_20_noise_added",
    }
    assert [c["region"] for c in out["cells"]] == ["TR", "EU", "US"]
    assert out["cells"][2]["status"] == "released" and isinstance(out["cells"][2]["value"], int)
    assert out["cells"][0] == {"region": "TR", "status": "hidden", "value": None}
    assert client.post("/memory/shared", json=body).content == r.content
    assert out["notices"] == ["hidden_under_20_noise_added"]
    assert not leaked(r.text.lower(), ["people", "patient", "person"])


def test_route_errors_and_logs(client: TestClient, conn: psycopg.Connection) -> None:
    body: dict[str, Any] = {
        "layer": "contributions",
        "ingredients": ["Q11"],
        "event": EVENT,
        "direction": "adverse",
    }
    assert client.post("/memory/shared", json={**body, "event": "no_such_key"}).status_code == 422
    assert client.post("/memory/shared", json={**body, "layer": "faers"}).status_code == 422
    assert client.post("/memory/shared", json={**body, "extra": 1}).status_code == 422
    assert (
        client.post("/memory/shared", json={**body, "ingredients": ["Q11", "Q11"]}).status_code
        == 422
    )
    # doctor-loop registers the outcome store: the layer answers, hidden like any cell under 20
    out = client.post("/memory/shared", json={**body, "layer": "outcomes"}).json()
    assert out["status"] == "ok"
    assert all(c["status"] == "hidden" and c["value"] is None for c in out["cells"])
    with capture_logs() as logs:
        client.post("/memory/shared", json={**body, "ingredients": ["Q99999"]})
    assert not leaked(logs.getvalue(), ["Q99999", EVENT])


def test_messages_used_exist() -> None:
    assert "hidden_under_20_noise_added" in messages.SENTENCES
    assert "layer_unavailable" in messages.SENTENCES and "not_available" in messages.SENTENCES
    _ = Path
