"""Private Prometheus metrics (observability): fixed label sets, nothing about a request in the
exposition, the separate port, the queue, dataset and pool series."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import socket
import urllib.error
import urllib.request
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from prometheus_client import generate_latest

from janus.db.pool import Database
from janus.main import create_app
from janus.observability import metrics
from janus.observability.metrics import ARTIFACT_DATASETS, DATASETS, AppCollector
from janus.settings import Settings, SettingsError, parse_metrics_port
from janus.simulation import queue as q
from janus.simulation.allowlist import allowlist
from janus.simulation.schemas import canonical, input_hash, parse

REPO = Path(__file__).resolve().parents[3]
SECRET = "ertugliflozin"  # noqa: S105 - a drug key, not a credential


def exposition() -> str:
    return generate_latest(metrics.REGISTRY).decode()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def sample(text: str, name: str, **labels: str) -> float | None:
    want = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    for line in text.splitlines():
        m = re.fullmatch(r"([a-z_0-9]+)(?:\{(.*)\})? (\S+)", line)
        if not m or m.group(1) != name:
            continue
        got = ",".join(sorted((m.group(2) or "").split(","))) if m.group(2) else ""
        if got == want:
            return float(m.group(3))
    return None


def test_route_template_is_the_label_and_the_request_leaks_nothing() -> None:
    app = create_app(Settings.from_env({}), configure_logs=False)
    client = TestClient(app)
    client.get(f"/modelkit/drugs/{SECRET}?name=secretquery&code=zq7leakcode")
    client.get("/no-such-page-zzqx")
    client.request("BREW", "/health")
    text = exposition()
    assert 'route="/modelkit/drugs/{key}"' in text
    assert 'route="<unmatched>"' in text
    assert 'method="OTHER"' in text
    for leak in (SECRET, "secretquery", "zq7leakcode", "zzqx", "BREW", "testclient", "testserver"):
        assert leak not in text
    count = sample(
        text,
        "janus_http_requests_total",
        method="GET",
        route="/modelkit/drugs/{key}",
        status_class="5xx",
    )
    assert count is None or count >= 0
    assert sample(
        text,
        "janus_http_requests_total",
        method="GET",
        route="/health",
        status_class="2xx",
    ) in (None, *[float(i) for i in range(1, 1000)])


def test_status_classes_and_in_flight_returns_to_zero() -> None:
    app = create_app(Settings.from_env({}), configure_logs=False)
    client = TestClient(app)
    client.get("/health")
    client.get("/nope")
    text = exposition()
    assert sample(text, "janus_http_requests_in_flight") == 0.0
    assert sample(
        text,
        "janus_http_request_duration_seconds_count",
        method="GET",
        route="/health",
        status_class="2xx",
    )
    assert sample(
        text,
        "janus_http_requests_total",
        method="GET",
        route="<unmatched>",
        status_class="4xx",
    )
    labels = set(re.findall(r'status_class="([^"]*)"', text))
    assert labels <= {"1xx", "2xx", "3xx", "4xx", "5xx"}


def test_public_app_has_no_metrics_route_and_openapi_omits_it() -> None:
    app = create_app(Settings.from_env({}), configure_logs=False)
    client = TestClient(app)
    for path in ("/metrics", "/api/metrics", "/health/metrics", "/modelkit/metrics", "/metrics/"):
        assert client.get(path).status_code == 404, path
    committed = json.loads((REPO / "docs" / "openapi-public.json").read_text(encoding="utf-8"))
    for spec in (app.openapi(), committed):
        assert not [p for p in spec["paths"] if p.rstrip("/").endswith("/metrics")]
        assert "9464" not in json.dumps(spec)


def test_listener_is_a_separate_port_and_serves_the_exposition() -> None:
    port = free_port()
    settings = Settings.from_env({"JANUS_METRICS_PORT": str(port)})
    app = create_app(settings, configure_logs=False)
    with TestClient(app) as client:
        client.get("/health")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=5) as r:
            body = r.read().decode()
            assert r.headers["content-type"].startswith("text/plain")
        assert "janus_http_requests_total" in body
        assert "process_cpu_seconds_total" in body
        assert "python_info" in body
        assert client.get("/metrics").status_code == 404
    with pytest.raises(urllib.error.URLError):
        urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=2)


def test_no_listener_without_the_setting() -> None:
    assert Settings.from_env({}).metrics_port is None


@pytest.mark.parametrize("raw", ["80", "8000", "abc", "70000", "9464.5", "-9464"])
def test_metrics_port_is_validated(raw: str) -> None:
    with pytest.raises(SettingsError, match="JANUS_METRICS_PORT"):
        parse_metrics_port(raw)


def test_metrics_port_accepts_a_port() -> None:
    assert parse_metrics_port("9464") == 9464
    assert parse_metrics_port("") is None


def test_web_proxy_targets_one_fixed_origin_that_is_not_the_metrics_port() -> None:
    config = (REPO / "apps" / "web" / "next.config.ts").read_text(encoding="utf-8")
    rewrites = re.findall(r"destination:\s*`([^`]*)`", config)
    assert rewrites == ["${apiOrigin}/:path*"]
    assert 'source: "/api/:path*"' in config
    assert "9464" not in config
    assert "http://127.0.0.1:8000" in config
    dockerfile = (REPO / "apps" / "web" / "Dockerfile").read_text(encoding="utf-8")
    assert "JANUS_API_ORIGIN=http://api:8000" in dockerfile
    assert "9464" not in dockerfile


# --- datasets ------------------------------------------------------------------------------


def make_run(root: Path, name: str, snapshot: str | None, mtime: float) -> None:
    run = root / "artifacts" / name / "runs" / "r1"
    run.mkdir(parents=True)
    if snapshot:
        (run / "manifest.json").write_text(json.dumps({"snapshot_date": snapshot}))
    os.utime(run, (mtime, mtime))
    (root / "artifacts" / name / "current").symlink_to(run)


def test_dataset_freshness(tmp_path: Path) -> None:
    now = dt.datetime(2026, 11, 12, 12, 0, tzinfo=dt.UTC).timestamp()
    make_run(tmp_path, "us_labels", "2026-11-09", now - 3600)
    make_run(tmp_path, "titck", None, now - 100)
    light = tmp_path / "light" / "builds" / "b1"
    light.mkdir(parents=True)
    os.utime(light, (now - 50, now - 50))
    (tmp_path / "light" / "current").symlink_to(light)
    (tmp_path / "artifacts" / "us_ndc").mkdir()
    (tmp_path / "artifacts" / "us_ndc" / "current").symlink_to(tmp_path / "gone")  # dangling
    # A directory that is not on the fixed list is never reported.
    make_run(tmp_path, f"secret_{SECRET}", "2026-01-01", now)
    text = generate_latest_of(AppCollector(None, tmp_path, clock=lambda: now))
    assert sample(text, "janus_dataset_present", dataset="us_labels") == 1
    assert sample(text, "janus_dataset_present", dataset="us_ndc") == 0
    assert sample(text, "janus_dataset_present", dataset="eu_fr_bdpm") == 0
    assert sample(text, "janus_dataset_loaded_timestamp_seconds", dataset="us_labels") == now - 3600
    assert sample(text, "janus_dataset_age_seconds", dataset="us_labels") == 3600
    assert sample(text, "janus_dataset_age_seconds", dataset="titck") == 100
    assert sample(text, "janus_dataset_age_seconds", dataset="light") == 50
    assert sample(text, "janus_dataset_age_seconds", dataset="us_ndc") is None
    midnight = dt.datetime(2026, 11, 9, tzinfo=dt.UTC).timestamp()
    assert sample(text, "janus_dataset_snapshot_age_seconds", dataset="us_labels") == now - midnight
    assert sample(text, "janus_dataset_snapshot_age_seconds", dataset="titck") is None
    assert SECRET not in text
    names = set(re.findall(r'dataset="([^"]*)"', text))
    assert names <= set(DATASETS)


def generate_latest_of(collector: AppCollector) -> str:
    from prometheus_client import CollectorRegistry

    reg = CollectorRegistry()
    reg.register(collector)
    return generate_latest(reg).decode()


def test_dataset_series_are_cached_for_the_ttl(tmp_path: Path) -> None:
    clock = [1000.0]
    collector = AppCollector(None, tmp_path, clock=lambda: clock[0], ttl=15)
    first = generate_latest_of(collector)
    assert sample(first, "janus_dataset_present", dataset="titck") == 0
    make_run(tmp_path, "titck", None, 900.0)
    clock[0] += 14
    assert sample(generate_latest_of(collector), "janus_dataset_present", dataset="titck") == 0
    clock[0] += 2
    assert sample(generate_latest_of(collector), "janus_dataset_present", dataset="titck") == 1


def test_no_data_dir_means_no_dataset_series() -> None:
    assert "janus_dataset" not in generate_latest_of(AppCollector(None, None))


def test_dataset_list_matches_the_pipeline_jobs() -> None:
    jobs = REPO / "pipelines" / "janus_pipelines" / "jobs"
    if not jobs.is_dir():  # the API image does not carry the pipelines
        pytest.skip("pipelines not present")
    names: set[str] = set()
    for path in jobs.glob("*.py"):
        names |= set(re.findall(r'^    name = "([a-z0-9_]+)"$', path.read_text(), re.M))
    assert names == set(ARTIFACT_DATASETS)


def test_every_label_set_is_fixed_size() -> None:
    assert len(DATASETS) == len(set(DATASETS))
    assert len(DATASETS) < 40


# --- queue and pool (throwaway PostgreSQL) -------------------------------------------------

ALLOW = allowlist()


def _key(dose: float) -> tuple[dict[str, object], str]:
    c = canonical(
        parse(
            {
                "kind": "compartmental",
                "compound": "amlodipine",
                "population": "adult",
                "dose_mg": dose,
                "interval_h": None,
                "doses": 1,
                "samples": 200,
            },
            ALLOW,
        )
    )
    return c, input_hash(c, ALLOW.version)


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


@pytest.mark.db
def test_queue_metrics(db_url: str, db_conn: psycopg.Connection) -> None:
    db_conn.execute("TRUNCATE simulation_jobs")
    now = _utcnow()
    s = dt.timedelta(seconds=1)
    with db_conn.transaction():
        for i, (t_submit, t_start, t_end) in enumerate(
            [(300, 290, 280), (200, 190, 170), (100, 90, None), (80, None, None), (60, None, None)]
        ):
            canon, h = _key(2.5 + i / 10)
            job, _ = q.submit(db_conn, "compartmental", canon, h, now - t_submit * s)
            if t_start is not None:
                claimed = q.claim(db_conn, now - t_start * s)
                assert claimed is not None and claimed.id == job.id
            if t_end is not None:
                q.finish(db_conn, job.id, {"x": 1}, now - t_end * s)
    # One failure.
    canon, h = _key(7.5)
    with db_conn.transaction():
        job, _ = q.submit(db_conn, "compartmental", canon, h, now - 10 * s)
        db_conn.execute(
            "UPDATE simulation_jobs SET state = 'running', started_at = %s WHERE id = %s",
            (now - 9 * s, job.id),
        )
        q.fail(db_conn, job.id, "timeout", now - 5 * s)
    database = Database(db_url, max_size=3)
    database.open()
    try:
        text = generate_latest_of(AppCollector(database, None))
    finally:
        database.close()
    assert sample(text, "janus_simulation_queue_readable") == 1
    assert sample(text, "janus_simulation_jobs", state="queued") == 2
    assert sample(text, "janus_simulation_jobs", state="running") == 1
    assert sample(text, "janus_simulation_jobs", state="done") == 2
    assert sample(text, "janus_simulation_jobs", state="failed") == 1
    oldest = sample(text, "janus_simulation_oldest_queued_age_seconds")
    assert oldest is not None and 80 <= oldest < 100
    assert sample(text, "janus_simulation_recent_jobs_done") == 2
    p50 = sample(text, "janus_simulation_recent_job_duration_seconds", quantile="0.5")
    p95 = sample(text, "janus_simulation_recent_job_duration_seconds", quantile="0.95")
    assert p50 is not None and p95 is not None
    assert 10 <= p50 <= p95 <= 20
    assert sample(text, "janus_db_pool_max") == 3
    assert sample(text, "janus_db_pool_in_use") is not None
    assert sample(text, "janus_db_pool_waiting") == 0
    assert "amlodipine" not in text


@pytest.mark.db
def test_empty_queue(db_url: str, db_conn: psycopg.Connection) -> None:
    db_conn.execute("TRUNCATE simulation_jobs")
    database = Database(db_url, max_size=2)
    database.open()
    try:
        text = generate_latest_of(AppCollector(database, None))
    finally:
        database.close()
    assert sample(text, "janus_simulation_oldest_queued_age_seconds") == 0
    assert sample(text, "janus_simulation_jobs", state="queued") == 0
    assert sample(text, "janus_simulation_recent_jobs_done") == 0
    assert "janus_simulation_recent_job_duration_seconds" not in text


def test_unreachable_database_reports_unreadable_not_an_error() -> None:
    database = Database("postgresql://nobody:x@127.0.0.1:1/none?connect_timeout=1")
    text = generate_latest_of(AppCollector(database, None))
    assert sample(text, "janus_simulation_queue_readable") == 0
    assert "janus_simulation_jobs" not in text
