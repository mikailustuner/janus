"""Request and response models of the evidence routes (evidence-integrity design §3.4).

Requests are strict and reject unknown keys. Responses carry fixed codes and data, no sentences.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    field_validator,
)

from janus.integrity.line import IntegrityLine
from janus.integrity.model import is_evidence_id
from janus.integrity.view import EvidenceItem, StatusCode
from janus.memory import messages

DISCLAIMER = messages.DISCLAIMER  # rule 9, em dash (doctor-loop DP18)

MAX_IDS = 200
_DATE = r"^\d{4}-\d{2}-\d{2}$"


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResolveIn(_In):
    evidence_ids: Annotated[list[StrictStr], Field(min_length=1, max_length=MAX_IDS)]

    @field_validator("evidence_ids")
    @classmethod
    def _ids(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("ids must be distinct")
        if not all(is_evidence_id(v) for v in value):
            raise ValueError("not an evidence id")
        return value


class ChangesIn(_In):
    since: Annotated[StrictStr, Field(pattern=_DATE)] | None = None
    limit: Annotated[StrictInt, Field(ge=1, le=500)] = 100

    @field_validator("since")
    @classmethod
    def _since(cls, value: str | None) -> str | None:
        if value is not None:
            dt.date.fromisoformat(value)  # ValueError → 422 naming the field
        return value


class Excluded(_Out):
    id: str
    reason: Literal["retracted", "not_registered", "no_citable_basis"]


class EvidenceResolution(_Out):
    integrity_version: str
    as_of: dt.date
    items: list[EvidenceItem]
    citable_ids: list[str]
    excluded: list[Excluded]
    line: IntegrityLine
    disclaimer: str = DISCLAIMER


class StatusCountsAll(_Out):
    ok: int
    corrected: int
    expression_of_concern: int
    retracted: int
    unknown: int


class ChangeView(_Out):
    evidence_id: str
    title: str | None
    doi: str | None
    from_status: StatusCode
    to_status: StatusCode
    observed_on: dt.date
    run_id: str | None


class ChangesResult(_Out):
    integrity_version: str
    as_of: dt.date
    since: dt.date | None
    observed_dates: list[dt.date]
    status_counts: StatusCountsAll
    changes: list[ChangeView]
    disclaimer: str = DISCLAIMER
