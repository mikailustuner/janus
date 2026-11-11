"""MCP server against a stub API: P1-P7 and examples (mcp-server task 3)."""

from __future__ import annotations

import contextlib
import io
import logging
import re
import string
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from mcp import Client

from janus_mcp import safety
from janus_mcp.config import ConfigError, from_env
from tests.stub import StubApi, call, text_of, with_client

TOOLS = {
    "janus_resolve_code",
    "janus_resolve_ndc",
    "janus_search_medicines",
    "janus_check_cascades",
    "janus_cascade_package_rows",
    "janus_time_machine_catalogue",
    "janus_time_machine_cascade",
    "janus_modelkit_search",
    "janus_modelkit_get",
}
DATASET = "a" * 64
# medical-safety.md rule 2, all five languages (kept equal to the steering file by hand).
FORBIDDEN = {
    "en": ["stop taking", "you should stop", "discontinue", "unnecessary medicine", "cure",
           "cures", "treatment for", "diagnosis", "you have", "safe to stop",
           "your medicines are safe"],
    "tr": ["ilacı bırakın", "ilacınızı kesin", "gereksiz ilaç", "tedavi eder", "tanı",
           "ilaçlarınız güvenli"],
    "de": ["absetzen Sie", "nicht mehr einnehmen", "unnötiges Medikament", "heilt", "Diagnose"],
    "fr": ["arrêtez de prendre", "médicament inutile", "guérit", "diagnostic"],
    "es": ["deje de tomar", "medicamento innecesario", "cura", "diagnóstico"],
}  # fmt: skip
SENTINEL = st.text(alphabet="ghjkmnpqrstuvwxy", min_size=3, max_size=10).map(lambda t: f"zz{t}zz")


def forbidden_in(text: str) -> list[str]:
    found: list[str] = []
    for phrases in FORBIDDEN.values():
        for p in phrases:
            if re.search(rf"(?<![^\W\d_]){re.escape(p)}(?![^\W\d_])", text, re.IGNORECASE):
                found.append(p)
    return found


@contextlib.contextmanager
def captured() -> Generator[io.StringIO]:
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    root = logging.getLogger()
    old = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            yield buffer
    finally:
        root.removeHandler(handler)
        root.setLevel(old)


# --- Tool list -------------------------------------------------------------------------------


def test_tool_list_and_annotations() -> None:
    async def tools(c: Client) -> Any:
        return (await c.list_tools()).tools

    listed = with_client(tools)
    assert {t.name for t in listed} == TOOLS
    for t in listed:
        assert t.annotations is not None
        assert t.annotations.read_only_hint is True
        assert t.annotations.open_world_hint is False
        assert safety.DISCLAIMER in (t.description or "")


def test_p5_no_forbidden_phrase_in_texts() -> None:
    """P5: descriptions, instructions and safety texts hold no forbidden phrase."""

    async def tools(c: Client) -> Any:
        return (await c.list_tools()).tools

    texts = [t.description or "" for t in with_client(tools)]
    texts += [safety.INSTRUCTIONS, safety.EMERGENCY, safety.DISCLAIMER, *safety.WORDING]
    texts += [*safety.CHECK_LINES, *safety.TIME_MACHINE_LINES, *safety.PACKAGE_LINES]
    texts += [*safety.RESOLVE_LINES, *safety.MODELKIT_LINES]
    for t in texts:
        assert forbidden_in(t) == [], t
    for path in Path(__file__).parents[1].joinpath("janus_mcp").glob("*.py"):
        assert forbidden_in(path.read_text(encoding="utf-8")) == [], path


# --- P1: requests are the API's contracts -----------------------------------------------------

REGION = st.none() | st.sampled_from(["TR", "US", "EU"])
QUERY = st.text(alphabet=string.ascii_letters + " ", min_size=2, max_size=40).filter(
    lambda q: len(q.strip()) >= 2
)


@st.composite
def check_items(draw: st.DrawFn) -> dict[str, str]:
    if draw(st.booleans()):
        return {"ingredient": f"Q{draw(st.integers(1, 10**9))}"}
    item = {"product": f"TR:titck:{draw(st.integers(0, 10**9 - 1))}"}
    month = draw(st.none() | st.sampled_from(["2024-01", "2026-11"]))
    return item | ({"started": month} if month else {})


