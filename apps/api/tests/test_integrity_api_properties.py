"""Evidence routes over HTTP (evidence-integrity design §6, §8): P17, P18, P19, P20 and examples."""

# ruff: noqa: RUF001
from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import psycopg
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.db.pool import Database
from janus.integrity import router as integrity_router
from janus.integrity.freshness import freshness
from janus.integrity.load import LoadInputs, gather, load
from janus.integrity.model import EvidenceRecord
from janus.integrity.schemas import DISCLAIMER
from janus.main import create_app
from janus.resolution.model import ResolutionResult
from janus.settings import Settings
from tests.conftest import DB_EXAMPLES
from tests.harness import assert_stateless, capture_logs, isolated_tempdir
from tests.integrity_db import (
    CORRECTION,
    NOTICE_DOI,
    PIPC_DOI,
    REGISTRY,
    reset,
    retraction_row,
    write_artifacts,
)
from tests.sentinels import ascii_sentinels, sentinels

pytestmark = pytest.mark.db

DAY1 = dt.date(2026, 11, 1)
DAY2 = dt.date(2026, 11, 7)
TODAY = dt.date(2026, 11, 8)
PAPER_DOI = "10.1136/bmj-2025-100499"
RETRACTION = {
    "type": "retraction",
    "source": "retraction-watch",
    "notice_doi": "10.1000/retraction-notice",
    "date": "2026-11-05",
}
PAPER = "paper:bmj_2026:e100499"
KNOWN_IDS = ["dataset:pipc", "dataset:titck", PAPER, "rule:pipc:12", "rule:bmj:1"]


def _rule(rid: str, source: str, basis: tuple[str, ...]) -> EvidenceRecord:
    return EvidenceRecord(
        id=rid,
        kind="rule",
        source_id=source,
        source_url="https://example.org/rule",
        license="CC BY 4.0",
        region=None,
        snapshot_date=dt.date(2025, 7, 31),
        snapshot_is_retrieval_time=False,
        locator="Table 1, row 12",
        basis=basis,
    )


def _inputs(root: Path, rows: list[dict[str, Any]], run: str) -> LoadInputs:
    root.mkdir(parents=True, exist_ok=True)
    papers = root / "evidence_papers.csv"
    papers.write_text(
        "key,doi,source_id,title,verified_on,note\n"
        f"e100499,{PAPER_DOI},bmj_2026,BMJ 2026 e100499,2026-11-07,\n",
        encoding="utf-8",
    )
    write_artifacts(root, retractions=rows, run=run)
    base = gather(root, REGISTRY, papers)
    return replace(
        base,
        records=(
            *base.records,
            _rule("rule:pipc:12", "pipc", ("dataset:pipc",)),
            _rule("rule:bmj:1", "pipc", (PAPER,)),
        ),
    )


