"""Tests for the `canon_gold` job (séance design §3.5): PMC3941892 name columns only."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from defusedxml import ElementTree
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.canonical import sha256_bytes
from janus_pipelines.core.registry import load_registry
from janus_pipelines.core.runner import RawInput, RunContext, run_job
from janus_pipelines.core.store import Store
from janus_pipelines.jobs.canon_gold import (
    CSV_COLUMNS,
    HEADER,
    CanonGoldJob,
    GoldShapeError,
    parse_tables,
)
from tests.stub_job import FIXED_NOW

REPO = Path(__file__).resolve().parents[2]
NAME = st.text(alphabet="abcdefghijklmnopqrstuvwxyz ABC.-()", min_size=1, max_size=20).filter(
    lambda s: s.strip() != ""
)


def _xml(tables: list[list[tuple[str, str, str]]]) -> bytes:
    def row(cells: tuple[str, ...], tag: str = "td") -> str:
        extra = "<td>temperament</td><td>effect text, not stored</td>"
        return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + extra + "</tr>"

    body = "".join(
        "<table-wrap><table>"
        + row(HEADER, "th")
        + "".join(row(r) for r in t)
        + "</table></table-wrap>"
        for t in tables
    )
    return f"<article><body>{body}</body></article>".encode()


@given(
    st.lists(st.lists(st.tuples(NAME, NAME, NAME), min_size=1, max_size=6), min_size=2, max_size=2)
)
def test_rows_are_the_name_columns_in_order(tables: list[list[tuple[str, str, str]]]) -> None:
    """P5 (Req 1.4): every data row becomes one gold row with the three name columns only."""
    rows, seen, excluded = parse_tables(ElementTree.fromstring(_xml(tables)))
    assert seen == sum(len(t) + 1 for t in tables)
    assert excluded == {"header_row": 2}
    flat = [r for t in tables for r in t]
    got = [(r["name_in_canon"], r["common_name"], r["scientific_name"]) for r in rows]
    assert got == [tuple(" ".join(c.split()) for c in r) for r in flat]
    assert all(set(r) == set(CSV_COLUMNS) for r in rows)


def test_wrong_table_count_is_refused() -> None:
    with pytest.raises(GoldShapeError):
        parse_tables(ElementTree.fromstring(_xml([[("a", "b", "c")]])))


def test_promotion_writes_committed_gold_table(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    ctx = RunContext(
        data_dir=tmp_path / "d",
        repo_root=repo,
        registry=load_registry(REPO / "pipelines" / "sources.toml"),
        code_version="test",
        now=lambda: FIXED_NOW,
        is_ignored=lambda _p: True,
    )
    data = _xml([[("AS", "Myrtle", "Myrtus communis L.")], [("Adas", "Lentil", "Lens")]])
    raw = RawInput(data, ("u",), sha256_bytes(data), FIXED_NOW, "2013-11-02")
    result = run_job(CanonGoldJob(), ctx, raw)
    assert result.manifest.license == "CC BY 3.0"
    out = repo / "data" / "canon_gold_pmc3941892.csv"
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert [r["gold_id"] for r in rows] == ["pmc3941892.t1.r01", "pmc3941892.t2.r01"]
    assert "effect" not in out.read_text(encoding="utf-8")
    assert Store(ctx.data_dir, "canon_gold").current_run_id() == result.run_id
