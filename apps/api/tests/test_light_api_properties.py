"""`/light/*` routes against PostgreSQL: integrity filter, patient layer, errors, privacy.

Feature: light-face, Properties P1 (route), P8, P13, P14. Database tests (`janus_test`).
"""

from __future__ import annotations

import base64
import datetime as dt
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from janus.db.pool import Database
from janus.light import build as light_build
from janus.main import create_app
from janus.settings import Settings
from tests.harness import capture_logs
from tests.integrity_db import reset as reset_evidence
from tests.test_light_build_cards_properties import LABELS, PAPER, PAPER2, write_world

pytestmark = pytest.mark.db

NOISE_KEY = base64.urlsafe_b64encode(b"k" * 32).decode().rstrip("=")
MONDAY = dt.date(2026, 11, 2)
INSERT = (
    "INSERT INTO contributions (report_week, age_band, sex, region, ingredients, event, direction, "
    "consent_version, deletion_token_hash) VALUES (%s, 40, NULL, %s, %s, %s, 'benefit', 'v1', %s)"
)
RECORDS = [
    ("dataset:onsides", "dataset", "onsides", None),
    ("dataset:faers", "dataset", "faers", None),
    (PAPER, "paper", "yang_2011", "10.1371/journal.pone.0028025"),
    (PAPER2, "paper", "zappacosta_1980", "10.1056/nejm198012183032516"),
]


def seed(conn: psycopg.Connection, retracted: set[str]) -> None:
    reset_evidence(conn)
    conn.execute("DELETE FROM contributions")
    for sid in ("onsides", "faers", "yang_2011", "zappacosta_1980"):
        conn.execute(
            "INSERT INTO evidence_source (source_id, name, storage, cadence_days) "
            "VALUES (%s, %s, %s, %s)",
            (
                sid,
                sid,
                "cache" if sid in ("onsides", "faers") else "cited_only",
                91 if sid in ("onsides", "faers") else None,
            ),
        )
    for rid, kind, sid, doi in RECORDS:
        conn.execute(
            "INSERT INTO evidence (id, kind, source_id, source_url, license, region, "
            "snapshot_date, "
            "snapshot_is_retrieval_time, doi, locator, title) VALUES "
            "(%s, %s, %s, 'https://example.org/x', 'CC0', NULL, '2026-11-08', false, %s, NULL, %s)",
            (rid, kind, sid, doi, f"title of {sid}"),
        )
        if doi is not None:
            status = "retracted" if rid in retracted else "ok"
            conn.execute(
                "INSERT INTO evidence_integrity (evidence_id, status, check_status, reason, "
                "checked_at, "
                "check_run_id) VALUES (%s, %s, %s, NULL, '2026-11-08', 'r1')",
                (rid, status, status),
            )


def donate(
    conn: psycopg.Connection, key: str, region: str, n: int, event: str = "improvement_pain"
) -> None:
    with conn.cursor() as cur:
        cur.executemany(INSERT, [(MONDAY, region, [key], event, os.urandom(32)) for _ in range(n)])


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("lightapi")
    cur = write_world(root, LABELS)
    light_build.write(root, light_build.build(root, cur))
    return root


@pytest.fixture
def env(db_url: str, data_dir: Path) -> Iterator[tuple[TestClient, str]]:
    database = Database(db_url)
    database.open()
    settings = Settings.from_env({"JANUS_DATA_DIR": str(data_dir), "JANUS_NOISE_KEY": NOISE_KEY})
    app = create_app(settings, database=database, configure_logs=False)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c, db_url
    with psycopg.connect(db_url, autocommit=True) as conn:
        reset_evidence(conn)
        conn.execute("DELETE FROM contributions")
    database.close()


