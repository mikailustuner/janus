"""`/memory` routes (collective-memory design §5).

Lookups are `POST` with a JSON body (medicines and events never appear in a URL), medical routes:
JSON only, at most 64 KiB, `no-store`, read-only, nothing logged but the access line. Bodies are
validated here so that a 422 names failing fields only and never echoes a value.
`GET /memory/snapshot` is operational: snapshot facts only, no medicine or event data.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from typing import Any

import psycopg
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool

from janus.db.pool import Database
from janus.http_policy.routes import medical_router, operational_router
from janus.memory import service, shared
from janus.memory.disclosure import keyed_noise_source
from janus.memory.reader import CountsError, CountsHolder, Session
from janus.memory.schemas import (
    CombinationIn,
    CombinationOut,
    PairIn,
    PairOut,
    RegionsIn,
    RegionsOut,
    SharedIn,
    SharedOut,
    SnapshotOut,
)
from janus.settings import Settings

router = medical_router()
snapshot_router = operational_router()

# Replaced in tests to freeze the date.
today: Callable[[], dt.date] = lambda: dt.datetime.now(dt.UTC).date()  # noqa: E731


def _error(status: int, error: str, fields: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(body, status_code=status)


def _field_names(exc: ValidationError) -> list[str]:
    """Failing fields as dotted paths; an unknown field's own name is never echoed."""
    out: set[str] = set()
    for e in exc.errors():
        loc = [str(p) for p in e["loc"]]
        if e["type"] == "extra_forbidden":
            loc = [*loc[:-1], "(unknown field)"]
        out.add(".".join(loc) or "body")
    return sorted(out)


async def _parse[M: BaseModel](request: Request, model: type[M]) -> M | JSONResponse:
    try:
        payload = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return _error(422, "invalid_request", ["body"])
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        return _error(422, "invalid_request", _field_names(exc))


def _served_version(db: Database | None) -> str | None:
    """The resolution dataset now served, or None when no database/dataset is available."""
    if db is None:
        return None
    try:
        with db.read_only_tx() as conn:
            row = conn.execute("SELECT dataset_id FROM res_current").fetchone()
    except psycopg.Error:
        return None
    return None if row is None else str(row[0])


def _context(request: Request) -> service.Context:
    db = getattr(request.app.state, "database", None)
    return service.Context(
        vocab=request.app.state.event_vocabulary,
        today=today(),
        served_version=_served_version(db if isinstance(db, Database) else None),
    )


async def _faers[M: BaseModel](
    request: Request,
    model: type[M],
    fn: Callable[[Session, M, service.Context], BaseModel],
) -> JSONResponse:
    body = await _parse(request, model)
    if isinstance(body, JSONResponse):
        return body
    holder: CountsHolder = request.app.state.counts

    def call() -> BaseModel:
        reader = holder.current()
        ctx = _context(request)
        with reader.session() as session:
            return fn(session, body, ctx)

    try:
        result = await run_in_threadpool(call)
    except CountsError:
        return _error(503, "memory_unavailable")
    except service.UnknownEventError:
        return _error(422, "invalid_request", ["event.key"])
    return JSONResponse(result.model_dump(mode="json"))


@router.post("/memory/pair", response_model=PairOut)
async def memory_pair(request: Request) -> Any:
    return await _faers(request, PairIn, service.pair)


@router.post("/memory/combination", response_model=CombinationOut)
async def memory_combination(request: Request) -> Any:
    return await _faers(request, CombinationIn, service.combination)


@router.post("/memory/regions", response_model=RegionsOut)
async def memory_regions(request: Request) -> Any:
    return await _faers(request, RegionsIn, service.regions)


@snapshot_router.get("/memory/snapshot", response_model=SnapshotOut)
async def memory_snapshot(request: Request) -> Any:
    holder: CountsHolder = request.app.state.counts
    settings: Settings = request.app.state.settings
    db = getattr(request.app.state, "database", None)

    def call() -> BaseModel:
        reader = holder.current()
        layers = {
            "faers": "ok",
            "contributions": (
                "ok"
                if isinstance(db, Database) and settings.noise_key is not None
                else "unavailable"
            ),
            "outcomes": "not_available",
        }
        ctx = service.Context(request.app.state.event_vocabulary, today(), None)
        with reader.session() as session:
            return service.snapshot(session, ctx, layers)

    try:
        result = await run_in_threadpool(call)
    except CountsError:
        return _error(503, "memory_unavailable")
    return JSONResponse(result.model_dump(mode="json"))


@router.post("/memory/shared", response_model=SharedOut)
async def memory_shared(request: Request) -> Any:
    """Contributions and outcomes (counts only): k = 20, discrete Laplace noise, sibling rule."""
    body = await _parse(request, SharedIn)
    if isinstance(body, JSONResponse):
        return body
    settings: Settings = request.app.state.settings
    db = getattr(request.app.state, "database", None)
    vocab = request.app.state.event_vocabulary
    if vocab.usable(body.event) is None:
        return _error(422, "invalid_request", ["event"])
    sources = request.app.state.user_layer_sources
    noise = keyed_noise_source(settings.noise_key) if settings.noise_key is not None else None

    def call() -> BaseModel:
        if not isinstance(db, Database):
            return shared.shared(
                body,
                sources=sources,
                conn=None,
                noise_source=noise,
                k=settings.k,
                epsilon=settings.epsilon,
            )
        with db.read_only_tx() as conn:
            return shared.shared(
                body,
                sources=sources,
                conn=conn,
                noise_source=noise,
                k=settings.k,
                epsilon=settings.epsilon,
            )

    result = await run_in_threadpool(call)
    return JSONResponse(result.model_dump(mode="json"))
