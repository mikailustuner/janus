"""The result contract grows only by additions (drug-resolution Req 4.5, task 16.3).

The Phase 1 field sets are frozen here; Phase 2 may add the fields named in `ADDED` and nothing
else, and may widen an enumeration but never remove a value.
"""

from __future__ import annotations

from typing import Any

from janus.resolution.model import (
    IngredientCandidate,
    Notice,
    ProductCandidate,
    ResolutionResult,
    ResolvedIngredient,
    ScanInfo,
)

PHASE1: dict[str, set[str]] = {
    "ProductCandidate": {
        "kind", "candidate_id", "region", "matched_by", "score", "product_name", "brand_name",
        "generic_name", "ingredient_text", "published_atc", "product_type", "routes",
        "dosage_form", "marketing_end_date", "suspension_status", "name_only", "homeopathic",
        "product_rxcuis", "packages", "ingredients", "source",
    },
    "ResolvedIngredient": {
        "position", "published_name", "strength", "status", "reason", "ingredient_key",
        "key_candidates", "match_step", "atc_codes", "atc_selection", "rxcuis", "rxcui_status",
        "source",
    },
    "IngredientCandidate": {
        "kind", "matched_by", "score", "ingredient_key", "atc_codes", "atc_selection", "rxcuis",
        "rxcui_status", "source",
    },
    "ScanInfo": {
        "gtin", "expiry", "expiry_status", "serial_present", "lot_present", "structural_hint",
    },
    "Notice": {"code", "region", "source_id", "date"},
    "ResolutionResult": {
        "dataset_version", "regions_searched", "sources", "scan", "notices", "candidates",
        "disclaimer",
    },
}  # fmt: skip

ADDED: dict[str, set[str]] = {
    "ProductCandidate": {"country", "status_published"},
    "Notice": {"country"},
}

MODELS: dict[str, Any] = {
    "ProductCandidate": ProductCandidate,
    "ResolvedIngredient": ResolvedIngredient,
    "IngredientCandidate": IngredientCandidate,
    "ScanInfo": ScanInfo,
    "Notice": Notice,
    "ResolutionResult": ResolutionResult,
}

PHASE1_NOTICES = {
    "source_may_be_outdated",
    "region_adapter_not_available",
    "unmapped_ingredients",
    "unknown_candidate_ids",
}


def test_result_fields_grow_only_by_the_named_additions() -> None:
    """Feature: drug-resolution, Req 4.5. Every Phase 1 field stays; only `ADDED` is new."""
    for name, model in MODELS.items():
        fields = set(model.model_fields)
        assert PHASE1[name] <= fields, name
        assert fields - PHASE1[name] == ADDED.get(name, set()), name


def test_enumerations_only_gain_values() -> None:
    notice_codes = set(Notice.model_json_schema()["properties"]["code"]["enum"])
    assert PHASE1_NOTICES <= notice_codes
    assert notice_codes - PHASE1_NOTICES == {"no_open_product_database"}
    matched = set(ProductCandidate.model_json_schema()["properties"]["matched_by"]["enum"])
    assert {"barcode", "ndc_gtin", "ndc", "name", "candidate_id"} <= matched
    region = set(ProductCandidate.model_json_schema()["properties"]["region"]["enum"])
    assert {"TR", "US"} <= region
