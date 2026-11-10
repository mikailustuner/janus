"""Tests for the `ca_dpd` and `eu_it_aifa` jobs (national-products Req 2). Synthetic files only."""

from __future__ import annotations

import csv
import io
import zipfile

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.validation import SchemaMismatchError
from janus_pipelines.jobs import ca_dpd, eu_it_aifa

CELL = st.text(alphabet="abcXYZ 0123-,.%", max_size=12)
DIN = st.text(alphabet="0123456789", min_size=8, max_size=8)


def dpd_files(drugs: list[list[str]], **extra: list[list[str]]) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for name, width in ca_dpd.COLUMNS.items():
        rows = drugs if name == ca_dpd.DRUG else extra.get(name, [])
        buf = io.StringIO()
        csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n").writerows(rows)
        out[name] = buf.getvalue().encode()
        assert all(len(r) == width for r in rows)
    return out


def drug(code: str, din: str, cls: str = "Human", brand: str = "BRAND") -> list[str]:
    row = [""] * 14
    row[0], row[2], row[3], row[4] = code, cls, din, brand
    return row


def ingredient(code: str, name: str, strength: str = "5", unit: str = "MG") -> list[str]:
    row = [""] * 15
    row[0], row[1], row[2], row[4], row[5] = code, "1", name, strength, unit
    return row


def test_dpd_joins_tables_and_measures_upc() -> None:
    package = [""] * 8
    package[0] = "10"
    files = dpd_files(
        [drug("10", "00012345"), drug("11", "bad")],
        ingred=[ingredient("10", "AMLODIPINE")],
        package=[package],
    )
    out = ca_dpd.parse_dpd(files)
    assert [r["din"] for r in out.rows] == ["00012345", None]
    assert [r["name_only"] for r in out.rows] == [False, True]
    assert out.rows[0]["ingredients"][0]["name"] == "AMLODIPINE"  # type: ignore[index]
    assert out.metrics["package_lines_with_upc"] == 0
    assert out.metrics["package_lines_with_upc_share"] == 0.0


def test_dpd_duplicate_drug_code_is_refused() -> None:
    with pytest.raises(ValueError):
        ca_dpd.parse_dpd(dpd_files([drug("10", "00012345"), drug("10", "00012346")]))


def test_dpd_wrong_column_count_fails_by_name() -> None:
    files = dpd_files([drug("10", "00012345")])
    files["form"] = b'"1","2","3"\r\n' * 3
    with pytest.raises(SchemaMismatchError):
        ca_dpd.parse_dpd(files)


def test_dpd_archive_member_missing() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("drug.txt", "")
    with pytest.raises(SchemaMismatchError):
        ca_dpd.unzip(buf.getvalue())
    with pytest.raises(SchemaMismatchError):
        ca_dpd.unzip(b"not a zip")


@given(st.lists(st.tuples(DIN, CELL), max_size=8, unique_by=lambda t: t[0]))
def test_dpd_accounting_one_row_per_drug(items: list[tuple[str, str]]) -> None:
    drugs = [drug(str(i + 1), din, brand=name) for i, (din, name) in enumerate(items)]
    out = ca_dpd.parse_dpd(dpd_files(drugs))
    assert len(out.rows) == len(drugs) == out.input_rows
    assert [r["brand_name"] for r in out.rows] == [n for _, n in items]


def aifa_files(packs: list[list[str]], ingredients: list[list[str]]) -> dict[str, bytes]:
    def blob(header: tuple[str, ...], rows: list[list[str]]) -> bytes:
        return "\r\n".join(";".join(r) for r in [list(header), *rows]).encode() + b"\r\n"

    return {
        eu_it_aifa.PACKS: blob(eu_it_aifa.HEADERS[eu_it_aifa.PACKS], packs),
        eu_it_aifa.INGREDIENTS: blob(eu_it_aifa.HEADERS[eu_it_aifa.INGREDIENTS], ingredients),
    }


def pack(aic: str, name: str = "DRUG", atc: str = "C08CA01") -> list[str]:
    row = [""] * 13
    row[0], row[3], row[9], row[10] = aic, name, "compressa", atc
    return row


def test_aifa_joins_ingredients_and_flags_bad_aic() -> None:
    files = aifa_files(
        [pack("012345678"), pack("12")],
        [["012345678", "AMLODIPINA", "5", "mg"], ["999999999", "X", "", ""]],
    )
    out = eu_it_aifa.parse_aifa(files)
    assert [r["aic"] for r in out.rows] == ["012345678", None]
    assert out.rows[0]["ingredients"] == [  # type: ignore[comparison-overlap]
        {"name": "AMLODIPINA", "quantity": "5", "unit": "mg"}
    ]
    assert out.rows[1]["ingredients"] == []
    assert out.metrics["ingredient_lines_of_unlisted_packs"] == 1


def test_aifa_header_mismatch_fails_by_name() -> None:
    files = aifa_files([pack("012345678")], [])
    files[eu_it_aifa.PACKS] = b"A;B\r\n1;2\r\n"
    with pytest.raises(SchemaMismatchError):
        eu_it_aifa.parse_aifa(files)


def test_aifa_malformed_line_is_counted_not_guessed() -> None:
    files = aifa_files([pack("012345678")], [])
    files[eu_it_aifa.PACKS] += b"too;few\r\n"
    out = eu_it_aifa.parse_aifa(files)
    assert len(out.rows) == 1
    assert out.input_rows == 2
    assert sum(out.excluded.values()) == 1


@given(st.lists(st.text(alphabet="0123456789", min_size=9, max_size=9), max_size=8, unique=True))
def test_aifa_one_row_per_pack(aics: list[str]) -> None:
    out = eu_it_aifa.parse_aifa(aifa_files([pack(a) for a in aics], []))
    assert [r["aic"] for r in out.rows] == aics


def test_aifa_last_modified_date() -> None:
    assert eu_it_aifa.last_modified_date("x", "Tue, 10 Nov 2026 03:00:00 GMT") == "2026-11-10"
    with pytest.raises(SchemaMismatchError):
        eu_it_aifa.last_modified_date("x", None)
