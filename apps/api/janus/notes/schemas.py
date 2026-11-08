"""Request and response models of the note and outcome routes (doctor-loop design §4.1, §7, §9).

Requests are strict and reject unknown fields (so `"demo": true` is refused); every string field
is a pattern or a literal, so no free text can reach the server (P21).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

from janus.cascades.schemas import EvaluateIn
from janus.notes.model import NoteOut

HEX64 = r"^[0-9a-f]{64}$"
BUILD_ID = r"^[0-9A-Za-z_.-]{1,80}$"
TOKEN = r"^[A-Za-z0-9_-]{40,4096}$"  # noqa: S105 (a pattern, not a secret)
CONSENT = r"^[a-z0-9][a-z0-9.-]{0,31}$"
Language = Literal["en", "tr", "de", "fr", "es"]
UserRegion = Literal["US", "TR", "EU", "OTHER", "UNKNOWN"]
LoopRegion = Literal["TR", "EU", "US"]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PinsIn(_In):
    rule_base_version: Annotated[StrictStr, Field(pattern=HEX64)] | None = None
    integrity_version: Annotated[StrictStr, Field(pattern=HEX64)] | None = None
    counts_build_id: Annotated[StrictStr, Field(pattern=BUILD_ID)] | None = None


class NoteIn(_In):
    evaluation: EvaluateIn
    pins: PinsIn = PinsIn()
    languages: Annotated[list[Language], Field(min_length=1, max_length=2)]
    region: UserRegion
    statistics_region: LoopRegion | None = None

    @model_validator(mode="after")
    def _distinct(self) -> NoteIn:
        if len(set(self.languages)) != len(self.languages):
            raise ValueError("languages must be distinct")
        return self


class TokenIn(_In):
    note: NoteIn
    consent_version: Annotated[StrictStr, Field(pattern=CONSENT)]
    outcome_region: LoopRegion

    @model_validator(mode="after")
    def _one_language(self) -> TokenIn:
        if len(self.note.languages) != 1:
            raise ValueError("a token note has one language")
        return self


class TokenOut(_Out):
    token: str
    qr_url: str | None
    expires_on: str
    findings_covered: int
    findings_total: int
    note: NoteOut


class TokenBodyIn(_In):
    token: Annotated[StrictStr, Field(pattern=TOKEN)]


Assessment = Literal["confirmed", "not_a_cascade"]
Action = Literal["dose_changed", "medicine_changed", "stopped", "no_change"]
ACTIONS_WITH_MEDICINE = frozenset({"dose_changed", "medicine_changed", "stopped"})


class AnswerIn(_In):
    ref: Annotated[StrictInt, Field(ge=0, le=254)]
    assessment: Assessment
    action: Action | None = None
    action_on: Literal["index", "marker"] | None = None

    @model_validator(mode="after")
    def _action_rule(self) -> AnswerIn:
        if (self.action in ACTIONS_WITH_MEDICINE) != (self.action_on is not None):
            raise ValueError("action_on is required exactly for dose, medicine and stop actions")
        return self


class OutcomeIn(_In):
    token: Annotated[StrictStr, Field(pattern=TOKEN)]
    answers: Annotated[list[AnswerIn], Field(min_length=1, max_length=255)]

    @model_validator(mode="after")
    def _distinct_refs(self) -> OutcomeIn:
        if len({a.ref for a in self.answers}) != len(self.answers):
            raise ValueError("one answer per finding")
        return self


class NamedIngredient(_Out):
    key: str
    name: str
    name_basis: str
    tag: str | None
    atc: list[str]


class CascadeNames(_Out):
    drug_a: str
    adverse_event: str
    drug_b: str


class FormFinding(_Out):
    ref: int
    rule_id: str
    cascade: CascadeNames
    index: NamedIngredient
    marker: NamedIngredient
    form_confirmed: bool


class OptionOut(_Out):
    code: str
    text: str


class FormOptions(_Out):
    assessment: list[OptionOut]
    action: list[OptionOut]
    action_on: list[OptionOut]


class FormTexts(_Out):
    heading: str
    intro: str
    stored_fields: str
    limits: str
    question_assessment: str
    question_action: str
    disclaimer: str


class OutcomeFormOut(_Out):
    language: str
    expires_on: str
    findings: list[FormFinding]
    options: FormOptions
    texts: FormTexts


class OutcomeStoredOut(_Out):
    stored: int


class WithdrawnOut(_Out):
    status: Literal["withdrawn"] = "withdrawn"
