"""Build file (`light-1`) and API models of the light face (design §7 to §9).

The build file is written by `janus.light.build` and read back by `janus.light.store`; the API
answers are built from it per request. Counts are reports or labels, never people.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from janus.memory.schemas import StatsOut

SCHEMA_VERSION: Literal["light-1"] = "light-1"
GoalKey = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,40}$")]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- build file -------------------------------------------------------------------------------


class GoalOut(_M):
    key: str
    labels: dict[str, str]
    faers_pts: list[str]
    benefit_keys: list[str]
    label_terms: list[str]  # active mapping terms pointing to the goal
    note: str


class MappingOut(_M):
    term: str
    goal: str
    status: Literal["active", "excluded"]
    evidence_ids: list[str]
    rationale: str


class LabelSignalOut(_M):
    regions: list[str]
    labels_with_effect: int
    labels_total: int
    share_low: float  # Wilson lower bound (95 %) of labels_with_effect / labels_total
    sections: list[str]
    terms: list[str]
    evidence_ids: list[str]


class InverseOut(_M):
    stats: StatsOut
    pts: list[str]
    reports: int
    evidence_ids: list[str]
    locator: str


class RankOut(_M):
    best: int
    worst: int
    population: int


class CandidateOut(_M):
    ingredient: str
    goal: str
    rank: RankOut
    label: LabelSignalOut | None
    inverse: InverseOut | None


class CaseOut(_M):
    id: str
    ingredient_name: str
    ingredient_key: str
    goal: str
    original_use: str
    later_year: int
    indication_terms: list[str]
    evidence_ids: list[str]
    note: str


class CaseRunOut(_M):
    run: Literal["primary", "sensitivity"]
    rank: RankOut | None
    population: int
    hit: bool
    informative: bool
    labels_used: int
    labels_removed_indication: int
    labels_removed_not_in_openfda: int
    signal_types: list[str]
    reason: Literal[
        "hit", "ranked_below_top", "not_a_candidate", "no_label_mapping", "not_evaluable"
    ]


class CaseResultOut(_M):
    case: CaseOut
    primary: CaseRunOut
    sensitivity: CaseRunOut
    faers: StatsOut | None
    faers_inverse: bool
    faers_includes_later_use: bool


class SummaryOut(_M):
    hits: int
    informative_hits: int
    misses: int
    not_evaluable: int


class ValidationPart(_M):
    top_k: int
    status: Literal["experimental", "prototype"]
    cases: list[CaseResultOut]
    primary: SummaryOut
    sensitivity: SummaryOut


class InputsOut(_M):
    onsides_run_id: str
    onsides_release: str
    onsides_date: str
    openfda_run_id: str
    openfda_date: str
    faers_build_id: str
    faers_snapshot_date: str
    faers_window: list[str]
    wikidata_run_id: str
    curated_sha256: dict[str, str]
    code_sha256: str


class CoverageOut(_M):
    labels: int
    single_ingredient_labels: int
    ingredients_by_method: dict[str, int]
    candidates_by_goal: dict[str, int]
    inverse_by_goal: dict[str, int]


class LightFile(_M):
    schema_version: Literal["light-1"]
    build_id: str
    inputs: InputsOut
    goals: list[GoalOut]
    mapping: list[MappingOut]
    ingredients: dict[str, dict[str, str]]  # key -> language -> name
    candidates: dict[str, list[CandidateOut]]  # goal -> ranked candidates
    validation: ValidationPart
    coverage: CoverageOut


# --- API ----------------------------------------------------------------------------------------


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CardsIn(_In):
    goal: GoalKey
    offset: Annotated[int, Field(ge=0, le=100_000)] = 0
    limit: Annotated[int, Field(ge=1, le=50)] = 20


class SnapshotOut(_M):
    build_id: str
    onsides_release: str
    onsides_date: str
    faers_snapshot_date: str
    faers_window: list[str]
    openfda_date: str


class SourceOut(_M):
    id: str
    title: str | None
    doi: str | None
    url: str
    status: str
    snapshot_date: str


class RemovedOut(_M):
    id: str
    reason: str


class IngredientOut(_M):
    key: str
    labels: dict[str, str]


class GoalRef(_M):
    key: str
    labels: dict[str, str]


class PatientCellOut(_M):
    region: str
    status: Literal["released", "hidden"]
    value: int | None = None


class PatientSignalOut(_M):
    event: str
    total_of_released: int
    cells: list[PatientCellOut]
    k: int
    epsilon: str


class CardSignalOut(_M):
    type: Literal["label_effect", "inverse_faers", "patient_reported"]
    label: LabelSignalOut | None = None
    inverse: InverseOut | None = None
    patient: PatientSignalOut | None = None
    codes: list[str]


class CardOut(_M):
    ingredient: IngredientOut
    goal: GoalRef
    rank: RankOut
    signals: list[CardSignalOut]
    sources: list[SourceOut]
    removed_sources: list[RemovedOut]
    mechanism: None = None
    codes: list[str]


class PatientOnlyOut(_M):
    ingredient: IngredientOut
    goal: GoalRef
    signal: PatientSignalOut
    codes: list[str]


class GoalSummaryOut(_M):
    key: str
    labels: dict[str, str]
    candidates: int
    label_terms: list[str]
    faers_pts: list[str]
    benefit_keys: list[str]


class Common(_M):
    schema_version: Literal["light-1"] = "light-1"
    status: Literal["experimental", "prototype"]
    review_status: Literal["ai_reviewed_pending_expert"] = "ai_reviewed_pending_expert"
    snapshot: SnapshotOut
    codes: list[str]
    disclaimer: str
    attribution: list[str]


class OverviewOut(Common):
    goals: list[GoalSummaryOut]
    top_k: int


class CardsOut(Common):
    goal: GoalRef
    total: int
    offset: int
    cards: list[CardOut]
    patient_reported: list[PatientOnlyOut]
    patient_layer: Literal["ok", "layer_unavailable"]
    removed_by_integrity: int
    warning_sources: list[SourceOut]


class ValidationOut(Common):
    top_k: int
    cases: list[CaseResultOut]
    primary: SummaryOut
    sensitivity: SummaryOut
    goals: list[GoalRef]
    ingredients: dict[str, dict[str, str]]
    sources: list[SourceOut]


class ExportRowOut(_M):
    goal: str
    ingredient: str
    ingredient_name_en: str
    rank_best: int
    rank_worst: int
    population: int
    signal_types: list[str]
    label_regions: list[str]
    labels_with_effect: int | None
    labels_total: int | None
    label_terms: list[str]
    faers_reports: int | None
    faers_ror: float | None
    faers_ror_low: float | None
    faers_ror_high: float | None
    patient_reported_released: int | None
    source_ids: list[str]


class ExportOut(Common):
    licence: str
    rows: list[ExportRowOut]
    goals: list[GoalSummaryOut]
