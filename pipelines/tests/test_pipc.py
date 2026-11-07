"""Tests for the pipc job (P11 and examples). Synthetic XML only; no network."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from xml.sax.saxutils import escape

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.canonical import sha256_bytes
from janus_pipelines.core.manifest import Outcome
from janus_pipelines.core.registry import load_registry
from janus_pipelines.core.runner import RawInput, RunContext, run_job
from janus_pipelines.jobs.pipc import (
    KINDS,
    Cascade,
    PipcJob,
    collapse,
    find_table,
    parse_table,
)
from tests.stub_job import FIXED_NOW

REPO = Path(__file__).resolve().parents[2]
_KIND_LABEL = {v: k for k, v in KINDS.items()}

CELL = (
    st.text(
        alphabet=st.sampled_from([*"abcdefghijklmnopqrstuvwxyzABCDE /-(),.'&<>\n\t", "é"]),
        min_size=1,
        max_size=25,
    )
    .filter(lambda s: collapse(s) != "")
    .filter(lambda s: collapse(s) not in KINDS)
)


@st.composite
def tables(draw: st.DrawFn) -> tuple[list[Cascade], list[tuple[str, str, str, int]]]:
    """A Table-1-like structure: systems → kinds → cascades, each maybe split over two rows.

    Returns the expected cascades and a flat row plan: (a, ae, b, split) with section
    markers encoded as ("§system", name, "", 0) / ("§kind", label, "", 0).
    """
    cascades: list[Cascade] = []
    plan: list[tuple[str, str, str, int]] = []
    for _ in range(draw(st.integers(1, 4))):
        system = draw(CELL)
        plan.append(("§system", system, "", 0))
        for kind in draw(st.lists(st.sampled_from(list(_KIND_LABEL)), min_size=1, max_size=2)):
            plan.append(("§kind", _KIND_LABEL[kind], "", 0))
            for _ in range(draw(st.integers(1, 6))):
                a, ae, b = draw(CELL), draw(CELL), draw(CELL)
                split = draw(st.sampled_from([0, 0, 0, 1, 2]))
                plan.append((a, ae, b, split))
                cascades.append(
                    Cascade(collapse(system), kind, collapse(a), collapse(ae), collapse(b))
                )
    return cascades, plan


def _td(text: str, italic: bool = False) -> str:
    body = escape(text)
    return f"<td>{'<italic>' + body + '</italic>' if italic else body}</td>"


def render_xml(plan: list[tuple[str, str, str, int]], doi: str = "10.1/x") -> bytes:
    rows: list[str] = []
    for a, ae, b, split in plan:
        if a == "§system" or a == "§kind":
            rows.append(f"<tr>{_td(ae)}<td/><td/></tr>")
        elif split == 0:
            rows.append(f"<tr>{_td(a, italic=True)}{_td(ae)}{_td(b)}</tr>")
        elif split == 1:  # statin style: Drug A + adverse event, then Drug B alone
            rows.append(f"<tr>{_td(a)}{_td(ae)}</tr>")
            rows.append(f"<tr>{_td(b)}</tr>")
        else:  # same split, padded with an empty cell
            rows.append(f"<tr>{_td(a)}{_td(ae)}<td/></tr>")
            rows.append(f"<tr><td/>{_td(b)}<td/></tr>")
    body = "".join(rows)
    return (
        '<?xml version="1.0"?><article><front><article-meta>'
        f'<article-id pub-id-type="doi">{doi}</article-id>'
        "<pub-date><day>5</day><month>8</month><year>2025</year></pub-date>"
        '</article-meta></front><body><table-wrap id="Tab1"><label>Table 1</label><table>'
        "<thead><tr><th>Drug A</th><th>Adverse event</th><th>Drug B</th></tr></thead>"
        f"<tbody>{body}</tbody></table></table-wrap></body></article>"
    ).encode()


def _parse(xml: bytes) -> list[Cascade]:
    from defusedxml import ElementTree

    return parse_table(find_table(ElementTree.fromstring(xml))).cascades


@given(tables())
def test_parse_returns_generated_cascades(
    table: tuple[list[Cascade], list[tuple[str, str, str, int]]],
) -> None:
    """Feature: data-pipelines, Property P11 — Validates: Req 5.2, 5.3, 5.4.

    For any generated Table-1-like XML (systems, Drug Class / Individual Drug rows, cascades,
    some split over two <tr>), the parser returns exactly the generated cascades, in order,
    with the right system and kind; the 65-row check fails for any other count.
    """
    expected, plan = table
    xml = render_xml(plan)
    assert _parse(xml) == expected
    raw = _raw(xml)
    job = PipcJob()
    if len(expected) == 65:
        assert len(job.parse(raw).rows) == 65
    else:
        with pytest.raises(ValueError, match="expected 65 cascades"):
            job.parse(raw)


def _raw(xml: bytes) -> RawInput[bytes]:
    return RawInput(
        payload=xml,
        source_urls=("https://example.org/pipc",),
        source_sha256=sha256_bytes(xml),
        retrieved_at=FIXED_NOW,
        snapshot_date="2025-08-05",
    )


def _real_like_plan() -> list[tuple[str, str, str, int]]:
    """64 complete cascades plus the statin cascade split over two rows, as in PMC12712104."""
    plan: list[tuple[str, str, str, int]] = [
        ("§system", "Cardiovascular system", "", 0),
        ("§kind", "Drug Class", "", 0),
        ("Angiotensin converting enzyme inhibitor", "Cough", "Cough remedy", 0),
        (
            "Hydroxymethylglutaryl-coenzyme A (HMG Co-A) reductase inhibitor (statin)",
            "Myalgia/myositis",
            "Pain reliever",
            1,
        ),
    ]
    plan += [(f"Drug {i}", f"Event {i}", f"Treatment {i}", 0) for i in range(63)]
    return plan


def test_statin_split_row_merges() -> None:
    """Validates: Req 5.4, 5.3 — 64 complete rows + the split statin row = 65 cascades."""
    cascades = _parse(render_xml(_real_like_plan()))
    assert len(cascades) == 65
    statin = cascades[1]
    assert statin.adverse_event == "Myalgia/myositis"
    assert statin.drug_b == "Pain reliever"
    assert statin.system == "Cardiovascular system"
    assert statin.kind == "drug_class"


def test_missing_table_is_schema_failure(tmp_path: Path) -> None:
    xml = b"<article><body><p>no table</p></body></article>"
    result = run_job(PipcJob(), _ctx(tmp_path), _raw(xml))
    assert result.outcome is Outcome.FAILED
    assert result.error is not None and "Tab1" in result.error


def test_renamed_header_is_schema_failure(tmp_path: Path) -> None:
    xml = render_xml(_real_like_plan()).replace(b"<th>Adverse event</th>", b"<th>ADR</th>")
    result = run_job(PipcJob(), _ctx(tmp_path), _raw(xml))
    assert result.outcome is Outcome.FAILED
    assert result.error is not None and "Adverse event" in result.error


def _ctx(tmp_path: Path) -> RunContext:
    repo = tmp_path / "repo"
    (repo / "data").mkdir(parents=True)
    return RunContext(
        data_dir=tmp_path / "datadir",
        repo_root=repo,
        registry=load_registry(REPO / "pipelines" / "sources.toml"),
        code_version="test",
        now=lambda: FIXED_NOW,
        is_ignored=lambda _p: True,
    )


def test_promotion_writes_committed_csv_and_meta(tmp_path: Path) -> None:
    """Validates: Req 5.5, 5.6, 1.4."""
    ctx = _ctx(tmp_path)
    xml = render_xml(_real_like_plan(), doi="10.1007/S41999-025-01215-X")
    result = run_job(PipcJob(), ctx, _raw(xml))
    assert result.outcome is Outcome.SUCCEEDED, result.error
    assert result.error is None
    csv_path = ctx.repo_root / "data" / "pipc.csv"
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 65
    assert rows[0]["drug_a"] == "Angiotensin converting enzyme inhibitor"
    assert rows[1]["locator"] == "Table 1, row 2"
    meta = json.loads((ctx.repo_root / "data" / "pipc.meta.json").read_text(encoding="utf-8"))
    assert meta["doi"] == "10.1007/s41999-025-01215-x"
    assert meta["license"] == "CC BY 4.0"
    assert meta["content_sha256"] == result.manifest.content_sha256
    assert result.manifest.snapshot_date == "2025-08-05"
    assert result.manifest.counts.excluded["merged_into_previous"] == 1
