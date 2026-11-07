"""Tests for the titck job (P4, P6, P12 and examples). Workbooks are generated in memory."""

from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from janus_pipelines.core.canonical import sha256_bytes
from janus_pipelines.core.manifest import Outcome
from janus_pipelines.core.registry import load_registry
from janus_pipelines.core.runner import RawInput, RunContext, run_job
from janus_pipelines.core.store import Store
from janus_pipelines.jobs.titck import (
    TitckJob,
    date_from_name,
    ean13_valid,
    newest_list_link,
    parse_workbook,
    split_ingredients,
)
from tests.stub_job import FIXED_NOW
from tests.titck_workbooks import HEADER, SpecRow, build_workbook, ean13, spec_rows

REPO = Path(__file__).resolve().parents[2]

# --- P12: ingredient split -----------------------------------------------------------

SEPARATORS = st.sampled_from([",", ", ", " ,", ";", "; ", "/", " / ", "+", " + ", " ve ", "  ve\t"])
NAME_CHARS = st.sampled_from(list("abcçdefgğhıijklmnoöprsştuüvyzİIÇŞĞÜÖ0123456789%-.'"))
WORD = st.text(alphabet=NAME_CHARS, min_size=1, max_size=8).filter(lambda w: w != "ve")
# A parenthesised part may itself contain separators; they must not split (titck-2, DP10).
PAREN = st.lists(WORD, min_size=1, max_size=3).flatmap(
    lambda ws: st.lists(SEPARATORS, min_size=len(ws) - 1, max_size=len(ws) - 1).map(
        lambda seps: "(" + "".join(w + s for w, s in zip(ws, [*seps, ""], strict=True)) + ")"
    )
)
NAME = (
    st.lists(st.one_of(WORD, WORD, PAREN), min_size=1, max_size=3)
    .map(" ".join)
    .filter(lambda n: n == n.strip())
)
_STANDALONE_VE = re.compile(r"(^|\s)ve(\s|$)")


@given(st.lists(NAME, min_size=1, max_size=5), st.data())
def test_split_returns_joined_names(names: list[str], data: st.DataObject) -> None:
    """Feature: data-pipelines, Property P12 — Validates: Req 6.6.

    For 1-5 names without separators, joined by any mix of the observed separators and
    spacing, split_ingredients returns exactly those names.
    """
    text = names[0]
    for name in names[1:]:
        text += data.draw(SEPARATORS) + name
    lead, trail = data.draw(st.sampled_from(["", " ", "\t"])), data.draw(st.sampled_from(["", " "]))
    assert split_ingredients(lead + text + trail) == names


def test_no_split_inside_parentheses() -> None:
    """titck-2 (drug-resolution DP10): the observed polio-vaccine text stays one name."""
    text = "difteri toksoidi, inaktif çocuk felci (tip 1, 2, 3), tetanoz"
    assert split_ingredients(text) == [
        "difteri toksoidi",
        "inaktif çocuk felci (tip 1, 2, 3)",
        "tetanoz",
    ]
    assert split_ingredients("a (b, c") == ["a (b, c"]  # unclosed: no split after "("
    assert split_ingredients("a) , b") == ["a)", "b"]  # stray ")" does not go below zero


def test_separator_runs_split_once() -> None:
    """Regression for the P12 counterexample `", ve "`."""
    assert split_ingredients("x, ve y") == ["x", "y"]
    assert split_ingredients(", ve ") == []
    assert split_ingredients("dove, vega ve x") == ["dove", "vega", "x"]


FRAGMENT = st.text(
    alphabet=st.characters(categories=["L", "N", "P", "S", "Zs"], exclude_characters=",;/+()"),
    max_size=12,
).filter(lambda f: not _STANDALONE_VE.search(f))


@given(st.lists(st.one_of(FRAGMENT, FRAGMENT, PAREN), min_size=1, max_size=6), st.data())
def test_split_keeps_every_non_separator_character(
    fragments: list[str], data: st.DataObject
) -> None:
    """Feature: data-pipelines, Property P12 — Validates: Req 6.6.

    For any text made of fragments and separators, the non-whitespace characters of the
    fragments are exactly the non-whitespace characters of the split names. Fragments may be
    parenthesised groups that contain separators; those separators are kept (titck-2).
    """
    text = fragments[0]
    for f in fragments[1:]:
        text += data.draw(SEPARATORS) + f
    parts = split_ingredients(text)

    def chars(items: list[str]) -> Counter[str]:
        return Counter(c for s in items for c in s if not c.isspace())

    assert chars(parts) == chars(fragments)
    assert all(p == p.strip() and p for p in parts)


