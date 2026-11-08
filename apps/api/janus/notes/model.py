"""Note document model (doctor-loop design §4.3) and the pure inputs of the builder. Pure.

The document is what the API returns and what the browser lays out; the product name as on the box
is only a slot the browser fills (`product_name_slot`). Ids of sections, blocks and sentences do not
depend on the language, so two languages of one note can be compared field by field (P12).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from janus.cascades.schemas import CascadeResult
from janus.integrity.line import IntegrityLine

NOTE_FORMAT: Final = "janus-note-1"
SECTION_ORDER: Final = (
    "header",
    "safety",
    "medicines",
    "findings",
    "findings_form_unconfirmed",
    "chains",
    "statistics",
    "scope",
    "integrity",
    "outcome_loop",
    "about",
)
RemovalReason = Literal[
    "no_evidence", "evidence_not_citable", "forbidden_phrase", "reassurance_word", "foreign_number"
]
NameBasis = Literal["glossary", "english_fallback", "not_reviewed", "code_only"]


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Text(_Out):
    template: str
    text: str


class Sentence(_Out):
    type: Literal["sentence"] = "sentence"
    id: str
    template: str
    kind: Literal["claim", "fixed"]
    text: str
    evidence_ids: list[str]
    numbers: list[str]


class IngredientOut(_Out):
    key: str
    name: Text | None
    name_basis: NameBasis
    tag: Text | None  # "name not translated" / "name not reviewed"
    atc: list[str]


class NotCheckedRow(_Out):
    position: int
    reason: str
    text: Text


class MedicineRow(_Out):
    type: Literal["medicine"] = "medicine"
    item: int
    product_name_slot: Literal[True] = True
    product_label: Text
    ingredients: list[IngredientOut]
    not_checked: list[NotCheckedRow]
    started: Text
    abrupt_stop: Sentence | None


class EstimatesNote(_Out):
    ror: float
    low: float
    high: float


class CitationNote(_Out):
    evidence_id: Literal["dataset:faers"] = "dataset:faers"
    locator: str


class StatRow(_Out):
    type: Literal["stat"] = "stat"
    id: str
    finding_ids: list[str]
    region: str
    ingredient_key: str
    event_key: str
    reports: int | None  # None when the cell is shown as coverage only (a < 3)
    assessment: str
    estimates: EstimatesNote | None
    pts: Text | None
    citation: CitationNote
    sentences: list[Sentence]


Block = Annotated[Sentence | MedicineRow | StatRow, Field(discriminator="type")]


class Section(_Out):
    id: str
    heading: Text | None
    blocks: list[Block]


class NoteDocument(_Out):
    language: str
    sections: list[Section]


class VersionsOut(_Out):
    rule_base_version: str
    dataset_version: str
    integrity_version: str
    counts_build_id: str | None
    glossary_version: str


class Removal(_Out):
    sentence_id: str
    reason: RemovalReason


class NoteOut(_Out):
    note_format: Literal["janus-note-1"] = "janus-note-1"
    versions: VersionsOut
    as_of_month: str
    removals: list[Removal]
    documents: list[NoteDocument]


# --- builder inputs (pure) --------------------------------------------------------------------


@dataclass(frozen=True)
class ItemIngredient:
    key: str
    codes: tuple[str, ...]
    label_en: str | None


@dataclass(frozen=True)
class ItemInfo:
    item: int
    started: str | None
    ingredients: tuple[ItemIngredient, ...]


@dataclass(frozen=True)
class RoleIds:
    """Which evidence ids play which role (from the rule base the engine used)."""

    window: str
    supporting: Mapping[str, tuple[str, ...]]  # rule id -> supporting ids
    extension: frozenset[str]
    pipc: str = "dataset:pipc"
    faers: str = "dataset:faers"


@dataclass(frozen=True)
class StatInput:
    finding_ids: tuple[str, ...]
    region: str
    ingredient_key: str
    event_key: str
    reports: int
    assessment: str
    estimates: tuple[float, float, float] | None  # ror, low, high
    codes: tuple[str, ...]
    locator: str
    pts: tuple[str, ...]


@dataclass(frozen=True)
class StatsContext:
    snapshot_date: dt.date
    first_quarter: str
    last_quarter: str
    share: Decimal  # percent of reports with a recognised medicine, one decimal
    stale: bool


@dataclass(frozen=True)
class NoteInputs:
    result: CascadeResult
    items: tuple[ItemInfo, ...]
    roles: RoleIds
    item_codes: Mapping[str, frozenset[str]]  # evidence id -> integrity item codes
    stats: tuple[StatInput, ...]
    stats_context: StatsContext | None  # None: counts file unavailable
    line: IntegrityLine
    versions: VersionsOut
    event_keys: Mapping[int, str]  # PIPC position -> Janus event key
    event_labels: Mapping[str, Mapping[str, str]]  # event key -> language -> label
    safety_lines: Mapping[str, str]  # event key -> safety line code
    user_region: str
    rule_texts: Mapping[int, tuple[str, str, str]]  # PIPC position -> English (A, event, B)
    qr: tuple[int, int] | None = None  # (findings covered, findings total) for token notes
