"""Formatting per language: P13 (pure part) (doctor-loop design §5.3)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.notes import render
from janus.notes.templates import CATALOGUE

LANGS = ("en", "tr", "de", "fr", "es")


def parse_back(text: str, lang: str) -> Decimal:
    body = text.lstrip("<>")
    body = body.replace(render.GROUP[lang], "")
    return Decimal(body.replace(render.DECIMAL[lang], "."))


@given(n=st.integers(0, 10**12), lang=st.sampled_from(LANGS))
def test_p13_integers(n: int, lang: str) -> None:
    """Feature: doctor-loop, Property P13 (integers). Validates Req 5.2."""
    text = render.format_int(n, lang)
    assert parse_back(text, lang) == n
    assert render.numerals(text) == [text]


@given(x=st.floats(min_value=0, max_value=1e7, allow_nan=False), lang=st.sampled_from(LANGS))
def test_p13_ratios(x: float, lang: str) -> None:
    """Feature: doctor-loop, Property P13 (ratios). Validates Req 5.2."""
    text = render.format_ratio(x, lang)
    assert len(render.numerals(text)) == 1
    value = parse_back(text, lang)
    if text.startswith("<"):
        assert x <= 0.005 and value == Decimal("0.01")
    elif text.startswith(">"):
        assert x >= 1000 and value == 1000
    else:
        assert abs(value - Decimal(repr(x))) <= Decimal("0.5")
        assert abs(value - Decimal(repr(x))) <= max(Decimal("0.005"), Decimal(repr(x)) / 100)


@given(
    d=st.decimals(min_value=0, max_value=100, places=1, allow_nan=False, allow_infinity=False),
    lang=st.sampled_from(LANGS),
)
def test_p13_percent_and_decimal_text(d: Decimal, lang: str) -> None:
    """Feature: doctor-loop, Property P13 (published decimals). Validates Req 5.2."""
    text = render.format_decimal(d, lang)
    assert parse_back(text, lang) == d
    assert render.numerals(render.format_percent(d, lang)) == [text]


@pytest.mark.parametrize(
    ("lang", "integer", "ratio", "percent", "month", "date"),
    [
        ("en", "12,345", "2.55", "11.9%", "03/2026", "2026-11-08"),
        ("tr", "12.345", "2,55", "%11,9", "03.2026", "08.11.2026"),
        ("de", "12.345", "2,55", "11,9\u00a0%", "03.2026", "08.11.2026"),
        ("fr", "12\u202f345", "2,55", "11,9\u202f%", "03/2026", "08/11/2026"),
        ("es", "12.345", "2,55", "11,9\u00a0%", "03/2026", "08/11/2026"),
    ],
)
def test_p13_hand_checked_examples(
    lang: str, integer: str, ratio: str, percent: str, month: str, date: str
) -> None:
    assert render.format_int(12345, lang) == integer
    assert render.format_ratio(2.551, lang) == ratio
    assert render.format_percent(Decimal("11.9"), lang) == percent
    assert render.format_month("2026-03", lang) == month
    assert render.format_date(dt.date(2026, 11, 8), lang) == date


def test_boundaries() -> None:
    assert render.format_int(1234, "es") == "1234"  # CLDR minimum grouping 2
    assert render.format_int(1234, "de") == "1.234"
    assert render.format_ratio(0.004, "en") == "<0.01"
    assert render.format_ratio(0.005, "en") == "<0.01"  # rounds (half-even) to 0.00
    assert render.format_ratio(0.0051, "en") == "0.01"
    assert render.format_ratio(9.995, "en") == "10.0"
    assert render.format_ratio(99.95, "de") == "100"
    assert render.format_ratio(999.6, "en") == "1,000"
    assert render.format_ratio(1000.0, "fr") == ">1\u202f000"
    assert render.format_ratio(12.25, "tr") == "12,2"  # half-even


@given(lang=st.sampled_from(LANGS), checked=st.integers(1, 65), total=st.integers(1, 65))
def test_p13_fill_numbers_are_the_parameters(lang: str, checked: int, total: int) -> None:
    spec = CATALOGUE["scope.checked"]
    text, numbers = render.fill(
        spec, "checked {checked} of {total}", {"checked": checked, "total": total}, lang
    )
    assert numbers == [render.format_int(checked, lang), render.format_int(total, lang)]
    assert not any(ch.isdigit() for ch in render.residue(text, numbers))
    with pytest.raises(ValueError):
        render.fill(spec, "x", {"checked": checked}, lang)
    with pytest.raises(TypeError):
        render.fill(spec, "x {checked} {total}", {"checked": "3", "total": total}, lang)
