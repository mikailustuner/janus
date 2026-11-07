"""Property tests for GS1 parsing (drug-resolution design §8: P1, P2, P3, P9)."""

from __future__ import annotations

import calendar
from datetime import date

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from janus.resolution.gs1 import (
    GS,
    Gs1Data,
    Gs1Error,
    Gs1ErrorCode,
    parse_element_string,
    parse_expiry,
)
from tests.resolution_strategies import (
    CSET82,
    Gs1Fields,
    gs1_field_sets,
    gtin14s,
    render_fnc1,
    render_parenthesised,
    short_gtins,
    today_dates,
    valid_yymmdd,
    yymmdd,
)

TODAY = date(2026, 11, 7)


@given(
    f=gs1_field_sets(),
    identifier=st.sampled_from(["", "]d2", GS, "]d2" + GS]),
    gs_after_fixed=st.booleans(),
    today=today_dates(),
)
def test_separator_invariance(
    f: Gs1Fields, identifier: str, gs_after_fixed: bool, today: date
) -> None:
    """Feature: drug-resolution, Property P1. Validates Req 1.1.

    The FNC1 form (with or without symbology identifier, any AI order, optional GS after fixed
    fields) and the parenthesised form of the same fields parse to the same result.
    """
    fnc1 = render_fnc1(f, identifier=identifier, gs_after_fixed=gs_after_fixed)
    assert parse_element_string(fnc1, today) == parse_element_string(render_parenthesised(f), today)


@given(gtin=gtin14s(), pos=st.integers(0, 13), delta=st.integers(1, 9))
def test_changed_digit_rejected(gtin: str, pos: int, delta: int) -> None:
    """Feature: drug-resolution, Property P2. Validates Req 1.2 (single-digit change)."""
    digit = (int(gtin[pos]) + delta) % 10
    bad = gtin[:pos] + str(digit) + gtin[pos + 1 :]
    for content in (f"01{bad}", f"(01){bad}", bad):
        with pytest.raises(Gs1Error) as exc:
            parse_element_string(content, TODAY)
        assert exc.value.code is Gs1ErrorCode.GTIN_CHECK_DIGIT


@given(gtin=gtin14s(), pos=st.integers(0, 12))
def test_adjacent_swap_rejected(gtin: str, pos: int) -> None:
    """Feature: drug-resolution, Property P2. Validates Req 1.2 (adjacent transposition).

    Mod-10 with weights 3,1 misses a swap only when the two digits differ by 5.
    """
    a, b = gtin[pos], gtin[pos + 1]
    assume(a != b and abs(int(a) - int(b)) != 5)
    bad = gtin[:pos] + b + a + gtin[pos + 2 :]
    with pytest.raises(Gs1Error) as exc:
        parse_element_string(f"(01){bad}", TODAY)
    assert exc.value.code is Gs1ErrorCode.GTIN_CHECK_DIGIT


@given(short=short_gtins())
def test_short_gtins_padded(short: str) -> None:
    """Feature: drug-resolution, Property P2. Valid GTIN-8/12/13 are accepted as GTIN-14."""
    data = parse_element_string(short, TODAY)
    assert data.gtin14 == short.zfill(14)
    assert (data.expiry_status, data.serial_present, data.lot_present) == ("absent", False, False)


@given(
    gtin=gtin14s(),
    expiry=valid_yymmdd(),
    lot=st.text(alphabet=CSET82, min_size=1, max_size=20),
    serial=st.text(alphabet=CSET82, min_size=1, max_size=20),
    order=st.permutations(["01", "17", "10", "21"]),
)
def test_round_trip(gtin: str, expiry: str, lot: str, serial: str, order: list[str]) -> None:
    """Feature: drug-resolution, Property P3. Validates Req 1.1, 1.3.

    Building an FNC1 element string from (GTIN, expiry, lot, serial) and parsing it returns the
    same GTIN and expiry; serial and lot are reported only as present.
    """
    values = {"01": gtin, "17": expiry, "10": lot, "21": serial}
    f = Gs1Fields(tuple((ai, values[ai]) for ai in order))
    data = parse_element_string(render_fnc1(f, identifier="]d2"), TODAY)
    assert data.gtin14 == gtin
    assert data.expiry == parse_expiry(expiry, TODAY)
    assert data.expiry_status == "valid"
    assert data.serial_present and data.lot_present
    assert set(Gs1Data.__dataclass_fields__) == {
        "gtin14",
        "expiry",
        "expiry_status",
        "serial_present",
        "lot_present",
    }


def _reference_year(yy: int, today: date) -> int:
    diff = yy - today.year % 100
    century = today.year // 100 + (-1 if diff >= 51 else 1 if diff <= -50 else 0)
    return century * 100 + yy


@given(value=yymmdd(), today=today_dates())
def test_expiry(value: str, today: date) -> None:
    """Feature: drug-resolution, Property P9. Validates Req 1.3.

    DD = 00 gives the month's last day; valid dates round-trip; impossible dates give None;
    the century follows the GS1 rule; the result is never more than ~50 years from today.
    """
    yy, mm, dd = int(value[:2]), int(value[2:4]), int(value[4:])
    year = _reference_year(yy, today)
    result = parse_expiry(value, today)
    if not 1 <= mm <= 12:
        assert result is None
        return
    last = calendar.monthrange(year, mm)[1]
    if dd == 0:
        assert result == date(year, mm, last)
    elif dd > last:
        assert result is None
    else:
        assert result == date(year, mm, dd)
        assert result is not None
        assert result.strftime("%y%m%d") == value
    assert -50 <= year - today.year <= 50


@given(gtin=gtin14s(), month=st.sampled_from(["00", "13", "99"]))
def test_invalid_expiry_still_resolves_gtin(gtin: str, month: str) -> None:
    """Feature: drug-resolution, Property P9. An impossible expiry does not block the GTIN."""
    data = parse_element_string(f"(01){gtin}(17)28{month}15", TODAY)
    assert data.gtin14 == gtin
    assert (data.expiry, data.expiry_status) == (None, "invalid")


def test_examples() -> None:
    amlipin = "08680199094206"
    data = parse_element_string(f"]d201{amlipin}17280500{GS}10AB12{GS}21XYZ", TODAY)
    assert data.gtin14 == amlipin
    assert data.expiry == date(2028, 5, 31)
    with pytest.raises(Gs1Error) as exc:
        parse_element_string("(01)08680199094206(99)1", TODAY)
    assert exc.value.code is Gs1ErrorCode.UNKNOWN_AI
    with pytest.raises(Gs1Error) as exc:
        parse_element_string("(10)AB(21)CD", TODAY)
    assert exc.value.code is Gs1ErrorCode.GTIN_MISSING
    with pytest.raises(Gs1Error) as exc:
        parse_element_string(f"01{amlipin}21A{GS}21B", TODAY)
    assert exc.value.code is Gs1ErrorCode.DUPLICATE_AI
    with pytest.raises(Gs1Error) as exc:
        parse_element_string(f"01{amlipin}21" + "A" * 21, TODAY)
    assert exc.value.code is Gs1ErrorCode.FIELD_LENGTH


@given(content=st.text(max_size=60))
def test_errors_never_contain_input(content: str) -> None:
    """Error messages are fixed codes (Req 8.4)."""
    try:
        parse_element_string(content, TODAY)
    except Gs1Error as exc:
        assert str(exc) in {c.value for c in Gs1ErrorCode}
