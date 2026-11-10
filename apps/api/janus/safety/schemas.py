"""Response models of `POST /safety/check` (safety-check design §7). The request is the body
of `POST /cascades/evaluate` (`janus.cascades.schemas.EvaluateIn`).

The answer carries keys, codes and counts; its only sentences are the fixed statements below,
quotations of a source and the disclaimer. Nothing in it grades a risk or tells a person what
to do.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from janus.cascades.schemas import DISCLAIMER, NotCheckedOut
from janus.resolution.model import SourceRef

NO_DUPLICATION = (
    "Janus found no active ingredient twice on this list and no two ingredients of the same "
    "ATC chemical subgroup. This does not mean your medicines are free of problems."
)


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StatementOut(_Out):
    code: Literal["no_duplication_found"]
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


class SafetyCheckOut(_Out):
    dataset_version: str
    items: int
    ingredients_checked: int
    not_checked: list[NotCheckedOut]
    duplication: DuplicationOut
    disclaimer: str = DISCLAIMER
