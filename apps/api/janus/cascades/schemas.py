"""Request and response models of `POST /cascades/evaluate` (cascade-engine design §3.6).

Requests are strict and reject unknown keys; the client never sends ATC codes. Responses carry
codes and data; the only sentences are the published PIPC text, the fixed statements, the
abrupt-stop sentence and the disclaimer.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

DISCLAIMER = (
    "Janus provides information, not medical advice. Research prototype - not a medical device."
)
MAX_ITEMS = 50
QID = r"^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$"  # Wikidata QID or Janus curated key
CANDIDATE = r"^(TR|US):[a-z_]+:[0-9]{1,9}$"
MONTH = r"^\d{4}-(0[1-9]|1[0-2])$"


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ChoiceIn(_In):
    position: Annotated[StrictInt, Field(ge=0, le=MAX_ITEMS - 1)]  # resolution positions start at 0
    ingredient: Annotated[StrictStr, Field(pattern=QID)]


class ItemIn(_In):
    product: Annotated[StrictStr, Field(pattern=CANDIDATE)] | None = None
    ingredient: Annotated[StrictStr, Field(pattern=QID)] | None = None
    choices: Annotated[list[ChoiceIn], Field(min_length=1, max_length=10)] | None = None
    started: Annotated[StrictStr, Field(pattern=MONTH)] | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> ItemIn:
        if (self.product is None) == (self.ingredient is None):
            raise ValueError("exactly one of product and ingredient")
        if self.choices is not None:
            if self.product is None:
                raise ValueError("choices need a product")
            if len({c.position for c in self.choices}) != len(self.choices):
                raise ValueError("one choice per position")
        return self


class EvaluateIn(_In):
    dataset_version: Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
    items: Annotated[list[ItemIn], Field(min_length=1, max_length=MAX_ITEMS)]


# --- Response ----------------------------------------------------------------------------------


class RuleTextOut(_Out):
    system: str
    kind: str
    drug_a: str
    adverse_event: str
    drug_b: str
    locator: str


class SideOut(_Out):
    ingredient_key: str
    label_en: str | None
    items: list[int]
    matched_codes: list[str]
    form_confirmed: bool
    start: str | None


class IndexSideOut(SideOut):
    via_form_extension: bool


class PriorityOut(_Out):
    source: Literal["bmj_2026_abstract"] = "bmj_2026_abstract"
    measure: Literal["incidence", "adjusted_sequence_ratio"]
    value: str
    ci_low: str
    ci_high: str
    unit: Literal["percent", "ratio"]
    locator: str
    evidence_id: str


class ExcludedOut(_Out):
    id: str
    reason: str


class FindingOut(_Out):
    finding_id: str
    rule_id: str
    rule_evidence_id: str
    rule_text: RuleTextOut
    index: IndexSideOut
    marker: SideOut
    status: Literal["probable", "possible"]
    timing: Literal["within_window", "date_unknown", "same_month", "after_window"]
    months_between: int | None
    low_priority: bool
    form_confirmed: bool
    via_form_extension: bool
    priority: PriorityOut | None
    abrupt_stop: list[Literal["index", "marker"]]
    evidence_ids: list[str]
    excluded_evidence: list[ExcludedOut]
    integrity_codes: list[str]
    faers_locator: str | None = None
    codes: list[Literal["matches_published_pattern"]] = ["matches_published_pattern"]


class LinkOut(_Out):
    index_key: str
    marker_key: str
    finding_ids: list[str]


class ChainOut(_Out):
    chain_id: str
    ingredient_keys: list[str]
    links: list[LinkOut]
    status: Literal["probable", "possible"]


class SameProductOut(_Out):
    rule_id: str
    index_key: str
    marker_key: str
    items: list[int]


class ItemWarningOut(_Out):
    item: int
    ingredient_key: str
    code: Literal["do_not_stop_suddenly"]
    text: str


class NotCheckedOut(_Out):
    item: int
    position: int
    reason: Literal[
        "homeopathic_product",
        "ambiguous",
        "no_ingredient_key",
        "possible_unsplit_combination",
        "no_ingredient_atc",
        "no_ingredient_atc_for_route",
    ]


class RemovedOut(_Out):
    id: str
    reason: str
    notice_types: list[str]
    notice_dois: list[str]


class DisabledOut(_Out):
    rule_id: str
    reason: Literal["no_source", "all_sources_retracted", "no_citable_source"]
    removed: list[RemovedOut]


class NotMatchableOut(_Out):
    rule_id: str
    role: Literal["index", "marker", "both"]
    reason: Literal["no_atc_code", "not_a_drug_class", "ambiguous_text"]


class RulesOut(_Out):
    total: int
    checked: int
    disabled: list[DisabledOut]
    not_matchable: list[NotMatchableOut]


class StatementOut(_Out):
    code: Literal["no_pattern_found", "rule_base_unavailable"]
    text: str


class CascadeResult(_Out):
    rule_base_version: str
    dataset_version: str
    integrity_version: str
    as_of_month: str
    window_months: int
    findings: list[FindingOut]
    chains: list[ChainOut]
    same_product: list[SameProductOut]
    item_warnings: list[ItemWarningOut]
    not_checked: list[NotCheckedOut]
    rules: RulesOut
    statement: StatementOut | None
    notices: list[Literal["chains_truncated"]]
    disclaimer: str = DISCLAIMER
