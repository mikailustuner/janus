"""Body policy for medical routes (privacy design §4.3, Req 1.4, 2.1).

Requests with a body must be `application/json` and at most 64 KiB (256 KiB for the CDS Hooks
service, whose FHIR bundles are verbose: cds-hooks design DP5). The body is buffered in memory up
to the limit and replayed to the app; multipart is never parsed, so nothing is spooled to disk.
Operational paths are exempt.
"""

from __future__ import annotations

import json
from typing import Final

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from janus.http_policy.routes import OPERATIONAL_ALLOWLIST

MAX_BODY_BYTES: Final = 64 * 1024
# Other limits for named paths only.
PATH_LIMITS: Final = {
    "/cds-services/janus-cascade": 256 * 1024,
    # The simulation request is a few bounded numbers (simulation-service DP-S2).
    "/simulate": 1024,
}
_BODY_METHODS: Final = frozenset({"POST", "PUT", "PATCH"})


def _header(scope: Scope, name: bytes) -> bytes | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return value
    return None


def is_json_content_type(value: bytes | None) -> bool:
    if value is None:
        return False
    main = value.split(b";", 1)[0].strip().lower()
    return main == b"application/json"


async def _reject(send: Send, status: int, error: str) -> None:
    body = json.dumps({"error": error}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BodyPolicyMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in OPERATIONAL_ALLOWLIST:
            await self.app(scope, receive, send)
            return
        length_raw = _header(scope, b"content-length")
        chunked = _header(scope, b"transfer-encoding") is not None
        try:
            declared = int(length_raw) if length_raw is not None else None
        except ValueError:
            await _reject(send, 400, "bad_content_length")
            return
        has_body = scope.get("method") in _BODY_METHODS or chunked or (declared or 0) > 0
        if not has_body:
            await self.app(scope, receive, send)
            return
        if not is_json_content_type(_header(scope, b"content-type")):
            await _reject(send, 415, "unsupported_media_type")
            return
        path = str(scope.get("path", ""))
        # A trailing slash is the same route for the limit (safety review F12).
        limit = PATH_LIMITS.get(path.rstrip("/") or path, self.max_bytes)
        if declared is not None and declared > limit:
            await _reject(send, 413, "payload_too_large")
            return
        chunks: list[bytes] = []
        size = 0
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:
                await _reject(send, 413, "payload_too_large")
                return
            chunks.append(chunk)
            more = bool(message.get("more_body", False))
        body = b"".join(chunks)
        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