@pytest.fixture
def client(
    db_url: str, db_conn: psycopg.Connection, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """Two loads: everything `ok` on 2026-11-01; on 2026-11-07 the PIPC paper is corrected and
    the BMJ paper is retracted."""
    monkeypatch.setattr(integrity_router, "today", lambda: TODAY)
    database = Database(db_url)
    database.open()
    reset(db_conn)
    first = [retraction_row(PIPC_DOI, "ok"), retraction_row(PAPER_DOI, "ok")]
    second = [
        retraction_row(PIPC_DOI, "corrected", [CORRECTION]),
        retraction_row(PAPER_DOI, "retracted", [RETRACTION]),
    ]
    load(database, _inputs(tmp_path / "a", first, "r1"), DAY1)
    load(database, _inputs(tmp_path / "b", second, "r2"), DAY2)
    app = create_app(Settings.from_env({}), database=database)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    database.close()


def _resolve(client: TestClient, ids: list[str]) -> Any:
    return client.post("/evidence/resolve", json={"evidence_ids": ids})


# --- examples -------------------------------------------------------------------------------


def test_pipc_evidence_as_the_api_returns_it(client: TestClient) -> None:
    r = _resolve(client, ["dataset:pipc", "rule:pipc:12"])
    assert r.status_code == 200
    body = r.json()
    assert body["disclaimer"] == DISCLAIMER == ResolutionResult.model_fields["disclaimer"].default
    pipc, rule = body["items"]
    assert pipc["id"] == "dataset:pipc" and rule["id"] == "rule:pipc:12"
    assert pipc["citable"] and pipc["doi"] == PIPC_DOI
    assert pipc["integrity"]["status"] == "corrected"
    assert pipc["integrity"]["checked_at"] == "2026-11-07"
    assert pipc["integrity"]["notices"] == [
        {
            "type": "correction",
            "source": "publisher",
            "date": "2025-12-18",
            "notice_doi": NOTICE_DOI,
            "notice_url": f"https://doi.org/{NOTICE_DOI}",
        }
    ]
    assert pipc["freshness"] == {"state": "current", "age_days": 465, "limit_days": 730}
    assert "corrected_notice" in pipc["codes"]
    (root,) = rule["roots"]
    assert (
        root["id"] == "dataset:pipc" and root["integrity"]["notices"][0]["notice_doi"] == NOTICE_DOI
    )
    assert rule["citable"] and "corrected_notice" in rule["codes"]
    line = body["line"]
    assert (line["sources_total"], line["checked_by_doi"], line["no_retracted_used"]) == (
        1,
        1,
        True,
    )
    assert line["by_status"]["corrected"] == 1
    assert line["oldest_check"] == "2026-11-07"
    assert body["citable_ids"] == ["dataset:pipc", "rule:pipc:12"]


def test_retracted_paper_is_excluded_and_its_rule_is_not_citable(client: TestClient) -> None:
    body = _resolve(client, [PAPER, "rule:bmj:1", "dataset:pipc", "nope:x:y"]).json()
    assert body["citable_ids"] == ["dataset:pipc"]
    assert {(e["id"], e["reason"]) for e in body["excluded"]} == {
        (PAPER, "retracted"),
        ("rule:bmj:1", "no_citable_basis"),
        ("nope:x:y", "not_registered"),
    }
    paper = next(i for i in body["items"] if i["id"] == PAPER)
    assert paper["integrity"]["status"] == "retracted" and not paper["citable"]
    assert "excluded_retracted" in paper["codes"]
    assert paper["integrity"]["notices"][0]["type"] == "retraction"
    assert body["line"]["no_retracted_used"] is True
    assert body["line"]["sources_total"] == 1


def test_changes_list(client: TestClient) -> None:
    body = client.post("/evidence/changes", json={}).json()
    assert body["since"] == "2026-11-07"
    assert body["observed_dates"] == ["2026-11-07"]
    got = {(c["evidence_id"], c["from_status"], c["to_status"]) for c in body["changes"]}
    assert got == {
        ("dataset:pipc", "ok", "corrected"),
        (PAPER, "ok", "retracted"),
    }
    assert body["status_counts"]["retracted"] == 1 and body["status_counts"]["corrected"] == 1
    later = client.post("/evidence/changes", json={"since": "2026-11-08"}).json()
    assert later["changes"] == []
    first = client.post("/evidence/changes", json={"since": "2026-11-01", "limit": 1}).json()
    assert len(first["changes"]) == 1


def test_routes_are_post_only_and_take_nothing_in_the_url(client: TestClient) -> None:
    assert (
        client.get("/evidence/resolve", params={"evidence_ids": "dataset:pipc"}).status_code == 405
    )
    assert client.post("/evidence/resolve/dataset:pipc", json={}).status_code == 404
    assert client.get("/evidence/changes").status_code == 405


def test_shared_freshness_rule_gives_14_days_for_weekly_sources() -> None:
    day = dt.date(2026, 11, 6)
    assert freshness(day, day + dt.timedelta(days=14), 7).state == "current"
    assert freshness(day, day + dt.timedelta(days=15), 7).state == "stale"


# --- P17: fail closed -----------------------------------------------------------------------


def test_p17_nothing_loaded_is_503_and_unregistered_is_not_citable(
    client: TestClient, db_conn: psycopg.Connection
) -> None:
    """Feature: evidence-integrity, Property P17 (Req 7.4)."""
    ok = _resolve(client, ["dataset:nothing:here"]).json()
    assert ok["items"][0]["registered"] is False
    assert ok["items"][0]["citable"] is False and ok["citable_ids"] == []
    assert ok["excluded"] == [{"id": "dataset:nothing:here", "reason": "not_registered"}]
    reset(db_conn)
    for path, body in (
        ("/evidence/resolve", {"evidence_ids": ["dataset:pipc"]}),
        ("/evidence/changes", {}),
    ):
        r = client.post(path, json=body)
        assert (r.status_code, r.json()) == (503, {"error": "integrity_unavailable"})


# --- P18: deterministic, order independent --------------------------------------------------


@settings(max_examples=DB_EXAMPLES, deadline=None)
@given(
    ids=st.lists(st.sampled_from([*KNOWN_IDS, "paper:s:unregistered"]), min_size=1, unique=True),
    data=st.data(),
)
def test_p18_response_is_order_independent(
    client: TestClient, ids: list[str], data: st.DataObject
) -> None:
    """Feature: evidence-integrity, Property P18 (route part) (Req 7.5)."""
    a = _resolve(client, ids)
    b = _resolve(client, data.draw(st.permutations(ids)))
    c = _resolve(client, sorted(ids))
    assert a.status_code == 200
    assert a.content == b.content == c.content == _resolve(client, ids).content


def test_p18_version_changes_with_content(client: TestClient, db_url: str, tmp_path: Path) -> None:
    v1 = _resolve(client, ["dataset:pipc"]).json()["integrity_version"]
    assert v1 == _resolve(client, ["dataset:titck"]).json()["integrity_version"]
    database = Database(db_url)
    database.open()
    try:
        rows = [
            retraction_row(PIPC_DOI, "corrected", [CORRECTION]),
            retraction_row(PAPER_DOI, "ok"),
        ]
        load(database, _inputs(tmp_path / "c", rows, "r3"), TODAY)
    finally:
        database.close()
    assert _resolve(client, ["dataset:pipc"]).json()["integrity_version"] != v1


def test_duplicate_ids_are_rejected(client: TestClient) -> None:
    r = _resolve(client, ["dataset:pipc", "dataset:pipc"])
    assert (r.status_code, r.json()["error"], r.json()["fields"]) == (
        422,
        "invalid_request",
        ["evidence_ids"],
    )


# --- P19: stateless and silent --------------------------------------------------------------


@settings(max_examples=DB_EXAMPLES, deadline=None)
@given(value=st.one_of(sentinels(), ascii_sentinels()), pick=st.integers(0, 5))
def test_p19_routes_are_stateless_and_log_nothing(
    client: TestClient, db_conn: psycopg.Connection, value: str, pick: int
) -> None:
    """Feature: evidence-integrity, Property P19 (Req 7.6, 8.5)."""
    requests: list[tuple[str, dict[str, Any]]] = [
        ("/evidence/resolve", {"evidence_ids": [f"paper:s:{value}"]}),
        ("/evidence/resolve", {"evidence_ids": [value]}),
        ("/evidence/resolve", {"evidence_ids": ["dataset:pipc"], "extra": value}),
        ("/evidence/resolve", {"evidence_ids": [f"dataset:{value}"]}),
        ("/evidence/changes", {"since": value}),
        ("/evidence/changes", {"limit": value}),
    ]
    path, body = requests[pick]
    with isolated_tempdir() as tmp, capture_logs() as logs:
        response = assert_stateless(db_conn, tmp, lambda: client.post(path, json=body))
    assert response.headers["cache-control"] == "no-store"
    assert value not in logs.getvalue()
    assert PIPC_DOI not in logs.getvalue() and NOTICE_DOI not in logs.getvalue()
    if response.status_code == 422:
        assert value not in response.text
    else:
        assert response.status_code == 200


def test_p19_real_ids_are_never_logged(client: TestClient, db_conn: psycopg.Connection) -> None:
    with isolated_tempdir() as tmp, capture_logs() as logs:
        r = assert_stateless(
            db_conn, tmp, lambda: _resolve(client, ["dataset:pipc", "rule:pipc:12"])
        )
    assert r.status_code == 200
    out = logs.getvalue()
    for secret in ("dataset:pipc", "rule:pipc:12", PIPC_DOI, NOTICE_DOI):
        assert secret not in out


# --- P20: validation and closed vocabulary --------------------------------------------------

ID_OK = st.sampled_from(KNOWN_IDS)
BAD_BODIES: list[Any] = [
    {},
    {"evidence_ids": []},
    {"evidence_ids": "dataset:pipc"},
    {"evidence_ids": [1]},
    {"evidence_ids": ["Dataset:pipc"]},
    {"evidence_ids": ["dataset"]},
    {"evidence_ids": ["dataset:pipc:" + "a" * 70]},
    {"evidence_ids": [f"paper:s:k{i}" for i in range(201)]},
    {"evidence_ids": ["dataset:pipc"], "other": 1},
    {"evidence_ids": ["dataset:pipc", "dataset:pipc"]},
    [],
    "dataset:pipc",
]


@pytest.mark.parametrize("body", BAD_BODIES)
def test_p20_resolve_rejects_near_misses(client: TestClient, body: Any) -> None:
    """Feature: evidence-integrity, Property P20 (Req 7.1, 7.6)."""
    r = client.post("/evidence/resolve", json=body)
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_request"
    assert isinstance(r.json()["fields"], list)


@given(n=st.integers(1, 200))
@settings(max_examples=10, deadline=None)
def test_p20_resolve_accepts_up_to_200(client: TestClient, n: int) -> None:
    ids = [f"paper:s:k{i}" for i in range(n)]
    assert _resolve(client, ids).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"since": "2026-13-01"},
        {"since": "2026-1-1"},
        {"since": "20261101"},
        {"since": 20261101},
        {"limit": 0},
        {"limit": 501},
        {"limit": "5"},
        {"limit": True},
        {"limit": 1.5},
        {"unknown": 1},
    ],
)
def test_p20_changes_rejects_near_misses(client: TestClient, body: Any) -> None:
    r = client.post("/evidence/changes", json=body)
    assert (r.status_code, r.json()["error"]) == (422, "invalid_request")


