"""`POST /medicine-info` (plain-medicine-info design §6, Req 4): what the groups of a medicine's
ingredients are used for, in fixed sentences of the asked language, and the official text or
page of the product when Janus holds one.

A medical route: ATC codes, the product code and the product name come in the JSON body only,
are never logged or stored, and a 422 names fields with fixed codes and never echoes input.
Read-only and stateless. No text is generated or translated: a group sentence is a row of
`groups.csv` returned with its review status, and the official text is the label section as
published, in its own language, cut only at the end and flagged when cut.

The answer never names a dose, never says how to take a medicine and never says a medicine is
right for a person.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from starlette.concurrency import run_in_threadpool

from janus.cascades.model import AtcClass
from janus.cascades.patterns import class_match
from janus.cascades.rulebase import ABRUPT_FILE, parse_abrupt_stop
from janus.http_policy.routes import medical_router
from janus.integrity.freshness import is_stale
from janus.plaininfo.groups import GroupTable, Language, ReviewStatus, Status, describe
from janus.plaininfo.official import LABEL_URL, Country, Holder, Labels, Pages, Run
from janus.resolution.atc import COMBINATION_RULES_FILE, DATA_DIR, CombinationRules
from janus.resolution.ndc import NdcError, parse_ndc_input

router = medical_router()

MAX_INGREDIENTS = 12
MAX_CODES = 20
TEXT_MAX = 6000  # characters of label text shown; the 99th percentile of the first run is 4,700
LABEL_CADENCE_DAYS = 7  # pipelines/sources.toml, openfda_label_indications
DISCLAIMER = (
    "Janus provides information, not medical advice. Research prototype — not a medical device."
)
SOURCE_URLS = {
    "openfda_label_indications": "https://open.fda.gov/apis/drug/label/",
    "bdpm": "https://base-donnees-publique.medicaments.gouv.fr/",
    "cima": "https://cima.aemps.es/cima/publico/home.html",
}
PAGE_LANGUAGE: dict[Country, Literal["fr", "es"]] = {"FR": "fr", "ES": "es"}

AtcCode = Annotated[str, StringConstraints(pattern=r"^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$")]
OfficialStatus = Literal[
    "text", "page", "not_asked", "not_found", "several_labels", "source_unavailable"
]
Notice = Literal[
    "group_level_only",
    "no_dose_information",
    "expert_review_not_done",
    "official_text_not_translated",
    "label_not_verified_by_fda",
    "label_may_differ_from_box",
    "page_found_by_name",
    "snapshot_outdated",
]

LABEL_NOTICES: tuple[Notice, ...] = (
    "official_text_not_translated",
    "label_not_verified_by_fda",
    "label_may_differ_from_box",
)
PAGE_NOTICES: tuple[Notice, ...] = ("official_text_not_translated", "page_found_by_name")

# Replaced in tests to freeze the date (the `snapshot_outdated` notice).
today: Callable[[], dt.date] = lambda: dt.datetime.now(dt.UTC).date()  # noqa: E731


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class IngredientIn(_In):
    atc_codes: Annotated[list[AtcCode], Field(max_length=MAX_CODES)]


class ProductIn(_In):
    country: Literal["US", "FR", "ES"]
    ndc: Annotated[str, StringConstraints(min_length=1, max_length=32)] | None = None
    name: Annotated[str, StringConstraints(min_length=1, max_length=300)] | None = None


class MedicineInfoIn(_In):
    language: Language
    ingredients: Annotated[list[IngredientIn], Field(max_length=MAX_INGREDIENTS)]
    product: ProductIn | None = None


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GroupOut(_Out):
    id: str
    name: str
    text: str
    codes: list[str]
    review_status: ReviewStatus


class IngredientOut(_Out):
    status: Status
    groups: list[GroupOut]
    other_uses: bool
    abrupt_stop: bool


class SourceOut(_Out):
    source_id: Literal["openfda_label_indications", "bdpm", "cima"]
    run_id: str
    snapshot_date: dt.date
    license: str
    url: str


class OfficialTextOut(_Out):
    kind: Literal["label_text"]
    country: Literal["US"]
    language: Literal["en"]
    section: Literal["indications_and_usage"]
    paragraphs: list[str]
    truncated: bool
    set_id: str
    version: str | None
    effective_date: dt.date | None
    url: str
    source: SourceOut


class OfficialPageOut(_Out):
    kind: Literal["product_page"]
    country: Literal["FR", "ES"]
    language: Literal["fr", "es"]
    url: str
    source: SourceOut


class MedicineInfoOut(_Out):
    language: Language
    groups_version: str
    ingredients: list[IngredientOut]
    official: OfficialTextOut | OfficialPageOut | None
    official_status: OfficialStatus
    notices: list[Notice]
    disclaimer: str


@dataclass(frozen=True)
class Knowledge:
    """What the route reads at startup: the group table and the abrupt-stop list."""

    table: GroupTable
    abrupt_stop: AtcClass


def load_abrupt_stop() -> AtcClass:
    combination = CombinationRules.load(COMBINATION_RULES_FILE)
    cls, _ = parse_abrupt_stop((DATA_DIR / ABRUPT_FILE).read_text(encoding="utf-8"), combination)
    return cls


def cut(paragraphs: Sequence[str], limit: int = TEXT_MAX) -> tuple[list[str], bool]:
    """Whole paragraphs while they fit; the first one that does not fit is cut at the limit when
    nothing else is shown. The result is always a prefix of the published text."""
    shown: list[str] = []
    used = 0
    for p in paragraphs:
        if used + len(p) > limit:
            if not shown:
                shown.append(p[:limit])
            return shown, True
        shown.append(p)
        used += len(p)
    return shown, False


def ingredient_out(k: Knowledge, codes: Sequence[str], language: Language) -> IngredientOut:
    d = describe(k.table, codes)
    return IngredientOut(
        status=d.status,
        groups=[
            GroupOut(
                id=g.id,
                name=g.names[language],
                text=g.uses[language],
                codes=list(matched),
                review_status=g.status,
            )
            for g, matched in d.groups
        ],
        other_uses=bool(d.groups) and bool(d.uncovered),
        abrupt_stop=any(class_match(c, k.abrupt_stop) is not None for c in set(codes)),
    )


def _source(run: Run, source_id: Literal["openfda_label_indications", "bdpm", "cima"]) -> SourceOut:
    return SourceOut(
        source_id=source_id,
        run_id=run.run_id,
        snapshot_date=run.snapshot_date,
        license=run.license,
        url=SOURCE_URLS[source_id],
    )


def label_out(labels: Labels | None, product: str) -> tuple[OfficialTextOut | None, OfficialStatus]:
    """The label text of a 9-digit product key, when exactly one label names it."""
    if labels is None:
        return None, "source_unavailable"
    set_ids = labels.set_ids(product)
    if len(set_ids) > 1:
        return None, "several_labels"
    text = labels.text(set_ids[0]) if set_ids else None
    if text is None:
        return None, "not_found"
    paragraphs, truncated = cut(text.paragraphs)
    return (
        OfficialTextOut(
            kind="label_text",
            country="US",
            language="en",
            section="indications_and_usage",
            paragraphs=paragraphs,
            truncated=truncated,
            set_id=text.set_id,
            version=text.version,
            effective_date=text.effective_date,
            url=LABEL_URL.format(text.set_id),
            source=_source(labels.run, "openfda_label_indications"),
        ),
        "text",
    )


def page_out(pages: Pages | None, name: str) -> tuple[OfficialPageOut | None, OfficialStatus]:
    if pages is None:
        return None, "source_unavailable"
    url = pages.url(name)
    if url is None:
        return None, "not_found"
    return (
        OfficialPageOut(
            kind="product_page",
            country=pages.country,
            language=PAGE_LANGUAGE[pages.country],
            url=url,
            source=_source(pages.run, "bdpm" if pages.country == "FR" else "cima"),
        ),
        "page",
    )


def answer(
    k: Knowledge,
    body: MedicineInfoIn,
    official: OfficialTextOut | OfficialPageOut | None,
    official_status: OfficialStatus,
    on: dt.date,
) -> MedicineInfoOut:
    ingredients = [ingredient_out(k, i.atc_codes, body.language) for i in body.ingredients]
    groups = [g for i in ingredients for g in i.groups]
    notices: list[Notice] = ["no_dose_information"]
    if groups:
        notices.append("group_level_only")
    if any(g.review_status == "not_reviewed" for g in groups):
        notices.append("expert_review_not_done")
    if isinstance(official, OfficialTextOut):
        notices.extend(LABEL_NOTICES)
        if is_stale(official.source.snapshot_date, on, LABEL_CADENCE_DAYS):
            notices.append("snapshot_outdated")
    elif official is not None:
        notices.extend(PAGE_NOTICES)
    return MedicineInfoOut(
        language=body.language,
        groups_version=k.table.version,
        ingredients=ingredients,
        official=official,
        official_status=official_status,
        notices=notices,
        disclaimer=DISCLAIMER,
    )


def _error(status: int, error: str, fields: list[str] | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": error}
    if fields is not None:
        body["fields"] = fields
    return JSONResponse(body, status_code=status)


_FIELDS = ("language", "ingredients", "product")


@router.post("/medicine-info", response_model=MedicineInfoOut)
async def medicine_info(request: Request) -> Any:
    """Fixed group sentences for the ATC codes of a medicine's ingredients, and the official
    label text (US) or product page (FR, ES) when Janus holds one. No dose, no advice."""
    try:
        payload = json.loads(await request.body())
    except (ValueError, UnicodeDecodeError):
        return _error(422, "invalid_request", ["body"])
    try:
        body = MedicineInfoIn.model_validate(payload)
    except ValidationError as exc:
        # Only the route's own field names: an unknown key is the client's text and is not echoed.
        names = {str(e["loc"][0]) if e["loc"] else "body" for e in exc.errors()}
        return _error(
            422, "invalid_request", sorted({n if n in _FIELDS else "body" for n in names})
        )
    product = body.product
    if product is None and not body.ingredients:
        return _error(422, "invalid_request", ["ingredients"])
    key: str | None = None
    if product is not None:
        # A US product is asked by its NDC, a French or Spanish one by its published name.
        if (product.country == "US") != (product.ndc is not None) or (product.country == "US") == (
            product.name is not None
        ):
            return _error(422, "invalid_request", ["product"])
        if product.ndc is not None:
            try:
                keys = parse_ndc_input(product.ndc)
            except NdcError:
                return _error(422, NdcError.code)
            if len(keys) != 1:
                return _error(422, NdcError.code)
            key = next(iter(keys)).code[:9]
    knowledge = getattr(request.app.state, "medicine_info", None)
    if not isinstance(knowledge, Knowledge):
        return _error(503, "medicine_info_unavailable")

    official: OfficialTextOut | OfficialPageOut | None = None
    status: OfficialStatus = "not_asked"
    if product is not None:
        state = request.app.state
        labels: Holder[Labels] | None = getattr(state, "medicine_labels", None)
        pages: dict[Country, Holder[Pages]] = getattr(state, "medicine_pages", {})
        country, name = product.country, product.name or ""

        def look_up() -> tuple[OfficialTextOut | OfficialPageOut | None, OfficialStatus]:
            if key is not None:
                return label_out(None if labels is None else labels.value, key)
            holder = pages.get(country) if country != "US" else None
            return page_out(None if holder is None else holder.value, name)

        # A file read (and, after a new run, an index build), off the event loop.
        official, status = await run_in_threadpool(look_up)
    return JSONResponse(answer(knowledge, body, official, status, today()).model_dump(mode="json"))
