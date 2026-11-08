"""Séance request and response models: the data contract of the séance view (séance design §7).

Responses carry data and fixed codes, no interface sentences: the web localises every label in
EN, TR, DE, FR and ES (Req 4.4). Ancient quotations stay in Arabic with an English machine
translation that is labelled as such. There is no score and no "proven" field (Req 2.2).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from janus.memory import messages

DISCLAIMER = messages.DISCLAIMER
SCHEMA_VERSION = "seance-1"

type ConditionName = Literal["wound", "burn", "ulcer", "infection"]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SeanceIn(_In):
    substance: Annotated[StrictStr, Field(pattern=r"^[a-z][a-z0-9_]{0,40}$")]
    condition: ConditionName


# --- substance ------------------------------------------------------------------------------


class GoldOut(_Out):
    gold_id: str
    scientific_name: str
    citation: str


class SubstanceOut(_Out):
    id: str
    name_en: str
    transliteration: str
    heading_ar: str
    kind: str
    identification: str
    identification_status: Literal["matches_gold", "uncertain", "not_in_gold"]
    # What the screen must show next to the name (Req 1.4, 4.1): "identified" only when the
    # identification matches the PMC3941892 gold table; otherwise "uncertain".
    identification_label: Literal["identified", "uncertain"]
    gold: GoldOut | None
    hamdard_ref: str | None  # cited only; no Hamdard text is ever returned
    hazard: Literal["toxic", "caustic"] | None
    note: str


# --- witnesses ------------------------------------------------------------------------------


class LocatorOut(_Out):
    entry_id: str
    span_id: str
    book: int
    page: str | None  # printed page of the edition behind the OpenITI text, e.g. "V01P474"
    line_start: int  # lines of the pinned OpenITI file
    line_end: int


class PastItemOut(_Out):
    claim_id: str
    locator: LocatorOut
    arabic_span: str
    translation: str
    translation_kind: Literal["machine_translation"]
    use_en: str  # Janus's short English summary (machine-written)
    ai_review: Literal["passed_both"]
    expert_review: Literal["pending", "reviewed"]
    headline_eligible: bool


class IntervalOut(_Out):
    low: float
    high: float
    level: float


class PresentItemOut(_Out):
    ingredient_key: str
    exposure_match: Literal["same", "component"]
    reports_with_both: int
    reports_with_ingredient: int
    ror: float
    ror_ci: IntervalOut
    region: Literal["ALL"]
    scope: Literal["suspect"]
    snapshot_date: str


class PresentObservedOut(_Out):
    """What was counted when the present witness was looked at (supporting or not)."""

    ingredient_key: str
    exposure_match: Literal["same", "component", "different"]
    reports_with_both: int
    reports_with_ingredient: int
    ror: float | None
    ror_ci: IntervalOut | None
    snapshot_date: str


class ScienceItemOut(_Out):
    evidence_id: str
    doi: str
    title: str
    study_type: Literal[
        "systematic_review", "rct", "clinical_other", "animal", "in_vitro", "narrative_review"
    ]
    finding_en: str
    integrity_status: Literal["ok", "corrected", "expression_of_concern", "unknown"]


Missing = Literal[
    "no_canon_passage",
    "passages_rejected_by_review",
    "no_faers_mapping",
    "exposure_differs",
    "counts_unavailable",
    "no_protective_association",
    "too_few_reports",
    "no_study_listed",
    "no_citable_study",
    "studies_do_not_support",
    "integrity_unavailable",
]


class PastOut(_Out):
    supports: bool
    confidence: Literal["none", "low", "moderate"]
    missing_reason: Missing | None
    items: list[PastItemOut]


class PresentOut(_Out):
    supports: bool
    confidence: Literal["none", "low", "moderate"]
    missing_reason: Missing | None
    items: list[PresentItemOut]
    observed: PresentObservedOut | None
    pts: list[str]  # MedDRA Preferred Terms counted for the condition
    codes: list[str]  # fixed caveat codes the screen must render (see design §7.4)


class ScienceOut(_Out):
    supports: bool
    confidence: Literal["none", "low", "moderate"]
    missing_reason: Missing | None
    items: list[ScienceItemOut]
    excluded: list[str]  # evidence ids removed by Evidence Integrity (e.g. retracted)


class WitnessesOut(_Out):
    past: PastOut
    present: PresentOut
    science: ScienceOut


class HeadlineOut(_Out):
    eligible: bool
    reasons: list[str]  # codes; empty when eligible


class SourceOut(_Out):
    id: str
    citation: str
    license: str


class SeanceOut(_Out):
    schema_version: Literal["seance-1"] = SCHEMA_VERSION
    substance: SubstanceOut
    condition: ConditionName
    witnesses: WitnessesOut
    supporting_witnesses: Annotated[int, Field(ge=0, le=3)]
    missing_witnesses: list[Literal["past", "present", "science"]]
    framing: Literal["hypothesis_not_treatment"] = "hypothesis_not_treatment"
    headline: HeadlineOut
    sources: list[SourceOut]
    disclaimer: str = DISCLAIMER


class PairSummaryOut(_Out):
    substance: str
    condition: ConditionName
    past_passages: int
    science_studies: int
    present_link: Literal["same", "component", "different", "none"]
    # The FAERS ingredient key of the present link (null for "none"), so that a researcher screen
    # can cross-reference the séance from a hypothesis card of the same ingredient.
    present_ingredient_key: str | None


class CatalogueOut(_Out):
    schema_version: Literal["seance-1"] = SCHEMA_VERSION
    substances: list[SubstanceOut]
    pairs: list[PairSummaryOut]
    sources: list[SourceOut]
    disclaimer: str = DISCLAIMER
