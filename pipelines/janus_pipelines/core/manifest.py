"""Manifest and promotion records (design §3.2, Req 1.1, 1.2, 2.2)."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from janus_pipelines.core.canonical import Json


class Outcome(StrEnum):
    SUCCEEDED = "succeeded"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class Counts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: int = 0
    output: int = 0
    excluded: dict[str, int] = Field(default_factory=dict[str, int])


class Manifest(BaseModel):
    """Provenance of one run. Holds no user data and no source row content."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    pipeline: str
    source_id: str
    source_urls: list[str] = Field(default_factory=list[str])
    license: str
    region: str | None = None
    snapshot_date: str | None = None
    snapshot_date_is_retrieval_time: bool = False
    retrieved_at: dt.datetime | None = None
    source_sha256: str | None = None
    content_sha256: str | None = None
    schema_version: str
    code_version: str
    outcome: Outcome
    counts: Counts = Field(default_factory=Counts)
    extra_columns: list[str] = Field(default_factory=list[str])
    metrics: dict[str, Json] = Field(default_factory=dict[str, Json])
    review_reasons: list[str] = Field(default_factory=list[str])
    changes: list[dict[str, Json]] = Field(default_factory=list[dict[str, Json]])
    errors: list[str] = Field(default_factory=list[str])
    previous_run_id: str | None = None
    query_sha256: dict[str, str] = Field(default_factory=dict[str, str])
    started_at: dt.datetime
    finished_at: dt.datetime | None = None


class Promotion(BaseModel):
    """Record of an explicit promotion of a needs_review run (Req 2.2).

    Kept next to the manifest so the manifest itself is never modified after the run.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    promoted_by: str
    promoted_at: dt.datetime
    previous_run_id: str | None


class EvidenceSource(BaseModel):
    """Source-level evidence record for the `evidence` table loader (Req 1.4)."""

    model_config = ConfigDict(extra="forbid")

    kind: str = "dataset"
    source_id: str
    source_url: str
    license: str
    region: str | None
    snapshot_date: str | None
    run_id: str
    doi: str | None = None


def dump(model: BaseModel) -> str:
    return model.model_dump_json(indent=2) + "\n"
