"""Donation endpoints (privacy design §5.1; Req 3.1-3.4).

- POST /contributions: explicit consent required, `"demo": true` rejected, only allowed fields;
  the server sets the report week; returns the deletion token once.
- POST /contributions/deletions: the token comes in the body, never in the URL.

Error responses name the failing fields only; they never echo values.
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

from janus.contributions import repository
from janus.contributions.models import (
    ContributionCreated,
    ContributionIn,
    ContributionStored,
    DeletionDone,
    DeletionIn,
)
from janus.contributions.service import donations_enabled
from janus.contributions.tokens import new_token, token_hash
from janus.contributions.week import report_week
from janus.db.pool import Database
from janus.http_policy.routes import donation_router
from janus.settings import Settings

router = donation_router()

# Replaced in tests to freeze the server clock (P8 router part).
clock: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC)  # noqa: E731


def _error(status: int, error: str, fields: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(body, status_code=status)


def _field_paths(exc: ValidationError) -> list[str]:
    return sorted({".".join(str(p) for p in err["loc"]) or "body" for err in exc.errors()})


async def _json_body(request: Request) -> object:
    try:
        return json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return None


@router.post("/contributions", status_code=201, response_model=ContributionCreated)
async def create_contribution(request: Request) -> Any:
    if not donations_enabled(request.app):
        return _error(503, "donations_unavailable")
    payload = await _json_body(request)
    if not isinstance(payload, dict):
        return _error(422, "invalid_donation", ["body"])
    if payload.get("demo") is True:  # pyright: ignore[reportUnknownMemberType]
        return _error(422, "demo_donation_rejected")
    settings: Settings = request.app.state.settings
    context = {"consent_versions": settings.consent_versions, "events": request.app.state.events}
    try:
        donation = ContributionIn.model_validate(payload, context=context)
    except ValidationError as exc:
        return _error(422, "invalid_donation", _field_paths(exc))
    stored = ContributionStored.from_request(donation, report_week(clock()))
    token = new_token()
    db: Database = request.app.state.database
    await run_in_threadpool(repository.insert, db, stored, token_hash(token))
    return JSONResponse(
        ContributionCreated(deletion_token=token, stored=stored).model_dump(mode="json"),
        status_code=201,
    )


@router.post("/contributions/deletions", response_model=DeletionDone)
async def delete_contribution(request: Request) -> Any:
    if not donations_enabled(request.app):
        return _error(503, "donations_unavailable")
    payload = await _json_body(request)
    try:
        deletion = DeletionIn.model_validate(payload)
    except ValidationError as exc:
        return _error(422, "invalid_deletion", _field_paths(exc))
    db: Database = request.app.state.database
    deleted = await run_in_threadpool(
        repository.delete_by_token_hash, db, token_hash(deletion.deletion_token)
    )
    if not deleted:
        return _error(404, "no_donation_for_token")
    return DeletionDone(deleted=True)
