"""Note and outcome routes (doctor-loop design §9).

`POST /notes/document` is a medical route: JSON only, at most 64 KiB, `no-store`, read-only, nothing
logged but the access line. Bodies are validated here so that a 422 names failing fields only and
never echoes a value. No route declares a path or query parameter (tokens arrive in bodies only).
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable, Sequence
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool

from janus.cascades import service as cascades
from janus.cascades.schemas import FindingOut
from janus.db.pool import Database
from janus.http_policy.routes import donation_router, medical_router
from janus.memory.reader import CountsError, CountsHolder
from janus.notes import loop, qr, service
from janus.notes.build import GlossaryMismatchError
from janus.notes.model import NoteOut
from janus.notes.outcomes import AnswerError
from janus.notes.schemas import (
    NoteIn,
    OutcomeFormOut,
    OutcomeIn,
    OutcomeStoredOut,
    TokenBodyIn,
    TokenIn,
    TokenOut,
    WithdrawnOut,
)
from janus.notes.token import Keyring, TokenError, TokenErrorCode, verify, verify_signature_only
from janus.privacy.regions import region_allows_donations
from janus.settings import Settings

router = medical_router()

# Replaced in tests to freeze the date.
today: Callable[[], dt.date] = lambda: dt.datetime.now(dt.UTC).date()  # noqa: E731


def error(status: int, code: str, fields: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": code}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(body, status_code=status)


def field_names(exc: ValidationError) -> list[str]:
    """Failing fields as dotted paths; an unknown field's own name is never echoed."""
    out: set[str] = set()
    for e in exc.errors():
        loc = [str(p) for p in e["loc"]]
        if e["type"] == "extra_forbidden":
            loc = [*loc[:-1], "(unknown field)"]
        out.add(".".join(loc) or "body")
    return sorted(out)


async def parse[M: BaseModel](request: Request, model: type[M]) -> M | JSONResponse:
    try:
        payload = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return error(422, "invalid_request", ["body"])
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        return error(422, "invalid_request", field_names(exc))


def compose_in_tx(
    request: Request,
    db: Database,
    body: NoteIn,
    qr: Callable[[Sequence[FindingOut]], tuple[int, int]] | None = None,
) -> service.Composed:
    """One read-only transaction plus a counts-file session when the file exists."""
    holder: CountsHolder = request.app.state.counts
    day = today()
    with db.read_only_tx() as conn:
        try:
            reader = holder.current()
        except CountsError:
            reader = None
        if reader is None:
            return service.compose(
                conn,
                body,
                today=day,
                vocab=request.app.state.event_vocabulary,
                glossary=request.app.state.glossary,
                session=None,
                qr=qr,
            )
        with reader.session() as session:
            return service.compose(
                conn,
                body,
                today=day,
                vocab=request.app.state.event_vocabulary,
                glossary=request.app.state.glossary,
                session=session,
                qr=qr,
            )


def compose_errors(exc: Exception) -> JSONResponse | None:
    match exc:
        case cascades.CascadesUnavailableError() | GlossaryMismatchError():
            return error(503, "notes_unavailable")
        case cascades.DatasetVersionMismatchError():
            return error(409, "dataset_version_mismatch")
        case cascades.InvalidItemsError():
            return error(422, "invalid_request", [f"evaluation.{f}" for f in exc.fields])
        case service.VersionMismatchError():
            return error(409, "version_mismatch", exc.fields)
        case service.NoteLanguageUnavailableError():
            return error(422, "note_language_unavailable", exc.fields)
        case _:
            return None


@router.post("/notes/document", response_model=NoteOut)
async def notes_document(request: Request) -> Any:
    body = await parse(request, NoteIn)
    if isinstance(body, JSONResponse):
        return body
    db = getattr(request.app.state, "database", None)
    if not isinstance(db, Database):
        return error(503, "notes_unavailable")
    try:
        composed = await run_in_threadpool(compose_in_tx, request, db, body)
    except Exception as exc:  # mapped to codes below; anything else re-raised (500, no values)
        mapped = compose_errors(exc)
        if mapped is None:
            raise
        return mapped
    return JSONResponse(composed.note.model_dump(mode="json"))


# --- outcome loop (design §7) -----------------------------------------------------------------

donation = donation_router()

# Replaced in tests to freeze the clock.
now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC)  # noqa: E731


def keyring_of(request: Request) -> Keyring | None:
    ring = getattr(request.app.state, "note_keyring", None)
    return ring if isinstance(ring, Keyring) else None


