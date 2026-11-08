"""`/light/*` routes (design §9, Req 4, 5.2, 6.4, 6.5). Researcher area only.

Medical routes: nothing is logged but the access line, `no-store`, read-only transactions. No user
data travels in a request; the goal key is in a POST body so the access log never names a
condition. A 422 names failing fields only and never echoes a value. Without a build or without an
integrity snapshot the answer is `503 light_unavailable` (fail closed, DP8); a missing patient layer
only marks `patient_layer: layer_unavailable`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

import psycopg
import psycopg_pool
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool

from janus.db.pool import Database
from janus.http_policy.routes import medical_router
from janus.integrity import repository as integrity_repository
from janus.integrity.model import IntegritySnapshot
from janus.light import benefit, service
from janus.light.schemas import (
    CardsIn,
    CardsOut,
    ExportOut,
    LightFile,
    OverviewOut,
    PatientSignalOut,
    ValidationOut,
)
from janus.light.store import LightHolder, LightUnavailableError
from janus.memory.disclosure import keyed_noise_source
from janus.settings import Settings

router = medical_router()


def _error(status: int, error: str, fields: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(body, status_code=status)


def _fields(exc: ValidationError) -> list[str]:
    out: set[str] = set()
    for e in exc.errors():
        loc = [str(p) for p in e["loc"]]
        if e["type"] == "extra_forbidden":
            loc = [*loc[:-1], "(unknown field)"]
        out.add(".".join(loc) or "(body)")
    return sorted(out)


type Patient = dict[tuple[str, str], PatientSignalOut] | None


def _with_db[T](
    request: Request,
    events: Callable[[LightFile], Sequence[str]],
    fn: Callable[[LightFile, IntegritySnapshot, Patient], T],
) -> T:
    """Load the build, the integrity snapshot and the patient layer in one read-only transaction."""
    holder: LightHolder = request.app.state.light
    light = holder.current()
    db = getattr(request.app.state, "database", None)
    if not isinstance(db, Database):
        raise LightUnavailableError("no database for the integrity snapshot")
    settings: Settings = request.app.state.settings
    with db.read_only_tx() as conn:
        snapshot = integrity_repository.load_snapshot(conn)
        patient = _patient(request, conn, settings, events(light))
        return fn(light, snapshot, patient)


def _patient(
    request: Request, conn: psycopg.Connection, settings: Settings, events: Sequence[str]
) -> Patient:
    if settings.noise_key is None:
        return None
    sources = request.app.state.user_layer_sources
    if "contributions" not in sources:
        return None
    return benefit.released(
        conn,
        events,
        sources=sources,
        noise_source=keyed_noise_source(settings.noise_key),
        k=settings.k,
        epsilon=settings.epsilon,
    )


async def _answer(call: Callable[[], BaseModel]) -> JSONResponse:
    try:
        result = await run_in_threadpool(call)
    except (LightUnavailableError, psycopg.OperationalError, psycopg_pool.PoolTimeout):
        return _error(503, "light_unavailable")
    except service.UnknownGoalError:
        return _error(422, "invalid_request", ["goal"])
    return JSONResponse(result.model_dump(mode="json"))


@router.get("/light/overview", response_model=OverviewOut)
async def light_overview(request: Request) -> Any:
    def call() -> BaseModel:
        holder: LightHolder = request.app.state.light
        return service.overview(holder.current())

    return await _answer(call)


@router.post("/light/cards", response_model=CardsOut)
async def light_cards(request: Request) -> Any:
    try:
        body = CardsIn.model_validate(json.loads(await request.body() or b"null"))
    except json.JSONDecodeError:
        return _error(422, "invalid_request", ["(body)"])
    except ValidationError as exc:
        return _error(422, "invalid_request", _fields(exc))

    def events(light: LightFile) -> Sequence[str]:
        goal = next((g for g in light.goals if g.key == body.goal), None)
        return goal.benefit_keys if goal else []

    def call() -> BaseModel:
        return _with_db(
            request, events, lambda light, snap, pat: service.cards(light, body, snap, pat)
        )

    return await _answer(call)


@router.get("/light/validation", response_model=ValidationOut)
async def light_validation(request: Request) -> Any:
    def call() -> BaseModel:
        return _with_db(
            request, lambda _light: [], lambda light, snap, _pat: service.validation(light, snap)
        )

    return await _answer(call)


@router.get("/light/export", response_model=ExportOut)
async def light_export(request: Request) -> Any:
    def events(light: LightFile) -> Sequence[str]:
        return sorted({k for g in light.goals for k in g.benefit_keys})

    def call() -> BaseModel:
        return _with_db(request, events, service.export)

    return await _answer(call)