# --- P6 / P4: metrics and row accounting on generated workbooks ----------------------


def _expected_metrics(spec: list[SpecRow]) -> dict[str, int]:
    out = [r for r in spec if r.kind in ("product", "name_only")]
    barcodes = Counter(str(r.barcode) for r in out if r.kind == "product")
    return {
        "output_rows": len(out),
        "rows_with_atc": sum(1 for r in out if r.atc),
        "multi_ingredient_products": sum(1 for r in out if len(r.ingredients) >= 2),
        "duplicate_barcodes": sum(1 for n in barcodes.values() if n > 1),
        "rows_with_duplicate_barcode": sum(n for n in barcodes.values() if n > 1),
        "name_only_rows": sum(1 for r in spec if r.kind == "name_only"),
    }


@settings(max_examples=60)
@given(spec_rows())
def test_metrics_equal_recount(spec: list[SpecRow]) -> None:
    """Feature: data-pipelines, Property P6 — Validates: Req 2.3, 6.4, 6.5.

    ATC share, multi-ingredient products, duplicate barcodes and name-only rows equal a direct
    recount of the generated rows; duplicate barcodes are all kept.
    """
    result = parse_workbook(build_workbook(spec))
    expected = _expected_metrics(spec)
    for key, value in expected.items():
        assert result.metrics[key] == value, key
    out = expected["output_rows"]
    share = round(expected["rows_with_atc"] / out, 4) if out else 0.0
    assert result.metrics["atc_share"] == share


@settings(max_examples=60)
@given(spec_rows())
def test_row_accounting_titck(spec: list[SpecRow]) -> None:
    """Feature: data-pipelines, Property P4 (titck) — Validates: Req 1.5, 6.4.

    input rows == output rows + excluded rows, with the right reason for each exclusion,
    and the product rows come out in order with their fields. Rows with an invalid barcode are
    output as name-only rows (barcode null), never excluded and never repaired (titck-2).
    """
    result = parse_workbook(build_workbook(spec))
    assert result.input_rows == len(spec)
    assert result.input_rows == len(result.rows) + sum(result.excluded.values())
    assert result.excluded.get("blank_row", 0) == sum(1 for r in spec if r.kind == "blank")
    assert "invalid_barcode" not in result.excluded
    out = [r for r in spec if r.kind in ("product", "name_only")]
    want = [str(p.barcode) if p.kind == "product" else None for p in out]
    assert [r["barcode"] for r in result.rows] == want
    assert [r["name_only"] for r in result.rows] == [p.kind == "name_only" for p in out]
    assert [r["product_name"] for r in result.rows] == [p.name for p in out]
    assert [r["ingredients"] for r in result.rows] == [list(p.ingredients) for p in out]


# --- examples -----------------------------------------------------------------------

AMLIPIN_BARCODE = ean13("868019909420")


def test_amlipin_splits_into_two_ingredients() -> None:
    """Validates: Req 6.3, 6.6, 6.8 — combination ATC kept as published."""
    spec = [
        SpecRow(
            "product",
            barcode=int(AMLIPIN_BARCODE),
            name="AMLIPIN 10 / 10 MG FILM TABLET, 30 ADET",
            ingredients=("amlodipin besilat", "lisinopril dihidrat"),
            separator="/",
            atc="C09BB03",
        )
    ]
    row = parse_workbook(build_workbook(spec)).rows[0]
    assert row["ingredient_text"] == "amlodipin besilat/lisinopril dihidrat"
    assert row["ingredients"] == ["amlodipin besilat", "lisinopril dihidrat"]
    assert row["atc_code"] == "C09BB03"
    assert row["barcode"] == AMLIPIN_BARCODE
    assert row["suspension_status"] == 0


