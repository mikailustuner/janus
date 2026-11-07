"""Property tests for donation storage, deletion, purge and region (design §8: P1, P6-P10,
P15, P16; tasks 9.1-9.7)."""

from __future__ import annotations

import base64
import datetime as dt
from collections.abc import Iterator
from fractions import Fraction
from typing import Any, cast

import psycopg
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.contributions import router as contributions_router
from janus.contributions.repository import purge_expired
from janus.contributions.retention import retention_cutoff
from janus.contributions.tokens import new_token, token_hash
from janus.contributions.week import report_week
from janus.db.pool import Database
from janus.main import create_app
from janus.memory.disclosure import Cell, keyed_noise_source, release_table
from janus.privacy.regions import EU_STORAGE_REGIONS, region_allows_donations
from janus.settings import Settings
from tests.conftest import DB_EXAMPLES
from tests.donation_strategies import CONSENT_VERSIONS, invalid_payloads, valid_payloads
from tests.harness import capture_logs, db_snapshot
from tests.sentinels import leaked

ALLOWED_COLUMNS = {
    "id",
    "report_week",
    "age_band",
    "sex",
    "region",
    "ingredients",
    "event",
    "direction",
    "consent_version",
    "deletion_token_hash",
}


def _settings(region: str | None = "local", consent: bool = True) -> Settings:
    env = {"JANUS_CONSENT_VERSIONS": ",".join(sorted(CONSENT_VERSIONS)) if consent else ""}
    if region is not None:
        env["JANUS_DONATION_REGION"] = region
    return Settings.from_env(env)


@pytest.fixture(scope="module")
def database(db_url: str) -> Iterator[Database]:
    db = Database(db_url)
    db.open()
    yield db
    db.close()


@pytest.fixture(scope="module")
def client(database: Database) -> Iterator[TestClient]:
    app = create_app(_settings(), database=database)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def clean(db_conn: psycopg.Connection) -> psycopg.Connection:
    db_conn.execute("TRUNCATE contributions")
    return db_conn


