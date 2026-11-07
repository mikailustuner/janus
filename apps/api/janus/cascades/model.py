"""Rule-base types of the cascade engine (cascade-engine design §3.4). Pure, frozen.

The rule base is built once per version from the curated files under `data/` and never
changes afterwards. Engine input and result types join this module in task 6.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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
