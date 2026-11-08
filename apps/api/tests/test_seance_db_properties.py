"""Séance science witness against the evidence store (séance design §4.4, §8): P21 and the
two-witness examples. Needs PostgreSQL (JANUS_TEST_DATABASE_URL)."""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from janus.db.pool import Database
from janus.integrity.load import gather, load
from janus.main import create_app
from janus.seance.catalogue import PAPERS_FILE, SCIENCE_SOURCE
from janus.settings import Settings
from tests.harness import assert_stateless, isolated_tempdir
from tests.integrity_db import REGISTRY, reset, retraction_row, write_artifacts
from tests.test_integrity_api_properties import DAY1

pytestmark = pytest.mark.db

RETRACTION = {
    "type": "retraction",
    "source": "retraction-watch",
    "notice_doi": "10.1000/retraction-notice",
    "date": "2026-11-05",
}


def _seance_dois() -> dict[str, str]:
    with PAPERS_FILE.open(encoding="utf-8", newline="") as f:
        return {r["key"]: r["doi"] for r in csv.DictReader(f) if r["source_id"] == SCIENCE_SOURCE}


def _client(db_url: str, conn: psycopg.Connection, root: Path, retracted: set[str]) -> Any:
    reset(conn)
    dois = _seance_dois()
    rows = [
        retraction_row(doi, "retracted", [RETRACTION])
        if key in retracted
        else retraction_row(doi, "ok")
        for key, doi in dois.items()
    ]
    write_artifacts(root, retractions=rows)
    database = Database(db_url)
    database.open()
    load(database, gather(root, REGISTRY, PAPERS_FILE), DAY1)
    return database


@pytest.fixture
def ok_client(db_url: str, db_conn: psycopg.Connection, tmp_path: Path) -> Iterator[TestClient]:
    database = _client(db_url, db_conn, tmp_path, set())
    app = create_app(Settings.from_env({}), database=database)
    with TestClient(app) as c:
        yield c
    database.close()


def _pair(c: TestClient, sub: str, cond: str) -> Any:
    r = c.post("/seance/pair", json={"substance": sub, "condition": cond})
    assert r.status_code == 200
    return r.json()


def test_two_witness_examples(ok_client: TestClient) -> None:
    """Gate 4 attempt: St John's wort / wound and vinegar / infection have the past and the
    science witness; the present witness is missing and says why. Honey / burn has science
    only; honey / wound's listed review does not support it."""
    d = _pair(ok_client, "st_johns_wort", "wound")
    assert d["supporting_witnesses"] == 2 and d["missing_witnesses"] == ["present"]
    assert d["witnesses"]["present"]["missing_reason"] == "no_faers_mapping"
    assert d["witnesses"]["science"]["items"][0]["study_type"] == "rct"
    assert d["substance"]["identification_label"] == "identified"
    assert d["headline"]["eligible"] is True

    d = _pair(ok_client, "vinegar", "infection")
    assert d["supporting_witnesses"] == 2 and d["missing_witnesses"] == ["present"]
    assert d["witnesses"]["science"]["confidence"] == "low"

    d = _pair(ok_client, "honey", "burn")
    assert d["supporting_witnesses"] == 1 and d["missing_witnesses"] == ["past", "present"]
    assert d["witnesses"]["science"]["confidence"] == "moderate"
    assert d["substance"]["identification_label"] == "uncertain"

    d = _pair(ok_client, "honey", "wound")
    assert d["witnesses"]["science"]["missing_reason"] == "studies_do_not_support"


def test_retracted_study_is_never_a_witness(
    db_url: str, db_conn: psycopg.Connection, tmp_path: Path
) -> None:
    """P21 (Req 4.3): when the trial is retracted the science witness drops it, lists it as
    excluded and falls silent; the count falls by one."""
    database = _client(db_url, db_conn, tmp_path, {"samadi_2010"})
    app = create_app(Settings.from_env({}), database=database)
    with TestClient(app) as c:
        d = _pair(c, "st_johns_wort", "wound")
    database.close()
    sci = d["witnesses"]["science"]
    assert not sci["supports"] and sci["missing_reason"] == "no_citable_study"
    assert sci["excluded"] == ["paper:seance_science:samadi_2010"]
    assert d["supporting_witnesses"] == 1


def test_seance_is_stateless(ok_client: TestClient, db_conn: psycopg.Connection) -> None:
    """Privacy: a séance request writes nothing to the database or to disk."""
    with isolated_tempdir() as tmp:
        assert_stateless(
            db_conn,
            tmp,
            lambda: ok_client.post(
                "/seance/pair", json={"substance": "vinegar", "condition": "infection"}
            ),
        )