def _rows(conn: psycopg.Connection) -> list[tuple[Any, ...]]:
    return conn.execute(
        "SELECT id, report_week, age_band, sex, region, ingredients, event, direction, "
        "consent_version, deletion_token_hash FROM contributions ORDER BY id"
    ).fetchall()


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(payload=valid_payloads())
def test_stored_donation_has_only_allowed_fields(
    client: TestClient, clean: psycopg.Connection, payload: dict[str, Any]
) -> None:
    """Feature: privacy, Property P6. Validates Req 3.2."""
    clean.execute("TRUNCATE contributions")
    r = client.post("/contributions", json=payload)
    assert r.status_code == 201, r.text
    assert r.headers["cache-control"] == "no-store"
    columns = {
        c[0]
        for c in clean.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='contributions'"
        ).fetchall()
    }
    assert columns == ALLOWED_COLUMNS
    rows = _rows(clean)
    assert len(rows) == 1
    _id, week, age, sex, region, ingredients, event, direction, consent, token_h = rows[0]
    assert (age, sex, region, event, direction, consent) == (
        payload["age_band"],
        payload.get("sex"),
        payload["region"],
        payload["event"],
        payload["direction"],
        payload["consent"]["version"],
    )
    assert ingredients == sorted(payload["ingredients"])
    assert week.isoweekday() == 1
    assert token_h == token_hash(r.json()["deletion_token"])
    stored = r.json()["stored"]
    assert set(stored) == ALLOWED_COLUMNS - {"id", "deletion_token_hash"}


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(payload=invalid_payloads())
def test_invalid_donation_rejected_nothing_stored(
    client: TestClient, clean: psycopg.Connection, payload: dict[str, Any]
) -> None:
    """Feature: privacy, Property P7 (endpoint part). Validates Req 3.1, 3.2."""
    before = db_snapshot(clean)
    r = client.post("/contributions", json=payload)
    assert r.status_code == 422
    if payload.get("demo") is True:
        assert r.json() == {"error": "demo_donation_rejected"}
    assert db_snapshot(clean) == before


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(
    payload=valid_payloads(),
    now=st.datetimes(
        min_value=dt.datetime(2026, 1, 1),
        max_value=dt.datetime(2030, 12, 31),
        timezones=st.timezones(),
    ),
)
def test_stored_week_comes_from_server_clock(
    client: TestClient, clean: psycopg.Connection, payload: dict[str, Any], now: dt.datetime
) -> None:
    """Feature: privacy, Property P8 (router part). Validates Req 3.2."""
    clean.execute("TRUNCATE contributions")
    original = contributions_router.clock
    contributions_router.clock = lambda: now
    try:
        r = client.post("/contributions", json=payload)
    finally:
        contributions_router.clock = original
    assert r.status_code == 201
    row = clean.execute("SELECT report_week FROM contributions").fetchone()
    assert row is not None and row[0] == report_week(now)


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(payloads=st.lists(valid_payloads(), min_size=1, max_size=6), data=st.data())
def test_deletion_is_complete(
    client: TestClient,
    clean: psycopg.Connection,
    payloads: list[dict[str, Any]],
    data: st.DataObject,
) -> None:
    """Feature: privacy, Property P9. Validates Req 3.3."""
    clean.execute("TRUNCATE contributions")
    tokens = [client.post("/contributions", json=p).json()["deletion_token"] for p in payloads]
    victim = data.draw(st.integers(0, len(tokens) - 1))
    by_hash = {row[9]: row for row in _rows(clean)}
    victim_row = by_hash[token_hash(tokens[victim])]
    r = client.post("/contributions/deletions", json={"deletion_token": tokens[victim]})
    assert r.status_code == 200 and r.json() == {"deleted": True}
    assert r.headers["cache-control"] == "no-store"
    remaining = _rows(clean)
    assert remaining == sorted(row for h, row in by_hash.items() if h != victim_row[9])
    # No query finds it: by id, by its exact field combination, by full scan.
    assert (
        clean.execute("SELECT 1 FROM contributions WHERE id = %s", (victim_row[0],)).fetchone()
        is None
    )
    combo = clean.execute(
        "SELECT count(*) FROM contributions WHERE deletion_token_hash = %s", (victim_row[9],)
    ).fetchone()
    assert combo == (0,)
    assert victim_row not in remaining
    # An aggregate computed afterwards does not count it.
    counts = clean.execute("SELECT region, count(*) FROM contributions GROUP BY region").fetchall()
    cells = [Cell((region,), n * 20) for region, n in counts]  # scaled so cells are released
    release = release_table(
        cells,
        k=20,
        epsilon=Fraction(1),
        noise_source=keyed_noise_source(bytes(32)),
        data_version="after-delete",
    )
    assert sum(n for _r, n in counts) == len(payloads) - 1
    assert len(release.cells) == len(counts)


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(payload=valid_payloads(), other=st.builds(new_token))
def test_token_secret_and_single_use(
    client: TestClient, clean: psycopg.Connection, payload: dict[str, Any], other: str
) -> None:
    """Feature: privacy, Property P10. Validates Req 3.3."""
    clean.execute("TRUNCATE contributions")
    token = client.post("/contributions", json=payload).json()["deletion_token"]
    payload_part = token.removeprefix("jdt_")
    raw = base64.urlsafe_b64decode(payload_part + "=")
    for row in _rows(clean):
        for value in row:
            text = value if isinstance(value, str) else repr(value)
            assert token not in text and payload_part not in text
            if isinstance(value, bytes):
                assert raw not in value
    before = _rows(clean)
    r = client.post("/contributions/deletions", json={"deletion_token": other})
    assert r.status_code == 404
    assert _rows(clean) == before
    assert (
        client.post("/contributions/deletions", json={"deletion_token": token}).status_code == 200
    )
    assert (
        client.post("/contributions/deletions", json={"deletion_token": token}).status_code == 404
    )


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(
    weeks=st.lists(
        st.dates(min_value=dt.date(2024, 1, 1), max_value=dt.date(2027, 12, 31)).map(
            lambda d: d - dt.timedelta(days=d.weekday())
        ),
        max_size=15,
    ),
    day=st.dates(min_value=dt.date(2025, 1, 1), max_value=dt.date(2029, 12, 31)),
)
def test_purge_deletes_exactly_expired(
    database: Database, clean: psycopg.Connection, weeks: list[dt.date], day: dt.date
) -> None:
    """Feature: privacy, Property P16 (database part). Validates Req 3.6."""
    clean.execute("TRUNCATE contributions")
    for i, week in enumerate(weeks):
        clean.execute(
            "INSERT INTO contributions (report_week, age_band, region, ingredients, event, "
            "direction, consent_version, deletion_token_hash) "
            "VALUES (%s, 40, 'EU', ARRAY['Q1'], 'cough', 'adverse', '2026-11-v1', %s)",
            (week, token_hash(f"t{i}")),
        )
    cutoff = retention_cutoff(day)
    expected_left = sorted(w for w in weeks if w > cutoff)
    deleted = purge_expired(database, day)
    assert deleted == sum(1 for w in weeks if w <= cutoff)
    left = sorted(r[0] for r in clean.execute("SELECT report_week FROM contributions").fetchall())
    assert left == expected_left
    assert purge_expired(database, day) == 0


