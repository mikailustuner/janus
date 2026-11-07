"""`POST /cascades/evaluate` (cascade-engine design §6, Req 9). A medical route: JSON body only,
`no-store`, read-only transaction, nothing logged but the access line.

The body is validated here (not by FastAPI) so that a 422 names failing fields only and never
echoes a candidate id, ingredient key or start month.
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

from janus.cascades import service
from janus.cascades.schemas import CascadeResult, EvaluateIn
from janus.db.pool import Database
from janus.http_policy.routes import medical_router

router = medical_router()

# Replaced in tests to freeze the date (the current month bounds start months).
today: Callable[[], dt.date] = lambda: dt.datetime.now(dt.UTC).date()  # noqa: E731


def _error(status: int, error: str, fields: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(body, status_code=status)


@router.post("/cascades/evaluate", response_model=CascadeResult)
async def cascades_evaluate(request: Request) -> Any:
    try:
        payload = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return _error(422, "invalid_request", ["body"])
    try:
        body = EvaluateIn.model_validate(payload)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in e["loc"]) or "body" for e in exc.errors()})
        return _error(422, "invalid_request", fields)
    db = getattr(request.app.state, "database", None)
    if not isinstance(db, Database):
        return _error(503, "cascades_unavailable")
    day = today()

    def call() -> CascadeResult:
        with db.read_only_tx() as conn:
            return service.evaluate_request(conn, body, day)

    try:
        result = await run_in_threadpool(call)
    except service.CascadesUnavailableError:
        return _error(503, "cascades_unavailable")
    except service.DatasetVersionMismatchError:
        return _error(409, "dataset_version_mismatch")
    except service.InvalidItemsError as exc:
        return _error(422, "invalid_request", exc.fields)
    return JSONResponse(result.model_dump(mode="json"))
