"""Simulation service: the queue in PostgreSQL and the routes (simulation-service design §9).

Q1  never more than QUEUE_MAX queued or running jobs, whatever the order of submissions and
    claims; a full queue refuses with a retry-after of 5-60 s
Q2  never more than SLOTS running jobs, even with several claimers
Q3  an identical input reuses the queued, running or finished job (cache); a failed one does not
Q4  results expire; the reaper fails stuck and stale jobs and deletes expired rows
R1  routes: 503 when off, 413/415 body policy, 422 naming fields only, 202 then 200 cached,
    429 queue_full and rate_limited with Retry-After, 404 unknown, 422 bad id; every job answer
    carries the validation status and the disclaimer; nothing about the client is stored
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from typing import Any

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from psycopg.conninfo import make_conninfo

from janus.db.pool import Database
from janus.main import create_app
from janus.settings import Settings
from janus.simulation import queue as q
from janus.simulation import router as sim_router
from janus.simulation.allowlist import allowlist
from janus.simulation.schemas import DISCLAIMER, canonical, input_hash, parse
from tests.conftest import DB_EXAMPLES

T0 = dt.datetime(2026, 11, 9, 12, 0, tzinfo=dt.UTC)
ALLOW = allowlist()


def body(dose: float = 5.0) -> dict[str, Any]:
    return {
        "kind": "compartmental",
        "compound": "amlodipine",
        "population": "adult",
        "dose_mg": dose,
        "interval_h": None,
        "doses": 1,
        "samples": 200,
    }


def key(b: dict[str, Any]) -> tuple[dict[str, Any], str]:
    c = canonical(parse(b, ALLOW))
    return c, input_hash(c, ALLOW.version)


def _clear(conn: psycopg.Connection) -> None:
    conn.execute("TRUNCATE simulation_jobs")


@pytest.fixture
def conn(db_conn: psycopg.Connection) -> psycopg.Connection:
    _clear(db_conn)
    return db_conn


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(st.lists(st.sampled_from(["submit", "claim", "finish"]), max_size=40))
def test_q1_q2_limits_hold(db_url: str, ops: list[str]) -> None:
    with psycopg.connect(db_url, autocommit=True) as c:
        _clear(c)
        n = 0
        running: list[uuid.UUID] = []
        for op in ops:
            with c.transaction():
                if op == "submit":
                    n += 1
                    canon, h = key(body(2.5 + n / 100))
                    try:
                        q.submit(c, "compartmental", canon, h, T0)
                    except q.QueueFullError as e:
                        assert q.active(c) >= q.QUEUE_MAX
                        assert 5 <= e.retry_after <= 60
                elif op == "claim":
                    job = q.claim(c, T0)
                    if job is not None:
                        running.append(job.id)
                elif running:
                    q.finish(c, running.pop(0), {"ok": 1}, T0)
                assert q.active(c) <= q.QUEUE_MAX
                r = c.execute(
                    "SELECT count(*) FROM simulation_jobs WHERE state = 'running'"
                ).fetchone()
                assert r is not None and r[0] <= q.SLOTS


@pytest.mark.db
def test_q2_two_claimers_never_exceed_the_slots(db_url: str, conn: psycopg.Connection) -> None:
    for i in range(6):
        canon, h = key(body(2.5 + i / 10))
        with conn.transaction():
            q.submit(conn, "compartmental", canon, h, T0)
    with psycopg.connect(db_url, autocommit=True) as other:
        got: list[q.Job | None] = []
        for c in (conn, other, conn, other):
            with c.transaction():
                got.append(q.claim(c, T0))
    assert sum(1 for g in got if g is not None) == q.SLOTS


@pytest.mark.db
def test_q3_cache_and_reuse(conn: psycopg.Connection) -> None:
    canon, h = key(body())
    with conn.transaction():
        a, reused_a = q.submit(conn, "compartmental", canon, h, T0)
        b, reused_b = q.submit(conn, "compartmental", canon, h, T0)
    assert (reused_a, reused_b) == (False, True) and a.id == b.id
    with conn.transaction():
        job = q.claim(conn, T0)
        assert job is not None and job.id == a.id
        q.finish(conn, a.id, {"x": 1}, T0)
        c, reused = q.submit(conn, "compartmental", canon, h, T0 + dt.timedelta(hours=1))
    assert reused and c.id == a.id and c.state == "done" and c.result == {"x": 1}
    # After expiry the same input is a new job.
    with conn.transaction():
        d, reused = q.submit(
            conn, "compartmental", canon, h, T0 + q.RESULT_TTL + dt.timedelta(seconds=1)
        )
    assert not reused and d.id != a.id
    # A failed run is never served from the cache.
    with conn.transaction():
        conn.execute("TRUNCATE simulation_jobs")
        e, _ = q.submit(conn, "compartmental", canon, h, T0)
        q.claim(conn, T0)
        q.fail(conn, e.id, "timeout", T0)
        f, reused = q.submit(conn, "compartmental", canon, h, T0)
    assert not reused and f.id != e.id


@pytest.mark.db
def test_q4_reaper_and_expiry(conn: psycopg.Connection) -> None:
    ids: list[uuid.UUID] = []
    for i in range(3):
        canon, h = key(body(2.5 + i))
        with conn.transaction():
            ids.append(q.submit(conn, "compartmental", canon, h, T0)[0].id)
    with conn.transaction():
        stuck = q.claim(conn, T0)
    assert stuck is not None
    later = T0 + q.QUEUED_TTL + dt.timedelta(seconds=1)
    with conn.transaction():
        counts = q.reap(conn, later)
    assert counts == {"worker_lost": 1, "expired": 2, "deleted": 0}
    with conn.transaction():
        assert q.get(conn, stuck.id, later) is not None
        gone = q.reap(conn, later + q.FAILED_TTL + dt.timedelta(seconds=1))
    assert gone["deleted"] == 3
    with conn.transaction():
        assert q.get(conn, stuck.id, later) is None


@pytest.mark.db
def test_q4_queue_position(conn: psycopg.Connection) -> None:
    jobs: list[q.Job] = []
    for i in range(3):
        canon, h = key(body(2.5 + i))
        with conn.transaction():
            jobs.append(q.submit(conn, "compartmental", canon, h, T0 + dt.timedelta(seconds=i))[0])
    with conn.transaction():
        positions = [q.get(conn, j.id, T0) for j in jobs]
    assert [p[1] for p in positions if p] == [1, 2, 3]


# --- routes ------------------------------------------------------------------------------------


Env = tuple[TestClient, FastAPI, Database]


@pytest.fixture
def env(db_url: str) -> Iterator[Env]:
    database = Database(db_url)
    database.open()
    with psycopg.connect(db_url, autocommit=True) as c:
        _clear(c)
    sim_router.now = lambda: T0
    app = create_app(Settings.from_env({"JANUS_SIMULATION": "on"}), database=database)
    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc, app, database
    database.close()


def test_r1_off_without_switch_or_database() -> None:
    app = create_app(Settings.from_env({}), database=None)
    with TestClient(app) as c:
        off = c.post("/simulate", json=body()).json()
        assert off == {"error": "simulation_unavailable", "disclaimer": DISCLAIMER}
        assert c.get(f"/simulate/jobs/{uuid.uuid4()}").status_code == 503
        r = c.get("/simulate/compounds")
        assert r.status_code == 200 and r.json()["server_runs"] is False
        assert r.headers["cache-control"] == "no-store"
        assert r.json()["disclaimer"] == DISCLAIMER


def test_r1_body_policy_before_anything() -> None:
    app = create_app(Settings.from_env({"JANUS_SIMULATION": "on"}), database=None)
    with TestClient(app) as c:
        big = {**body(), "pad": "x" * 2000}
        assert c.post("/simulate", json=big).status_code == 413
        assert (
            c.post("/simulate", content=b"a=1", headers={"content-type": "text/plain"}).status_code
            == 415
        )


@pytest.mark.db
def test_r1_submit_poll_cache(env: Env) -> None:
    client, _, db = env
    r = client.post("/simulate", json=body())
    assert r.status_code == 202
    job = r.json()
    assert job["state"] == "queued" and job["queue_position"] == 1 and not job["cached"]
    assert job["validation"]["credibility"] == "borderline" and job["disclaimer"] == DISCLAIMER
    assert client.post("/simulate", json=body()).json()["job_id"] == job["job_id"]
    # A worker runs it.
    with db.write_tx() as conn:
        claimed = q.claim(conn, T0)
        assert claimed is not None
        q.finish(conn, claimed.id, {"model": "compartmental", "p50_ng_ml": [0.0, 1.0]}, T0)
    polled = client.get(f"/simulate/jobs/{job['job_id']}").json()
    assert polled["state"] == "done" and polled["result"]["model"] == "compartmental"
    again = client.post("/simulate", json=body())
    assert again.status_code == 200 and again.json()["cached"] is True
    # Nothing about the client is stored.
    with db.read_only_tx() as conn:
        cols = [
            r[0]
            for r in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'simulation_jobs'"
            ).fetchall()
        ]
    assert not {"ip", "address", "client", "user_agent", "key"} & set(cols)


@pytest.mark.db
def test_r1_errors_name_fields_only(env: Env) -> None:
    client = env[0]
    r = client.post("/simulate", json={**body(), "secret_field_name": "../../x"})
    assert r.status_code == 422 and r.json()["fields"] == ["<unknown>"]
    r = client.post("/simulate", json=body(dose=999))
    assert r.json() == {"error": "invalid_request", "fields": ["dose_mg"], "disclaimer": DISCLAIMER}
    assert "999" not in r.text
    assert client.get("/simulate/jobs/not-a-uuid").json()["fields"] == ["job_id"]
    assert client.get(f"/simulate/jobs/{uuid.uuid4()}").json()["error"] == "unknown_job"


@pytest.mark.db
def test_r1_queue_full_and_rate_limit(env: Env) -> None:
    client, app, _ = env
    # Lift the client limit to fill the queue from one test client.
    app.state.simulation_limits = sim_router.SimulationLimits(
        submit=sim_router.Limiter(per_client=(sim_router.Window(100, 600),))
    )
    for i in range(q.QUEUE_MAX):
        assert client.post("/simulate", json=body(2.5 + i / 2)).status_code == 202
    full = client.post("/simulate", json=body(9.9))
    assert full.status_code == 429 and full.json()["error"] == "queue_full"
    assert 5 <= int(full.headers["retry-after"]) <= 60
    # Default limits: three submissions per 30 s per client.
    app.state.simulation_limits = sim_router.SimulationLimits()
    codes = [client.post("/simulate", json=body(3.0)).status_code for _ in range(4)]
    assert codes == [202, 202, 202, 429]  # the same queued job is reused, then limited
    limited = client.post("/simulate", json=body(3.0))
    assert limited.json()["error"] == "rate_limited" and int(limited.headers["retry-after"]) >= 1


@pytest.mark.db
@settings(max_examples=25)
@given(
    st.one_of(
        st.dictionaries(st.text(max_size=12), st.one_of(st.integers(), st.text(max_size=8))),
        st.just(body()),
        st.just({**body(), "body_weight_kg": 70}),
        st.just({**body(), "dose_mg": 50.0}),
    )
)
def test_r2_every_answer_carries_the_disclaimer(env: Env, payload: dict[str, Any]) -> None:
    """Owner decision 2026-11-09: every answer of the simulation routes (results, queue states,
    errors) says "Virtual population, for research. Not about any person and not a dose
    recommendation." (Body-policy rejections 413/415 happen before the routes; covered by R1.)"""
    client, app, _ = env
    app.state.simulation_limits = sim_router.SimulationLimits(
        submit=sim_router.Limiter(per_client=(sim_router.Window(10_000, 1),)),
        poll=sim_router.Limiter(per_client=(sim_router.Window(10_000, 1),)),
    )
    answers = [
        client.post("/simulate", json=payload),
        client.get("/simulate/compounds"),
        client.get(f"/simulate/jobs/{uuid.uuid4()}"),
        client.get("/simulate/jobs/x"),
    ]
    job = answers[0].json().get("job_id")
    if job:
        answers.append(client.get(f"/simulate/jobs/{job}"))
    for a in answers:
        assert a.json()["disclaimer"] == DISCLAIMER, a.status_code
        assert "Virtual population, for research." in a.text


@pytest.mark.db
def test_q5_worker_role_can_touch_the_queue_only(db_url: str, conn: psycopg.Connection) -> None:
    """Safety review F1: the worker's role reads, updates and deletes queue rows, nothing else."""
    from janus.simulation.dbrole import set_password

    password = "test-only-" + "x" * 20
    set_password(conn, password)
    with pytest.raises(ValueError):
        set_password(conn, "short")
    url = make_conninfo(db_url, user="janus_simulator", password=password)
    with psycopg.connect(url, autocommit=True) as worker:
        worker.execute("SELECT count(*) FROM simulation_jobs")
        worker.execute("UPDATE simulation_jobs SET attempts = attempts WHERE false")
        worker.execute("DELETE FROM simulation_jobs WHERE false")
        for sql in (
            b"SELECT count(*) FROM contributions",
            b"INSERT INTO simulation_jobs (id) VALUES (gen_random_uuid())",
            b"CREATE TABLE x (y int)",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                worker.execute(sql)
