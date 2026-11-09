"""CORS for the CDS Hooks routes only (cds-hooks design §7, DP10).

Browser-based CDS clients (the public CDS Hooks sandbox) need CORS; the rest of the API is
same-origin. The listed origins get CORS on paths under `/cds-services`, nothing else.
"""

from __future__ import annotations

from collections.abc import Iterable

from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

PREFIX = "/cds-services"


class CdsCorsMiddleware:
    def __init__(self, app: ASGIApp, origins: Iterable[str]) -> None:
        self.app = app
        self.cors = CORSMiddleware(
            app,
            allow_origins=sorted(origins),
            allow_methods=["GET", "POST"],
            allow_headers=["authorization", "content-type"],
            allow_credentials=False,
            max_age=600,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] == "http" and (path == PREFIX or path.startswith(PREFIX + "/")):
            await self.cors(scope, receive, send)
        else:
            await self.app(scope, receive, send)
