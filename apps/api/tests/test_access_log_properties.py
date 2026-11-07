"""Property tests for the access log (privacy design §8, P1 and P3)."""

from __future__ import annotations

import json
import uuid
from urllib.parse import quote

from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from janus.main import create_app
from janus.observability.logging import UNMATCHED_ROUTE
from janus.settings import Settings
from tests.harness import capture_logs, stub_medical_router
from tests.sentinels import ascii_sentinels, leaked, sentinels

APP = create_app(Settings.from_env({}), extra_routers=[stub_medical_router()])
CLIENT = TestClient(APP, raise_server_exceptions=False)


def _access_lines(output: str) -> list[dict[str, object]]:
    lines = [json.loads(x) for x in output.splitlines() if x.startswith("{")]
    return [x for x in lines if x.get("event") == "access"]


@st.composite
def medical_requests(draw: st.DrawFn) -> tuple[str, str, dict[str, object], list[str]]:
    """(method, url, kwargs, secrets) for the stub routes and unmatched paths."""
    code = draw(sentinels())
    q = draw(sentinels())
    header = draw(ascii_sentinels())
    headers = {"X-Request-ID": header, "User-Agent": header, "X-Note": header}
    kind = draw(st.sampled_from(["resolve", "raise", "echo", "echo_fail", "unmatched", "bad_json"]))
    if kind in ("resolve", "raise"):
        mode = "raise" if kind == "raise" else "ok"
        url = f"/test/resolve/{quote(code)}?q={quote(q)}&mode={mode}"
        return "GET", url, {"headers": headers}, [code, q, header]
    if kind in ("echo", "echo_fail"):
        values = draw(st.lists(sentinels(), min_size=1, max_size=4))
        body = {"values": values, "fail": kind == "echo_fail"}
        return "POST", "/test/echo", {"json": body, "headers": headers}, [*values, header]
    if kind == "bad_json":
        values = draw(st.lists(sentinels(), min_size=1, max_size=3))
        body = {"values": values, "unexpected": 1, "fail": "notabool"}
        return "POST", "/test/echo", {"json": body, "headers": headers}, [*values, header]
    url = f"/{quote(code)}/{quote(q)}?x={quote(q)}"
    return "GET", url, {"headers": headers}, [code, q, header]


@given(medical_requests())
def test_no_medical_value_in_logs(req: tuple[str, str, dict[str, object], list[str]]) -> None:
    """Feature: privacy, Property P1. Validates Req 2.2."""
    method, url, kwargs, secrets = req
    with capture_logs() as buf:
        CLIENT.request(method, url, **kwargs)  # pyright: ignore[reportArgumentType]
    out = buf.getvalue()
    assert out, "expected at least the access line"
    assert leaked(out, secrets) == []


@given(medical_requests())
def test_one_access_line_with_template_route(
    req: tuple[str, str, dict[str, object], list[str]],
) -> None:
    """Feature: privacy, Property P3. Validates Req 2.2."""
    method, url, kwargs, _secrets = req
    with capture_logs() as buf:
        response = CLIENT.request(method, url, **kwargs)  # pyright: ignore[reportArgumentType]
    lines = _access_lines(buf.getvalue())
    assert len(lines) == 1
    line = lines[0]
    if url.startswith("/test/resolve/"):
        assert line["route"] == "/test/resolve/{code}"
    elif url.startswith("/test/echo"):
        assert line["route"] == "/test/echo"
    else:
        assert line["route"] == UNMATCHED_ROUTE
    assert line["status"] == response.status_code
    rid = response.headers["x-request-id"]
    assert line["request_id"] == rid
    assert uuid.UUID(rid).version == 4
    sent = kwargs["headers"]
    assert isinstance(sent, dict)
    assert rid != sent["X-Request-ID"]  # pyright: ignore[reportUnknownMemberType]
    latency = line["latency_ms"]
    assert isinstance(latency, float) and latency >= 0


def test_unhandled_error_returns_generic_500() -> None:
    with capture_logs() as buf:
        r = CLIENT.get("/test/resolve/zzabczz?mode=raise")
    assert r.status_code == 500
    assert r.json() == {"error": "internal_error", "request_id": r.headers["x-request-id"]}
    errors = [json.loads(x) for x in buf.getvalue().splitlines() if '"unhandled_error"' in x]
    assert errors and errors[0]["error_class"] == "RuntimeError"
    assert "zzabczz" not in buf.getvalue()


def test_method_not_allowed_logs_template() -> None:
    with capture_logs() as buf:
        r = CLIENT.delete("/test/resolve/zzabczz")
    assert r.status_code == 405
    assert _access_lines(buf.getvalue())[0]["route"] == "/test/resolve/{code}"
