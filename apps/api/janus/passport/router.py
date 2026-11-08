"""`POST /passport/presence` (medication-passport design §3, Req 4, 5). Medical route: JSON body
only, `no-store`, one read-only transaction, nothing logged but the access line.

The body is parsed and validated here (not by FastAPI), as in `resolution/router.py`, so that a 422
names failing field paths with a fixed code and never echoes a value (Req 5.2).
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from typing import Any

import psycopg
from fastapi import Request
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from janus.db.pool import Database
from janus.http_policy.routes import medical_router
from janus.passport import service
from janus.passport.forms import FormTable
from janus.passport.schemas import PresenceIn, PresenceOut

router = medical_router()

# Replaced in tests to freeze the date (staleness).
today: Callable[[], dt.date] = lambda: dt.datetime.now(dt.UTC).date()  # noqa: E731


def _error(status: int, error: str, fields: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(body, status_code=status)


def _unavailable() -> JSONResponse:
    return _error(503, "passport_unavailable")


@router.post("/passport/presence", response_model=PresenceOut)
async def presence(request: Request) -> Any:
    try:
        payload = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return _error(422, "invalid_request", ["body"])
    try:
        body = PresenceIn.model_validate(payload)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in e["loc"]) or "body" for e in exc.errors()})
        return _error(422, "invalid_request", fields)
    db = getattr(request.app.state, "database", None)
    forms = getattr(request.app.state, "dose_forms", None)
    if not isinstance(db, Database) or not isinstance(forms, FormTable) or not forms.reviewed:
        return _unavailable()
    day = today()

    def call() -> PresenceOut:
        with db.read_only_tx() as conn:
            return service.presence(conn, body, forms, day)

    try:
        result = await run_in_threadpool(call)
    except (service.PassportUnavailableError, psycopg.OperationalError, PoolTimeout):
        # No current dataset, the database is unreachable, or the statement timed out
        # (`QueryCanceled` is an `OperationalError`): nothing partial (Req 5.3).
        return _unavailable()
    return JSONResponse(result.model_dump(mode="json"))
