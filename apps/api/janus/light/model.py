"""Types of the light-face core (light-face design §4 to §8). Pure: no I/O, no clock.

Counts are reports or labels, never people. Every output of this package is a candidate worth
investigating, never a treatment (medical-safety rule 7).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from janus.memory.stats import Sensitivity, Stats

LABEL_REGIONS: Final = ("US", "EU", "UK", "JP")
LANGS: Final = ("en", "tr", "de", "fr", "es")
GOAL_KEY_RE: Final = re.compile(r"[a-z][a-z0-9_]{1,40}")
CASE_ID_RE: Final = re.compile(r"[a-z][a-z0-9_]{1,60}")
SIGNAL_TYPES: Final = ("label_effect", "inverse_faers", "patient_reported")
ONSIDES_EVIDENCE_ID: Final = "dataset:onsides"
TOP_K: Final = 10
REVIEW_STATUS: Final = "automated_checks_pending_expert"

SignalType = Literal["label_effect", "inverse_faers", "patient_reported"]
MapStatus = Literal["active", "excluded"]
RunName = Literal["primary", "primary_indication", "primary_strict", "sensitivity"]
Reason = Literal["hit", "ranked_below_top", "not_a_candidate", "no_label_mapping", "not_evaluable"]
LightStatus = Literal["experimental", "prototype"]


@dataclass(frozen=True)
class Goal:
    key: str
    labels: Mapping[str, str]  # language -> name of the condition
    faers_pts: tuple[str, ...]  # sorted; empty = no inverse signal
    benefit_keys: tuple[str, ...]  # sorted Janus benefit keys
    note: str = ""


@dataclass(frozen=True)
class MappingRow:
    term: str  # OnSIDES term name as published (MedDRA PT or LLT)
    goal: str
    status: MapStatus
    evidence: tuple[str, ...]  # paper evidence ids
    rationale: str
    nonspecific: bool = False  # also a common sign of illness or toxicity (pharmacologist F4)


@dataclass(frozen=True)
class Case:
    id: str
    ingredient_name: str
    ingredient_key: str
    goal: str
    original_use: str
    later_year: int
    indication_terms: tuple[str, ...]
    evidence: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class Curated:
    goals: Mapping[str, Goal]
    mapping: tuple[MappingRow, ...]
    cases: tuple[Case, ...]

    def active_terms(self) -> dict[str, MappingRow]:
        return {m.term: m for m in self.mapping if m.status == "active"}


@dataclass(frozen=True)
class Label:
    """One OnSIDES label, reduced to what the light face reads.

    `ingredients` are OnSIDES ingredient ids (RxNorm or OMOP); `effects` are (term, section)
    pairs of the label, already restricted by the caller to any subset that contains the mapped
    terms.
    `set_id` is the DailyMed set id for US labels, else "".
    """

    label_id: int
    source: str
    set_id: str
    ingredients: tuple[str, ...]
    effects: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class LabelSignal:
    key: str
    goal: str
    regions: tuple[str, ...]  # subset of LABEL_REGIONS, in that order
    labels_with_effect: int
    labels_total: int
    sections: tuple[str, ...]
    terms: tuple[str, ...]
    evidence: tuple[str, ...]  # dataset:onsides first, then the mapping papers (sorted)
    nonspecific: bool = False  # every matched term is a nonspecific one


@dataclass(frozen=True)
class InverseSignal:
    key: str
    goal: str
    stats: Stats
    sensitivity: Sensitivity
    pts: tuple[str, ...]


@dataclass(frozen=True)
class Rank:
    best: int
    worst: int
    population: int


@dataclass(frozen=True)
class Candidate:
    key: str
    goal: str
    label: LabelSignal | None
    inverse: InverseSignal | None
    rank: Rank

    @property
    def signal_types(self) -> tuple[SignalType, ...]:
        out: list[SignalType] = []
        if self.label is not None:
            out.append("label_effect")
        if self.inverse is not None:
            out.append("inverse_faers")
        return tuple(out)


@dataclass(frozen=True)
class CaseRun:
    run: RunName
    rank: Rank | None
    population: int
    hit: bool
    informative: bool
    labels_used: int
    labels_removed_indication: int
    labels_removed_not_in_openfda: int
    signal_types: tuple[SignalType, ...]
    reason: Reason
    chance_hit: float | None  # TOP_K / population: a random candidate's chance of a hit
    percentile: float | None  # worst rank / population


@dataclass(frozen=True)
class CaseFaers:
    """FAERS numbers of (case drug, goal PT set); the window includes the later use."""

    stats: Stats
    sensitivity: Sensitivity
    inverse: bool


@dataclass(frozen=True)
class CaseResult:
    case: Case
    primary: CaseRun  # the worse of the two primary variants
    primary_indication: CaseRun
    primary_strict: CaseRun
    sensitivity: CaseRun
    faers: CaseFaers | None


@dataclass(frozen=True)
class RunSummary:
    hits: int
    informative_hits: int
    misses: int
    not_evaluable: int
    expected_hits_by_chance: float  # sum of chance_hit over informative ranked cases


@dataclass(frozen=True)
class Validation:
    top_k: int
    results: tuple[CaseResult, ...]
    primary: RunSummary
    sensitivity: RunSummary
    status: LightStatus
    notes: tuple[str, ...] = field(default=())
