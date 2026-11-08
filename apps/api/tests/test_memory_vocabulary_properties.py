"""Property tests for the Janus event vocabulary loader (collective-memory design §10: P15)."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus.memory.vocabulary import (
    COLUMNS,
    PIPC_ROWS,
    PLACEHOLDER_KEYS,
    VocabularyError,
    load_events,
    missing_pts,
    parse_events,
)

PT_POOL = [
    "Cough",
    "Nausea",
    "Rash",
    "Hallucination, visual",
    "Oedema peripheral",
    "Dizziness",
    "Tremor",
    "Müdigkeit",
    "Insomnia",
    "Arthralgia",
]
ADVERSE_PLACEHOLDERS = [k for k in PLACEHOLDER_KEYS if not k.startswith("improvement_")]
BENEFIT_PLACEHOLDERS = [k for k in PLACEHOLDER_KEYS if k.startswith("improvement_")]

Row = dict[str, str]


def render(rows: list[Row], header: tuple[str, ...] = COLUMNS) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow([r.get(c, "") for c in COLUMNS])
    return buf.getvalue()


@st.composite
def valid_rows(draw: st.DrawFn) -> list[Row]:
    extra = draw(st.integers(0, 4))
    adverse = [*ADVERSE_PLACEHOLDERS, *[f"extra_key_{i}" for i in range(extra)]]
    positions = list(range(1, PIPC_ROWS + 1))
    owners = [draw(st.integers(0, len(adverse) - 1)) for _ in positions]
    rows: list[Row] = []
    for i, key in enumerate(adverse):
        mine = [str(p) for p, o in zip(positions, owners, strict=True) if o == i]
        pts = draw(st.lists(st.sampled_from(PT_POOL), min_size=1, max_size=4, unique=True))
        rows.append(
            {
                "key": key,
                "direction": "adverse",
                **{f"label_{c}": f"{key} {c}" for c in ("en", "tr", "de", "fr", "es")},
                "pts": "|".join(pts),
                "pipc_positions": ";".join(mine),
                "status": draw(st.sampled_from(["proposed", "active", "deprecated"])),
                "note": draw(st.text(max_size=20)),
            }
        )
    for key in BENEFIT_PLACEHOLDERS:
        rows.append(
            {
                "key": key,
                "direction": "benefit",
                **{f"label_{c}": f"{key} {c}" for c in ("en", "tr", "de", "fr", "es")},
                "status": "proposed",
            }
        )
    return rows


@settings(max_examples=100, deadline=None)
@given(valid_rows())
def test_valid_file_is_accepted_and_active_keys_drive_the_hook(rows: list[Row]) -> None:
    """Feature: collective-memory, Property P15 — Validates: Req 6.2, 6.6."""
    vocab = parse_events(render(rows))
    assert [k.key for k in vocab.keys] == [r["key"] for r in rows]
    active = {r["key"] for r in rows if r["status"] == "active"}
    assert {k.key for k in vocab.active()} == active
    # only active adverse keys reach the finding hook; every position maps to its own key
    expected = {
        int(p): r["key"]
        for r in rows
        if r["status"] == "active" and r["pipc_positions"]
        for p in r["pipc_positions"].split(";")
    }
    assert dict(vocab.pipc_event_keys()) == expected
    for r in rows:
        assert (vocab.usable(r["key"]) is not None) == (r["status"] == "active")


def mutate(rows: list[Row], defect: str) -> tuple[list[Row], tuple[str, ...]]:
    rows = [dict(r) for r in rows]
    adverse = [r for r in rows if r["direction"] == "adverse"]
    withpos = [r for r in adverse if r["pipc_positions"]]
    header = COLUMNS
    if defect == "bad_header":
        header = ("clef", *COLUMNS[1:])
    elif defect == "duplicate_key":
        rows.append(dict(rows[0]))
    elif defect == "bad_key":
        rows[0]["key"] = "Bad Key"
    elif defect == "bad_direction":
        rows[0]["direction"] = "neutral"
    elif defect == "bad_status":
        rows[0]["status"] = "reviewed"
    elif defect == "missing_label":
        rows[0]["label_tr"] = ""
    elif defect == "empty_pts":
        adverse[0]["pts"] = ""
    elif defect == "benefit_has_pts":
        next(r for r in rows if r["direction"] == "benefit")["pts"] = "Cough"
    elif defect == "benefit_has_positions":
        next(r for r in rows if r["direction"] == "benefit")["pipc_positions"] = "1"
    elif defect == "bad_pt":
        adverse[0]["pts"] = " Cough"
    elif defect == "duplicate_pt":
        adverse[0]["pts"] = "Cough|Cough"
    elif defect == "bad_position":
        withpos[0]["pipc_positions"] += ";66"
    elif defect == "position_covered_twice":
        a, b = withpos[0], next((r for r in adverse if r is not withpos[0]), withpos[0])
        b["pipc_positions"] = ";".join(
            filter(None, [b["pipc_positions"], a["pipc_positions"].split(";")[0]])
        )
    elif defect == "position_uncovered":
        parts = withpos[0]["pipc_positions"].split(";")
        withpos[0]["pipc_positions"] = ";".join(parts[1:])
    elif defect == "bad_safety_line":
        rows[0]["safety_line"] = "call_us"
    elif defect == "placeholder_key_missing":
        rows = [r for r in rows if r["key"] != "improvement_sleep"]
    else:
        raise AssertionError(defect)
    return rows, header


DEFECTS = [
    ("bad_header", "bad_header"),
    ("duplicate_key", "duplicate_key"),
    ("bad_key", "bad_key"),
    ("bad_direction", "bad_direction"),
    ("bad_status", "bad_status"),
    ("missing_label", "missing_label"),
    ("empty_pts", "empty_pts"),
    ("benefit_has_pts", "benefit_has_pts"),
    ("benefit_has_positions", "benefit_has_positions"),
    ("bad_pt", "bad_pt"),
    ("duplicate_pt", "duplicate_pt"),
    ("bad_position", "bad_position"),
    ("position_covered_twice", "position_covered_twice"),
    ("position_uncovered", "position_uncovered"),
    ("bad_safety_line", "bad_safety_line"),
    ("placeholder_key_missing", "placeholder_key_missing"),
]


@settings(max_examples=40, deadline=None)
@given(valid_rows(), st.sampled_from(DEFECTS))
def test_each_defect_is_rejected_with_its_code(rows: list[Row], defect: tuple[str, str]) -> None:
    """Feature: collective-memory, Property P15 — Validates: Req 6.2, 6.6."""
    name, code = defect
    bad, header = mutate(rows, name)
    with pytest.raises(VocabularyError) as exc:
        parse_events(render(bad, header))
    assert exc.value.code == code


@settings(max_examples=60, deadline=None)
@given(valid_rows(), st.sets(st.sampled_from(PT_POOL)))
def test_missing_pt_report_is_exact(rows: list[Row], known: set[str]) -> None:
    """Feature: collective-memory, Property P15 (missing-PT report) — Validates: Req 6.5."""
    vocab = parse_events(render(rows))
    report = missing_pts(vocab, known)
    for k in vocab.keys:
        gone = tuple(pt for pt in k.pts if pt not in known)
        assert report.get(k.key, ()) == gone
    assert set(report) == {k.key for k in vocab.keys if any(pt not in known for pt in k.pts)}


def test_partial_coverage_is_allowed_only_when_asked() -> None:
    rows: list[Any] = [
        {
            "key": k,
            "direction": "adverse",
            **{f"label_{c}": "x" for c in ("en", "tr", "de", "fr", "es")},
            "pts": "Cough",
            "status": "proposed",
        }
        for k in ADVERSE_PLACEHOLDERS
    ] + [
        {
            "key": k,
            "direction": "benefit",
            **{f"label_{c}": "x" for c in ("en", "tr", "de", "fr", "es")},
            "status": "proposed",
        }
        for k in BENEFIT_PLACEHOLDERS
    ]
    with pytest.raises(VocabularyError, match="position_uncovered"):
        parse_events(render(rows))
    assert len(parse_events(render(rows), require_full_pipc=False).keys) == len(PLACEHOLDER_KEYS)


DATA_FILE = Path(__file__).resolve().parents[1] / "janus" / "memory" / "memory_events.csv"


def test_the_committed_vocabulary_is_valid_and_accepted() -> None:
    vocab = load_events(DATA_FILE)
    adverse = [k for k in vocab.keys if k.direction == "adverse"]
    benefit = [k for k in vocab.keys if k.direction == "benefit"]
    assert (len(adverse), len(benefit)) == (34, 5)
    assert sorted(p for k in adverse for p in k.pipc_positions) == list(range(1, 66))
    assert {k.key for k in vocab.keys} >= set(PLACEHOLDER_KEYS)
    # Owner review 2026-11-08 (event-mapping-review.md, section 4): all keys are accepted.
    assert all(k.status == "active" for k in vocab.keys)
    assert set(vocab.pipc_event_keys()) == set(range(1, 66))
    assert all(vocab.usable(k.key) is not None for k in vocab.keys)
    # owner decisions applied
    arrhythmia = vocab.get("arrhythmia")
    assert arrhythmia is not None
    assert {"Torsade de pointes", "Ventricular tachycardia", "Ventricular fibrillation"} <= set(
        arrhythmia.pts
    )
    assert not {
        "Electrocardiogram QT prolonged",
        "Long QT syndrome",
        "Atrial fibrillation",
        "Supraventricular tachycardia",
    } & set(arrhythmia.pts)
    genital = vocab.get("genital_fungal_infection")
    assert genital is not None and "Balanoposthitis" not in genital.pts
    # safety lines (owner decision 2026-11-08)
    assert {k.key: k.safety_line for k in vocab.keys if k.safety_line} == {
        "depression": "crisis_support",
        "rash": "urgent_care_skin",
        "arrhythmia": "urgent_care_heart",
    }
    periph = vocab.get("peripheral_oedema")
    assert periph is not None and "Peripheral swelling" in periph.pts
    assert "Fluid retention" in (vocab.get("oedema") or periph).pts
    assert "Dementia" not in (vocab.get("cognitive_impairment") or periph).pts
