"""CDS Hooks routes (cds-hooks design §2, §3, §7): `GET /cds-services` and
`POST /cds-services/janus-cascade`. Medical routes: `no-store`, nothing logged but the access line.

The body is validated here (not by FastAPI) so that a 422 names failing fields only and never
echoes a code, id or name from the request. Janus never calls the client's FHIR server and never
reads `fhirAuthorization`.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from typing import Any, Final, Literal, cast

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from janus.cascades import service as cascades
from janus.cds import fhir, service
from janus.cds.cards import CardsOut
from janus.db.pool import Database
from janus.http_policy.routes import medical_router

router = medical_router()

SERVICE_ID: Final = "janus-cascade"
SERVICE_PATH: Final = f"/cds-services/{SERVICE_ID}"

# Replaced in tests to freeze the date.
today: Callable[[], dt.date] = lambda: dt.datetime.now(dt.UTC).date()  # noqa: E731


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ServiceOut(_Out):
    hook: Literal["order-select", "order-sign"]
    title: str
    description: str
    id: str
    prefetch: dict[str, str]
    usage_requirements: str = Field(serialization_alias="usageRequirements")


class DiscoveryOut(_Out):
    services: list[ServiceOut]


TITLE: Final = "Janus prescribing-cascade check (research prototype)"
DESCRIPTION: Final = (
    "Checks the draft medication orders against the patient's active medications for patterns of "
    "the published PIPC list of potentially inappropriate prescribing cascades (Rochon et al. "
    "2025). Research prototype, not a medical device, not for clinical use. Janus shows a card "
    "only when it finds a pattern from its rule list; no card does not mean the medicines are free "
    "of problems."
)
USAGE: Final = (
    "Research prototype, not a medical device, not for clinical use. Reads NDC, RxNorm and ATC "
    "codings of MedicationRequest and MedicationStatement resources; start dates are not read. "
    "Stores and logs nothing of the request. Client authentication (JWT) is not implemented yet. "
    "No card does not mean the medicines are free of problems."
)
PREFETCH: Final = {
    "medicationRequests": "MedicationRequest?patient={{context.patientId}}&status=active,on-hold",
    "medicationStatements": (
        "MedicationStatement?patient={{context.patientId}}&status=active,on-hold"
    ),
}
DISCOVERY: Final = DiscoveryOut(
    services=[
        ServiceOut(
            hook=hook,
            title=TITLE,
            description=DESCRIPTION,
            id=SERVICE_ID,
            prefetch=PREFETCH,
            usage_requirements=USAGE,
        )
        for hook in ("order-select", "order-sign")
    ]
)


def _error(status: int, error: str, fields: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(body, status_code=status)


def _field(loc: tuple[int | str, ...], kind: str) -> str:
    """The failing field's path. An unknown key is named `<unknown>`: its name is the sender's
    text and could carry data (P8 counterexample: a key named after an id)."""
    parts = [str(p) for p in loc]
    if kind == "extra_forbidden" and parts:
        parts[-1] = "<unknown>"
    return ".".join(parts) or "body"


@router.get("/cds-services", response_model=DiscoveryOut)
def discovery() -> Any:
    """CDS Hooks discovery: the `janus-cascade` service for `order-select` and `order-sign`."""
    return JSONResponse(DISCOVERY.model_dump(mode="json", by_alias=True))


@router.post(SERVICE_PATH, response_model=CardsOut)
async def janus_cascade(request: Request) -> Any:
    try:
        payload = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return _error(422, "invalid_request", ["body"])
    if not isinstance(payload, dict):
        return _error(422, "invalid_request", ["body"])
    try:
        body = fhir.HookRequest.model_validate(payload)
    except ValidationError as exc:
        fields = sorted({_field(e["loc"], e["type"]) for e in exc.errors()})
        return _error(422, "invalid_request", fields)
    prefetch = cast(dict[str, Any], payload).get("prefetch")
    sent: frozenset[str] = (
        frozenset(cast(dict[str, Any], prefetch)) if isinstance(prefetch, dict) else frozenset()
    )
    try:
        extracted = fhir.extract(body, sent)
    except fhir.PrefetchMissingError:
        return _error(412, "prefetch_missing")
    except fhir.FieldError as exc:
        return _error(422, "invalid_request", exc.fields)
    db = getattr(request.app.state, "database", None)
    if not isinstance(db, Database):
        return _error(503, "cascades_unavailable")
    day = today()
    keys = request.app.state.event_vocabulary.pipc_event_keys()

    def call() -> CardsOut:
        with db.read_only_tx() as conn:
            return service.evaluate(conn, extracted, day, keys)

    try:
        result = await run_in_threadpool(call)
    except cascades.CascadesUnavailableError:
        return _error(503, "cascades_unavailable")
    except service.TooManyMedicationsError:
        return _error(422, "too_many_medications")
    return JSONResponse(result.model_dump(mode="json"))
