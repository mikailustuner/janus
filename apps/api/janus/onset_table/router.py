"""`/open/faers-onset` routes (faers-onset-table design §7): the descriptive onset table for the
65 PIPC rows as JSON and CSV. Read-only, precomputed by `python -m janus.onset_table.build`.
Medical routes (no-store, access line only). 503 `onset_table_unavailable` when not installed;
404 `unknown_position` and 422 for a bad position in `/open/faers-onset/{position}`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from janus.http_policy.routes import medical_router
from janus.onset_table import dataset as d

router = medical_router()
UNAVAILABLE = {"error": "onset_table_unavailable"}

Status = Literal[
    "described",
    "small_sample",
    "cluster_dominated",
    "count_only",
    "no_interval",
    "no_candidate_reports",
]
Reason = Literal[
    "no_therapy_start",
    "start_date_partial",
    "event_date_missing",
    "event_date_partial",
    "negative_interval",
    "interval_over_max",
]


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MemberCountOut(_Out):
    key: str
    candidate_reports: int
    reports_with_interval: int


class RowNoteOut(_Out):
    code: str
    note: str


class OnsetRowOut(_Out):
    pipc_position: int
    pipc_system: str
    pipc_drug_a: str
    pipc_adverse_event: str
    pipc_drug_b: str
    pipc_locator: str
    index_class: str
    class_ingredient_keys: list[str]
    excluded_class_keys: list[str]
    route_groups_counted: list[
        Literal["systemic_or_unknown", "eye", "rectal", "nasal_inhaled", "joint_lesion"]
    ]
    form_extensions_on: bool
    event_key: str
    event_pts: list[str]
    shared_with_positions: list[int]
    candidate_reports: int
    reports_with_interval: int
    usable_share: float | None
    candidates_without_interval_by_reason: dict[Reason, int]
    members_with_reports: list[MemberCountOut]
    distinct_intervals: int
    multi_line_reports: int
    multi_event_reports: int
    event_year_min: int | None
    event_year_max: int | None
    status: Status
    small_sample: bool
    omitted_reason: str | None
    median_days: float | None
    q25_days: float | None
    q75_days: float | None
    median_ci_low_days: float | None
    median_ci_high_days: float | None
    median_ci_degenerate: bool | None
    median_exact_ci_low_days: float | None
    median_exact_ci_high_days: float | None
    median_exact_ci_coverage: float | None
    median_reflects_zero_heaping: bool | None
    median_days_earliest_class_start: float | None
    median_days_distinct_date_pairs: float | None
    zero_day_reports: int
    zero_day_share: float | None
    day_one_reports: int
    jan_one_reports: int
    day_one_share: float | None
    reports_without_day_one: int
    median_days_without_day_one: float | None
    sensitivity_omitted_reason: str | None
    largest_date_cluster: int
    reports_in_clusters_ge3: int
    weibull_shape: float | None
    weibull_shape_ci_low: float | None
    weibull_shape_ci_high: float | None
    weibull_scale_days: float | None
    weibull_shape_class: Literal["early", "random", "wear_out"] | None
    shape_omitted_reason: str | None
    row_notes: list[RowNoteOut]
    descriptive_only: Literal[True]
    causal: Literal[False]
    incidence: Literal[False]
    counts_are: Literal["reports"]


class OnsetSummaryOut(_Out):
    rows: int
    by_status: dict[Status, int]
    rows_with_any_interval: int
    rows_with_median: int
    rows_with_weibull_shape: int
    weibull_shape_classes: dict[Literal["early", "random", "wear_out"], int]
    distinct_class_event_pairs: int


class OnsetTableOut(_Out):
    dataset: Literal["janus-faers-onset-pipc"]
    version: str
    built_at: str
    faers_receipt_quarters: list[str]
    faers_snapshot_date: str | None
    faers_run_id: str
    faers_onset_run_id: str
    faers_counts_build_id: str
    resolution_dataset: str
    rule_base_version: str
    event_vocabulary_sha256: str
    key_exclusions_sha256: str
    row_notes_sha256: str
    faers_onset_quality: dict[str, Any]
    license: Literal["CC BY 4.0"]
    license_url: str
    attribution: str
    meddra_notice: str
    dictionary_url: str
    review_status: str
    disclaimer: str
    descriptive_only: Literal[True]
    causal: Literal[False]
    incidence: Literal[False]
    counts_are: Literal["reports"]
    caveats: dict[str, str]
    method: dict[str, Any]
    summary: OnsetSummaryOut
    rows: list[OnsetRowOut]


class OnsetRowResponse(_Out):
    dataset: Literal["janus-faers-onset-pipc"]
    version: str
    faers_receipt_quarters: list[str]
    license: Literal["CC BY 4.0"]
    attribution: str
    meddra_notice: str
    caveats: dict[str, str]
    row: OnsetRowOut


class OnsetTableHolder:
    """Reads `<data_dir>/onset_table/current/faers_onset_pipc.json` once; None when absent."""

    def __init__(self, data_dir: Path | None) -> None:
        self._path = (
            None
            if data_dir is None
            else data_dir / "onset_table" / "current" / "faers_onset_pipc.json"
        )
        self._value: dict[str, Any] | None = None
        self._loaded = False

    @property
    def value(self) -> dict[str, Any] | None:
        if not self._loaded:
            self._loaded = True
            if self._path is not None:
                try:
                    payload = json.loads(self._path.read_text(encoding="utf-8"))
                    OnsetTableOut.model_validate(payload)
                    self._value = payload
                except (OSError, ValueError):
                    self._value = None
        return self._value


def _table(request: Request) -> dict[str, Any] | None:
    holder = getattr(request.app.state, "onset_table", None)
    return holder.value if isinstance(holder, OnsetTableHolder) else None


@router.get("/open/faers-onset", response_model=OnsetTableOut)
def onset_table(request: Request) -> Any:
    """All 65 PIPC rows with their FAERS report counts and reported time to onset."""
    data = _table(request)
    if data is None:
        return JSONResponse(UNAVAILABLE, status_code=503)
    return JSONResponse(data)


@router.get(
    "/open/faers-onset.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "One row per PIPC row."}},
)
def onset_table_csv(request: Request) -> Any:
    data = _table(request)
    if data is None:
        return JSONResponse(UNAVAILABLE, status_code=503)
    return Response(
        d.to_csv(data),
        media_type="text/csv; charset=utf-8",
        headers={
            "content-disposition": 'attachment; filename="janus-faers-onset-pipc.csv"',
            "x-janus-dataset-version": str(data["version"]),
        },
    )


@router.get("/open/faers-onset/{position}", response_model=OnsetRowResponse)
def onset_row(request: Request, position: str) -> Any:
    """One PIPC row (1-65) with the dataset's caveats."""
    data = _table(request)
    if data is None:
        return JSONResponse(UNAVAILABLE, status_code=503)
    if not (position.isdigit() and len(position) <= 2):
        return JSONResponse({"error": "invalid_request", "fields": ["position"]}, status_code=422)
    found = [r for r in data["rows"] if r["pipc_position"] == int(position)]
    if not found:
        return JSONResponse({"error": "unknown_position"}, status_code=404)
    return JSONResponse(
        {
            "dataset": data["dataset"],
            "version": data["version"],
            "faers_receipt_quarters": data["faers_receipt_quarters"],
            "meddra_notice": data["meddra_notice"],
            "license": data["license"],
            "attribution": data["attribution"],
            "caveats": data["caveats"],
            "row": found[0],
        }
    )
