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
    national=st.text(alphabet="0123456789", min_size=7, max_size=7),
    order=st.permutations(["01", "17", "10", "712"]),
)
def test_round_trip(gtin: str, expiry: str, lot: str, national: str, order: list[str]) -> None:
    """Feature: drug-resolution, Property P3. Validates Req 1.1, 1.3.

    Building an FNC1 element string from (GTIN, expiry, lot, AI 712) and parsing it returns the
    same GTIN and expiry and the national code; the lot is reported only as present.
    """
    values = {"01": gtin, "17": expiry, "10": lot, "712": national}
    f = Gs1Fields(tuple((ai, values[ai]) for ai in order))
    data = parse_element_string(render_fnc1(f, identifier="]d2"), TODAY)
    assert data.gtin14 == gtin
    assert data.expiry == parse_expiry(expiry, TODAY)
    assert data.expiry_status == "valid"
    assert data.lot_present and not data.serial_present
    assert data.national_code == national
    assert set(Gs1Data.__dataclass_fields__) == {
        "gtin14",
        "expiry",
        "expiry_status",
        "serial_present",
        "lot_present",
        "national_code",
    }


@given(
    gtin=gtin14s(),
    national=st.one_of(
        st.text(alphabet="0123456789", min_size=1, max_size=6),
        st.text(alphabet="0123456789", min_size=8, max_size=20),
        st.text(alphabet="ABCDEFG", min_size=7, max_size=7),
    ),
    form=st.sampled_from(["paren", "fnc1"]),
)
def test_bad_national_code_is_dropped(gtin: str, national: str, form: str) -> None:
    """Feature: drug-resolution, Property P50 (AI 712 part). Validates Req 1.1.

    An AI (712) value that is not exactly 7 digits is dropped; the GTIN still resolves.
    """
    f = Gs1Fields((("01", gtin), ("712", national)))
    content = render_parenthesised(f) if form == "paren" else render_fnc1(f)
    data = parse_element_string(content, TODAY)
    assert data.gtin14 == gtin
    assert data.national_code is None


@given(
    gtin=gtin14s(),
    serial=st.text(alphabet=CSET82, min_size=1, max_size=25),
    others=st.lists(st.sampled_from(["10", "17", "712"]), unique=True, max_size=3),
    position=st.integers(0, 3),
    form=st.sampled_from(["paren", "fnc1"]),
    identifier=st.sampled_from(["", "]d2"]),
)
def test_serial_is_rejected(
    gtin: str, serial: str, others: list[str], position: int, form: str, identifier: str
) -> None:
    """Feature: drug-resolution, Property P50. Validates Req 1.4 (owner decision 2026-11-08).

    An element string that carries AI (21), in either form and at any position, is rejected with
    the fixed code and the error never contains the serial. The serial is not validated: even
    a value with a bad length or characters gives the same code.
    """
    sample = {"10": "LOT1", "17": "280531", "712": "6543217"}
    fields: list[tuple[str, str]] = [("01", gtin)] + [(ai, sample[ai]) for ai in others]
    fields.insert(min(position, len(fields)), ("21", serial))
    f = Gs1Fields(tuple(fields))
    if form == "paren":
        assume("(" not in serial and ")" not in serial)
        content = render_parenthesised(f)
    else:
        content = render_fnc1(f, identifier=identifier)
    with pytest.raises(Gs1Error) as exc:
        parse_element_string(content, TODAY)
    assert exc.value.code is Gs1ErrorCode.SERIAL_NOT_ACCEPTED
    assert str(exc.value) == "gs1_serial_not_accepted"  # a fixed code, nothing of the input


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
    data = parse_element_string(f"]d201{amlipin}17280500{GS}10AB12", TODAY)
    assert data.gtin14 == amlipin
    assert data.expiry == date(2028, 5, 31)
    with pytest.raises(Gs1Error) as serial_exc:  # the serial of a real box never reaches us
        parse_element_string(f"]d201{amlipin}17280500{GS}10AB12{GS}21XYZ", TODAY)
    assert serial_exc.value.code is Gs1ErrorCode.SERIAL_NOT_ACCEPTED
    with pytest.raises(Gs1Error) as exc:
        parse_element_string("(01)08680199094206(99)1", TODAY)
    assert exc.value.code is Gs1ErrorCode.UNKNOWN_AI
    with pytest.raises(Gs1Error) as exc:
        parse_element_string("(10)AB(11)010101", TODAY)
    assert exc.value.code is Gs1ErrorCode.GTIN_MISSING
    with pytest.raises(Gs1Error) as exc:
        parse_element_string(f"01{amlipin}10A{GS}10B", TODAY)
    assert exc.value.code is Gs1ErrorCode.DUPLICATE_AI
    with pytest.raises(Gs1Error) as exc:
        parse_element_string(f"01{amlipin}10" + "A" * 21, TODAY)
    assert exc.value.code is Gs1ErrorCode.FIELD_LENGTH


@given(content=st.text(max_size=60))
def test_errors_never_contain_input(content: str) -> None:
    """Error messages are fixed codes (Req 8.4)."""
    try:
        parse_element_string(content, TODAY)
    except Gs1Error as exc:
        assert str(exc) in {c.value for c in Gs1ErrorCode}
