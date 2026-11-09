"""The job queue in PostgreSQL (simulation-service design §6, DP-S4). All SQL is parameterised.

Every function takes a connection inside a transaction and the current time (tests freeze it).
Submissions and claims take one transaction-scoped advisory lock, so the queue limit (10 queued
or running jobs) and the two worker slots hold under concurrent requests and several workers.

- `submit`: an identical input that is queued, running or done and not expired is reused (the
  cache); otherwise a new queued job, unless the queue is full (`QueueFullError`).
- `claim`: the oldest queued job, only while fewer than `SLOTS` jobs run.
- `finish` / `fail`: final states; a result lives `RESULT_TTL`, a failure `FAILED_TTL`.
- `reap`: running jobs past their deadline fail as `worker_lost`, queued jobs older than
  `QUEUED_TTL` fail as `expired`, expired rows are deleted.
"""

from __future__ import annotations

import datetime as dt
import math
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

QUEUE_MAX = 10
SLOTS = 2
JOB_TIMEOUT_S = 30
TYPICAL_RUN_S = 5
RESULT_TTL = dt.timedelta(hours=24)
FAILED_TTL = dt.timedelta(hours=1)
QUEUED_TTL = dt.timedelta(minutes=10)
GRACE = dt.timedelta(seconds=30)
LOCK_KEY = 2026110901

_COLS = "id, kind, input, state, created_at, started_at, finished_at, expires_at, result, error"


@dataclass(frozen=True)
class Job:
    id: uuid.UUID
    kind: str
    input: dict[str, Any]
    state: str
    created_at: dt.datetime
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    expires_at: dt.datetime
    result: dict[str, Any] | None
    error: str | None


class QueueFullError(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("simulation queue is full")
        self.retry_after = retry_after


def retry_after(active: int) -> int:
    """Seconds until a slot is likely free: the jobs ahead, two at a time, 5 s each, 5-60 s."""
    return min(60, max(5, math.ceil(active / SLOTS) * TYPICAL_RUN_S))


def _job(row: tuple[Any, ...]) -> Job:
    return Job(*row)


def _lock(conn: psycopg.Connection) -> None:
    conn.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))


def active(conn: psycopg.Connection) -> int:
    row = conn.execute(
        "SELECT count(*) FROM simulation_jobs WHERE state IN ('queued', 'running')"
    ).fetchone()
    return int(row[0]) if row else 0


def submit(
    conn: psycopg.Connection,
    kind: str,
    canon: dict[str, Any],
    input_hash: str,
    now: dt.datetime,
) -> tuple[Job, bool]:
    """(job, reused). Raises `QueueFullError` when a new job would exceed `QUEUE_MAX`."""
    _lock(conn)
    row = conn.execute(
        f"SELECT {_COLS} FROM simulation_jobs "
        "WHERE input_hash = %s AND state <> 'failed' AND expires_at > %s "
        "ORDER BY created_at DESC LIMIT 1",
        (input_hash, now),
    ).fetchone()
    if row is not None:
        return _job(row), True
    n = active(conn)
    if n >= QUEUE_MAX:
        raise QueueFullError(retry_after(n))
    row = conn.execute(
        f"INSERT INTO simulation_jobs (id, input_hash, kind, input, state, created_at, expires_at) "
        f"VALUES (%s, %s, %s, %s, 'queued', %s, %s) RETURNING {_COLS}",
        (uuid.uuid4(), input_hash, kind, Jsonb(canon), now, now + RESULT_TTL),
    ).fetchone()
    if row is None:  # INSERT ... RETURNING always returns the row
        raise RuntimeError("insert returned no row")
    return _job(row), False


def claim(conn: psycopg.Connection, now: dt.datetime) -> Job | None:
    _lock(conn)
    running = conn.execute(
        "SELECT count(*) FROM simulation_jobs WHERE state = 'running'"
    ).fetchone()
    if running and int(running[0]) >= SLOTS:
        return None
    row = conn.execute(
        "UPDATE simulation_jobs SET state = 'running', started_at = %s, attempts = attempts + 1 "
        "WHERE id = (SELECT id FROM simulation_jobs WHERE state = 'queued' "
        "ORDER BY created_at, id LIMIT 1 FOR UPDATE SKIP LOCKED) "
        f"RETURNING {_COLS}",
        (now,),
    ).fetchone()
    return _job(row) if row else None


def finish(
    conn: psycopg.Connection, job_id: uuid.UUID, result: dict[str, Any], now: dt.datetime
) -> bool:
    cur = conn.execute(
        "UPDATE simulation_jobs SET state = 'done', result = %s, finished_at = %s, expires_at = %s "
        "WHERE id = %s AND state = 'running'",
        (Jsonb(result), now, now + RESULT_TTL, job_id),
    )
    return cur.rowcount == 1


def fail(conn: psycopg.Connection, job_id: uuid.UUID, error: str, now: dt.datetime) -> bool:
    cur = conn.execute(
        "UPDATE simulation_jobs SET state = 'failed', error = %s, finished_at = %s, "
        "expires_at = %s WHERE id = %s AND state = 'running'",
        (error, now, now + FAILED_TTL, job_id),
    )
    return cur.rowcount == 1


def reap(conn: psycopg.Connection, now: dt.datetime) -> dict[str, int]:
    """Counts only (worker logs)."""
    deadline = now - dt.timedelta(seconds=JOB_TIMEOUT_S) - GRACE
    lost = conn.execute(
        "UPDATE simulation_jobs SET state = 'failed', error = 'worker_lost', finished_at = %s, "
        "expires_at = %s WHERE state = 'running' AND started_at < %s",
        (now, now + FAILED_TTL, deadline),
    ).rowcount
    stale = conn.execute(
        "UPDATE simulation_jobs SET state = 'failed', error = 'expired', finished_at = %s, "
        "expires_at = %s WHERE state = 'queued' AND created_at < %s",
        (now, now + FAILED_TTL, now - QUEUED_TTL),
    ).rowcount
    gone = conn.execute("DELETE FROM simulation_jobs WHERE expires_at < %s", (now,)).rowcount
    return {"worker_lost": lost, "expired": stale, "deleted": gone}


def get(
    conn: psycopg.Connection, job_id: uuid.UUID, now: dt.datetime
) -> tuple[Job, int | None] | None:
    """The job and, while queued, its 1-based position; None when unknown or expired."""
    row = conn.execute(
        f"SELECT {_COLS} FROM simulation_jobs WHERE id = %s AND expires_at > %s",
        (job_id, now),
    ).fetchone()
    if row is None:
        return None
    job = _job(row)
    if job.state != "queued":
        return job, None
    ahead = conn.execute(
        "SELECT count(*) FROM simulation_jobs WHERE state = 'queued' "
        "AND (created_at, id) < (%s, %s)",
        (job.created_at, job.id),
    ).fetchone()
    return job, (int(ahead[0]) if ahead else 0) + 1
