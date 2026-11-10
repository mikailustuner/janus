"""Request and response models of `POST /passport/presence` (medication-passport design §3).

The request holds ingredient keys, strength codes and dose-form groups only (Req 4.3, 9.1): no
product name, product code, candidate id, item region, date, free text or `demo` field
(`extra="forbid"`). The response holds codes and numbers only (Req 4.5); the client words them.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from janus.memory import messages

KEY = r"^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$"
AMOUNT = r"^(0|[1-9][0-9]{0,8})(\.[0-9]{0,5}[1-9])?$"
MAX_ITEMS = 50
MAX_INGREDIENTS = 10
MAX_KEYS = 50

# The closed set of `janus.passport.forms.GROUPS` (a test checks that both agree).
FormGroup = Literal[
    "oral_solid",
    "oral_solid_delayed_release",
    "oral_solid_prolonged_release",
    "oral_liquid",
    "injection",
    "inhaled",
    "nasal",
    "ophthalmic",
    "otic",
    "cutaneous",
    "transdermal",
    "rectal",
    "vaginal",
    "other",
]
Key = Annotated[str, StringConstraints(pattern=KEY)]
SourceId = Literal["titck", "eu_fr_bdpm", "eu_es_cima", "openfda_ndc"]
Status = Literal["present", "not_present", "not_in_source", "source_unavailable"]
Result = Literal["matched", "differs", "could_not_compare"]
CmpReason = Literal["not_known_for_item", "not_known_in_source", "not_all_comparable"]
Notice = Literal["presence_is_lower_bound", "unknown_ingredient_keys"]
# `POST /passport/products` (design §15). Sources whose licence allows showing product names.
ListableSourceId = Literal["eu_fr_bdpm", "eu_es_cima", "openfda_ndc"]
Level = Literal["same", "different", "unknown"]
LevelReason = Literal["not_known_for_item", "not_known_in_source"]
Marketed = Literal["listed_as_marketed", "listed_as_not_marketed", "not_stated"]
ListingNotice = Literal["listing_is_lower_bound", "unknown_ingredient_keys"]
MAX_PAGE = 100
MAX_OFFSET = 100_000


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class StrengthIn(_In):
    amount: Annotated[str, StringConstraints(pattern=AMOUNT)]
    unit: Literal["ug", "IU"]
    basis: Literal["unit", "mL", "g"]

    @field_validator("amount")
    @classmethod
    def _positive(cls, v: str) -> str:
        if Decimal(v) == 0:
            raise ValueError("amount must be greater than 0")
        return v


class IngredientIn(_In):
    key: Key
    strength: StrengthIn | None = None


class ItemIn(_In):
    ingredients: Annotated[list[IngredientIn], Field(min_length=1, max_length=MAX_INGREDIENTS)]
    dose_form: FormGroup | None = None

    @field_validator("ingredients")
    @classmethod
    def _distinct(cls, v: list[IngredientIn]) -> list[IngredientIn]:
        if len({i.key for i in v}) != len(v):
            raise ValueError("ingredient keys must be distinct within an item")
        return v


class PresenceIn(_In):
    items: Annotated[list[ItemIn], Field(min_length=1, max_length=MAX_ITEMS)]

    @field_validator("items")
    @classmethod
    def _keys(cls, v: list[ItemIn]) -> list[ItemIn]:
        if len({i.key for item in v for i in item.ingredients}) > MAX_KEYS:
            raise ValueError("at most 50 distinct keys")
        return v


class ProductsIn(_In):
    """One medicine (keys and codes only, as an item of `PresenceIn`) and one target source."""

    ingredients: Annotated[list[IngredientIn], Field(min_length=1, max_length=MAX_INGREDIENTS)]
    dose_form: FormGroup | None = None
    target: ListableSourceId
    offset: Annotated[int, Field(ge=0, le=MAX_OFFSET)] = 0
    limit: Annotated[int, Field(ge=1, le=MAX_PAGE)] = 50

    @field_validator("ingredients")
    @classmethod
    def _distinct(cls, v: list[IngredientIn]) -> list[IngredientIn]:
        if len({i.key for i in v}) != len(v):
            raise ValueError("ingredient keys must be distinct")
        return v


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CanCompare(_Out):
    strength: bool
    dose_form: bool


class SourceOut(_Out):
    source: int  # index 0..4 in the fixed order TR, EU-FR, EU-ES, EU-DE, US
    source_id: SourceId | None
    region: Literal["TR", "EU", "US"]
    country: Literal["FR", "ES", "DE"] | None
    status: Literal["loaded", "source_unavailable"]
    reason: Literal["not_loaded", "no_open_product_database"] | None
    snapshot_date: str | None
    stale: bool
    attribution: Literal["titck", "bdpm", "cima", "openfda"] | None
    as_published: bool
    can_compare: CanCompare


class Cmp(_Out):
    result: Result
    reason: CmpReason | None
    comparable: int
    equal: int


class Comparison(_Out):
    strength: Cmp
    dose_form: Cmp
    strength_and_dose_form: Cmp


class Answer(_Out):
    source: int
    status: Status
    products: int
    with_other_ingredients: int
    keys_found: list[str]
    homeopathic_left_out: int
    comparison: Comparison | None


class ItemOut(_Out):
    item: int
    keys: list[str]
    unknown_keys: list[str]
    answers: list[Answer]


class PresenceOut(_Out):
    dataset_version: str
    form_table_version: str
    sources: list[SourceOut]
    items: list[ItemOut]
    notices: list[Notice]
    disclaimer: str = messages.DISCLAIMER


class ListedIngredient(_Out):
    key: str
    strength_published: str | None  # exactly as the source publishes it


class ListedProduct(_Out):
    name: str  # exactly as the source publishes it
    ingredients: list[ListedIngredient]
    dose_form_published: str | None
    dose_form_group: FormGroup | None  # Janus's grouping, not source data
    strength: Level
    strength_reason: LevelReason | None  # only for `unknown`
    dose_form: Level
    dose_form_reason: LevelReason | None
    marketed: Marketed
    listings: int  # source entries that share every field shown here


class LevelCounts(_Out):
    same: int
    different: int
    unknown: int


class ListingCounts(_Out):
    strength: LevelCounts
    dose_form: LevelCounts


class ProductsOut(_Out):
    dataset_version: str
    form_table_version: str
    source: SourceOut
    keys: list[str]
    unknown_keys: list[str]
    status: Status
    total: int  # listed rows (distinct published entries), before paging
    listings: int  # source entries behind them
    counts: ListingCounts  # over `listings`
    with_other_ingredients: int
    keys_found: list[str]
    homeopathic_left_out: int
    not_finished_left_out: int
    offset: int
    limit: int
    products: list[ListedProduct]
    notices: list[ListingNotice]
    disclaimer: str = messages.DISCLAIMER
