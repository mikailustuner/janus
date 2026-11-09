"""A stub Janus API (httpx2 MockTransport) and helpers to call the server in-process."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import anyio
import httpx2
from mcp import Client
from mcp_types import CallToolResult

from janus_mcp.config import from_env
from janus_mcp.server import build_server


@dataclass
class Sent:
    method: str
    path: str
    body: Any


@dataclass
class StubApi:
    """Answers every request with `status` and `body`; records what was sent."""

    status: int = 200
    body: Any = field(default_factory=lambda: {"ok": True})
    sent: list[Sent] = field(default_factory=list[Sent])
    raise_error: bool = False

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        if self.raise_error:
            raise httpx2.ConnectError("refused")
        raw = request.content
        self.sent.append(Sent(request.method, request.url.path, json.loads(raw) if raw else None))
        return httpx2.Response(self.status, json=self.body)


def call(stub: StubApi, tool: str, args: dict[str, Any]) -> CallToolResult:
    server = build_server(from_env({}), httpx2.MockTransport(stub.handler))

    async def go() -> CallToolResult:
        async with Client(server) as c:
            return await c.call_tool(tool, args)

    return anyio.run(go)


def with_client[T](fn: Callable[[Client], Any]) -> Any:
    server = build_server(from_env({}), httpx2.MockTransport(StubApi().handler))

    async def go() -> Any:
        async with Client(server) as c:
            return await fn(c)

    return anyio.run(go)


def text_of(r: CallToolResult) -> str:
    return "\n".join(getattr(c, "text", "") for c in r.content)
