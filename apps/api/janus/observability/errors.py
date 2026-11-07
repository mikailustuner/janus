"""Unhandled-error response (privacy design §4.4): no exception details leave the process."""

from __future__ import annotations

import json

from starlette.types import Send


def internal_error_body(request_id: str) -> bytes:
    return json.dumps({"error": "internal_error", "request_id": request_id}).encode()


async def send_internal_error(send: Send, request_id: str) -> None:
    body = internal_error_body(request_id)
    await send(
        {
            "type": "http.response.start",
            "status": 500,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
