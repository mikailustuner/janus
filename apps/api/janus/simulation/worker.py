"""The simulation worker (simulation-service design §5, §8). Runs in its own container on the
internal network (no route out), as a non-root user with a read-only root file system.

    python -m janus.simulation.worker            # serve the queue (DATABASE_URL)
    python -m janus.simulation.worker --selftest # one compartmental and one httk run, no database

`SLOTS` threads each claim a job, run it in a child process with a 30 s timeout and store the
result or the failure. The database also limits running jobs to `SLOTS`, so a second worker
container could not exceed it. A heartbeat file in /tmp feeds the container health check. Logs
carry states, counts and durations only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import sys
import threading
import time
from pathlib import Path

import psycopg

from janus.observability.logging import LogEvent, configure_logging, log_event
from janus.simulation import execute
from janus.simulation import queue as q
from janus.simulation.allowlist import allowlist

POLL_S = 1.0
REAP_EVERY_S = 30.0
HEARTBEAT = Path(os.environ.get("JANUS_SIMULATOR_HEARTBEAT", "/tmp/simulator-heartbeat"))


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _slot(url: str, stop: threading.Event) -> None:
    with psycopg.connect(url, connect_timeout=10) as conn:
        while not stop.is_set():
            with conn.transaction():
                job = q.claim(conn, _now())
            if job is None:
                stop.wait(POLL_S)
                continue
            started = time.monotonic()
            try:
                result = execute.run(job.input)
            except execute.JobTimeoutError:
                with conn.transaction():
                    q.fail(conn, job.id, "timeout", _now())
                log_event(
                    LogEvent.simulation_failed, latency_ms=(time.monotonic() - started) * 1000
                )
                continue
            except Exception as exc:
                with conn.transaction():
                    q.fail(conn, job.id, "model_failed", _now())
                log_event(
                    LogEvent.simulation_failed,
                    level=logging.WARNING,
                    latency_ms=(time.monotonic() - started) * 1000,
                    error_class=type(exc),
                )
                continue
            try:
                with conn.transaction():
                    q.finish(conn, job.id, result, _now())
            except psycopg.errors.CheckViolation:  # a result the table refuses ends the job only
                with conn.transaction():
                    q.fail(conn, job.id, "model_failed", _now())
                log_event(LogEvent.simulation_failed, level=logging.WARNING)
                continue
            log_event(LogEvent.simulation_done, latency_ms=(time.monotonic() - started) * 1000)


def serve(url: str) -> None:
    allowlist()  # a broken allow-list stops the worker at start, not at the first job
    stop = threading.Event()
    threads = [
        threading.Thread(target=_slot, args=(url, stop), daemon=True) for _ in range(q.SLOTS)
    ]
    for t in threads:
        t.start()
    log_event(LogEvent.simulation_start, count=q.SLOTS)
    with psycopg.connect(url, connect_timeout=10) as conn:
        while all(t.is_alive() for t in threads):
            with conn.transaction():
                counts = q.reap(conn, _now())
            if any(counts.values()):
                log_event(LogEvent.simulation_reap, count=sum(counts.values()))
            HEARTBEAT.write_text(str(int(time.time())))
            stop.wait(REAP_EVERY_S)
    stop.set()
    raise SystemExit(1)  # a dead slot restarts the container (restart policy)


SELFTEST = (
    {
        "kind": "compartmental",
        "compound": "amlodipine",
        "population": "adult_65plus",
        "dose_mg": 10.0,
        "interval_h": 24,
        "doses": 14,
        "samples": 2000,
    },
    {"kind": "httk_population", "compound": "haloperidol", "samples": 100},
    {"kind": "httk_population", "compound": "haloperidol", "samples": 1000},
)


def selftest() -> int:
    for canon in SELFTEST:
        t0 = time.monotonic()
        out = execute.run(canon)
        print(f"{canon['kind']}: ok in {time.monotonic() - t0:.2f} s ({len(out)} fields)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    configure_logging()
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    serve(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
