"""Resolution routes over HTTP (drug-resolution design §8: P10, P22; task 12.3)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.db.pool import Database
from janus.main import create_app
from janus.resolution import router as resolution_router
from janus.resolution.load import load
from janus.settings import Settings
from tests.conftest import DB_EXAMPLES
from tests.harness import assert_stateless, capture_logs, isolated_tempdir
from tests.resolution_db import inputs, reset
from tests.resolution_strategies import (
    barcode13,
    titck_row,
    us_row,
    wikidata_row,
    with_check_digit,
)
from tests.sentinels import ascii_sentinels, sentinels

pytestmark = pytest.mark.db

BARCODES = [barcode13(i) for i in range(1, 4)]


@pytest.fixture(scope="module")
def client(db_url: str) -> Iterator[TestClient]:
    database = Database(db_url)
    database.open()
    with psycopg.connect(db_url, autocommit=True) as conn:
        reset(conn)
    wd = [wikidata_row("Q411347", ["C08CA01"], {"en": "amlodipine", "tr": "amlodipin"})]
    tr = [
        titck_row(b, f"AMLIPIN {i}", ["amlodipin besilat"], "C08CA01")
        for i, b in enumerate(BARCODES)
    ]
    us = [us_row("12345-678", ["12345-678-90"], ["amlodipine besylate"], ["ORAL"], brand="NORVASC")]
    load(database, inputs(tr, us, wd))
    app = create_app(Settings.from_env({}), database=database)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    database.close()


def _gtin(barcode: str) -> str:
    return "0" + barcode


@settings(max_examples=DB_EXAMPLES)
@given(
    barcode=st.sampled_from(BARCODES),
    serial=st.one_of(ascii_sentinels(), sentinels()),
    lot=st.one_of(ascii_sentinels(), sentinels()),
    form=st.sampled_from(["paren", "fnc1"]),
    extra=st.sampled_from(["", "(21)ZZDUPZZ", "(99)1"]),
)
def test_serial_and_lot_never_leave_the_parser(
    client: TestClient,
    db_conn: psycopg.Connection,
    barcode: str,
    serial: str,
    lot: str,
    form: str,
    extra: str,
) -> None:
    """Feature: drug-resolution, Property P10. Validates Req 1.4, 8.3, 8.4.

    Serial and lot values (valid or invalid, with or without a parse error) never appear in the
    response body or headers, in any log output, or in the database.
    """
    gtin = _gtin(barcode)
    if form == "paren":
        content = f"(01){gtin}(17)300131(21){serial}(10){lot}{extra}"
    else:
        content = (
            f"]d201{gtin}17300131"
            + f"21{serial}\x1d10{lot}"
            + extra.replace("(", "").replace(")", "")
        )
    with isolated_tempdir() as tmp, capture_logs() as logs:
        response = assert_stateless(
            db_conn, tmp, lambda: client.post("/resolve/scan", json={"content": content})
        )
    wire = response.text + " ".join(f"{k}: {v}" for k, v in response.headers.items())
    for secret in (serial, lot):
        assert secret not in wire
        assert secret not in logs.getvalue()
    assert response.headers["cache-control"] == "no-store"
    if response.status_code == 200:
        scan = response.json()["scan"]
        assert scan["serial_present"] and scan["lot_present"]


def _requests(value: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        ("/resolve/scan", {"content": value}),
        ("/resolve/scan", {"content": f"(01){_gtin(BARCODES[0])}(21){value}"}),
        ("/resolve/ndc", {"ndc": value}),
        ("/resolve/ndc", {"ndc": "12345-678-90"}),
        ("/resolve/search", {"query": value, "region": "TR"}),
        ("/resolve/search", {"query": value, "limit": 99}),
        ("/resolve/products", {"candidate_ids": [value]}),
        ("/resolve/products", {"candidate_ids": ["TR:titck:1", "US:openfda_ndc:1"]}),
        ("/resolve/search", {"query": "amlodipin", "extra": value}),
    ]


@settings(max_examples=DB_EXAMPLES)
@given(value=st.one_of(sentinels(), ascii_sentinels()), pick=st.integers(0, 8))
def test_routes_are_stateless_and_log_nothing(
    client: TestClient, db_conn: psycopg.Connection, value: str, pick: int
) -> None:
    """Feature: drug-resolution, Property P22. Validates Req 8.1-8.3.

    The four routes leave the database and the temp directory unchanged, send `no-store`, and
    no input value appears in any log output (valid requests and 422s alike).
    """
    path, body = _requests(value)[pick]
    with isolated_tempdir() as tmp, capture_logs() as logs:
        response = assert_stateless(db_conn, tmp, lambda: client.post(path, json=body))
    assert response.headers["cache-control"] == "no-store"
    assert response.status_code in (200, 422)
    assert value not in logs.getvalue()
    if response.status_code == 422:
        assert value not in response.text  # errors name fields, never values


def test_codes_only_in_the_body(client: TestClient) -> None:
    """Task 12.3, Req 8.2: no route takes a code in the path or the query string."""
    gtin = _gtin(BARCODES[0])
    assert client.get("/resolve/scan", params={"content": gtin}).status_code == 405
    assert client.post(f"/resolve/scan/{gtin}", json={}).status_code == 404
    ok = client.post("/resolve/scan", json={"content": gtin})
    assert ok.status_code == 200
    assert len(ok.json()["candidates"]) == 1
    assert "not medical advice" in ok.json()["disclaimer"]


def test_errors_and_override(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import datetime as dt

    monkeypatch.setattr(resolution_router, "today", lambda: dt.date(2026, 11, 8))
    bad_check = _gtin(BARCODES[0])[:-1] + str((int(BARCODES[0][-1]) + 1) % 10)
    r = client.post("/resolve/scan", json={"content": bad_check})
    assert (r.status_code, r.json()) == (422, {"error": "gtin_check_digit"})
    r = client.post("/resolve/ndc", json={"ndc": "12-34"})
    assert (r.status_code, r.json()) == (422, {"error": "ndc_malformed"})
    r = client.post("/resolve/scan", json={"content": _gtin(BARCODES[0]), "region": "US"})
    assert r.status_code == 200 and r.json()["regions_searched"] == ["US"]
    assert r.json()["candidates"] == []
    r = client.post("/resolve/scan", json={"content": with_check_digit("340093000000")})  # FR
    notices = [n["code"] for n in r.json()["notices"]]
    assert "region_adapter_not_available" in notices
    r = client.post("/resolve/ndc", json={"ndc": "1234567890"})
    assert r.status_code == 200 and [c["brand_name"] for c in r.json()["candidates"]] == ["NORVASC"]
