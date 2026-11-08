"""Donation request and stored-record models (privacy design §5.1, Req 3.1, 3.2).

Only the allowed fields exist. Unknown fields, strings for numbers and any date are rejected.
Consent versions and event keys are checked against the configured sets, passed as the
validation context; without a context validation fails (fail closed).
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Final, Literal, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
)

# Adults only (owner decision, DP6): no parental-consent flow. 90 means "90 and over".
AGE_BANDS: Final = (*range(20, 90, 5), 90)
Sex = Literal["female", "male"]
Region = Literal["TR", "EU", "US"]
Direction = Literal["adverse", "benefit"]

# Wikidata items and curated Janus keys `J<n>` (collective-memory DP17, migration 0007).
QID_PATTERN: Final = r"^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$"
EVENT_PATTERN: Final = r"^[a-z0-9][a-z0-9_.-]{0,63}$"
CONSENT_PATTERN: Final = r"^[a-z0-9][a-z0-9.-]{0,31}$"
TOKEN_PATTERN: Final = r"^jdt_[A-Za-z0-9_-]{43}$"  # noqa: S105 (a format, not a secret)

Qid = Annotated[str, StringConstraints(pattern=QID_PATTERN)]
EventKey = Annotated[str, StringConstraints(pattern=EVENT_PATTERN)]
ConsentVersion = Annotated[str, StringConstraints(pattern=CONSENT_PATTERN)]

STORED_FIELDS: Final = (
    "report_week",
    "age_band",
    "sex",
    "region",
    "ingredients",
    "event",
    "direction",
    "consent_version",
)


def _context_set(info: ValidationInfo, name: str) -> frozenset[str]:
    ctx = cast(object, info.context)
    value: object = cast(dict[str, object], ctx).get(name) if isinstance(ctx, dict) else None
    if not isinstance(value, frozenset):
        raise ValueError("validation context missing")
    return cast(frozenset[str], value)


class Consent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    version: ConsentVersion
    # Strict bool, then `is True`: Literal[True] would also accept 1 (equality check).
    explicit: bool

    @field_validator("explicit")
    @classmethod
    def _explicit_true(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("explicit consent is required")
        return value

    @field_validator("version")
    @classmethod
    def _known_version(cls, value: str, info: ValidationInfo) -> str:
        if value not in _context_set(info, "consent_versions"):
            raise ValueError("unknown consent version")
        return value


class ContributionIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    consent: Consent
    # Strict int, then membership: Literal[...] would also accept 65.0 (equality check).
    age_band: int
    sex: Sex | None = None
    region: Region
    ingredients: Annotated[list[Qid], Field(min_length=1, max_length=20)]
    event: EventKey
    direction: Direction

    @field_validator("age_band")
    @classmethod
    def _adult_band(cls, value: int) -> int:
        if value not in AGE_BANDS:
            raise ValueError("age band must be 20, 25, ..., 85 or 90")
        return value

    @field_validator("ingredients")
    @classmethod
    def _distinct(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("ingredients must be distinct")
        return sorted(value)

    @field_validator("event")
    @classmethod
    def _known_event(cls, value: str, info: ValidationInfo) -> str:
        if value not in _context_set(info, "events"):
            raise ValueError("unknown event key")
        return value


class ContributionStored(BaseModel):
    """Exactly what is stored, returned so the client can show it (no id, no token hash)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    report_week: dt.date
    age_band: int
    sex: Sex | None
    region: Region
    ingredients: list[str]
    event: str
    direction: Direction
    consent_version: str

    @classmethod
    def from_request(cls, req: ContributionIn, report_week: dt.date) -> ContributionStored:
        return cls(
            report_week=report_week,
            age_band=req.age_band,
            sex=req.sex,
            region=req.region,
            ingredients=list(req.ingredients),
            event=req.event,
            direction=req.direction,
            consent_version=req.consent.version,
        )


class DeletionIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    deletion_token: Annotated[str, StringConstraints(pattern=TOKEN_PATTERN)]


class ContributionCreated(BaseModel):
    deletion_token: str
    stored: ContributionStored


class DeletionDone(BaseModel):
    deleted: Literal[True]
