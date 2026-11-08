"""Resolution routes (drug-resolution design §3.1, Req 8). Medical routes: JSON bodies only,
`no-store`, read-only transactions, nothing logged but the access line.

Codes and names come only in the POST body, never in the URL (DP13). Bodies are validated here
(not by FastAPI) so that a 422 names failing fields with fixed codes and never echoes input,
such as a serial number (DP14, Req 8.4).
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
from janus.resolution import service
from janus.resolution.gs1 import Gs1Error
from janus.resolution.model import NdcIn, ProductsIn, ResolutionResult, ScanIn, SearchIn
from janus.resolution.ndc import NdcError

router = medical_router()

# Replaced in tests to freeze the date (expiry century, staleness).
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


async def _run(request: Request, fn: Callable[..., ResolutionResult], *args: Any) -> Any:
    db = getattr(request.app.state, "database", None)
    if not isinstance(db, Database):
        return _error(503, "resolution_unavailable")

    # The accepted dose-form table, for the additive Passport fields (medication-passport Req 6.6).
    forms = getattr(request.app.state, "dose_forms", None)

    def call() -> ResolutionResult:
        with db.read_only_tx() as conn:
            return fn(conn, *args, forms=forms)

    try:
        result = await run_in_threadpool(call)
    except service.ResolutionUnavailableError:
        return _error(503, "resolution_unavailable")
    except Gs1Error as exc:
        return _error(422, exc.code.value)
    except NdcError:
        return _error(422, NdcError.code)
    except ValueError:
        return _error(422, "invalid_request", ["query"])
    return JSONResponse(result.model_dump(mode="json"))


@router.post("/resolve/scan", response_model=ResolutionResult)
async def resolve_scan(request: Request) -> Any:
    body = await _parse(request, ScanIn)
    if isinstance(body, JSONResponse):
        return body
    return await _run(request, service.resolve_scan, body.content, body.region, today())


@router.post("/resolve/ndc", response_model=ResolutionResult)
async def resolve_ndc(request: Request) -> Any:
    body = await _parse(request, NdcIn)
    if isinstance(body, JSONResponse):
        return body
    return await _run(request, service.resolve_ndc, body.ndc, today())


@router.post("/resolve/search", response_model=ResolutionResult)
async def resolve_search(request: Request) -> Any:
    body = await _parse(request, SearchIn)
    if isinstance(body, JSONResponse):
        return body
    return await _run(request, service.search, body.query, body.region, body.limit, today())


@router.post("/resolve/products", response_model=ResolutionResult)
async def resolve_products(request: Request) -> Any:
    body = await _parse(request, ProductsIn)
    if isinstance(body, JSONResponse):
        return body
    return await _run(request, service.resolve_products, body.candidate_ids, today())
