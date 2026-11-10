"""Response models of `POST /safety/check` (safety-check design §7). The request is the body
of `POST /cascades/evaluate` (`janus.cascades.schemas.EvaluateIn`).

The answer carries keys, codes and counts; its only sentences are the fixed statements below,
quotations of a source and the disclaimer. Nothing in it grades a risk or tells a person what
to do.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict

from janus.cascades.schemas import DISCLAIMER, NotCheckedOut
from janus.resolution.model import SourceRef

NO_DUPLICATION = (
    "Janus found no active ingredient twice on this list and no two ingredients of the same "
    "ATC chemical subgroup. This does not mean your medicines are free of problems."
)


NO_LABEL_PASSAGE = (
    'Janus read the "Drug Interactions" section of the US labels listed here and found no '
    "passage that names another ingredient on this list. This does not mean that these "
    "medicines do not affect each other."
)
LABEL_SOURCE_URL = "https://open.fda.gov/apis/drug/label/"
LABEL_TERMS_URL = "https://open.fda.gov/terms/"
DAILYMED_LABEL_URL = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={}"


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StatementOut(_Out):
    code: Literal["no_duplication_found", "no_label_passage_found"]
    text: str


class MemberOut(_Out):
    ingredient_key: str
    label_en: str | None
    items: list[int]
    codes: list[str]
    form_confirmed: bool


class DuplicationFindingOut(_Out):
    finding_id: str
    kind: Literal["same_ingredient", "same_group"]
    atc_group: str | None  # the ATC chemical subgroup of a same_group finding
    members: list[MemberOut]
    items: list[int]
    form_confirmed: bool


class DuplicationOut(_Out):
    status: Literal["checked"] = "checked"
    rules_version: str
    atc_level: Literal[4] = 4
    findings: list[DuplicationFindingOut]
    sources: list[SourceRef]
    statement: StatementOut | None
    notices: list[
        Literal["between_list_items_only", "residual_groups_not_compared", "may_be_intended"]
    ]


class LabelSourceOut(_Out):
    source_id: Literal["openfda_label_interactions"]
    run_id: str
    snapshot_date: dt.date
    license: str
    url: str
    terms_url: str
    labels: int  # label sections Janus holds (one per active substance)


class LabelOut(_Out):
    substance_name: str  # as published on the label
    set_id: str
    version: str | None
    effective_date: dt.date | None
    product_type: str | None
    url: str  # the label at DailyMed


class IngredientRefOut(_Out):
    ingredient_key: str
    label_en: str | None
    items: list[int]


class LabelReadOut(IngredientRefOut):
    label: LabelOut


class PassageOut(_Out):
    text: str  # quoted from the label, as published
    cut_start: bool
    cut_end: bool


class InteractionFindingOut(_Out):
    finding_id: str
    label_of: IngredientRefOut  # the ingredient whose label is quoted
    names: IngredientRefOut  # the ingredient the passage names
    matched_name: str
    label: LabelOut
    passages: list[PassageOut]
    total_passages: int
    codes: list[Literal["label_text_names_ingredient"]] = ["label_text_names_ingredient"]


InteractionNotice = Literal[
    "us_labels_only",
    "one_label_per_substance",
    "quoted_label_text_not_an_assessment",
    "names_matched_automatically",
    "passage_may_state_no_effect",
    "classes_not_matched",
    "absence_is_not_clearance",
    "snapshot_outdated",
]


class InteractionsOut(_Out):
    status: Literal["checked", "unavailable"]
    rules_version: str
    source: LabelSourceOut | None
    findings: list[InteractionFindingOut]
    total_findings: int
    truncated: bool
    labels_read: list[LabelReadOut]
    labels_not_found: list[IngredientRefOut]
    statement: StatementOut | None
    notices: list[InteractionNotice]


class BurdenDrugOut(_Out):
    published_name: str  # as printed in the paper
    locator: str  # table of the paper


class BurdenContributionOut(_Out):
    ingredient_key: str
    label_en: str | None
    items: list[int]
    score: int  # as published
    drug: BurdenDrugOut


class BurdenScaleOut(_Out):
    scale_id: Literal["kiesel2018", "crideco2022", "brazil2019"]
    title: str
    citation: str
    url: str  # the paper
    license: str
    license_url: str
    drugs_listed: int  # drugs the scale lists
    drugs_matched: int  # of those, drugs Janus can match to an ingredient key
    contributions: list[BurdenContributionOut]
    total: int  # sum of the published scores of the contributions shown


BurdenNotice = Literal[
    "published_scores_only",
    "scales_not_comparable",
    "no_threshold",
    "list_not_complete",
    "absence_is_not_clearance",
]


class BurdenOut(_Out):
    status: Literal["checked"]
    rules_version: str
    scales: list[BurdenScaleOut]
    notices: list[BurdenNotice]


class SafetyCheckOut(_Out):
    dataset_version: str
    items: int
    ingredients_checked: int
    not_checked: list[NotCheckedOut]
    duplication: DuplicationOut
    interactions: InteractionsOut
    burden: BurdenOut
    disclaimer: str = DISCLAIMER
