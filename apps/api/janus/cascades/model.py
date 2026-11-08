"""Rule-base types of the cascade engine (cascade-engine design §3.4). Pure, frozen.

The rule base is built once per version from the curated files under `data/` and never
changes afterwards. Engine input and result types join this module in task 6.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["index", "marker"]
MatchKind = Literal["include", "exclude"]
Scope = Literal["pipc", "form_extension"]
Basis = Literal["whocc_lookup", "titck_observed", "wikidata", "pharmacology"]
UnmatchableReason = Literal["no_atc_code", "not_a_drug_class", "ambiguous_text"]
Measure = Literal["incidence", "adjusted_sequence_ratio"]
Unit = Literal["percent", "ratio"]

ROLES: tuple[Role, ...] = ("index", "marker")
MATCH_KINDS: tuple[MatchKind, ...] = ("include", "exclude")
SCOPES: tuple[Scope, ...] = ("pipc", "form_extension")
BASES: tuple[Basis, ...] = ("whocc_lookup", "titck_observed", "wikidata", "pharmacology")
UNMATCHABLE_REASONS: tuple[UnmatchableReason, ...] = (
    "no_atc_code",
    "not_a_drug_class",
    "ambiguous_text",
)
MEASURE_UNITS: Mapping[Measure, Unit] = {
    "incidence": "percent",
    "adjusted_sequence_ratio": "ratio",
}
# The six groups that medical-safety.md rule 4 names; the abrupt-stop list must cover them.
REQUIRED_ABRUPT_GROUPS: tuple[str, ...] = (
    "antidepressant",
    "antiepileptic",
    "benzodiazepine",
    "beta_blocker",
    "clonidine",
    "corticosteroid",
)

PIPC_COUNT = 65
PIPC_SCHEMA_VERSION = "pipc-1"  # schema of the pipeline rows behind data/pipc.csv
SOURCE_PAPER_ID = "dataset:pipc"
WINDOW_EVIDENCE_ID = "paper:hendrix_2024:s12874_023_02108_y"
DEFAULT_WINDOW_MONTHS = 12
WINDOW_RANGE = (1, 60)
# Bump when matching, timing, merging or result rules change (part of the rule base version).
ENGINE_RULES_VERSION = "cascade-engine-1"


@dataclass(frozen=True)
class Pattern:
    prefix: str
    match: MatchKind
    scope: Scope = "pipc"
    evidence_id: str | None = None  # form extensions only
    basis: Basis | None = None
    note: str = ""


@dataclass(frozen=True)
class AtcClass:
    class_id: str
    patterns: tuple[Pattern, ...]  # sorted by prefix, prefixes unique

    @property
    def extension_ids(self) -> frozenset[str]:
        return frozenset(p.evidence_id for p in self.patterns if p.evidence_id is not None)


@dataclass(frozen=True)
class Priority:
    evidence_id: str
    measure: Measure
    value: str  # decimal text as published, e.g. "11.9"
    ci_low: str
    ci_high: str
    unit: Unit
    locator: str
    note: str = ""


@dataclass(frozen=True)
class Rule:
    position: int
    system: str
    kind: str
    drug_a: str
    adverse_event: str
    drug_b: str
    locator: str
    index_class: str | None
    marker_class: str | None
    unmatchable: tuple[Role, UnmatchableReason] | None
    supporting: tuple[str, ...]
    priority: Priority | None
    note: str = ""

    @property
    def rule_id(self) -> str:
        return f"pipc:{self.position}"

    @property
    def evidence_id(self) -> str:
        return f"rule:pipc:{self.position}"

    @property
    def matchable(self) -> bool:
        return self.unmatchable is None


@dataclass(frozen=True)
class AbruptGroup:
    prefix: str
    group: str


@dataclass(frozen=True)
class RuleBase:
    window_months: int
    rules: tuple[Rule, ...]  # 65, by position
    classes: Mapping[str, AtcClass]
    abrupt_stop: AtcClass
    abrupt_groups: tuple[AbruptGroup, ...]
    version: str
    source_paper_id: str = SOURCE_PAPER_ID
    window_evidence_id: str = WINDOW_EVIDENCE_ID
    engine_version: str = ENGINE_RULES_VERSION
    # PIPC position -> Janus event key of `collective-memory` (active keys only; empty by default).
    # A finding of such a rule also cites the FAERS snapshot with a locator (cascade-engine DP22).
    faers_event_keys: Mapping[int, str] = field(default_factory=dict[int, str])


# --- Engine input and result (design §4) ---------------------------------------------------

Month = int  # year * 12 + (month - 1)
Status = Literal["probable", "possible"]
Timing = Literal["within_window", "date_unknown", "same_month", "after_window"]
TIMING_ORDER: tuple[Timing, ...] = ("within_window", "date_unknown", "same_month", "after_window")
NotCheckedReason = Literal[
    "homeopathic_product",
    "ambiguous",
    "no_ingredient_key",
    "possible_unsplit_combination",
    "no_ingredient_atc",
    "no_ingredient_atc_for_route",
]
StatementCode = Literal["no_pattern_found", "rule_base_unavailable"]

NO_PATTERN_TEXT = (
    "Janus found no pattern from its rule list. "
    "This does not mean your medicines are free of problems."
)
RULE_BASE_UNAVAILABLE_TEXT = "Janus could not check its rule list."
ABRUPT_STOP_CODE = "do_not_stop_suddenly"
ABRUPT_STOP_TEXT = "Do not stop this medicine suddenly."
PATTERN_CODE = "matches_published_pattern"
CHAINS_TRUNCATED = "chains_truncated"


@dataclass(frozen=True)
class EngineIngredient:
    key: str  # Wikidata QID
    codes: frozenset[str]  # ingredient-level ATC codes (rule input)
    form_confirmed: bool
    label_en: str | None = None


@dataclass(frozen=True)
class EngineItem:
    index: int  # position in the request
    start: Month | None
    ingredients: tuple[EngineIngredient, ...]


@dataclass(frozen=True)
class NotChecked:
    item: int
    position: int
    reason: NotCheckedReason


@dataclass(frozen=True)
class Exposure:
    """One ingredient key's copies that match one class (design §4.3)."""

    key: str
    items: frozenset[int]
    start: Month | None
    form_confirmed: bool
    via_extension: bool
    matched_codes: tuple[str, ...]
    label_en: str | None


