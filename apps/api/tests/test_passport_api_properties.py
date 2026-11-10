"""`POST /passport/presence` over HTTP (medication-passport task 7, design §3, §4.2).

Feature: medication-passport, Properties P11 (stateless, silent logs, closed schema, no echo),
P12 (validation bounds and boundary values), P13 (every answer names its source; missing sources;
Germany; staleness), P14 (503 cases with nothing partial), P15 (constant statement budget).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any, cast

import psycopg
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.db.pool import Database
from janus.integrity.freshness import is_stale
from janus.main import create_app
from janus.passport import repository, service
from janus.passport import router as passport_router
from janus.passport.forms import FormTable, load
from janus.passport.schemas import PresenceIn
from janus.settings import Settings
from tests.conftest import DB_EXAMPLES
from tests.harness import assert_stateless, capture_logs, isolated_tempdir
from tests.passport_db import KEYS, PRODUCT_SOURCES, SOURCE_DATES, Ing, Product, install
from tests.resolution_db import reset
from tests.sentinels import leaked, sentinels

pytestmark = pytest.mark.db
TODAY = dt.date(2026, 11, 8)
URL = "/passport/presence"
JSON = {"content-type": "application/json"}
DATA = [
    Product("openfda_ndc", "TABLET", ("ORAL",), (Ing("mapped", KEYS[0], "5 mg/1", "TESTNAME"),)),
    Product("eu_fr_bdpm", "gélule", ("orale",), (Ing("mapped", KEYS[0], "5 mg", "TESTNAME"),)),
    Product("titck", None, (), (Ing("mapped", KEYS[1], None, "TESTNAME"),)),
]


@pytest.fixture(scope="module")
def env(db_url: str) -> Iterator[tuple[TestClient, Database]]:
    database = Database(db_url)
    database.open()
    app = create_app(Settings.from_env({}), database=database)
    old = passport_router.today
    passport_router.today = lambda: TODAY
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, database
    passport_router.today = old
    database.close()
    with psycopg.connect(db_url, autocommit=True) as conn:
        reset(conn)


def body_of(keys: list[list[str]], form: str | None = None) -> dict[str, Any]:
    return {"items": [{"ingredients": [{"key": k} for k in ks], "dose_form": form} for ks in keys]}


qkeys = st.integers(1, 10**9 - 1).map(lambda n: f"Q{n}")


# --- P11 ---------------------------------------------------------------------------------------
@settings(max_examples=DB_EXAMPLES)
@given(
    keys=st.lists(st.lists(qkeys, min_size=1, max_size=3, unique=True), min_size=1, max_size=5),
    secret=sentinels(),
    mode=st.sampled_from(["valid", "extra_field", "bad_key", "demo", "candidate_id", "not_json"]),
)
def test_p11_stateless_silent_closed(
    env: tuple[TestClient, Database],
    db_conn: psycopg.Connection,
    keys: list[list[str]],
    secret: str,
    mode: str,
) -> None:
    """Feature: medication-passport, Property P11. Validates Req 4.1-4.3, 5.2, 9.1, 9.2."""
    client, _ = env
    install(db_conn, DATA)
    body: Any = body_of(keys)
    if mode == "extra_field":
        body["items"][0]["name"] = secret
    elif mode == "bad_key":
        body["items"][0]["ingredients"][0]["key"] = secret
    elif mode == "demo":
        body["demo"] = secret
    elif mode == "candidate_id":
        body["items"][0]["candidate_id"] = f"TR:titck:{secret}"
    with capture_logs() as logs, isolated_tempdir() as tmp:
        if mode == "not_json":
            r = assert_stateless(
                db_conn, tmp, lambda: client.post(URL, content=secret.encode(), headers=JSON)
            )
        else:
            r = assert_stateless(db_conn, tmp, lambda: client.post(URL, json=body))
    assert r.headers["cache-control"] == "no-store"
    flat = [k for ks in keys for k in ks]
    assert leaked(logs.getvalue(), [secret, *flat]) == []
    if mode == "valid":
        assert r.status_code == 200, r.text
        assert secret not in r.text
    else:
        assert r.status_code == 422
        out = r.json()
        assert out["error"] == "invalid_request" and set(out) == {"error", "fields"}
        assert secret not in r.text and not any(k in r.text for k in flat)


def test_p11_closed_schema() -> None:
    """Feature: medication-passport, Property P11: every string field of the request has a pattern
    or a literal; unknown fields are rejected."""
    schema = PresenceIn.model_json_schema()

    def walk(node: Any) -> Iterator[dict[str, Any]]:
        if isinstance(node, dict):
            d = cast(dict[str, Any], node)
            if d.get("type") == "string":
                yield d
            for v in d.values():
                yield from walk(v)
        elif isinstance(node, list):
            for v in cast(list[Any], node):
                yield from walk(v)

    strings = list(walk(schema))
    assert strings and all("pattern" in s or "enum" in s or "const" in s for s in strings)
    defs = cast(dict[str, Any], schema["$defs"])
    assert all(d.get("additionalProperties") is False for d in defs.values() if "properties" in d)
    assert schema.get("additionalProperties") is False


# --- P12 ---------------------------------------------------------------------------------------
GOOD_STRENGTH = {"amount": "5000", "unit": "ug", "basis": "unit"}
NEAR_MISSES: list[tuple[Any, str]] = [
    ({"items": []}, "items"),
    (body_of([[f"Q{n}"] for n in range(1, 52)]), "items"),
    (body_of([[]]), "items.0.ingredients"),
    (body_of([[f"Q{n}" for n in range(1, 12)]]), "items.0.ingredients"),
    (body_of([["Q1", "Q1"]]), "items.0.ingredients"),
    (
        body_of([[f"Q{n}" for n in range(i * 10 + 1, i * 10 + 11)] for i in range(5)] + [["Q99"]]),
        "items",
    ),
    (body_of([["Q0"]]), "items.0.ingredients.0.key"),
    (body_of([["J0"]]), "items.0.ingredients.0.key"),
    (body_of([["aspirin"]]), "items.0.ingredients.0.key"),
    (body_of([["Q1"]], form="tablet"), "items.0.dose_form"),
    (body_of([["Q1"]], form="OTHER"), "items.0.dose_form"),
    (
        {"items": [{"ingredients": [{"key": "Q1", "strength": {**GOOD_STRENGTH, "amount": "0"}}]}]},
        "items.0.ingredients.0.strength.amount",
    ),
    (
        {
            "items": [
                {"ingredients": [{"key": "Q1", "strength": {**GOOD_STRENGTH, "amount": "5.0"}}]}
            ]
        },
        "items.0.ingredients.0.strength.amount",
    ),
    (
        {
            "items": [
                {"ingredients": [{"key": "Q1", "strength": {**GOOD_STRENGTH, "amount": "05"}}]}
            ]
        },
        "items.0.ingredients.0.strength.amount",
    ),
    (
        {"items": [{"ingredients": [{"key": "Q1", "strength": {**GOOD_STRENGTH, "amount": 5}}]}]},
        "items.0.ingredients.0.strength.amount",
    ),
    (
        {"items": [{"ingredients": [{"key": "Q1", "strength": {**GOOD_STRENGTH, "unit": "mg"}}]}]},
        "items.0.ingredients.0.strength.unit",
    ),
    (
        {
            "items": [
                {"ingredients": [{"key": "Q1", "strength": {**GOOD_STRENGTH, "basis": "tablet"}}]}
            ]
        },
        "items.0.ingredients.0.strength.basis",
    ),
    ({"items": [{"ingredients": [{"key": 1}]}]}, "items.0.ingredients.0.key"),
]
BOUNDARIES: list[Any] = [
    body_of([["Q1"]]),
    body_of([[f"Q{n}" for n in range(1, 11)]]),
    body_of([[f"Q{n}"] for n in range(1, 51)]),
    body_of([[f"Q{n}" for n in range(i * 10 + 1, i * 10 + 11)] for i in range(5)]),
    {
        "items": [
            {"ingredients": [{"key": "J1", "strength": {**GOOD_STRENGTH, "amount": "0.000001"}}]}
        ]
    },
    {
        "items": [
            {"ingredients": [{"key": "Q1", "strength": {**GOOD_STRENGTH, "amount": "999999999"}}]}
        ]
    },
]


@pytest.mark.parametrize(("body", "field"), NEAR_MISSES)
def test_p12_near_misses_name_the_field(
    env: tuple[TestClient, Database], db_conn: psycopg.Connection, body: Any, field: str
) -> None:
    """Feature: medication-passport, Property P12. Validates Req 5.1, 5.2."""
    install(db_conn, DATA)
    r = env[0].post(URL, json=body)
    assert r.status_code == 422, r.text
    assert any(f == field or f.startswith(field + ".") for f in r.json()["fields"]), r.json()


@pytest.mark.parametrize("body", BOUNDARIES)
def test_p12_boundaries_are_accepted(
    env: tuple[TestClient, Database], db_conn: psycopg.Connection, body: Any
) -> None:
    """Feature: medication-passport, Property P12. Validates Req 5.1: 1, 10, 50 are accepted."""
    install(db_conn, DATA)
    r = env[0].post(URL, json=body)
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == len(body["items"])


# --- P13 ---------------------------------------------------------------------------------------
@settings(max_examples=DB_EXAMPLES)
@given(
    loaded=st.lists(st.sampled_from(PRODUCT_SOURCES), max_size=6, unique=True),
    days=st.integers(0, 60),
)
def test_p13_sources_named(
    env: tuple[TestClient, Database], db_conn: psycopg.Connection, loaded: list[str], days: int
) -> None:
    """Feature: medication-passport, Property P13. Validates Req 2.1, 5.4, 7.1, 7.4, 7.5."""
    install(db_conn, DATA, loaded)
    day = dt.date(2026, 11, 1) + dt.timedelta(days=days)
    passport_router.today = lambda: day
    try:
        r = env[0].post(URL, json=body_of([[KEYS[0]], [KEYS[1]]]))
    finally:
        passport_router.today = lambda: TODAY
    assert r.status_code == 200, r.text
    out = r.json()
    ids = [s["source_id"] for s in out["sources"]]
    assert ids == [
        "titck",
        "eu_fr_bdpm",
        "eu_es_cima",
        None,
        "openfda_ndc",
        "eu_it_aifa",
        "ca_dpd",
    ]
    assert [(s["region"], s["country"]) for s in out["sources"][5:]] == [("EU", "IT"), ("CA", None)]
    for s in out["sources"]:
        sid = s["source_id"]
        assert s["as_published"] == (sid == "eu_fr_bdpm")
        if sid is None:
            assert (s["country"], s["status"], s["reason"]) == (
                "DE",
                "source_unavailable",
                "no_open_product_database",
            )
        elif sid in loaded:
            _, snap, cadence = SOURCE_DATES[sid]
            assert s["status"] == "loaded" and s["snapshot_date"] == snap
            assert s["attribution"] in ("titck", "bdpm", "cima", "openfda", "aifa", "dpd")
            assert s["stale"] == is_stale(dt.date.fromisoformat(snap), day, cadence)
        else:
            assert (s["status"], s["reason"]) == ("source_unavailable", "not_loaded")
    for item in out["items"]:
        assert [a["source"] for a in item["answers"]] == list(range(len(out["sources"])))
        for a, s in zip(item["answers"], out["sources"], strict=True):
            if s["status"] != "loaded":
                assert a["status"] == "source_unavailable" and a["comparison"] is None


# --- P14 ---------------------------------------------------------------------------------------
def _assert_503(r: Any) -> None:
    assert r.status_code == 503
    assert r.json() == {"error": "passport_unavailable"}


def test_p14_unavailable(
    env: tuple[TestClient, Database],
    db_conn: psycopg.Connection,
    db_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Feature: medication-passport, Property P14. Validates Req 5.3."""
    client, database = env
    body = body_of([[KEYS[0]]])
    reset(db_conn)  # no current dataset
    _assert_503(client.post(URL, json=body))
    install(db_conn, DATA)
    assert client.post(URL, json=body).status_code == 200
    app = cast(Any, client.app)
    table = app.state.dose_forms
    try:
        app.state.dose_forms = None  # table not loaded
        _assert_503(client.post(URL, json=body))
        app.state.dose_forms = FormTable(table.rows, table.version, reviewed=False)  # not accepted
        _assert_503(client.post(URL, json=body))
    finally:
        app.state.dose_forms = table
    monkeypatch.setattr(repository, "STATEMENT_TIMEOUT", "50ms")
    monkeypatch.setattr(
        repository,
        "PRESENCE_SQL",
        "SELECT 1 FROM pg_sleep(1) WHERE %(d)s::text <> '' AND %(keys)s::text[] IS NOT NULL",
    )
    _assert_503(client.post(URL, json=body))  # statement timeout
    monkeypatch.undo()
    no_db = create_app(Settings.from_env({}), database=None)
    with TestClient(no_db, raise_server_exceptions=False) as c:
        _assert_503(c.post(URL, json=body))
    del database, db_url


# --- P15 ---------------------------------------------------------------------------------------
class Counting:
    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn
        self.statements = 0

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        self.statements += 1
        return self.conn.execute(*args, **kwargs)


@settings(max_examples=20)
@given(n=st.integers(1, 50))
def test_p15_statement_budget(
    env: tuple[TestClient, Database], db_conn: psycopg.Connection, n: int
) -> None:
    """Feature: medication-passport, Property P15. Validates Req 13.2."""
    install(db_conn, DATA)
    counts: list[int] = []
    for size in (1, n):
        body = PresenceIn.model_validate(body_of([[f"Q{k}"] for k in range(1, size + 1)]))
        with env[1].read_only_tx() as conn:
            counter = Counting(conn)
            service.presence(cast(psycopg.Connection, counter), body, load(), TODAY)
            counts.append(counter.statements)
    assert counts[0] == counts[1] == 5  # timeout, current (2), known keys, presence
