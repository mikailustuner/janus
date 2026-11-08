"""`/seance` routes (séance design §6). Medical routes: JSON bodies only, `no-store`, read-only,
nothing logged but the access line. The pair travels in a POST body, never in the URL.

A missing counts file or evidence store does not fail the request: that witness is reported as
missing with its reason (Req 2.3). A missing séance catalogue answers 503.
"""

from __future__ import annotations

import json
from typing import Any

import psycopg
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool

from janus.db.pool import Database
from janus.http_policy.routes import medical_router
from janus.integrity import repository
from janus.integrity.model import IntegritySnapshot
from janus.memory.reader import CountsError, CountsHolder
from janus.seance import service
from janus.seance.catalogue import Catalogue
from janus.seance.schemas import CatalogueOut, SeanceIn, SeanceOut

router = medical_router()


def _error(status: int, error: str, fields: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(body, status_code=status)


def _field_names(exc: ValidationError) -> list[str]:
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


def _integrity(db: object) -> IntegritySnapshot | None:
    if not isinstance(db, Database):
        return None
    try:
        with db.read_only_tx() as conn:
            return repository.load_snapshot(conn)
    except (psycopg.Error, repository.TooManyRecordsError):
        return None


@router.post("/seance/pair", response_model=SeanceOut)
async def seance_pair(request: Request) -> Any:
    body = await _parse(request, SeanceIn)
    if isinstance(body, JSONResponse):
        return body
    cat: Catalogue | None = getattr(request.app.state, "seance", None)
    if cat is None:
        return _error(503, "seance_unavailable")
    if body.substance not in cat.substances:
        return _error(422, "invalid_request", ["substance"])
    holder: CountsHolder = request.app.state.counts
    db = getattr(request.app.state, "database", None)

    def call() -> SeanceOut:
        integrity = _integrity(db)
        try:
            reader = holder.current()
        except CountsError:
            reader = None
        if reader is None:
            return service.build(
                cat,
                body.substance,
                body.condition,
                cells=None,
                snapshot_date=None,
                integrity=integrity,
            )
        try:
            with reader.session() as session:
                cells, snapshot = service.present_cells(
                    cat, session, body.substance, body.condition
                )
        except CountsError:
            cells, snapshot = None, None
        return service.build(
            cat,
            body.substance,
            body.condition,
            cells=cells,
            snapshot_date=snapshot,
            integrity=integrity,
        )

    result = await run_in_threadpool(call)
    return JSONResponse(result.model_dump(mode="json"))


@router.get("/seance/catalogue", response_model=CatalogueOut)
async def seance_catalogue(request: Request) -> Any:
    cat: Catalogue | None = getattr(request.app.state, "seance", None)
    if cat is None:
        return _error(503, "seance_unavailable")
    return JSONResponse(service.catalogue(cat).model_dump(mode="json"))