def cards(c: TestClient, goal: str = "goal_a", **kw: Any) -> Any:
    r = c.post("/light/cards", json={"goal": goal, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_cards_validation_export(env: tuple[TestClient, str]) -> None:
    """Feature: light-face, Properties P13, P14: disclaimer and rule-7 code on every answer."""
    c, url = env
    with psycopg.connect(url, autocommit=True) as conn:
        seed(conn, set())
    ov = c.get("/light/overview")
    assert ov.status_code == 200
    assert ov.json()["review_status"] == "automated_checks_pending_expert"
    body = cards(c)
    assert body["total"] == 2 and body["removed_by_integrity"] == 0
    assert all("candidate_not_treatment" in card["codes"] for card in body["cards"])
    assert "Janus provides information" in body["disclaimer"]
    assert body["patient_layer"] == "ok"
    v = c.get("/light/validation").json()
    assert v["cases"][0]["case"]["id"] == "aspirin_goal_a"
    ex = c.get("/light/export").json()
    assert ex["licence"] == "CC BY 4.0" and "export_aggregated" in ex["codes"]
    assert len(ex["rows"]) == body["total"] + cards(c, "goal_b")["total"]
    paged = cards(c, offset=1, limit=1)
    assert [x["ingredient"]["key"] for x in paged["cards"]] == [
        x["ingredient"]["key"] for x in body["cards"][1:2]
    ]


def test_retracted_mapping_paper_is_removed(env: tuple[TestClient, str]) -> None:
    """Feature: light-face, Property P1: a retracted paper is listed as removed, not as a source."""
    c, url = env
    with psycopg.connect(url, autocommit=True) as conn:
        seed(conn, {PAPER2})
    body = cards(c)
    for card in body["cards"]:
        assert PAPER2 not in [s["id"] for s in card["sources"]]
    removed = {r["id"]: r["reason"] for card in body["cards"] for r in card["removed_sources"]}
    assert removed.get(PAPER2) == "retracted"


def test_patient_layer_releases_only_groups_of_twenty(env: tuple[TestClient, str]) -> None:
    """Feature: light-face, Property P8: under 20 nothing; 20 or more a noisy released total."""
    c, url = env
    with psycopg.connect(url, autocommit=True) as conn:
        seed(conn, set())
        donate(conn, "Q3", "EU", 19)  # Q3 has no goal_a candidate
        donate(conn, "Q2", "US", 25)  # Q2 is a goal_a candidate
        donate(conn, "Q9", "TR", 30)  # no candidate at all
    body = cards(c)
    q2 = next(x for x in body["cards"] if x["ingredient"]["key"] == "Q2")
    pats = [s for s in q2["signals"] if s["type"] == "patient_reported"]
    assert len(pats) == 1 and pats[0]["patient"]["total_of_released"] >= 0
    for cell in pats[0]["patient"]["cells"]:
        assert (cell["status"] == "released") == (cell["value"] is not None)
    only = {p["ingredient"]["key"] for p in body["patient_reported"]}
    assert only == {"Q9"}
    assert all(
        s["type"] != "patient_reported"
        for x in body["cards"]
        if x["ingredient"]["key"] == "Q3"
        for s in x["signals"]
    )
    text = str(body)
    assert "19" not in [
        str(s.get("value")) for p in body["patient_reported"] for s in p["signal"]["cells"]
    ]
    assert (
        "Q3" not in [p["ingredient"]["key"] for p in body["patient_reported"]]
        and "improvement_pain" in text
    )


def test_errors_never_echo_and_fail_closed(env: tuple[TestClient, str], tmp_path: Path) -> None:
    """Feature: light-face, Property P13: unknown goal 422 without echo; no build 503."""
    c, url = env
    with psycopg.connect(url, autocommit=True) as conn:
        seed(conn, set())
    with capture_logs() as logs:
        r = c.post("/light/cards", json={"goal": "zz_secret_goal"})
        bad = c.post("/light/cards", json={"goal": "goal_a", "extra": "zz_secret"})
        junk = c.post(
            "/light/cards", content=b"{not json", headers={"content-type": "application/json"}
        )
    assert r.status_code == 422 and r.json() == {"error": "invalid_request", "fields": ["goal"]}
    assert bad.status_code == 422 and "zz_secret" not in bad.text
    assert junk.status_code == 422
    assert "zz_secret" not in logs.getvalue() and "goal_a" not in logs.getvalue()
    empty = TestClient(
        create_app(Settings.from_env({"JANUS_DATA_DIR": str(tmp_path)}), configure_logs=False)
    )
    assert empty.get("/light/overview").status_code == 503
    assert empty.get("/light/validation").json() == {"error": "light_unavailable"}
