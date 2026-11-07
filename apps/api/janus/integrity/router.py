"""Evidence routes (evidence-integrity design §6.1, Req 7). Medical routes: JSON bodies only,
`no-store`, read-only transactions, nothing logged but the access line.

Evidence ids can reveal which finding a person has, so both routes are POST with the ids in the
body. Bodies are validated here (not by FastAPI) so that a 422 names failing fields only and
never echoes input.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool

from janus.db.pool import Database
from janus.http_policy.routes import medical_router
from janus.integrity import service
from janus.integrity.schemas import ChangesIn, ChangesResult, EvidenceResolution, ResolveIn

router = medical_router()

# Replaced in tests to freeze the date (ages, staleness).
today: Callable[[], dt.date] = lambda: dt.datetime.now(dt.UTC).date()  # noqa: E731


def _error(status: int, error: str, fields: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(body, status_code=status)


async def _parse[M: BaseModel](request: Request, model: type[M]) -> M | JSONResponse:
    try:
        payload = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return _error(422, "invalid_request", ["body"])
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in e["loc"]) or "body" for e in exc.errors()})
        return _error(422, "invalid_request", fields)


async def _run(request: Request, fn: Callable[..., BaseModel], *args: Any) -> Any:
    db = getattr(request.app.state, "database", None)
    if not isinstance(db, Database):
        return _error(503, "integrity_unavailable")

    def call() -> BaseModel:
        with db.read_only_tx() as conn:
            return fn(conn, *args)

    try:
        result = await run_in_threadpool(call)
    except service.IntegrityUnavailableError:
        return _error(503, "integrity_unavailable")
    return JSONResponse(result.model_dump(mode="json"))


@router.post("/evidence/resolve", response_model=EvidenceResolution)
async def evidence_resolve(request: Request) -> Any:
    body = await _parse(request, ResolveIn)
    if isinstance(body, JSONResponse):
        return body
    return await _run(request, service.resolve_evidence, body.evidence_ids, today())


@router.post("/evidence/changes", response_model=ChangesResult)
async def evidence_changes(request: Request) -> Any:
    body = await _parse(request, ChangesIn)
    if isinstance(body, JSONResponse):
        return body
    since = None if body.since is None else dt.date.fromisoformat(body.since)
    return await _run(request, service.list_changes, since, body.limit, today())
