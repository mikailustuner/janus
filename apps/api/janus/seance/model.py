"""Séance model and three-witness synthesis (séance design §4, Req 2). Pure: no I/O.

Each witness is returned on its own with its own confidence. The number of supporting witnesses
(0-3) is a count, never a score: nothing here merges the witnesses into one strength value, and
there is no "proven" outcome (Req 2.2).

A witness supports the pair exactly when its section has at least one supporting item; the
items carry the evidence (a text locator, a report-count statistic, a paper id).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final, Literal

WITNESSES: Final = ("past", "present", "science")
CONDITIONS: Final = ("wound", "burn", "ulcer", "infection")

type WitnessName = Literal["past", "present", "science"]
type Confidence = Literal["none", "low", "moderate"]
type MissingReason = Literal[
    # past
    "no_canon_passage",
    "passages_rejected_by_review",
    # present
    "no_faers_mapping",
    "exposure_differs",
    "counts_unavailable",
    "no_protective_association",
    "too_few_reports",
    # science
    "no_study_listed",
    "no_citable_study",
    "studies_do_not_support",
    "integrity_unavailable",
]
type IdStatus = Literal["matches_gold", "uncertain", "not_in_gold"]


@dataclass(frozen=True)
class Locator:
    """Where an ancient claim sits in the OpenITI text (resolves to an entry of the package)."""

    entry_id: str
    span_id: str
    book: int
    page: str | None
    line_start: int
    line_end: int


@dataclass(frozen=True)
class PastItem:
    claim_id: str
    locator: Locator
    arabic_span: str
    machine_translation_en: str
    use_en: str
    ai_review: str  # "passed_both" (historian and pharmacologist AI passes)
    expert_review: str  # "pending" until the experts review it
    headline_eligible: bool


@dataclass(frozen=True)
class Interval:
    low: float
    high: float


@dataclass(frozen=True)
class PresentItem:
    """One FAERS 2x2 result for (ingredient key, the condition's PT group). Reports, not people."""

    ingredient_key: str
    exposure_match: Literal["same", "component"]
    a: int  # reports with the ingredient and the event
    exposure: int
    ror: float
    ror_ci: Interval
    snapshot_date: str


@dataclass(frozen=True)
class ScienceItem:
    evidence_id: str
    doi: str
    title: str
    study_type: str
    finding_en: str
    integrity_status: str  # ok | corrected | expression_of_concern | unknown (never retracted)


type Item = PastItem | PresentItem | ScienceItem


@dataclass(frozen=True)
class Witness:
    name: WitnessName
    items: tuple[Item, ...]  # supporting items only
    confidence: Confidence
    missing: MissingReason | None  # why the witness does not support, when it does not
    context: tuple[str, ...] = ()  # fixed codes for what was looked at but not counted

    @property
    def supports(self) -> bool:
        return bool(self.items)

    def __post_init__(self) -> None:
        if self.items and self.missing is not None:
            raise ValueError("a supporting witness has no missing reason")
        if not self.items and self.missing is None:
            raise ValueError("a silent witness needs a missing reason")
        if not self.items and self.confidence != "none":
            raise ValueError("a silent witness has no confidence")
        if self.items and self.confidence == "none":
            raise ValueError("a supporting witness needs a confidence")


@dataclass(frozen=True)
class Seance:
    substance_id: str
    condition: str
    past: Witness
    present: Witness
    science: Witness
    supporting: int = field(init=False)
    missing: tuple[WitnessName, ...] = field(init=False)

    def __post_init__(self) -> None:
        ws = (self.past, self.present, self.science)
        if tuple(w.name for w in ws) != WITNESSES:
            raise ValueError("witnesses out of order")
        object.__setattr__(self, "supporting", sum(1 for w in ws if w.supports))
        object.__setattr__(self, "missing", tuple(w.name for w in ws if not w.supports))


def silent(name: WitnessName, reason: MissingReason, context: Sequence[str] = ()) -> Witness:
    return Witness(name, (), "none", reason, tuple(context))


def synthesize(
    substance_id: str, condition: str, past: Witness, present: Witness, science: Witness
) -> Seance:
    """Put the three witnesses at one table. Count only; no merging (Req 2.1-2.3)."""
    return Seance(substance_id, condition, past, present, science)
