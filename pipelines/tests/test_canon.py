"""Tests for the `canon` job and its pure text module (séance design §3; P1-P6). Synthetic
OpenITI-shaped text only; no network, no OpenITI text in the repository's tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.canonical import sha256_bytes
from janus_pipelines.core.manifest import Outcome
from janus_pipelines.core.registry import load_registry
from janus_pipelines.core.runner import RawInput, RunContext, run_job
from janus_pipelines.core.store import Store
from janus_pipelines.jobs import canon
from janus_pipelines.jobs.canon import CanonJob, SourceVersionError, git_blob_sha1, span_id
from janus_pipelines.jobs.canon_text import (
    BOOK2_TITLE,
    CanonShapeError,
    normalize,
    normalize_with_map,
    rule_extract,
    sections,
    source_lines,
    split_book2,
    theme_spans,
)
from tests.stub_job import FIXED_NOW

REPO = Path(__file__).resolve().parents[2]

WORDS = ["ينفع", "من", "الأورام", "الحارة", "ورقه", "ضمادا", "بالخل", "يسكن", "الوجع", "شرابه"]
THEME_WORDS = ["حرق النار", "الجراحات", "للقروح", "القروح الخبيثة", "الداحس", "قيحها"]
LABELS = ["الماهية:", "الجراح والقروح:", "الأورام والبثور:", "أعضاء الرأس:"]


@st.composite
def bodies(draw: st.DrawFn) -> list[str]:
    """Body lines of one entry: paragraphs (`# `), continuations (`~~`), page markers."""
    lines: list[str] = []
    for _ in range(draw(st.integers(0, 6))):
        words = draw(
            st.lists(st.sampled_from(WORDS + THEME_WORDS + LABELS), min_size=1, max_size=12)
        )
        text = " ".join(words) + draw(st.sampled_from(["", ".", " ms0383 ."]))
        lines.append(draw(st.sampled_from(["# ", "~~"])) + text)
        if draw(st.booleans()):
            lines.append(f"# PageV01P{draw(st.integers(300, 700)):03d}")
    return lines


@st.composite
def documents(draw: st.DrawFn) -> tuple[str, list[int]]:
    """A whole OpenITI-like file: a header, Book 1, Book 2 with headings, then Book 3."""
    out = [
        "######OpenITI#",
        "#META#Header#End#",
        "### | الكتاب الأول الأمور الكلية",
        "# نص الكتاب الأول.",
    ]
    out.append(f"### | {BOOK2_TITLE} ")
    levels = [1]
    out += draw(bodies())
    for _ in range(draw(st.integers(0, 8))):
        level = draw(st.integers(2, 6))
        levels.append(level)
        name = draw(st.sampled_from(["آس", "حناء", "خل", "عسل", "كندر", "ورد"]))
        out.append(f"### {'|' * level} {name}:")
        out += draw(bodies())
    out += ["### | الكتاب الثالث الأمراض الجزئية", "# نص."]
    return "\n".join(out), levels


@given(documents())
def test_one_entry_per_heading_and_locators_resolve(doc: tuple[str, list[int]]) -> None:
    """P1 (Req 1.2): one entry per Book 2 heading, in order; each locator resolves to the
    source lines starting at its heading; every body line belongs to exactly one entry."""
    source, levels = doc
    entries = split_book2(source)
    assert [e.level for e in entries] == levels
    lines = source.split("\n")
    covered: list[int] = []
    for e in entries:
        got = source_lines(source, e.line_start, e.line_end)
        assert got and got[0].startswith("### ")
        covered.extend(range(e.line_start, e.line_end + 1))
        assert all(e.line_start <= ln <= e.line_end for ln in e.line_of)
        assert e.parent is None or entries[e.parent - 1].level < e.level
    assert covered == sorted(set(covered))
    last = lines.index("### | الكتاب الثالث الأمراض الجزئية")
    assert covered[-1] == last  # up to the line before Book 3 (1-based = index)


@given(documents())
def test_spans_lie_inside_their_entry_and_name_a_theme(doc: tuple[str, list[int]]) -> None:
    """P2 (Req 1.3): every theme span is a substring of its entry body, inside the entry's lines,
    and contains a theme term; label words alone never make a span."""
    source, _ = doc
    for e in split_book2(source):
        for sp in theme_spans(e):
            text = e.text[sp.start : sp.end]
            assert text and text == text.strip()
            assert e.line_start <= sp.line_start <= sp.line_end <= e.line_end
            assert sp.themes and sp.terms
            norm = normalize(text)
            assert any(t in norm or "لل" + t[2:] in norm for t in sp.terms)
            rule = rule_extract(e, sp)
            assert rule.substance == e.heading and rule.themes == sp.themes


@given(st.text(alphabet="ابتثجحخدذرزسشصضطظعغفقكلمنهويىةأإآ ًٌٍَُِّْـ", max_size=40))
def test_normalize_map_points_to_source(text: str) -> None:
    """P3: the normalised text is idempotent and every character maps back to its source."""
    norm, idx = normalize_with_map(text)
    assert normalize(norm) == norm == normalize(text)
    assert len(idx) == len(norm) and idx == sorted(set(idx))
    assert all(0 <= i < len(text) for i in idx)


def test_li_prefix_and_suffix_forms_are_found() -> None:
    """`لل` (li- + al-) and pronoun suffixes are matched; `حرقة` (burning sensation) is not."""
    src = "\n".join(
        [
            f"### | {BOOK2_TITLE}",
            "### |||||| عدس:",
            "# الجراح والقروح: ينفع للقروح الخبيثة وقيحها. وينفع من حرقة البول.",
            "### | الكتاب الثالث",
        ]
    )
    e = split_book2(src)[1]
    spans = theme_spans(e)
    assert len(spans) == 1
    assert spans[0].themes == ("ulcer", "infection") and spans[0].section == "wounds_ulcers"
    assert "حرقة" not in "".join(spans[0].terms)


def test_sections_split_on_labels() -> None:
    text = "معروف. الطبع: بارد. الجراح والقروح: يدمل الجراحات."
    assert [s.section for s in sections(text)] == ["body", "temperament", "wounds_ulcers"]


def test_missing_book_is_refused() -> None:
    with pytest.raises(CanonShapeError):
        split_book2("### | الكتاب الأول\n# نص")


@given(st.text(min_size=1, max_size=30), st.integers(1, 10**6))
def test_span_id_changes_with_the_text(text: str, line: int) -> None:
    """P4: a span id is stable for the same text and changes when the text changes, so a review
    of an old span can never attach to a changed one."""
    a = span_id("canon.b2.h0001", line, text)
    assert a == span_id("canon.b2.h0001", line, text)
    assert a != span_id("canon.b2.h0001", line, text + "x")


def _ctx(tmp_path: Path) -> RunContext:
    repo = tmp_path / "repo"
    repo.mkdir()
    return RunContext(
        data_dir=tmp_path / "datadir",
        repo_root=repo,
        registry=load_registry(REPO / "pipelines" / "sources.toml"),
        code_version="test",
        now=lambda: FIXED_NOW,
        is_ignored=lambda _p: True,
    )


SAMPLE = "\n".join(
    [
        "######OpenITI#",
        f"### | {BOOK2_TITLE}",
        "# مقدمة.",
        "### |||||| حناء:",
        "# الجراح والقروح: طبيخه نافع لحرق النار نطولا.",
        "# PageV01P474",
        "### | الكتاب الثالث الأمراض الجزئية",
    ]
).encode("utf-8")


def _raw(data: bytes) -> RawInput[bytes]:
    return RawInput(
        payload=data,
        source_urls=(canon.SOURCE_URL,),
        source_sha256=sha256_bytes(data),
        retrieved_at=FIXED_NOW,
        snapshot_date=canon.OPENITI_COMMIT_DATE,
    )


def test_run_writes_the_separate_package(tmp_path: Path) -> None:
    """Req 1.1, 1.2, 3.1: the run is recorded with its licence and pinned version, and the
    derived files go to datasets/canon/ (not data/)."""
    ctx = _ctx(tmp_path)
    result = run_job(CanonJob(), ctx, _raw(SAMPLE))
    # Two headings instead of 844: the run is kept for review, not promoted.
    assert result.outcome is Outcome.NEEDS_REVIEW
    assert result.manifest.license == "CC BY-NC-SA 4.0"
    assert result.manifest.snapshot_date == canon.OPENITI_COMMIT_DATE
    CanonJob().on_promote(ctx, Store(ctx.data_dir, "canon"), result.run_id)
    pkg = ctx.repo_root / "datasets" / "canon"
    assert not (ctx.repo_root / "data").exists()
    entries = list(csv.DictReader((pkg / "entries.csv").open(encoding="utf-8")))
    spans = list(csv.DictReader((pkg / "theme_spans.csv").open(encoding="utf-8")))
    assert [e["heading"] for e in entries] == [BOOK2_TITLE, "حناء"]
    assert entries[1]["page"] == "V01P474" and entries[1]["themes"] == "burn"
    assert spans[0]["entry_id"] == entries[1]["entry_id"]
    assert "حرق النار" in spans[0]["arabic_span"]
    source = json.loads((pkg / "source.json").read_text(encoding="utf-8"))
    assert source["commit"] == canon.OPENITI_COMMIT and source["license"] == "CC BY-NC-SA 4.0"


def test_fetch_refuses_another_version(tmp_path: Path) -> None:
    """Req 1.1: only the pinned OpenITI file is accepted (git blob hash)."""
    f = tmp_path / "other.txt"
    f.write_bytes(SAMPLE)
    ctx = _ctx(tmp_path)
    ctx.options["input"] = str(f)
    assert git_blob_sha1(SAMPLE) != canon.BLOB_SHA1
    with pytest.raises(SourceVersionError):
        CanonJob().fetch(ctx)
