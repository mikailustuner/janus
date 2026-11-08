"""Request and result models of drug resolution (drug-resolution design §3.1, §3.2).

`rule_input` is the only function the cascade engine uses to read ingredient codes: codes of
`mapped` ingredients only, never a combination code (Req 5.2, 5.4).
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from janus.memory import messages

Region = Literal["TR", "US", "EU"]
# Regions a request may name. `EU` asks the French and Spanish adapters.
RequestRegion = Literal["TR", "US", "EU"]
Country = Literal["FR", "ES"]
CANDIDATE_ID = r"^(TR|US|EU):[a-z_]+:[0-9]{1,9}$"


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ScanIn(_In):
    content: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    region: RequestRegion | None = None


class NdcIn(_In):
    ndc: Annotated[str, StringConstraints(min_length=1, max_length=32)]


class SearchIn(_In):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
    region: RequestRegion | None = None
    limit: Annotated[int, Field(ge=1, le=20)] = 10


class ProductsIn(_In):
    candidate_ids: Annotated[
        list[Annotated[str, StringConstraints(pattern=CANDIDATE_ID)]],
        Field(min_length=1, max_length=50),
    ]


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceRef(_Out):
    source_id: str
    run_id: str
    region: str | None
    snapshot_date: str


class AtcCodeOut(_Out):
    code: str
    source: SourceRef
    product: str | None = None  # candidate id of the TİTCK product the code was observed on


class IngredientKey(_Out):
    qid: str
    label_en: str | None
    labels: dict[str, str | None]


class ResolvedIngredient(_Out):
    position: int
    published_name: str
    strength: str | None
    status: Literal["mapped", "ambiguous", "unmapped"]
    reason: (
        Literal[
            "no_ingredient_key",
            "possible_unsplit_combination",
            "no_ingredient_atc",
            "no_ingredient_atc_for_route",
        ]
        | None
    )
    ingredient_key: IngredientKey | None
    key_candidates: list[str]
    match_step: str | None
    atc_codes: list[AtcCodeOut]
    atc_selection: (
        Literal[
            "single_ingredient_product",
            "therapeutic_group",
            "anatomical_group",
            "route_group",
            "all_codes",
            "component_code",
        ]
        | None
    )
    rxcuis: list[str]
    rxcui_status: Literal["from_wikidata", "not_in_wikidata"] | None
    source: SourceRef


class Package(_Out):
    ndc_published: str
    ndc11: str


class ProductCandidate(_Out):
    kind: Literal["product"] = "product"
    candidate_id: str
    region: Region
    country: Country | None = None  # EU products only (Phase 2)
    matched_by: Literal[
        "barcode",
        "ndc_gtin",
        "ndc",
        "name",
        "candidate_id",
        "cip13",
        "ntin",
        "gtin",
        "ai_712",
        "ntin_digits",
    ]
    score: float | None = None
    product_name: str | None
    brand_name: str | None
    generic_name: str | None
    ingredient_text: str | None
    published_atc: str | None  # as published, display only; never an ingredient code
    product_type: str | None
    routes: list[str]
    dosage_form: str | None
    marketing_end_date: str | None
    suspension_status: int | None
    name_only: bool
    homeopathic: bool = False  # strengths in homeopathic units: not evaluated as the substance
    # EU authorisation and marketing status as published (display only; no rule reads it).
    status_published: list[str] = Field(default_factory=list[str])
    product_rxcuis: list[str]
    packages: list[Package]
    ingredients: list[ResolvedIngredient]
    source: SourceRef


class IngredientCandidate(_Out):
    kind: Literal["ingredient"] = "ingredient"
    matched_by: Literal["name"] = "name"
    score: float | None = None
    ingredient_key: IngredientKey
    atc_codes: list[AtcCodeOut]
    atc_selection: Literal["all_codes"] | None
    rxcuis: list[str]
    rxcui_status: Literal["from_wikidata", "not_in_wikidata"]
    source: SourceRef


class ScanInfo(_Out):
    gtin: str
    expiry: dt.date | None
    expiry_status: Literal["absent", "valid", "invalid"]
    serial_present: bool
    lot_present: bool
    structural_hint: Literal["TR", "US", "FR", "ES", "DE", "other", "none"]


class Notice(_Out):
    code: Literal[
        "source_may_be_outdated",
        "region_adapter_not_available",
        "unmapped_ingredients",
        "unknown_candidate_ids",
        "no_open_product_database",
    ]
    region: str | None = None
    country: str | None = None
    source_id: str | None = None
    date: str | None = None


class ResolutionResult(_Out):
    dataset_version: str
    regions_searched: list[Region]
    sources: list[SourceRef]
    scan: ScanInfo | None = None
    notices: list[Notice]
    candidates: list[ProductCandidate | IngredientCandidate]
    disclaimer: str = messages.DISCLAIMER  # rule 9, em dash (doctor-loop DP18)


# Homeopathic strength units of openFDA (UCUM-style annotations: [hp_X], [hp_C], [hp_M],
# [hp_Q], [kp_C]). Owner decision 2026-11-07: such products contain negligible active substance
# and are never evaluated as the substance.
HOMEOPATHIC_UNIT = re.compile(r"\[(hp|kp)_[a-z]+\]", re.IGNORECASE)


def is_homeopathic_strength(strength: str | None) -> bool:
    return bool(strength) and HOMEOPATHIC_UNIT.search(strength or "") is not None


def is_homeopathic_product(strengths: Iterable[str | None]) -> bool:
    """A product is homeopathic when any of its ingredient strengths is in homeopathic units
    (13,481 of 135,688 openFDA products on 2026-11-06; 44 of them mix units)."""
    return any(is_homeopathic_strength(s) for s in strengths)


def rule_input(ingredient: ResolvedIngredient) -> tuple[str, ...]:
    """Ingredient-level codes for rule matching: unique and sorted, only for `mapped`."""
    if ingredient.status != "mapped":
        return ()
    return tuple(sorted({a.code for a in ingredient.atc_codes}))
