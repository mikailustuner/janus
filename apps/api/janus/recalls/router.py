"""`POST /recalls/check` (recall-check design §7, Req 4): the FDA enforcement report records that
name a US product code and, when a lot is given, whether a record's lot text lists it.

A medical route: the NDC and the lot come in the JSON body only, are never logged or stored, and
a 422 names fields with fixed codes and never echoes input. Read-only and stateless; 503
`recalls_unavailable` when no `us_recalls` run is installed.

The answer quotes the record and adds nothing to it: no statement about the medicine, and an
empty `matches` list is not a statement that the product has no problem (notice
`absence_is_not_clearance`).
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError
from starlette.concurrency import run_in_threadpool

from janus.http_policy.routes import medical_router
from janus.integrity.freshness import is_stale
from janus.recalls.codes import normalise_lot
from janus.recalls.match import LotMatch, Match, NdcMatch, Query, find, query_from_input
from janus.recalls.store import SOURCE_ID, Loaded, RecallsHolder
from janus.resolution.ndc import NdcError

router = medical_router()

MAX_MATCHES = 20
CODE_INFO_MAX = 2000
CADENCE_DAYS = 7  # pipelines/sources.toml, openfda_enforcement
DISCLAIMER = (
    "Janus provides information, not medical advice. Research prototype — not a medical device."
)
SOURCE_URL = "https://open.fda.gov/apis/drug/enforcement/"
TERMS_URL = "https://open.fda.gov/terms/"
SEARCH_URL = "https://www.accessdata.fda.gov/scripts/ires/index.cfm"
RECORD_URL = "https://api.fda.gov/drug/enforcement.json?search=recall_number.exact:%22{}%22&limit=1"
# GS1 character set 82 (the characters AI (10) may hold).
LOT_PATTERN = r"^[!\"%&'()*+,\-./0-9:;<=>?A-Z_a-z]{1,20}$"

Notice = Literal[
    "us_records_only",
    "absence_is_not_clearance",
    "status_as_published",
    "records_without_ndc_not_searched",
    "lot_text_read_automatically",
    "not_an_alert_service",
    "snapshot_outdated",
]
FIXED_NOTICES: tuple[Notice, ...] = (
    "us_records_only",
    "absence_is_not_clearance",
    "status_as_published",
    "records_without_ndc_not_searched",
    "lot_text_read_automatically",
    "not_an_alert_service",
)

# Replaced in tests to freeze the date (the `snapshot_outdated` notice).
today: Callable[[], dt.date] = lambda: dt.datetime.now(dt.UTC).date()  # noqa: E731


class RecallCheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    ndc: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    lot: Annotated[str, StringConstraints(pattern=LOT_PATTERN)] | None = None


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceOut(_Out):
    source_id: Literal["openfda_enforcement"]
    run_id: str
    snapshot_date: dt.date
    license: str
    url: str
    terms_url: str
    search_url: str
    records: int
    records_with_ndc: int


class RecallMatchOut(_Out):
    recall_number: str
    event_id: str | None
    classification: str | None
    status: str | None
    terminated: bool
    recall_initiation_date: dt.date | None
    center_classification_date: dt.date | None
    report_date: dt.date | None
    termination_date: dt.date | None
    reason_for_recall: str | None
    product_description: str | None
    code_info: str | None
    code_info_truncated: bool
    recalling_firm: str | None
    ndc_match: NdcMatch
    lot_match: LotMatch
    lot_codes: list[str]
    record_url: str


class RecallCheckOut(_Out):
    region: Literal["US"]
    source: SourceOut
    ndc_level: NdcMatch
    lot_given: bool
    matches: list[RecallMatchOut]
    total_matches: int
    truncated: bool
    notices: list[Notice]
    disclaimer: str


def _error(status: int, error: str, fields: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(body, status_code=status)


def _date(text: str | None) -> dt.date | None:
    return dt.date.fromisoformat(text) if text else None


def match_out(m: Match) -> RecallMatchOut:
    r = m.recall
    lot_text = "\n".join(t for t in (r.code_info, r.more_code_info) if t) or None
    return RecallMatchOut(
        recall_number=r.recall_number,
        event_id=r.event_id,
        classification=r.classification,
        status=r.status,
        terminated=r.terminated,
        recall_initiation_date=_date(r.recall_initiation_date),
        center_classification_date=_date(r.center_classification_date),
        report_date=_date(r.report_date),
        termination_date=_date(r.termination_date),
        reason_for_recall=r.reason_for_recall,
        product_description=r.product_description,
        code_info=lot_text[:CODE_INFO_MAX] if lot_text else None,
        code_info_truncated=lot_text is not None and len(lot_text) > CODE_INFO_MAX,
        recalling_firm=r.recalling_firm,
        ndc_match=m.ndc_match,
        lot_match=m.lot_match,
        lot_codes=sorted(r.lot_codes),
        record_url=RECORD_URL.format(quote(r.recall_number, safe="")),
    )


def check(loaded: Loaded, query: Query, on: dt.date) -> RecallCheckOut:
    """The answer for one product code on the day `on`."""
    matches = find(loaded.index, query)
    notices = list(FIXED_NOTICES)
    if is_stale(loaded.snapshot_date, on, CADENCE_DAYS):
        notices.append("snapshot_outdated")
    return RecallCheckOut(
        region="US",
        source=SourceOut(
            source_id=SOURCE_ID,
            run_id=loaded.run_id,
            snapshot_date=loaded.snapshot_date,
            license=loaded.license,
            url=SOURCE_URL,
            terms_url=TERMS_URL,
            search_url=SEARCH_URL,
            records=loaded.index.records,
            records_with_ndc=loaded.index.records_with_ndc,
        ),
        ndc_level="package" if query.package is not None else "product",
        lot_given=query.lot is not None,
        matches=[match_out(m) for m in matches[:MAX_MATCHES]],
        total_matches=len(matches),
        truncated=len(matches) > MAX_MATCHES,
        notices=notices,
        disclaimer=DISCLAIMER,
    )


@router.post("/recalls/check", response_model=RecallCheckOut)
async def recalls_check(request: Request) -> Any:
    """FDA enforcement report records that name this US product code. Quotes the record; an
    empty list means no record with this code was found, nothing more."""
    try:
        payload = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return _error(422, "invalid_request", ["body"])
    try:
        body = RecallCheckIn.model_validate(payload)
    except ValidationError as exc:
        # Only the route's own field names: an unknown key is the client's text and is not echoed.
        names = {str(e["loc"][0]) if e["loc"] else "body" for e in exc.errors()}
        fields = sorted({n if n in ("ndc", "lot") else "body" for n in names})
        return _error(422, "invalid_request", fields)
    if body.lot is not None and not normalise_lot(body.lot):
        return _error(422, "invalid_request", ["lot"])
    try:
        query = query_from_input(body.ndc, body.lot)
    except NdcError:
        return _error(422, NdcError.code)
    holder = getattr(request.app.state, "recalls", None)
    # The first call after a new run reads the artifact (a file read), off the event loop.
    loaded = (
        await run_in_threadpool(lambda: holder.value) if isinstance(holder, RecallsHolder) else None
    )
    if loaded is None:
        return _error(503, "recalls_unavailable")
    return JSONResponse(check(loaded, query, today()).model_dump(mode="json"))
