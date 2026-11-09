"""The tools against a real Janus API (mcp-server Req 6.2). Skipped unless
`JANUS_MCP_INTEGRATION_URL` names a running API with a loaded dataset, for example
`uv run uvicorn janus.main:app --port 8010` in apps/api."""

from __future__ import annotations

import os
from typing import Any

import anyio
import pytest
from mcp import Client

from janus_mcp.config import from_env
from janus_mcp.server import build_server

URL = os.environ.get("JANUS_MCP_INTEGRATION_URL")
pytestmark = pytest.mark.skipif(not URL, reason="JANUS_MCP_INTEGRATION_URL not set")


def run(steps: Any) -> Any:
    server = build_server(from_env({"JANUS_API_URL": URL or ""}))

    async def go() -> Any:
        async with Client(server) as c:
            return await steps(c)

    return anyio.run(go)


def structured(r: Any) -> dict[str, Any]:
    assert not r.is_error, r.content
    assert r.structured_content is not None
    return r.structured_content


def test_package_rows() -> None:
    async def steps(c: Client) -> Any:
        return structured(await c.call_tool("janus_cascade_package_rows", {"row": 5}))

    out = run(steps)
    (row,) = out["result"]["rows"]
    assert (row["position"], row["index_class"], row["marker_class"]) == (5, "ccb", "diuretic")


def test_search_then_check_finds_row_5() -> None:
    async def steps(c: Client) -> Any:
        items: list[dict[str, str]] = []
        version = ""
        for name in ("amlodipine", "furosemide"):
            found = structured(
                await c.call_tool("janus_search_medicines", {"query": name, "limit": 20})
            )["result"]
            version = found["dataset_version"]
            ingredients = [
                {"ingredient": x["ingredient_key"]["qid"]}
                for x in found["candidates"]
                if x["kind"] == "ingredient"
                and (x["ingredient_key"]["label_en"] or "").lower() == name
            ]
            products = [
                {"product": x["candidate_id"]}
                for x in found["candidates"]
                if x["kind"] == "product" and len(x["ingredients"]) == 1
            ]
            items.append((ingredients or products)[0])
        return structured(
            await c.call_tool("janus_check_cascades", {"dataset_version": version, "items": items})
        )

    out = run(steps)
    assert "pipc:5" in {f["rule_id"] for f in out["result"]["findings"]}
    assert out["result"]["disclaimer"] == out["janus_safety"]["disclaimer"]


def test_time_machine_catalogue_or_its_error_code() -> None:
    async def steps(c: Client) -> Any:
        return await c.call_tool("janus_time_machine_catalogue", {})

    r = run(steps)
    if r.is_error:
        assert "janus_api_error: time_machine_not_installed" in str(r.content)
    else:
        assert "cascade_ids" in r.structured_content["result"]