def test_ean13() -> None:
    assert ean13_valid("8699508010752")  # check digit of a published barcode format
    assert not ean13_valid("8699508010753")
    assert not ean13_valid("869950801075")
    assert not ean13_valid("８６９９５０８０１０７５２")  # noqa: RUF001 - full-width digits


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(
        data_dir=tmp_path / "data_dir",
        repo_root=tmp_path / "repo",
        registry=load_registry(REPO / "pipelines" / "sources.toml"),
        code_version="test",
        now=lambda: FIXED_NOW,
        is_ignored=lambda _p: True,
    )


def _raw(data: bytes) -> RawInput[bytes]:
    return RawInput(
        payload=data,
        source_urls=("https://www.titck.gov.tr/dinamikmodul/85",),
        source_sha256=sha256_bytes(data),
        retrieved_at=FIXED_NOW,
        snapshot_date="2026-11-06",
    )


def test_missing_column_fails_and_names_it(tmp_path: Path) -> None:
    """Validates: Req 2.1, 6.2."""
    header = [h if h != "ATC KODU" else "ATC" for h in HEADER]
    spec = [SpecRow("product", barcode=AMLIPIN_BARCODE, name="A", ingredients=("b",))]
    result = run_job(TitckJob(), _ctx(tmp_path), _raw(build_workbook(spec, header=header)))
    assert result.outcome is Outcome.FAILED
    assert result.error is not None and "ATC KODU" in result.error


def test_missing_sheet_fails(tmp_path: Path) -> None:
    spec = [SpecRow("product", barcode=AMLIPIN_BARCODE, name="A", ingredients=("b",))]
    result = run_job(TitckJob(), _ctx(tmp_path), _raw(build_workbook(spec, sheet="Other")))
    assert result.outcome is Outcome.FAILED
    assert result.error is not None and "sheet" in result.error


def test_retyped_barcode_fails(tmp_path: Path) -> None:
    # openpyxl reads whole floats back as int, so use a fractional value.
    spec = [SpecRow("product", barcode=1.5, name="A", ingredients=("b",))]  # type: ignore[arg-type]
    result = run_job(TitckJob(), _ctx(tmp_path), _raw(build_workbook(spec)))
    assert result.outcome is Outcome.FAILED
    assert result.error is not None and "BARKOD" in result.error


def test_runtime_only_keeps_no_raw_copy(tmp_path: Path) -> None:
    """Validates: Req 6.7 — no raw/ copy of the list, artifacts only in the data dir."""
    spec = [SpecRow("product", barcode=AMLIPIN_BARCODE, name="A", ingredients=("b",))]
    ctx = _ctx(tmp_path)
    result = run_job(TitckJob(), ctx, _raw(build_workbook(spec)))
    assert result.outcome is Outcome.SUCCEEDED
    assert not (ctx.data_dir / "raw").exists()
    assert Store(ctx.data_dir, "titck").current_run_id() == result.run_id


def test_dates_and_links() -> None:
    assert date_from_name("ruhsatli_06112026.xlsx") == "2026-11-06"
    assert date_from_name("Liste 30.10.2026.xlsx") == "2026-10-30"
    assert date_from_name("liste.xlsx") is None
    html = (
        '<a href="/storage/a/ruhsatli_30102026.xlsx">30.10.2026</a>'
        '<a href="/storage/a/ruhsatli_06112026.xlsx">06.11.2026</a>'
        '<a href="/x.pdf">pdf</a>'
    )
    url, date = newest_list_link(html, "https://www.titck.gov.tr/dinamikmodul/85")
    assert url == "https://www.titck.gov.tr/storage/a/ruhsatli_06112026.xlsx"
    assert date == "2026-11-06"


@pytest.mark.skipif(not os.environ.get("JANUS_TITCK_LIST"), reason="JANUS_TITCK_LIST not set")
def test_local_titck_list() -> None:
    """Optional integration test against a local TİTCK list (Req 6.1, 6.2). Not run in CI."""
    path = Path(os.environ["JANUS_TITCK_LIST"])
    result = parse_workbook(path.read_bytes())
    assert result.input_rows == len(result.rows) + sum(result.excluded.values())
    assert int(str(result.metrics["output_rows"])) > 20000
    amlipin = [r for r in result.rows if str(r["product_name"]).startswith("AMLIPIN 10 / 10")]
    assert amlipin
    assert amlipin[0]["ingredients"] == ["amlodipin besilat", "lisinopril dihidrat"]
