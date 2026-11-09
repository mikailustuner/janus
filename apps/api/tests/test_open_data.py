"""Open data (open-data design §7): the released outcome dataset and the cascade data package.

Property tests over the pure parts; database tests run against real PostgreSQL 16
(`JANUS_TEST_DATABASE_URL`, after migrations), like the Collective Memory user layers.
"""

from __future__ import annotations

import base64
import csv
import datetime as dt
import hashlib
import io
import json
import os
from collections.abc import Iterator, Sequence
from fractions import Fraction

import psycopg
import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from janus.db.pool import Database
from janus.main import create_app
from janus.memory.disclosure import keyed_noise_source
from janus.memory.shared import ContributionsSource, UserLayerSource
from janus.notes.source import OutcomesSource
from janus.open import outcomes as o
from janus.open import package as pkg
from janus.settings import Settings

KEY = b"o" * 32
NOISE = keyed_noise_source(KEY)
K = 20
EPS = Fraction(1)
MONDAY = dt.date(2026, 11, 2)
SOURCES: dict[str, UserLayerSource] = {
    "contributions": ContributionsSource(),
    "outcomes": OutcomesSource(),
}
INSERT = (
    "INSERT INTO contributions (report_week, age_band, sex, region, ingredients, event, direction, "
    "consent_version, deletion_token_hash) VALUES (%s, 40, NULL, %s, %s, %s, %s, 'v1', %s)"
)


# --- the cascade data package (no database) ------------------------------------------------


def test_committed_package_is_what_the_builder_writes() -> None:
    """Req 4.4: `data/open/cascade-package/` is generated; a stale copy fails CI."""
    assert pkg.check() == []


def test_package_has_no_titck_row_and_a_licence_per_file() -> None:
    files = pkg.build()
    meta = json.loads(files["datapackage.json"])
    hashes = pkg.titck_hashes()
    assert hashes, "the TİTCK name hashes are committed"
    for res in meta["resources"]:
        assert res["licenses"], res["name"]
        assert res["sources"], res["name"]
        text = files[res["path"]]
        assert res["hash"].endswith(hashlib.sha256(text.encode()).hexdigest())
    rows = list(csv.DictReader(io.StringIO(files["ingredient_synonyms.csv"])))
    for r in rows:
        assert not pkg.cites_titck(r["note"])
        assert not pkg.from_coverage_report(r["note"])
        assert pkg.name_hash(r["name"]) not in hashes
    pipc = next(r for r in meta["resources"] if r["name"] == "pipc")
    assert [x["name"] for x in pipc["licenses"]] == ["CC-BY-4.0"]
    assert "10.1007/s41999-025-01215-x" in files["README.md"]


@given(st.text(max_size=40), st.sampled_from(["TİTCK", "titck", "TITCK", "Titck"]))
def test_any_titck_citation_is_recognised(prefix: str, word: str) -> None:
    assert pkg.cites_titck(f"{prefix} {word} code")


@given(st.text(min_size=1, max_size=30))
def test_name_hash_ignores_case_and_spacing(name: str) -> None:
    assert pkg.name_hash(name) == pkg.name_hash(f"  {name.upper()}  ".casefold())


def test_package_check_runs_against_the_local_titck_list() -> None:
    """When the TİTCK artifact is present, no published synonym occurs in it (local only)."""
    root = os.environ.get("JANUS_DATA_DIR")
    path = None if not root else os.path.join(root, "artifacts/titck/current/rows.parquet")
    if not path or not os.path.isfile(path):
        pytest.skip("no local TİTCK artifact")
    import duckdb

    values = (
        duckdb.connect()
        .execute("SELECT product_name, ingredient_text FROM read_parquet(?)", [path])
        .fetchall()
    )
    blob = "\n".join(" ".join(str(v).casefold().split()) for row in values for v in row if v)
    rows = csv.DictReader(io.StringIO(pkg.build()["ingredient_synonyms.csv"]))
    assert [r["name"] for r in rows if " ".join(r["name"].casefold().split()) in blob] == []


# --- the outcome dataset: pure parts -------------------------------------------------------


