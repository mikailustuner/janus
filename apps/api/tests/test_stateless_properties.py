"""Property tests for stateless medical endpoints and the body policy (design §8, P4, P5)."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st
from psycopg import sql

from janus.db.pool import Database
from janus.http_policy.body_limits import MAX_BODY_BYTES
from janus.http_policy.routes import RouteClassificationError, classify, medical_router
from janus.main import create_app
from janus.settings import Settings
from tests.conftest import DB_EXAMPLES
from tests.harness import (
    STUB_TABLE,
    assert_stateless,
    isolated_tempdir,
    stub_medical_router,
    tmp_snapshot,
)
from tests.sentinels import sentinels

JANUS = Path(__file__).resolve().parents[1] / "janus"


@pytest.fixture(scope="module")
def stub_client(db_url: str) -> Iterator[TestClient]:
    with psycopg.connect(db_url, autocommit=True) as conn:
        table = sql.Identifier(STUB_TABLE)
        conn.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (v text)").format(table))
        conn.execute(sql.SQL("INSERT INTO {} (v) VALUES ('baseline')").format(table))
    app = create_app(
        Settings.from_env({}),
        database=Database(db_url),
        extra_routers=[stub_medical_router(with_db=True)],
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(STUB_TABLE)))


@pytest.mark.db
@settings(max_examples=DB_EXAMPLES)
@given(
    code=sentinels(),
    route=st.sampled_from(["db", "resolve", "echo"]),
    values=st.lists(sentinels(), min_size=1, max_size=3),
)
def test_medical_requests_persist_nothing(
    stub_client: TestClient, db_conn: psycopg.Connection, code: str, route: str, values: list[str]
) -> None:
    """Feature: privacy, Property P4. Validates Req 2.1."""
    with isolated_tempdir() as tmp:

        def call() -> object:
            if route == "db":
                return stub_client.get(f"/test/db/{code}")
            if route == "resolve":
                return stub_client.get(f"/test/resolve/{code}", params={"q": values[0]})
            return stub_client.post("/test/echo", json={"values": values})

        response = assert_stateless(db_conn, tmp, call)
    assert response.headers["cache-control"] == "no-store"  # type: ignore[attr-defined]
    if route == "db":
        assert response.json() == {"write_blocked": True}  # type: ignore[attr-defined]


APP = create_app(Settings.from_env({}), extra_routers=[stub_medical_router()])
CLIENT = TestClient(APP, raise_server_exceptions=False)

CONTENT_TYPES = st.sampled_from(
    [
        None,
        "multipart/form-data; boundary=xyz",
        "image/png",
        "application/x-www-form-urlencoded",
        "text/plain",
        "application/jsonx",
        "application/json",
        "application/json; charset=utf-8",
    ]
)


@given(
    content_type=CONTENT_TYPES,
    size=st.sampled_from([0, 10, MAX_BODY_BYTES - 1, MAX_BODY_BYTES, MAX_BODY_BYTES + 1, 200_000]),
    send_length=st.booleans(),
    path=st.sampled_from(["/test/echo", "/contributions", "/test/unknown"]),
)
def test_body_policy(content_type: str | None, size: int, send_length: bool, path: str) -> None:
    """Feature: privacy, Property P5. Validates Req 1.4, 2.1."""
    prefix = b'{"values": ["'
    suffix = b'"]}'
    filler = max(0, size - len(prefix) - len(suffix))
    body = prefix + b"a" * filler + suffix
    headers: dict[str, str] = {}
    if content_type is not None:
        headers["content-type"] = content_type
    with isolated_tempdir() as tmp:
        before = tmp_snapshot(tmp)
        if send_length:
            response = CLIENT.post(path, content=body, headers=headers)
        else:
            response = CLIENT.post(path, content=iter([body]), headers=headers)
        assert tmp_snapshot(tmp) == before
    is_json = content_type is not None and content_type.split(";")[0] == "application/json"
    if not is_json:
        assert response.status_code == 415
    elif len(body) > MAX_BODY_BYTES:
        assert response.status_code == 413
    else:
        assert response.status_code not in (413, 415)
    assert response.headers["cache-control"] == "no-store"


def test_classify_rejects_unclassified_route() -> None:
    app = FastAPI()

    @app.get("/plain")
    def plain() -> int:  # pyright: ignore[reportUnusedFunction]
        return 1

    with pytest.raises(RouteClassificationError):
        classify(app, [])


def test_classify_rejects_prefix_and_unlisted_operational() -> None:
    from janus.http_policy.routes import operational_router

    app = FastAPI()
    op = operational_router()

    @op.get("/not-listed")
    def nl() -> int:  # pyright: ignore[reportUnusedFunction]
        return 1

    app.include_router(op)
    with pytest.raises(RouteClassificationError):
        classify(app, [op])
    pref = medical_router(prefix="/x")
    with pytest.raises(RouteClassificationError):
        classify(FastAPI(), [pref])


def test_write_tx_used_only_by_contributions_repository() -> None:
    """`write_tx` is the only write path; only the donation repository may use it (DP5)."""
    users: list[str] = []
    for path in JANUS.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "write_tx":
                users.append(str(path.relative_to(JANUS)))
            if isinstance(node, ast.ImportFrom) and any(a.name == "write_tx" for a in node.names):
                users.append(str(path.relative_to(JANUS)))
    assert set(users) <= {"contributions/repository.py"}
