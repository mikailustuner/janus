"""The `aceponate` correction (name-rules review, owner decision 2, 2026-11-08).

WHOCC D07AC lists methylprednisolone aceponate (D07AC14) and hydrocortisone aceponate (D07AC16)
with codes of their own, so `aceponate` is not a salt word: stripping it indexed the topical
hydrocortisone aceponate item as plain "hydrocortisone" and sent hydrocortisone acetate, sodium
succinate and valerate to it instead of to hydrocortisone (H02AB09, systemic).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from janus.resolution.matching import IndexItem, NameIndex, map_name
from janus.resolution.name_lists import BASE_SALT_WORDS
from janus.resolution.names import fold, strip_salts

SALTED = [
    "HYDROCORTISONE ACETATE",
    "HYDROCORTISONE SODIUM SUCCINATE",
    "HYDROCORTISONE VALERATE",
]


def test_aceponate_is_not_a_salt_word() -> None:
    assert "aceponate" not in BASE_SALT_WORDS and "aseponat" not in BASE_SALT_WORDS
    assert strip_salts(fold("hydrocortisone aceponate")) == "hydrocortisone aceponate"
    assert strip_salts(fold("metilprednisolon aseponat"), "tr") == "metilprednisolon aseponat"


def test_hydrocortisone_salts_map_to_hydrocortisone_not_the_aceponate_item() -> None:
    index = NameIndex.build(
        [
            IndexItem("Q1", {"en": "hydrocortisone"}),  # H02AB09, systemic
            IndexItem("Q2", {"en": "hydrocortisone aceponate"}),  # D07AC16, topical
        ]
    )
    for name in SALTED:
        m = map_name(name, index, lang="en")
        assert (m.status, m.keys) == ("mapped", ("Q1",)), name
    assert map_name("hydrocortisone aceponate", index, lang="en").keys == ("Q2",)


_DATA = Path(os.environ.get("JANUS_DATA_DIR") or Path(__file__).resolve().parents[3] / ".data")


@pytest.mark.skipif(
    os.environ.get("CI") == "true" or not (_DATA / "artifacts" / "wikidata_ingredients").exists(),
    reason="real artifacts are local only",
)
def test_real_wikidata_hydrocortisone_salts_reach_h02ab09() -> None:
    """With the real extract: the three salts map to an item whose codes include H02AB09."""
    from janus.resolution.load import gather
    from janus.resolution.prepare import build_name_index, eligible_items

    inputs = gather(_DATA)
    rows = inputs.artifacts["wikidata"].rows
    index = build_name_index(rows, inputs.rules, inputs.synonyms, inputs.curated.rows)
    items, _codes, _check = eligible_items(rows, inputs.rules, inputs.curated.rows)
    for name in SALTED:
        m = map_name(name, index, lang="en")
        assert m.status == "mapped", name
        codes: list[str] = [str(c) for c in list(items[m.keys[0]].get("atc_codes") or [])]
        assert "H02AB09" in codes, name