@st.composite
def tool_calls(draw: st.DrawFn) -> tuple[str, dict[str, Any], str, str, Any]:
    kind = draw(st.sampled_from(sorted(TOOLS)))
    if kind == "janus_resolve_code":
        code, region = draw(st.text(string.digits, min_size=8, max_size=14)), draw(REGION)
        args: dict[str, Any] = {"code": code} | ({"region": region} if region else {})
        body = {"content": code} | ({"region": region} if region else {})
        return kind, args, "POST", "/resolve/scan", body
    if kind == "janus_resolve_ndc":
        ndc = draw(st.text(string.digits + "-", min_size=1, max_size=13))
        return kind, {"ndc": ndc}, "POST", "/resolve/ndc", {"ndc": ndc}
    if kind == "janus_search_medicines":
        q, region, limit = draw(QUERY), draw(REGION), draw(st.integers(1, 20))
        args = {"query": q, "limit": limit} | ({"region": region} if region else {})
        body = {"query": q.strip(), "limit": limit} | ({"region": region} if region else {})
        return kind, args, "POST", "/resolve/search", body
    if kind == "janus_check_cascades":
        items = draw(st.lists(check_items(), min_size=1, max_size=5))
        args = {"dataset_version": DATASET, "items": items}
        return kind, args, "POST", "/cascades/evaluate", args
    if kind == "janus_cascade_package_rows":
        return kind, {}, "GET", "/open/cascade-package/pipc", None
    if kind == "janus_time_machine_catalogue":
        return kind, {}, "GET", "/timemachine/catalogue", None
    if kind == "janus_modelkit_search":
        return kind, {}, "GET", "/modelkit/drugs", None
    if kind == "janus_modelkit_get":
        key = draw(st.text(string.ascii_lowercase, min_size=1, max_size=20))
        return kind, {"key": key}, "GET", f"/modelkit/drugs/{key}", None
    cid = draw(st.text(string.ascii_lowercase + "_", min_size=1, max_size=30))
    return kind, {"cascade_id": cid}, "GET", f"/timemachine/cascade/{cid}", None


JSON = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=10),
    lambda kids: (
        st.lists(kids, max_size=3) | st.dictionaries(st.text(max_size=5), kids, max_size=3)
    ),
    max_leaves=10,
)


@settings(max_examples=60, deadline=None)
@given(tool_calls(), st.dictionaries(st.text(min_size=1, max_size=5), JSON, max_size=4))
def test_p1_p2_request_and_result_unchanged(
    c: tuple[str, dict[str, Any], str, str, Any], api_body: dict[str, Any]
) -> None:
    """P1: the request has the API's field names and the values unchanged. P2: the API JSON is
    returned unchanged under `result`, with the safety block."""
    tool, args, method, path, body = c
    stub = StubApi(body=api_body)
    r = call(stub, tool, args)
    assert not r.is_error, text_of(r)
    assert len(stub.sent) == 1
    sent = stub.sent[0]
    assert (sent.method, sent.path, sent.body) == (method, path, body)
    out = r.structured_content
    assert out is not None
    assert out["result"] == api_body
    assert out["janus_safety"]["disclaimer"] == safety.DISCLAIMER
    assert out["janus_safety"]["emergency"] == safety.EMERGENCY


# --- P3, P4: errors and logs carry no value ---------------------------------------------------


@settings(max_examples=40, deadline=None)
@given(
    SENTINEL,
    st.sampled_from(["cascades_unavailable", "invalid_request", "dataset_version_mismatch"]),
    st.lists(st.sampled_from(["items.0.product", "items.1.started", "body"]), max_size=3),
    st.sampled_from([409, 422, 503]),
)
def test_p3_p4_errors_and_logs(secret: str, code: str, fields: list[str], status: int) -> None:
    stub = StubApi(status=status, body={"error": code, "fields": fields})
    args = {"dataset_version": DATASET, "items": [{"ingredient": "Q1"}]}
    with captured() as logs:
        r = call(stub, "janus_search_medicines", {"query": secret})
        r2 = call(stub, "janus_check_cascades", args)
    assert r.is_error and r2.is_error
    want = f"janus_api_error: {code}" + (f" fields: {', '.join(fields)}" if fields else "")
    assert text_of(r).endswith(f": {want}")
    assert secret not in text_of(r)
    assert secret not in logs.getvalue()
    assert "Q1" not in logs.getvalue()


@settings(max_examples=30, deadline=None)
@given(SENTINEL)
def test_p4_nothing_logged_on_success_or_unreachable(secret: str) -> None:
    with captured() as logs:
        ok = call(StubApi(), "janus_resolve_code", {"code": secret})
        down = call(StubApi(raise_error=True), "janus_resolve_code", {"code": secret})
        bad = call(StubApi(), "janus_time_machine_cascade", {"cascade_id": secret + "!"})
    assert not ok.is_error
    assert down.is_error and text_of(down).endswith(": janus_api_unreachable")
    assert bad.is_error
    assert secret not in logs.getvalue()


def test_non_json_answer_is_bad_response() -> None:
    import httpx2

    from janus_mcp.config import from_env as cfg
    from janus_mcp.server import build_server

    server = build_server(cfg({}), httpx2.MockTransport(lambda _: httpx2.Response(502, text="x")))

    async def go(c: Client) -> Any:
        return await c.call_tool("janus_time_machine_catalogue", {})

    import anyio

    async def run() -> Any:
        async with Client(server) as c:
            return await go(c)

    r = anyio.run(run)
    assert r.is_error and text_of(r).endswith(": janus_api_bad_response")


# --- P6: arguments outside the API's limits are refused before a request ----------------------

