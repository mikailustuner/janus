"""Test-only rule data for the language-aware name functions (drug-resolution Phase 2).

The committed lists stay at the Phase 1 content until the owner has accepted the review sheet
(Req 12.11). The properties of P34-P40 therefore try the mechanism with the lists below, set for
the duration of one `with rule_data(...)` block and restored afterwards. They are examples, not
review decisions.
"""

from __future__ import annotations

from typing import Any

from janus.resolution import name_lists
from janus.resolution.name_lists import Lang

NONE: frozenset[str] = frozenset()

# A French and a Spanish salt vocabulary of the shape seen in the BDPM and the Nomenclátor.
FR_SALTS = frozenset({"chlorhydrate", "sodique", "anhydre", "fumarate"})
ES_SALTS = frozenset({"hidrocloruro", "besilato", "sodico", "trihidrato"})
EN_EXTRA = frozenset({"cypionate", "enanthate"})
FR_CONNECTORS = frozenset({"de", "d", "du", "des"})
ES_CONNECTORS = frozenset({"de", "del"})

TEST_LISTS: dict[str, Any] = {
    "EXTRA_SALT_WORDS": {"tr": NONE, "en": EN_EXTRA, "fr": FR_SALTS, "es": ES_SALTS},
    "EXTRA_NOT_ALONE": {"tr": NONE, "en": NONE, "fr": frozenset({"chlorure"}), "es": NONE},
    "CONNECTORS": {"tr": NONE, "en": NONE, "fr": FR_CONNECTORS, "es": ES_CONNECTORS},
}
ALL_SWITCHES: dict[str, Any] = {
    "BIOLOGIC_SUFFIX_ENABLED": True,
    "ES_FINAL_VOWEL_ENABLED": True,
    "ACID_WORD_ORDER_ENABLED": True,
}


rule_data = name_lists.override


def with_everything() -> Any:
    """All test lists and switches on."""
    return rule_data(**TEST_LISTS, **ALL_SWITCHES)


def effective_salts(lang: Lang) -> frozenset[str]:
    """The salt words a language uses right now (Phase 1 base plus additions)."""
    return name_lists.BASE_SALT_WORDS | name_lists.EXTRA_SALT_WORDS[lang]