cells_st = st.lists(
    st.builds(
        o.OpenCell,
        layer=st.sampled_from(o.LAYERS),
        ingredients=st.lists(st.sampled_from(["Q1", "Q2", "Q3"]), min_size=1, max_size=2).map(
            lambda xs: tuple(sorted(set(xs)))
        ),
        event=st.sampled_from(["cough", "oedema"]),
        direction=st.sampled_from(["adverse", "benefit"]),
        region=st.sampled_from(["TR", "EU", "US"]),
        value=st.integers(0, 500),
    ),
    max_size=12,
)


@given(cells_st)
def test_csv_has_one_row_per_cell_and_the_version(cells: list[o.OpenCell]) -> None:
    v = o.version(cells, K, EPS)
    text = o.to_csv(cells, v, MONDAY)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert next(iter(csv.reader(io.StringIO(text)))) == list(o.CSV_COLUMNS)
    assert len(rows) == len(cells)
    assert all(r["dataset_version"] == v for r in rows)
    assert [int(r["value"]) for r in rows] == [c.value for c in cells]


@given(cells_st, cells_st)
def test_version_changes_with_the_released_content_only(
    a: list[o.OpenCell], b: list[o.OpenCell]
) -> None:
    assert (o.version(a, K, EPS) == o.version(b, K, EPS)) == (a == b)
    assert o.version(a, K, EPS).startswith(o.RULE_VERSION + "+")


# --- database ------------------------------------------------------------------------------


def reset(conn: psycopg.Connection) -> None:
    conn.execute("DELETE FROM contributions")
    conn.execute("DELETE FROM outcomes")


@pytest.fixture
def conn(db_conn: psycopg.Connection) -> Iterator[psycopg.Connection]:
    reset(db_conn)
    yield db_conn
    reset(db_conn)


def add(
    conn: psycopg.Connection,
    region: str,
    ingredients: Sequence[str],
    n: int,
    event: str = "cough",
    direction: str = "adverse",
) -> None:
    rows = [
        (MONDAY, region, sorted(ingredients), event, direction, os.urandom(32)) for _ in range(n)
    ]
    with conn.cursor() as cur:
        cur.executemany(INSERT, rows)


def release(conn: psycopg.Connection) -> list[o.OpenCell]:
    """Release as if consent "v1" named open publication (the test rows use it)."""
    cells, withheld = o.release(
        conn, SOURCES, k=K, epsilon=EPS, noise_source=NOISE, consent_versions=frozenset({"v1"})
    )
    assert withheld == []
    return cells


@pytest.mark.db
def test_a_layer_without_open_release_consent_is_withheld_whole(conn: psycopg.Connection) -> None:
    """Review O1 (DP10): no consent version names open publication yet, so stored donations are
    never published here, however large the group."""
    assert o.OPEN_RELEASE_CONSENT_VERSIONS == frozenset()
    add(conn, "EU", ["Q11"], 40)
    cells, withheld = o.release(conn, SOURCES, k=K, epsilon=EPS, noise_source=NOISE)
    assert cells == [] and withheld == ["contributions"]


@pytest.mark.db
def test_empty_store_releases_nothing(conn: psycopg.Connection) -> None:
    assert release(conn) == []


@pytest.mark.db
@pytest.mark.parametrize("n", [1, 19])
def test_a_group_under_k_is_never_listed(conn: psycopg.Connection, n: int) -> None:
    add(conn, "EU", ["Q11"], n)
    assert release(conn) == []