PHRASES = [
    "stop taking",
    "you should stop",
    "discontinue",
    "unnecessary medicine",
    "cure",
    "cures",
    "treatment for",
    "diagnosis",
    "you have",
    "safe to stop",
    "your medicines are safe",
    "ilacı bırakın",
    "ilacınızı kesin",
    "gereksiz ilaç",
    "tedavi eder",
    "tanı",
    "ilaçlarınız güvenli",
    "absetzen sie",
    "nicht mehr einnehmen",
    "unnötiges medikament",
    "heilt",
    "diagnose",
    "arrêtez de prendre",
    "médicament inutile",
    "guérit",
    "diagnostic",
    "deje de tomar",
    "medicamento innecesario",
    "cura",
    "diagnóstico",
]
STATUSES = {"ok", "corrected", "expression_of_concern", "retracted", "unknown"}
REASONS = {"retracted", "not_registered", "no_citable_basis"}
CODES = {
    "corrected_notice",
    "expression_of_concern_notice",
    "integrity_unknown",
    "source_may_be_outdated",
    "integrity_check_may_be_out_of_date",
    "excluded_retracted",
    "not_registered",
}


def test_p20_closed_vocabularies_and_no_forbidden_phrase(client: TestClient) -> None:
    body = _resolve(client, [*KNOWN_IDS, "paper:s:unregistered"]).json()
    seen: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            d = cast(dict[str, Any], value)
            seen.append(d)
            for v in d.values():
                walk(v)
        elif isinstance(value, list):
            for v in cast(list[Any], value):
                walk(v)

    walk(body)
    for d in seen:
        for key in ("status", "check_status"):
            if key in d:
                assert d[key] in STATUSES
        for key in ("reason", "exclusion_reason"):
            if d.get(key) is not None and "check_status" not in d:
                assert d[key] in REASONS | {None}
        for code in d.get("codes", []):
            assert code in CODES
    text = json.dumps(body, ensure_ascii=False).lower()
    for phrase in PHRASES:
        assert re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is None, phrase
    changes = client.post("/evidence/changes", json={}).json()
    for c in changes["changes"]:
        assert c["from_status"] in STATUSES and c["to_status"] in STATUSES
