"""Request and response models of the `/memory` routes (collective-memory design §5)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from janus.memory.model import (
    EVENT_KEY_PATTERN,
    INGREDIENT_KEY_PATTERN,
    MAX_INGREDIENTS,
    MAX_PT_LENGTH,
    Assessment,
    Level,
)

type RegionName = Literal["ALL", "TR", "EU", "US", "OTHER", "UNKNOWN"]
type ScopeName = Literal["suspect", "any"]

Key = Annotated[str, StringConstraints(pattern=INGREDIENT_KEY_PATTERN)]
EventKeyStr = Annotated[str, StringConstraints(pattern=EVENT_KEY_PATTERN)]
PtStr = Annotated[str, StringConstraints(min_length=1, max_length=MAX_PT_LENGTH)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _distinct(values: list[str]) -> list[str]:
    if len(set(values)) != len(values):
        raise ValueError("duplicate ingredient")
    return values


# --- requests ------------------------------------------------------------------------------


class EventRefIn(_In):
    pt: PtStr | None = None
    key: EventKeyStr | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> EventRefIn:
        if (self.pt is None) == (self.key is None):
            raise ValueError("exactly one of pt and key")
        return self


class PairIn(_In):
    ingredient: Key
    event: EventRefIn
    region: RegionName = "ALL"
    scope: ScopeName = "suspect"


class CombinationIn(_In):
    ingredients: Annotated[list[Key], Field(min_length=2, max_length=MAX_INGREDIENTS)]
    region: RegionName = "ALL"
    scope: ScopeName = "any"
    top_events: Annotated[int, Field(ge=1, le=50)] = 20

    @model_validator(mode="after")
    def _distinct_keys(self) -> CombinationIn:
        _distinct(self.ingredients)
        return self


class RegionsIn(_In):
    ingredients: Annotated[list[Key], Field(min_length=1, max_length=MAX_INGREDIENTS)]
    event: EventRefIn | None = None
    scope: ScopeName | None = None

    @model_validator(mode="after")
    def _distinct_keys(self) -> RegionsIn:
        _distinct(self.ingredients)
        return self


class SharedIn(_In):
    layer: Literal["contributions", "outcomes"]
    ingredients: Annotated[list[Key], Field(min_length=1, max_length=MAX_INGREDIENTS)]
    event: EventKeyStr
    direction: Literal["adverse", "benefit"]

    @model_validator(mode="after")
    def _distinct_keys(self) -> SharedIn:
        _distinct(self.ingredients)
        return self


# --- responses: FAERS ----------------------------------------------------------------------


class SnapshotPart(_Out):
    build_id: str
    snapshot_date: str
    window: list[str]
    faers_run_id: str
    resolution_dataset_version: str
    served_resolution_dataset_version: str | None
    counts_match_served: bool | None
    stale: bool
    age_days: int


class CitationOut(_Out):
    evidence_id: Literal["dataset:faers"]
    locator: str


class CellsOut(_Out):
    a: int
    b: int
    c: int
    d: int
    n: int


class IntervalOut(_Out):
    low: float
    high: float
    level: float
    method: str


class EstimatesOut(_Out):
    prr: float
    ror: float
    ror_ci: IntervalOut
    chi2: float
    chi2_form: str


class SensitivityOut(_Out):
    cells: CellsOut
    haldane_applied: bool
    estimates: EstimatesOut | None
    assessment: Assessment
    differs: bool


class StatsOut(_Out):
    region: RegionName
    scope: ScopeName
    cells: CellsOut
    haldane_applied: bool
    estimates: EstimatesOut | None
    evans_met: bool
    ror_signal: bool
    assessment: Assessment
    sensitivity: SensitivityOut
    denominator_sensitive: bool
    codes: list[str]


class EventOut(_Out):
    pt: str | None
    key: str | None
    pts: list[str]
    reported_in_window: bool
    safety_line: str | None


class FaersCommon(_Out):
    layer: Literal["faers"] = "faers"
    snapshot: SnapshotPart
    notices: list[str]
    disclaimer: str
    attribution: str
    meddra_notice: str | None


class PairOut(FaersCommon):
    status: Literal["ok", "not_available"]
    ingredient: str
    event: EventOut
    stats: StatsOut | None
    citation: CitationOut | None


class MemberAloneOut(_Out):
    key: str
    reports: int


class EventStatsOut(_Out):
    pt: str
    reports: int
    stats: StatsOut
    safety_line: str | None
    members_alone: list[MemberAloneOut]
    citation: CitationOut


class PairGroupOut(_Out):
    keys: list[str]
    reports: int
    citation: CitationOut
    events_omitted: bool  # events are listed for the pairs with the most reports only
    events: list[EventStatsOut]


class SingleGroupOut(_Out):
    key: str
    reports: int
    citation: CitationOut
    events: list[EventStatsOut]


class IngredientCountOut(_Out):
    key: str
    reports: int
    citation: CitationOut
    assessment: Literal["no_reports", "ok"]


class SkippedOut(_Out):
    level: Level
    reason: str


class CombinationCountOut(_Out):
    reports: int
    n: int


class CombinationOut(FaersCommon):
    region: RegionName
    scope: ScopeName
    level: Level
    exposure: Literal["all_of_set"] = "all_of_set"
    comparison: Literal["all_other_mapped_reports"] = "all_other_mapped_reports"
    skipped: list[SkippedOut]
    ingredients: list[IngredientCountOut]
    combination: CombinationCountOut
    citation: CitationOut
    events: list[EventStatsOut]
    pairs: list[PairGroupOut]
    singles: list[SingleGroupOut]


class RegionRowOut(_Out):
    region: RegionName
    n_primary: int
    n_all: int
    reports: int
    stats: StatsOut | None
    citation: CitationOut | None


class UnknownShareOut(_Out):
    reports: int
    share: float


class BasisOut(_Out):
    region: RegionName
    occurrence: int
    reporter_fallback: int


class RegionsOut(FaersCommon):
    scope: ScopeName
    event: EventOut | None
    rows: list[RegionRowOut]
    unknown: UnknownShareOut
    basis: list[BasisOut]
    adrreports_url: str


class TotalsOut(_Out):
    region: RegionName
    reports_mapped: int
    reports_all: int


class SnapshotOut(_Out):
    build_id: str
    snapshot_date: str
    window: list[str]
    faers_run_id: str
    resolution_dataset_version: str
    stale: bool
    age_days: int
    totals: list[TotalsOut]
    unknown_share: float
    layers: dict[str, str]
    notices: list[str]
    meddra_notice: str
    attribution: str


# --- responses: user layers ----------------------------------------------------------------


class SharedCellOut(_Out):
    region: Literal["TR", "EU", "US"]
    status: Literal["released", "hidden"]
    value: int | None = None


class DisclosureOut(_Out):
    k: int
    epsilon: str
    wording: Literal["hidden_under_20_noise_added"] = "hidden_under_20_noise_added"


class SharedOut(_Out):
    layer: Literal["contributions", "outcomes"]
    status: Literal["ok", "layer_unavailable", "not_available"]
    cells: list[SharedCellOut]
    total_of_released: int | None
    disclosure: DisclosureOut
    disclaimer: str
    notices: list[str]
