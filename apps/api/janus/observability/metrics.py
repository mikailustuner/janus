"""Private Prometheus metrics (observability; deploy README "Metrics").

Served by `serve()` on its own port, never by the public app, so the web app's `/api/*` rewrite
cannot reach it. Privacy: every label value comes from a fixed set (a route template of this
app, an HTTP method of a fixed list, a status class, a job state, a dataset name from `DATASETS`,
a quantile). No query string, path parameter, name, code, id, address or user agent is ever a
label, and nothing is read from a request except those.

The HTTP series are updated by `AccessLogMiddleware`. The queue, dataset and pool series are
read when Prometheus scrapes (one cheap query and a few `stat` calls, cached for `CACHE_S`).
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from http.server import HTTPServer
from pathlib import Path
from typing import Final

import psycopg
import psycopg_pool
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, start_http_server
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.gc_collector import GCCollector
from prometheus_client.platform_collector import PlatformCollector
from prometheus_client.process_collector import ProcessCollector
from prometheus_client.registry import Collector

from janus.db.pool import Database
from janus.observability.logging import UNMATCHED_ROUTE, registered_route_templates

CACHE_S: Final = 15.0
QUERY_TIMEOUT_MS: Final = 2000
METHODS: Final = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})
OTHER_METHOD: Final = "OTHER"
JOB_STATES: Final = ("queued", "running", "done", "failed")  # simulation_jobs.state (queue.py)
QUANTILES: Final = ("0.5", "0.95")
DURATION_WINDOW: Final = "1 hour"  # keep equal to the interval in `_read_queue`

# The fixed dataset list: the pipeline job names (pipelines/janus_pipelines/jobs) read from
# `<data dir>/artifacts/<name>/current`, plus the four built datasets the API follows through
# their own `current` link. A test keeps the first part equal to the pipeline job list.
ARTIFACT_DATASETS: Final = (
    "ca_dpd",
    "canon",
    "canon_gold",
    "eu_es_cima",
    "eu_fr_bdpm",
    "eu_it_aifa",
    "faers",
    "faers_onset",
    "modelkit_ctgov",
    "modelkit_documents",
    "modelkit_evidence",
    "modelkit_special_populations",
    "onsides",
    "openfda_label",
    "pipc",
    "retractions",
    "titck",
    "tm_admet",
    "tm_bioactivity",
    "tm_labels",
    "tm_molecules",
    "tm_pbpk",
    "us_label_interactions",
    "us_labels",
    "us_ndc",
    "us_recalls",
    "wikidata_ingredients",
)
BUILT_DATASETS: Final = {
    "faers_counts": ("memory", "faers_counts"),
    "light": ("light",),
    "data_quality": ("quality",),
    "onset_table": ("onset_table",),
}
DATASETS: Final = (*ARTIFACT_DATASETS, *BUILT_DATASETS)

REGISTRY: Final = CollectorRegistry(auto_describe=True)
ProcessCollector(registry=REGISTRY)
PlatformCollector(registry=REGISTRY)
GCCollector(registry=REGISTRY)

_HTTP_LABELS: Final = ("route", "method", "status_class")
HTTP_REQUESTS: Final = Counter(
    "janus_http_requests",
    "HTTP requests by route template, method and status class.",
    _HTTP_LABELS,
    registry=REGISTRY,
)
HTTP_LATENCY: Final = Histogram(
    "janus_http_request_duration_seconds",
    "HTTP request latency by route template, method and status class.",
    _HTTP_LABELS,
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
    registry=REGISTRY,
)
HTTP_IN_FLIGHT: Final = Gauge(
    "janus_http_requests_in_flight", "HTTP requests being handled now.", registry=REGISTRY
)


def observe_request(route: str, method: str, status: int, seconds: float) -> None:
    """Record one finished request. Labels are clamped to their fixed sets."""
    if route not in registered_route_templates():
        route = UNMATCHED_ROUTE
    method = method if method in METHODS else OTHER_METHOD
    status_class = f"{status // 100}xx" if 100 <= status <= 599 else "5xx"
    HTTP_REQUESTS.labels(route, method, status_class).inc()
    HTTP_LATENCY.labels(route, method, status_class).observe(max(0.0, seconds))


def _isoformat_epoch(text: str) -> float | None:
    from janus.integrity.freshness import parse_snapshot_date

    try:
        day = parse_snapshot_date(text)
    except ValueError:
        return None
    return datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp()


class AppCollector(Collector):
    """Queue, dataset and pool series, computed at scrape time and cached for `CACHE_S`."""

    def __init__(
        self,
        database: Database | None,
        data_dir: Path | None,
        *,
        clock: Callable[[], float] = time.time,
        ttl: float = CACHE_S,
    ) -> None:
        self._database = database
        self._data_dir = data_dir
        self._clock = clock
        self._ttl = ttl
        self._lock = threading.Lock()
        self._at = float("-inf")
        self._families: list[GaugeMetricFamily] = []

    def describe(self) -> Iterable[GaugeMetricFamily]:
        return []  # dynamic series; also keeps registration from querying the database

    def collect(self) -> Iterable[GaugeMetricFamily]:
        with self._lock:
            now = self._clock()
            if now - self._at >= self._ttl:
                self._families = [*self._queue(), *self._datasets(now)]
                self._at = now
            families = list(self._families)
        return [*families, *self._pool()]

    # --- simulation queue ---------------------------------------------------------------------

    def _queue(self) -> list[GaugeMetricFamily]:
        readable = GaugeMetricFamily(
            "janus_simulation_queue_readable", "1 when the queue table could be read."
        )
        if self._database is None:
            return []
        try:
            counts, oldest, quantiles, done = self._read_queue(self._database)
        except (psycopg.Error, psycopg_pool.PoolTimeout, psycopg_pool.PoolClosed):
            readable.add_metric([], 0)
            return [readable]
        readable.add_metric([], 1)
        jobs = GaugeMetricFamily(
            "janus_simulation_jobs", "Simulation jobs in the table by state.", labels=["state"]
        )
        for state in JOB_STATES:
            jobs.add_metric([state], counts.get(state, 0))
        age = GaugeMetricFamily(
            "janus_simulation_oldest_queued_age_seconds",
            "Age of the oldest queued job; 0 when none is queued.",
        )
        age.add_metric([], oldest)
        recent = GaugeMetricFamily(
            "janus_simulation_recent_jobs_done",
            f"Jobs that finished successfully in the last {DURATION_WINDOW}.",
        )
        recent.add_metric([], done)
        out = [readable, jobs, age, recent]
        if quantiles:
            dur = GaugeMetricFamily(
                "janus_simulation_recent_job_duration_seconds",
                f"Run time of jobs that finished successfully in the last {DURATION_WINDOW}.",
                labels=["quantile"],
            )
            for q, value in zip(QUANTILES, quantiles, strict=True):
                dur.add_metric([q], value)
            out.append(dur)
        return out

    @staticmethod
    def _read_queue(db: Database) -> tuple[dict[str, int], float, list[float], int]:
        with db.pool.connection(timeout=2) as conn, conn.transaction():
            conn.execute(
                "SELECT set_config('statement_timeout', %s, true)", (str(QUERY_TIMEOUT_MS),)
            )
            counts = {
                str(state): int(n)
                for state, n in conn.execute(
                    "SELECT state, count(*) FROM simulation_jobs GROUP BY state"
                ).fetchall()
            }
            row = conn.execute(
                "SELECT coalesce(extract(epoch FROM now() - min(created_at)), 0) "
                "FROM simulation_jobs WHERE state = 'queued'"
            ).fetchone()
            oldest = max(0.0, float(row[0])) if row else 0.0
            row = conn.execute(
                "SELECT count(*), percentile_cont(%s) WITHIN GROUP (ORDER BY secs) FROM ("
                "SELECT extract(epoch FROM finished_at - started_at) AS secs FROM simulation_jobs "
                "WHERE state = 'done' AND finished_at > now() - interval '1 hour' "
                "AND started_at IS NOT NULL) d",
                ([float(q) for q in QUANTILES],),
            ).fetchone()
        done = int(row[0]) if row else 0
        values = [float(v) for v in row[1]] if row and row[1] is not None else []
        return counts, oldest, values, done

    # --- datasets -----------------------------------------------------------------------------

    def _datasets(self, now: float) -> list[GaugeMetricFamily]:
        if self._data_dir is None:
            return []
        present = GaugeMetricFamily(
            "janus_dataset_present", "1 when the dataset has a current run.", labels=["dataset"]
        )
        loaded = GaugeMetricFamily(
            "janus_dataset_loaded_timestamp_seconds",
            "Modification time (Unix seconds) of the dataset's current run.",
            labels=["dataset"],
        )
        age = GaugeMetricFamily(
            "janus_dataset_age_seconds",
            "Seconds since the dataset's current run was installed.",
            labels=["dataset"],
        )
        snapshot = GaugeMetricFamily(
            "janus_dataset_snapshot_age_seconds",
            "Seconds since the snapshot date in the current run's manifest (when it has one).",
            labels=["dataset"],
        )
        for name in DATASETS:
            link = self._link(name)
            try:
                target = Path(os.path.realpath(link, strict=True))
                mtime = target.stat().st_mtime
            except OSError:
                present.add_metric([name], 0)
                continue
            present.add_metric([name], 1)
            loaded.add_metric([name], mtime)
            age.add_metric([name], max(0.0, now - mtime))
            taken = self._snapshot_epoch(target)
            if taken is not None:
                snapshot.add_metric([name], max(0.0, now - taken))
        return [present, loaded, age, snapshot]

    def _link(self, name: str) -> Path:
        root = self._data_dir or Path()
        if name in BUILT_DATASETS:
            return root.joinpath(*BUILT_DATASETS[name], "current")
        return root / "artifacts" / name / "current"

    @staticmethod
    def _snapshot_epoch(run: Path) -> float | None:
        try:
            manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        text = manifest.get("snapshot_date") if isinstance(manifest, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        return _isoformat_epoch(text) if isinstance(text, str) else None

    # --- connection pool ----------------------------------------------------------------------

    def _pool(self) -> list[GaugeMetricFamily]:
        if self._database is None:
            return []
        try:
            stats = self._database.pool.get_stats()
        except Exception:
            return []
        size, free = stats.get("pool_size"), stats.get("pool_available")
        if size is None or free is None:
            return []
        out: list[GaugeMetricFamily] = []
        for name, doc, value in (
            ("janus_db_pool_max", "Configured maximum connections.", stats.get("pool_max")),
            ("janus_db_pool_size", "Connections now open.", size),
            ("janus_db_pool_in_use", "Connections handed out to requests.", size - free),
            (
                "janus_db_pool_waiting",
                "Requests waiting for a connection.",
                stats.get("requests_waiting"),
            ),
        ):
            if value is not None:
                family = GaugeMetricFamily(name, doc)
                family.add_metric([], value)
                out.append(family)
        return out


_collector: AppCollector | None = None


def install(database: Database | None, data_dir: Path | None) -> AppCollector:
    """Make this app's database and data directory the source of the scrape-time series
    (one app per process; a later call replaces the earlier one, as tests do)."""
    global _collector
    if _collector is not None:
        REGISTRY.unregister(_collector)
    _collector = AppCollector(database, data_dir)
    REGISTRY.register(_collector)
    return _collector


def serve(port: int, addr: str = "0.0.0.0") -> HTTPServer:  # noqa: S104 - container interface
    """Start the private listener in a daemon thread; the caller shuts it down."""
    server, _thread = start_http_server(port, addr=addr, registry=REGISTRY)
    return server
