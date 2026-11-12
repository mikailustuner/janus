"""Access-log middleware (privacy design §4.1, Req 2.1, 2.2).

Outermost of the app's own middleware. For every HTTP request it generates a request id
(the caller's `X-Request-ID` is ignored), returns it in `X-Request-ID`, adds
`Cache-Control: no-store` to every non-operational response, turns unhandled exceptions into a
500 without details, and writes exactly one access line: request id, route template, status,
latency. It never reads the path, query string, headers or body into the log.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from janus.http_policy.routes import RouteKind, route_kind
from janus.observability.errors import send_internal_error
from janus.observability.logging import UNMATCHED_ROUTE, LogEvent, log_event
from janus.observability.metrics import HTTP_IN_FLIGHT, observe_request

REQUEST_ID_HEADER = b"x-request-id"


def _route_template(scope: Scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else UNMATCHED_ROUTE


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid.uuid4())
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        started_ns = time.perf_counter_ns()
        status = 500
        response_started = False
        HTTP_IN_FLIGHT.inc()

        async def send_wrapper(message: Message) -> None:
            nonlocal status, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status = int(message["status"])
                no_store = not _is_operational(scope)
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() != REQUEST_ID_HEADER
                    and not (no_store and k.lower() == b"cache-control")
                ]
                headers.append((REQUEST_ID_HEADER, request_id.encode()))
                if no_store:
                    headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            log_event(
                LogEvent.unhandled_error,
                logging.ERROR,
                request_id=request_id,
                error_class=type(exc),
            )
            if not response_started:
                await send_internal_error(send_wrapper, request_id)
            status = 500
        finally:
            latency_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
            route = _route_template(scope)
            HTTP_IN_FLIGHT.dec()
            observe_request(route, str(scope.get("method", "")), status, latency_ms / 1000)
            log_event(
                LogEvent.access,
                request_id=request_id,
                route=route,
                status=status,
                latency_ms=latency_ms,
            )


def _is_operational(scope: Scope) -> bool:
    route = scope.get("route")
    return route is not None and route_kind(route) is RouteKind.operational
