"""Shared vocabulary of Collective Memory (design §3, §5). Pure: no I/O."""

from __future__ import annotations

from typing import Final, Literal

REGIONS: Final = ("TR", "EU", "US", "OTHER", "UNKNOWN")
ALL_REGION: Final = "ALL"
RESPONSE_REGIONS: Final = (*REGIONS, ALL_REGION)
USER_LAYER_REGIONS: Final = ("TR", "EU", "US")

type Region = Literal["TR", "EU", "US", "OTHER", "UNKNOWN", "ALL"]
type Scope = Literal["suspect", "any"]
type Layer = Literal["faers", "contributions", "outcomes"]
type Direction = Literal["adverse", "benefit"]
type Level = Literal["combination", "pairwise", "single"]
type Assessment = Literal[
    "no_reports", "insufficient_data", "not_disproportionate", "weak", "disproportionate"
]

ASSESSMENT_ORDER: Final[tuple[Assessment, ...]] = (
    "no_reports",
    "insufficient_data",
    "not_disproportionate",
    "weak",
    "disproportionate",
)

# Ingredient keys: a Wikidata item or a Janus key (data/janus_ingredients.csv).
INGREDIENT_KEY_PATTERN: Final = r"^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$"
# Janus event keys (apps/api/janus/memory/memory_events.csv).
EVENT_KEY_PATTERN: Final = r"^[a-z0-9][a-z0-9_.-]{0,39}$"

MAX_INGREDIENTS: Final = 20
MAX_PT_LENGTH: Final = 200