@dataclass(frozen=True)
class TimingResult:
    status: Status
    timing: Timing
    months_between: int | None
    low_priority: bool


@dataclass(frozen=True)
class Side:
    key: str
    label_en: str | None
    items: tuple[int, ...]
    matched_codes: tuple[str, ...]
    form_confirmed: bool
    via_form_extension: bool
    start: Month | None


@dataclass(frozen=True)
class Finding:
    finding_id: str
    rule: Rule
    index: Side
    marker: Side
    status: Status
    timing: Timing
    months_between: int | None
    low_priority: bool
    form_confirmed: bool
    via_form_extension: bool
    priority: Priority | None
    abrupt_stop: tuple[Role, ...]
    evidence_ids: tuple[str, ...]
    excluded_evidence: tuple[tuple[str, str], ...]
    integrity_codes: tuple[str, ...]
    faers_locator: str | None = None


@dataclass(frozen=True)
class ChainLink:
    index_key: str
    marker_key: str
    finding_ids: tuple[str, ...]


@dataclass(frozen=True)
class Chain:
    chain_id: str
    ingredient_keys: tuple[str, ...]
    links: tuple[ChainLink, ...]
    status: Status


@dataclass(frozen=True)
class SameProduct:
    rule_id: str
    index_key: str
    marker_key: str
    items: tuple[int, ...]


@dataclass(frozen=True)
class ItemWarning:
    item: int
    ingredient_key: str
    code: str = ABRUPT_STOP_CODE
    text: str = ABRUPT_STOP_TEXT


@dataclass(frozen=True)
class RemovedSource:
    id: str
    reason: str
    notice_types: tuple[str, ...]
    notice_dois: tuple[str, ...]


@dataclass(frozen=True)
class DisabledRule:
    rule_id: str
    reason: str
    removed: tuple[RemovedSource, ...]


@dataclass(frozen=True)
class NotMatchable:
    rule_id: str
    role: str
    reason: str


@dataclass(frozen=True)
class Statement:
    code: StatementCode
    text: str


@dataclass(frozen=True)
class EngineResult:
    findings: tuple[Finding, ...]
    chains: tuple[Chain, ...]
    same_product: tuple[SameProduct, ...]
    item_warnings: tuple[ItemWarning, ...]
    not_checked: tuple[NotChecked, ...]
    rules_total: int
    rules_checked: int
    disabled: tuple[DisabledRule, ...]
    not_matchable: tuple[NotMatchable, ...]
    statement: Statement | None
    notices: tuple[str, ...]
