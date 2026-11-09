"""One request to the Janus API (mcp-server design §4, §5).

A timeout on every call, no retry, no cache, no log. Errors carry the API's fixed code and field
names only; an input value is never formatted into an error.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final, cast

import httpx2

from janus_mcp.config import Config

_CODE = re.compile(r"^[a-z0-9_]{1,64}$")
_FIELD = re.compile(r"^[A-Za-z0-9_.<>-]{1,128}$")
MAX_FIELDS: Final = 20


class ApiError(Exception):
    """A failed call; `str()` is a fixed text built from API codes only."""


def _error_text(status: int, body: Any) -> str:
    if isinstance(body, dict):
        obj = cast(dict[str, Any], body)
        code = obj.get("error")
        if isinstance(code, str) and _CODE.fullmatch(code):
            raw = obj.get("fields")
            listed = cast(list[Any], raw) if isinstance(raw, list) else []
            fields = [f for f in listed if isinstance(f, str) and _FIELD.fullmatch(f)][:MAX_FIELDS]
            text = f"janus_api_error: {code}"
            return text + (f" fields: {', '.join(fields)}" if fields else "")
    return f"janus_api_error: http_{status}"


async def call(
    config: Config,
    method: str,
    path: str,
    body: Mapping[str, Any] | None = None,
    transport: httpx2.AsyncBaseTransport | None = None,
) -> Any:
    """Send one request; return the decoded JSON body. Raises `ApiError`."""
    try:
        async with httpx2.AsyncClient(
            base_url=config.api_url, timeout=config.timeout, transport=transport
        ) as http:
            response = await http.request(
                method, path, json=dict(body) if body is not None else None
            )
    except httpx2.HTTPError:
        raise ApiError("janus_api_unreachable") from None
    try:
        payload = response.json()
    except ValueError:
        raise ApiError("janus_api_bad_response") from None
    if response.status_code != 200:
        raise ApiError(_error_text(response.status_code, payload))
    return payload