BAD_ARGS: list[tuple[str, dict[str, Any]]] = [
    ("janus_resolve_code", {"code": ""}),
    ("janus_resolve_code", {"code": "x" * 513}),
    ("janus_resolve_code", {"code": "1", "region": "DE"}),
    ("janus_resolve_ndc", {"ndc": "1" * 33}),
    ("janus_search_medicines", {"query": " a "}),
    ("janus_search_medicines", {"query": "aspirin", "limit": 21}),
    ("janus_check_cascades", {"dataset_version": "x", "items": [{"ingredient": "Q1"}]}),
    ("janus_check_cascades", {"dataset_version": DATASET, "items": []}),
    ("janus_check_cascades", {"dataset_version": DATASET, "items": [{"ingredient": "Q1"}] * 51}),
    ("janus_check_cascades", {"dataset_version": DATASET, "items": [{}]}),
    ("janus_check_cascades", {"dataset_version": DATASET, "items": [{"product": "TR:titck:1",
                                                                     "ingredient": "Q1"}]}),
    ("janus_check_cascades", {"dataset_version": DATASET, "items": [{"ingredient": "Q1",
                                                                     "extra": 1}]}),
    ("janus_check_cascades", {"dataset_version": DATASET, "items": [{"ingredient": "Q1",
                                                                     "started": "2026-13"}]}),
    ("janus_check_cascades", {"dataset_version": DATASET, "items": [
        {"ingredient": "Q1", "choices": [{"position": 0, "ingredient": "Q2"}]}]}),
    ("janus_cascade_package_rows", {"row": 66}),
    ("janus_time_machine_cascade", {"cascade_id": "../health"}),
    ("janus_modelkit_get", {"key": "../health"}),
    ("janus_modelkit_get", {"key": "Bad-Key"}),
    ("janus_modelkit_search", {"query": "x" * 33}),
]  # fmt: skip


@pytest.mark.parametrize(("tool", "args"), BAD_ARGS)
def test_p6_bad_arguments_send_nothing(tool: str, args: dict[str, Any]) -> None:
    stub = StubApi()
    r = call(stub, tool, args)
    assert r.is_error
    assert stub.sent == []


# --- P7: package rows ------------------------------------------------------------------------


@given(st.lists(st.integers(1, 65), max_size=10), st.integers(1, 65))
@settings(max_examples=40, deadline=None)
def test_p7_row_filter(positions: list[int], row: int) -> None:
    rows = [{"position": p, "drug_a": f"a{i}"} for i, p in enumerate(positions)]
    stub = StubApi(body={"package": "janus-cascade-package", "rows": rows})
    out = call(stub, "janus_cascade_package_rows", {"row": row}).structured_content
    assert out is not None
    assert out["result"]["rows"] == [r for r in rows if r["position"] == row]
    assert out["result"]["package"] == "janus-cascade-package"
    whole = call(stub, "janus_cascade_package_rows", {}).structured_content
    assert whole is not None and whole["result"]["rows"] == rows


def test_modelkit_search_filters_and_carries_the_research_lines() -> None:
    drugs = [{"key": "sunitinib"}, {"key": "tramadol"}, {"key": "telmisartan"}]
    stub = StubApi(body={"release": {}, "drugs": drugs})
    out = call(stub, "janus_modelkit_search", {"query": " TRA "}).structured_content
    assert out is not None and out["result"]["drugs"] == [{"key": "tramadol"}]
    assert any("Research use only" in w for w in out["janus_safety"]["wording"])
    whole = call(stub, "janus_modelkit_search", {}).structured_content
    assert whole is not None and whole["result"]["drugs"] == drugs


def test_check_result_carries_the_check_lines() -> None:
    out = call(
        StubApi(body={"findings": []}),
        "janus_check_cascades",
        {"dataset_version": DATASET, "items": [{"ingredient": "Q1"}]},
    ).structured_content
    assert out is not None
    for line in safety.CHECK_LINES:
        assert line in out["janus_safety"]["wording"]


# --- Configuration ---------------------------------------------------------------------------


def test_config() -> None:
    assert from_env({}).api_url == "http://127.0.0.1:8000"
    assert from_env({"JANUS_API_URL": "https://janus.example.org/api/"}).api_url == (
        "https://janus.example.org/api"
    )
    assert from_env({"JANUS_API_TIMEOUT": "2.5"}).timeout == 2.5
    assert from_env({"JANUS_API_URL": "http://localhost:8000"}).api_url == "http://localhost:8000"
    for env in (
        {"JANUS_API_URL": "ftp://x"},
        {"JANUS_API_URL": "http://janus.example.org"},
        {"JANUS_API_URL": "https://x?y=zzsecretzz"},
        {"JANUS_API_TIMEOUT": "0"},
        {"JANUS_API_TIMEOUT": "61"},
        {"JANUS_API_TIMEOUT": "zzsecretzz"},
    ):
        with pytest.raises(ConfigError) as exc:
            from_env(env)
        assert "zzsecretzz" not in str(exc.value)
        assert str(exc.value).startswith(("JANUS_API_URL", "JANUS_API_TIMEOUT"))


def test_http_transport_is_loopback_only(capsys: pytest.CaptureFixture[str]) -> None:
    from janus_mcp.server import main

    assert main(["--transport", "streamable-http", "--host", "0.0.0.0"]) == 2  # noqa: S104
    assert "--host must be" in capsys.readouterr().err
