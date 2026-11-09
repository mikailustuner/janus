"""`/open/data-quality` routes (data-quality design §9): the current report as JSON, CSV and
Markdown. Read-only, stateless, precomputed by `python -m janus.quality.build`; nothing is
computed on a request. Medical routes (no-store, access line only). 503
`data_quality_unavailable` when no report is installed or the file is malformed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from janus.http_policy.routes import medical_router
from janus.quality import report as r

router = medical_router()
UNAVAILABLE = {"error": "data_quality_unavailable"}


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Klass = Literal["confirmed_error", "needs_pharmacist", "benign_difference"]
CheckName = Literal["exclusion_status", "item_group", "regulator_group", "substance_code_keys"]


class FindingOut(_Out):
    id: str
    status: Literal["new", "persisting", "resolved"]
    class_: Klass = Field(alias="class")
    class_changed_from: Klass | None
    check: CheckName
    source: str
    key: str
    label_en: str | None
    wikidata_url: str | None
    code: str
    compared_codes: list[str]
    products: int
    reasons: list[str]
    other_keys: list[str]
    upstream: Literal["persisting", "resolved_upstream"] | None
    whocc_group_urls: list[str]
    how_to_find: str


class SummaryOut(_Out):
    findings: int
    by_class: dict[Klass, int]
    by_check: dict[CheckName, int]
    by_check_class: dict[CheckName, dict[Klass, int]]
    by_status: dict[Literal["new", "persisting", "resolved"], int]
    confirmed_errors_still_published: int
    confirmed_errors_resolved_upstream: int


class DataQualityOut(_Out):
    dataset: Literal["janus-data-quality"]
    version: str
    run_id: str
    run_date: str
    previous_run_id: str | None
    previous_version: str | None
    license: Literal["CC BY 4.0"]
    license_url: str
    attribution: str
    disclaimer: str
    class_meaning: str
    dictionary_url: str
    review_status: str
    notices: list[str]
    resolution_dataset: str
    code_version: str
    sources: dict[str, dict[str, Any]]
    rules: dict[str, str]
    metrics: dict[str, Any]
    summary: SummaryOut
    findings: list[FindingOut]


class DataQualityHolder:
    """Reads `<data_dir>/quality/current/report.json` once; `value` is None when absent."""

    def __init__(self, data_dir: Path | None) -> None:
        self._dir = None if data_dir is None else data_dir / "quality" / "current"
        self._value: dict[str, Any] | None = None
        self._loaded = False

    @property
    def value(self) -> dict[str, Any] | None:
        if not self._loaded:
            self._loaded = True
            if self._dir is not None:
                try:
                    payload = json.loads((self._dir / "report.json").read_text(encoding="utf-8"))
                    DataQualityOut.model_validate(payload)
                    self._value = payload
                except (OSError, ValueError):
                    self._value = None
        return self._value


def _report(request: Request) -> dict[str, Any] | None:
    holder = getattr(request.app.state, "data_quality", None)
    return holder.value if isinstance(holder, DataQualityHolder) else None


@router.get("/open/data-quality", response_model=DataQualityOut, response_model_by_alias=True)
def data_quality(request: Request) -> Any:
    """The current data-quality report: findings with their class and status against the
    previous run, the sources and the rules. Codes and counts only."""
    rep = _report(request)
    if rep is None:
        return JSONResponse(UNAVAILABLE, status_code=503)
    return JSONResponse(rep)


@router.get(
    "/open/data-quality.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "One row per finding."}},
)
def data_quality_csv(request: Request) -> Any:
    rep = _report(request)
    if rep is None:
        return JSONResponse(UNAVAILABLE, status_code=503)
    return Response(
        r.to_csv(rep),
        media_type="text/csv; charset=utf-8",
        headers={
            "content-disposition": (
                f'attachment; filename="janus-data-quality-{rep["run_date"]}.csv"'
            ),
            "x-janus-dataset-version": str(rep["version"]),
        },
    )


@router.get(
    "/open/data-quality.md",
    response_class=Response,
    responses={200: {"content": {"text/markdown": {}}, "description": "Readable summary."}},
)
def data_quality_markdown(request: Request) -> Any:
    rep = _report(request)
    if rep is None:
        return JSONResponse(UNAVAILABLE, status_code=503)
    return Response(
        r.to_markdown(rep),
        media_type="text/markdown; charset=utf-8",
        headers={"x-janus-dataset-version": str(rep["version"])},
    )
