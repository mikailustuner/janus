"""Tests for the séance claim assembly (séance design §3.6; P6-P8) and the real package."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.jobs.canon_package import (
    CONDITIONS,
    PackageError,
    Review,
    assemble,
    final_conditions,
)

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "datasets" / "canon"
COND = st.lists(st.sampled_from(CONDITIONS), min_size=1, max_size=4, unique=True).map(
    lambda xs: tuple(c for c in CONDITIONS if c in xs)
)
VERDICT = st.sampled_from(["accept", "correct", "reject"])


@st.composite
def reviews(draw: st.DrawFn) -> Review:
    verdict = draw(VERDICT)
    cond = draw(st.none() | COND) if verdict == "correct" else None
    return Review(verdict, cond, None, "" if verdict == "accept" else "n")


@given(COND, reviews(), reviews())
def test_final_conditions_never_add_and_reject_wins(
    reader: tuple[str, ...], a: Review, b: Review
) -> None:
    """P6 (Req 1.5): a claim's conditions are what both passes leave standing; a reject in
    either pass removes the passage; a pass can remove but not add a condition both did not
    give."""
    got = final_conditions(reader, a, b)
    if "reject" in (a.verdict, b.verdict):
        assert got == ()
    ca = a.conditions if a.conditions is not None else reader
    cb = b.conditions if b.conditions is not None else reader
    assert set(got) <= set(ca) & set(cb)
    assert final_conditions(reader, b, a) == got


def _rows() -> dict[str, list[dict[str, str]]]:
    span = {
        "span_id": "canon.b2.h0002.l5.abcdef",
        "entry_id": "canon.b2.h0002",
        "line_start": "5",
        "line_end": "6",
        "arabic_span": "طبيخه نافع لحرق النار.",
    }
    return {
        "spans": [span],
        "reader": [
            {
                "span_id": span["span_id"],
                "substance_id": "henna",
                "conditions": "wound|burn",
                "use_en": "decoction",
                "machine_translation_en": "Its decoction helps fire burns.",
                "rule_theme_agrees": "yes",
                "rule_use_agrees": "yes",
            }
        ],
        "ids": [
            {
                "substance_id": "henna",
                "entry_id": "canon.b2.h0002",
                "transliteration": "hinna",
                "name_en": "henna",
                "kind": "plant",
                "janus_identification": "Lawsonia inermis L.",
                "gold_id": "pmc3941892.t1.r06",
                "hamdard_ref": "x",
                "hamdard_identification": "y",
                "status": "matches_gold",
                "note": "",
            }
        ],
        "entries": [{"entry_id": "canon.b2.h0002", "page": "V01P474", "heading": "حناء"}],
        "gold": [{"gold_id": "pmc3941892.t1.r06", "scientific_name": "Lawsonia inermis L."}],
    }


def _review(verdict: str, cond: str = "") -> list[dict[str, str]]:
    note = "" if verdict == "accept" else "why"
    return [
        {
            "span_id": "canon.b2.h0002.l5.abcdef",
            "verdict": verdict,
            "conditions": cond,
            "machine_translation_en": "",
            "note": note,
        }
    ]


def _idrev(hazard: str = "") -> list[dict[str, str]]:
    return [
        {
            "substance_id": "henna",
            "verdict": "accept",
            "status": "",
            "janus_identification": "",
            "hazard": hazard,
            "note": "",
        }
    ]


def test_claims_are_never_expert_reviewed_and_hazards_never_headline() -> None:
    """Req 1.5, 4.1: assembly marks AI review only; expert review stays pending; a hazardous
    substance is never headline-eligible."""
    r = _rows()
    out = assemble(
        r["spans"],
        r["reader"],
        r["ids"],
        _review("correct", "burn"),
        _review("accept"),
        _idrev("toxic"),
        r["entries"],
        r["gold"],
    )
    assert [c["condition"] for c in out.claims] == ["burn"]
    assert all(c["expert_review"] == "pending" for c in out.claims)
    assert all(c["headline_eligible"] == "no" for c in out.claims)
    assert out.substances[0]["gold_scientific_name"] == "Lawsonia inermis L."
    assert out.quality["expert_reviewed"] == 0


def test_missing_or_dangling_review_is_refused() -> None:
    r = _rows()
    with pytest.raises(PackageError):
        assemble(
            r["spans"],
            r["reader"],
            r["ids"],
            [],
            _review("accept"),
            _idrev(),
            r["entries"],
            r["gold"],
        )
    bad = _review("correct")  # a correction without a note
    bad[0]["note"] = ""
    with pytest.raises(PackageError):
        assemble(
            r["spans"],
            r["reader"],
            r["ids"],
            bad,
            _review("accept"),
            _idrev(),
            r["entries"],
            r["gold"],
        )


def _read(name: str) -> list[dict[str, str]]:
    with (PKG / name).open(encoding="utf-8", newline="") as f:
        return [{k: (v or "") for k, v in row.items()} for row in csv.DictReader(f)]


@pytest.mark.skipif(not (PKG / "claims.csv").exists(), reason="data package not built")
def test_committed_package_is_reproducible() -> None:
    """P7 (Req 4.2): the committed claims and substances are exactly what assembly gives from
    the committed inputs, and every claim's locator lies inside its entry."""
    out = assemble(
        _read("theme_spans.csv"),
        _read("reader_ai.csv"),
        _read("identifications.csv"),
        _read("review_historian.csv"),
        _read("review_pharmacologist.csv"),
        _read("review_pharmacologist_identifications.csv"),
        _read("entries.csv"),
        _read_gold(),
    )
    assert out.claims == _read("claims.csv")
    assert out.substances == _read("substances.csv")
    entries = {e["entry_id"]: e for e in _read("entries.csv")}
    for c in out.claims:
        e = entries[c["entry_id"]]
        assert int(e["line_start"]) <= int(c["line_start"]) <= int(c["line_end"])
        assert int(c["line_end"]) <= int(e["line_end"])


def _read_gold() -> list[dict[str, str]]:
    with (REPO / "data" / "canon_gold_pmc3941892.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))