@pytest.mark.db
def test_a_group_of_k_is_released_with_noise_and_matches_the_memory_answer(
    conn: psycopg.Connection,
) -> None:
    add(conn, "EU", ["Q11", "Q12"], 25)
    add(conn, "US", ["Q11"], 3)
    cells = release(conn)
    regions = {(c.ingredients, c.region) for c in cells}
    # {Q11} in EU: 25 donations; {Q11, Q12} in EU: 25; {Q12} in EU: 25. US has 3: hidden.
    assert regions == {(("Q11",), "EU"), (("Q12",), "EU"), (("Q11", "Q12"), "EU")}
    assert all(c.layer == "contributions" and c.value >= 0 for c in cells)
    # Same cell, same value as the Collective Memory route (one release path, DP2).
    from janus.memory.schemas import SharedIn
    from janus.memory.shared import shared

    req = SharedIn.model_validate(
        {
            "layer": "contributions",
            "ingredients": ["Q11", "Q12"],
            "event": "cough",
            "direction": "adverse",
        }
    )
    ans = shared(req, sources=SOURCES, conn=conn, noise_source=NOISE, k=K, epsilon=EPS)
    eu = next(c for c in ans.cells if c.region == "EU")
    mine = next(c for c in cells if c.ingredients == ("Q11", "Q12"))
    assert eu.value == mine.value
    assert release(conn) == cells  # deterministic


@pytest.mark.db
def test_the_sibling_rule_hides_a_cell_that_would_reveal_a_small_group(
    conn: psycopg.Connection,
) -> None:
    add(conn, "TR", ["Q11", "Q13"], 22)
    add(conn, "TR", ["Q11"], 3)
    got = {(c.ingredients, c.region) for c in release(conn)}
    # {Q11} has 25, but 25 - 22 = 3 of them do not name Q13: releasing both {Q11} and
    # {Q11, Q13} would reveal a group of 3, so {Q11} is hidden.
    assert (("Q11",), "TR") not in got
    assert (("Q11", "Q13"), "TR") in got
    assert (("Q13",), "TR") in got


@pytest.fixture
def client(db_url: str) -> Iterator[TestClient]:
    key = base64.urlsafe_b64encode(KEY).decode()
    db = Database(db_url)
    db.open()
    app = create_app(
        Settings.from_env({"DATABASE_URL": db_url, "JANUS_NOISE_KEY": key}),
        database=db,
        configure_logs=False,
    )
    yield TestClient(app, raise_server_exceptions=False)
    db.close()


@pytest.mark.db
def test_routes_answer_the_empty_state_and_csv(
    client: TestClient, conn: psycopg.Connection
) -> None:
    r = client.get("/open/outcomes")
    assert r.status_code == 200
    body = r.json()
    assert body["cells"] == []
    assert body["license"] == "CC BY 4.0"
    assert body["release_rule"]["k"] == K and body["release_rule"]["hidden_cells_listed"] is False
    assert body["version"].startswith("open-outcomes-1+")
    c = client.get("/open/outcomes.csv")
    assert c.status_code == 200
    assert c.headers["content-type"].startswith("text/csv")
    assert c.text.strip() == ",".join(o.CSV_COLUMNS)
    assert c.headers["x-janus-dataset-version"] == body["version"]
    assert body["withheld_layers"] == []
    add(conn, "US", ["Q11"], 21)
    body = client.get("/open/outcomes").json()
    # The rows' consent (v1) does not name open publication: the layer is withheld whole.
    assert body["cells"] == [] and body["withheld_layers"] == ["contributions"]
    assert "no-store" in client.get("/open/outcomes").headers.get("cache-control", "")


def test_routes_refuse_without_the_release_rule() -> None:
    app = create_app(Settings.from_env({}), database=None, configure_logs=False)
    c = TestClient(app, raise_server_exceptions=False)
    for path in ("/open/outcomes", "/open/outcomes.csv"):
        r = c.get(path)
        assert r.status_code == 503
        assert r.json() == {"error": "open_data_unavailable"}


# --- the public API document ---------------------------------------------------------------


def test_public_openapi_document_is_current_and_read_only() -> None:
    """Req 7: `docs/openapi-public.json` is generated from the app and lists GET routes only,
    none with a request body; every path exists in the app."""
    from janus.open import openapi

    assert openapi.OUT.read_text(encoding="utf-8") == openapi.text()
    doc = json.loads(openapi.text())
    assert sorted(doc["paths"]) == sorted(openapi.PUBLIC)
    for path, item in doc["paths"].items():
        assert list(item) == ["get"], path
        assert "requestBody" not in item["get"], path
