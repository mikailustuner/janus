"""The glossary name filler: only empty cells of accepted rows, checked labels, a note per row."""

from __future__ import annotations

import csv
import importlib.util
import io
from pathlib import Path
from types import ModuleType

from hypothesis import given
from hypothesis import strategies as st

TOOL = Path(__file__).resolve().parents[1] / "tools" / "glossary_fill_names.py"
HEADER = "key,en,tr,de,fr,es,pt,en_alt,status,edited,source,note\n"


def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("glossary_fill_names", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = tool()


def rows(text: str) -> dict[str, dict[str, str]]:
    return {r["key"]: r for r in csv.DictReader(io.StringIO(text))}


def test_fills_only_empty_cells_of_accepted_rows() -> None:
    text = (
        HEADER
        + "\n".join(
            [
                "Q1,ibuprofen,,,,,,,accepted,,d,",
                "Q2,naproxen,,,,,naproxeno,,accepted,,d,Review: kept",
                "Q3,rejected one,,,,,,,rejected,,d,",
                "Q4,no label,,,,,,,accepted,,d,",
            ]
        )
        + "\n"
    )
    labels = {
        "Q1": "Ibuprofeno",
        "Q2": "other",
        "Q3": "x",
    }
    out, counts = T.fill(text, labels, "pt", "2026-11-13")
    r = rows(out)
    assert r["Q1"]["pt"] == "ibuprofeno"
    assert "Wikidata label (CC0)" in r["Q1"]["note"]
    assert "review not yet done" in r["Q1"]["note"]
    assert r["Q2"]["pt"] == "naproxeno" and r["Q2"]["note"] == "Review: kept"
    assert r["Q3"]["pt"] == ""
    assert r["Q4"]["pt"] == ""
    assert counts == {"accepted": 3, "had_name": 1, "filled": 1, "no_label": 1, "rejected": 0}


def test_checks() -> None:
    assert T.clean("sulfato de ferro (II)") == "sulfato de ferro (II)"
    assert T.clean("Hidroxocobalamina (Vitamina B12)") is None
    assert T.clean("a, b") is None
    assert T.clean("x" * 61) is None
    assert T.clean("ACTH") == "ACTH"
    assert T.clean("Insulina asparte") == "insulina asparte"
    assert T.clean("5-hidroxitriptofano") == "5-hidroxitriptofano"


@given(st.text(max_size=80))
def test_clean_output_is_nfc_and_checked(label: str) -> None:
    import unicodedata

    name = T.clean(label)
    if name is not None:
        assert unicodedata.normalize("NFC", name) == name
        assert 0 < len(name) <= T.MAX_LEN
        assert not any(c in name for c in "[];,")


def test_unchanged_text_round_trips() -> None:
    text = HEADER + 'Q9,"a, b",,,,,x,,accepted,,d,"note, with comma"\n'
    out, _ = T.fill(text, {}, "pt", "2026-11-13")
    assert out == text