@given(
    st.one_of(
        st.sampled_from([*sorted(EU_STORAGE_REGIONS), "local"]),
        st.sampled_from(
            [
                "eu-zurich-1",
                "eu-jovanovac-1",
                "uk-london-1",
                "EU-FRANKFURT-1",
                "eu-frankfurt-1 ",
                " local",
                "LOCAL",
                "eu-frankfurt",
                "eu-frankfurt-2",
                "me-dubai-1",
                "",
            ]
        ),
        st.text(max_size=20),
    )
)
def test_region_guard(region: str) -> None:
    """Feature: privacy, Property P15. Validates Req 3.4."""
    assert region_allows_donations(region) == (region == "local" or region in EU_STORAGE_REGIONS)
    assert not region_allows_donations("eu-zurich-1")
    assert not region_allows_donations(None)


@pytest.mark.db
def test_storage_endpoint_and_disabled_routes(database: Database) -> None:
    """Task 9.7. Validates Req 3.4, 5.2."""
    app = create_app(_settings(), database=database)
    with TestClient(app) as c:
        r = c.get("/privacy/storage")
        assert r.json() == {
            "donation_storage_region": "local",
            "in_eu": False,
            "donations_enabled": True,
        }
        text = r.text.lower()
        for claim in ("compliant", "certified", "gdpr", "hipaa", "audit"):
            assert claim not in text
    for settings_ in (
        _settings(region=None),
        _settings(region="eu-zurich-1"),
        _settings(consent=False),
    ):
        disabled = create_app(settings_, database=database)
        with TestClient(disabled) as c:
            assert c.get("/privacy/storage").json()["donations_enabled"] is False
            r = c.post("/contributions", json={"anything": 1})
            assert r.status_code == 503
            r = c.post("/contributions/deletions", json={"deletion_token": new_token()})
            assert r.status_code == 503
    eu = create_app(_settings(region="eu-frankfurt-1"), database=database)
    with TestClient(eu) as c:
        assert c.get("/privacy/storage").json() == {
            "donation_storage_region": "eu-frankfurt-1",
            "in_eu": True,
            "donations_enabled": True,
        }
    no_db = create_app(_settings())
    with TestClient(no_db) as c:
        assert c.post("/contributions", json={}).status_code == 503


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(payload=st.one_of(valid_payloads(), invalid_payloads()))
def test_donation_values_never_logged(
    client: TestClient, clean: psycopg.Connection, payload: dict[str, Any]
) -> None:
    """Feature: privacy, Property P1 over the donation routes. Validates Req 2.2."""
    with capture_logs() as buf:
        r = client.post("/contributions", json=payload)
        if r.status_code == 201:
            token = r.json()["deletion_token"]
            client.post("/contributions/deletions", json={"deletion_token": token})
    out = buf.getvalue()
    ingredients = payload.get("ingredients")
    values: list[str] = []
    if isinstance(ingredients, list):
        values = [v for v in cast(list[object], ingredients) if isinstance(v, str)]
    for key in ("event", "region", "sex", "direction"):
        if isinstance(payload.get(key), str) and len(payload[key]) >= 4:
            values.append(payload[key])
    if r.status_code == 201:
        values.append(r.json()["deletion_token"])
    assert leaked(out, [v for v in values if isinstance(v, str)]) == []