def token_error(exc: TokenError) -> JSONResponse:
    if exc.code is TokenErrorCode.token_expired:
        return error(410, "token_expired")
    return error(400, "invalid_token")


@router.post("/notes/token", response_model=TokenOut)
async def notes_token(request: Request) -> Any:
    body = await parse(request, TokenIn)
    if isinstance(body, JSONResponse):
        return body
    settings: Settings = request.app.state.settings
    ring = keyring_of(request)
    db = getattr(request.app.state, "database", None)
    if ring is None or not settings.outcome_consent_versions or not isinstance(db, Database):
        return error(503, "notes_unavailable")
    if body.consent_version not in settings.outcome_consent_versions:
        return error(422, "invalid_request", ["consent_version"])
    issued = loop.Issued()
    sign = loop.signer(
        ring,
        now=now(),
        language=body.note.languages[0],
        region=body.outcome_region,
        consent_version=body.consent_version,
        event_keys=request.app.state.event_vocabulary.pipc_event_keys(),
        issued=issued,
    )
    try:
        composed = await run_in_threadpool(compose_in_tx, request, db, body.note, sign)
    except loop.NoFindingsError:
        return error(422, "no_findings")
    except Exception as exc:  # mapped to codes; anything else re-raised (500, no values)
        mapped = compose_errors(exc)
        if mapped is None:
            raise
        return mapped
    assert issued.expires_on is not None  # noqa: S101 (set by the signer)
    out = TokenOut(
        token=issued.token,
        qr_url=None
        if settings.public_base_url is None
        else qr.outcome_url(settings.public_base_url, issued.token),
        expires_on=issued.expires_on.isoformat(),
        findings_covered=issued.covered,
        findings_total=issued.total,
        note=composed.note,
    )
    return JSONResponse(out.model_dump(mode="json"))


@router.post("/outcomes/form", response_model=OutcomeFormOut)
async def outcomes_form(request: Request) -> Any:
    body = await parse(request, TokenBodyIn)
    if isinstance(body, JSONResponse):
        return body
    ring = keyring_of(request)
    db = getattr(request.app.state, "database", None)
    if ring is None or not isinstance(db, Database):
        return error(503, "notes_unavailable")
    try:
        payload = verify(ring, body.token, today())
    except TokenError as exc:
        return token_error(exc)

    def call() -> OutcomeFormOut:
        with db.read_only_tx() as conn:
            return loop.form(conn, payload, request.app.state.glossary)

    try:
        out = await run_in_threadpool(call)
    except loop.TokenUsedError:
        return error(409, "token_used")
    except loop.TokenNotUsableError:
        return error(410, "token_not_usable")
    except loop.LoopUnavailableError:
        return error(503, "notes_unavailable")
    return JSONResponse(out.model_dump(mode="json"))


def _writes_allowed(request: Request) -> tuple[Keyring, Database] | None:
    settings: Settings = request.app.state.settings
    ring = keyring_of(request)
    db = getattr(request.app.state, "database", None)
    if ring is None or not isinstance(db, Database):
        return None
    if not region_allows_donations(settings.donation_region):
        return None  # outcomes are stored in an EU region only (privacy Req 3.4)
    return ring, db


@donation.post("/outcomes", response_model=OutcomeStoredOut)
async def outcomes_submit(request: Request) -> Any:
    body = await parse(request, OutcomeIn)
    if isinstance(body, JSONResponse):
        return body
    allowed = _writes_allowed(request)
    if allowed is None:
        return error(503, "notes_unavailable")
    ring, db = allowed
    try:
        payload = verify(ring, body.token, today())
    except TokenError as exc:
        return token_error(exc)
    try:
        stored = await run_in_threadpool(loop.submit, db, payload, body.answers, now())
    except AnswerError as exc:
        return error(422, "invalid_request", exc.fields)
    except loop.TokenUsedError:
        return error(409, "token_used")
    except loop.TokenNotUsableError:
        return error(410, "token_not_usable")
    return JSONResponse(OutcomeStoredOut(stored=stored).model_dump(mode="json"))


@donation.post("/notes/withdraw", response_model=WithdrawnOut)
async def notes_withdraw(request: Request) -> Any:
    body = await parse(request, TokenBodyIn)
    if isinstance(body, JSONResponse):
        return body
    allowed = _writes_allowed(request)
    if allowed is None:
        return error(503, "notes_unavailable")
    ring, db = allowed
    try:
        payload = verify_signature_only(ring, body.token)
    except TokenError as exc:
        return token_error(exc)
    await run_in_threadpool(loop.withdraw, db, payload, today())
    return JSONResponse(WithdrawnOut().model_dump(mode="json"))
