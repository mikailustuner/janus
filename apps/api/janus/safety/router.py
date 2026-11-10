"""`POST /safety/check` (safety-check design §7, Req 1). A medical route: JSON body only,
`no-store`, read-only transaction, nothing logged but the access line.

The body is validated here (not by FastAPI) so that a 422 names failing fields only and never
echoes a candidate id, an ingredient key or a start month.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from janus.cascades import service as cascades
from janus.cascades.schemas import EvaluateIn
from janus.db.pool import Database
from janus.http_policy.routes import medical_router
from janus.safety import service
from janus.safety.schemas import SafetyCheckOut

router = medical_router()

# Replaced in tests to freeze the date (the current month bounds start months).
today: Callable[[], dt.date] = lambda: dt.datetime.now(dt.UTC).date()  # noqa: E731


def _error(status: int, error: str, fields: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(body, status_code=status)


def _field(loc: tuple[Any, ...]) -> str:
    """A path of the route's own field names and positions; an unknown key is the client's
    text and is not echoed."""
    known = {"dataset_version", "items", "product", "ingredient", "choices", "started", "position"}
    parts: list[str] = []
    for p in loc:
        if isinstance(p, int) or p in known:
            parts.append(str(p))
        else:
            break
    return ".".join(parts) or "body"


@router.post("/safety/check", response_model=SafetyCheckOut)
async def safety_check(request: Request) -> Any:
    """Automated comparisons of one medicine list: the same ingredient or ATC chemical subgroup
    in two list items. States what the sources say; an empty result is not a clearance."""
    try:
        payload = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return _error(422, "invalid_request", ["body"])
    try:
        body = EvaluateIn.model_validate(payload)
    except ValidationError as exc:
        return _error(422, "invalid_request", sorted({_field(e["loc"]) for e in exc.errors()}))
    db = getattr(request.app.state, "database", None)
    if not isinstance(db, Database):
        return _error(503, "safety_unavailable")
    day = today()

    def call() -> SafetyCheckOut:
        with db.read_only_tx() as conn:
            return service.check(conn, body, day)

    try:
        result = await run_in_threadpool(call)
    except service.SafetyUnavailableError:
        return _error(503, "safety_unavailable")
    except cascades.DatasetVersionMismatchError:
        return _error(409, "dataset_version_mismatch")
    except cascades.InvalidItemsError as exc:
        return _error(422, "invalid_request", exc.fields)
    return JSONResponse(result.model_dump(mode="json"))
