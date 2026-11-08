"""Strength codes (medication-passport design §5.1; task 2.1).

Feature: medication-passport, Property P5. Validates Req 6.3, 6.4: equal quantities give equal
codes; unsupported units, homeopathic units, non-terminating divisions and out-of-range amounts
give `None`; Nomenclátor and TİTCK always `None`; BDPM only for countable forms; the function never
raises and every code matches the request pattern. The expected values come from a reference
written with `decimal.Decimal`, independent of the `Fraction` path of the module.
"""

from __future__ import annotations

import re
from decimal import Decimal, localcontext
from fractions import Fraction

from hypothesis import given
from hypothesis import strategies as st

from janus.passport.forms import COUNTABLE_GROUPS, GROUPS
from janus.passport.strength import StrengthCode, strength_code

PATTERN = re.compile(r"^(0|[1-9][0-9]{0,8})(\.[0-9]{0,5}[1-9])?$")  # requirements 5.1
SOURCES = ("titck", "openfda_ndc", "eu_fr_bdpm", "eu_es_cima")
MASS = {"kg": 10**9, "g": 10**6, "mg": 10**3, "ug": 1, "mcg": 1}
FR_MASS = {"g": 10**6, "mg": 10**3, "microgrammes": 1, "microgramme": 1, "µg": 1}
COUNTABLE = sorted(COUNTABLE_GROUPS)
NOT_COUNTABLE = sorted(set(GROUPS) - COUNTABLE_GROUPS)

# A decimal as a (digits, places) pair: digits / 10**places.
decimals = st.tuples(st.integers(min_value=1, max_value=10**7), st.integers(0, 4))


def text_of(d: tuple[int, int]) -> str:
    digits, places = d
    if places == 0:
        return str(digits)
    s = str(digits).rjust(places + 1, "0")
    return f"{s[:-places]}.{s[-places:]}"


def value_of(d: tuple[int, int]) -> Decimal:
    return Decimal(d[0]).scaleb(-d[1])


def reference(amount: Decimal, unit: str, basis: str) -> StrengthCode | None:
    """Independent reference: exact decimal division, six places at most, request pattern."""
    with localcontext() as ctx:
        ctx.prec = 60
        if amount <= 0 or (amount * 10**6) != (amount * 10**6).to_integral_value():
            return None
        text = format(amount.normalize(), "f")
    return StrengthCode(text, unit, basis) if PATTERN.fullmatch(text) else None  # pyright: ignore[reportArgumentType]


def us_ref(
    a: tuple[int, int], unit: str, n: tuple[int, int] | None, du: str | None
) -> StrengthCode | None:
    factor = 1 if unit in ("[iU]", "[IU]") else MASS[unit]
    code_unit = "IU" if factor == 1 and unit.startswith("[") else "ug"
    with localcontext() as ctx:
        ctx.prec = 60
        if du is None:
            if n is None or value_of(n) != 1:
                return None
            return reference(value_of(a) * factor, code_unit, "unit")
        denominator = value_of(n) if n is not None else Decimal(1)
        quotient = value_of(a) * factor / denominator
        if quotient * denominator != value_of(a) * factor:  # inexact at 60 digits: never a code
            return None
        return reference(quotient, code_unit, "mL" if du == "mL" else "g")


@given(
    a=decimals,
    unit=st.sampled_from([*MASS, "[iU]", "[IU]"]),
    n=st.one_of(st.none(), decimals),
    du=st.sampled_from([None, "mL", "g"]),
    space=st.sampled_from(["", " "]),
)
def test_p5_openfda_matches_the_reference(
    a: tuple[int, int], unit: str, n: tuple[int, int] | None, du: str | None, space: str
) -> None:
    """Feature: medication-passport, Property P5. Validates Req 6.3."""
    denominator = "" if n is None else text_of(n) + space
    published = f"{text_of(a)} {unit}/{denominator}{du or ''}"
    if n is None and du is None:
        published = f"{text_of(a)} {unit}/1"
        n = (1, 0)
    got = strength_code("openfda_ndc", published, None)
    assert got == us_ref(a, unit, n, du)
    if got is not None:
        assert PATTERN.fullmatch(got.amount) and Decimal(got.amount) > 0


@given(q=st.integers(min_value=1, max_value=10**8), basis=st.sampled_from(["1", "mL", "g"]))
def test_p5_equal_quantities_equal_codes(q: int, basis: str) -> None:
    """Feature: medication-passport, Property P5. Validates Req 6.3: the same quantity written in
    g, mg and ug, and with a scaled denominator, gives one code."""
    den = "1" if basis == "1" else f"1{basis}"
    spellings = [
        f"{text_of((q, 6))} g/{den}",
        f"{text_of((q, 3))} mg/{den}",
        f"{q} ug/{den}",
        f"{q} mcg/{den}",
    ]
    if basis != "1":
        spellings.append(f"{q * 5} ug/5 {basis}")  # A ÷ N
    codes = {strength_code("openfda_ndc", s, None) for s in spellings}
    assert len(codes) == 1
    (code,) = codes
    if code is not None:
        assert code.unit == "ug" and Decimal(code.amount) == q


def test_p5_examples() -> None:
    """Feature: medication-passport, Property P5. Validates Req 6.3, 6.4 (design examples)."""
    us = "openfda_ndc"
    assert strength_code(us, "1 g/1", None) == strength_code(us, "1000 mg/1", None)
    assert strength_code(us, "250 mg/5mL", None) == strength_code(us, "50 mg/mL", None)
    assert strength_code(us, "250 mg/5mL", None) == StrengthCode("50000", "ug", "mL")
    assert strength_code(us, ".5 mg/1", None) == StrengthCode("500", "ug", "unit")
    assert strength_code(us, "100 mg/3 mL", None) is None  # does not end within six decimals
    assert strength_code(us, "1 [iU]/1", None) == StrengthCode("1", "IU", "unit")
    for unsupported in (
        "6 [hp_X]/mL",
        "30 [hp_C]/1",
        "10 [USP'U]/g",
        "5 mL/100mL",
        "1 kg/kg",
        "5 mg/2",
        "5 mg/d",
        "2 mg/h",
        "5 mg",
        "",
        "1 kg/1",
    ):
        assert strength_code(us, unsupported, None) is None, unsupported
    fr, tablet, liquid = "eu_fr_bdpm", COUNTABLE[0], "oral_liquid"
    assert strength_code(fr, "0,5 mg", tablet) == strength_code(fr, "500 microgrammes", tablet)
    assert strength_code(fr, "1 000 mg", tablet) == StrengthCode("1000000", "ug", "unit")
    assert strength_code(fr, "1\u00a0000 UI", tablet) == StrengthCode("1000", "IU", "unit")
    assert strength_code(fr, "250 mg", liquid) is None  # basis unknown (DP5)
    assert strength_code(fr, "5 CH", tablet) is None
    assert strength_code("eu_es_cima", "500 mg", tablet) is None
    assert strength_code("titck", "500 mg", tablet) is None


@given(
    a=decimals,
    unit=st.sampled_from(list(FR_MASS)),
    group=st.sampled_from([*GROUPS, None]),
    thousands=st.booleans(),
)
def test_p5_bdpm_only_for_countable_forms(
    a: tuple[int, int], unit: str, group: str | None, thousands: bool
) -> None:
    """Feature: medication-passport, Property P5. Validates Req 6.4: a BDPM strength has a code
    exactly when the form group is countable, and then equals the per-unit reference."""
    whole, _, frac = text_of(a).partition(".")
    if thousands and len(whole) > 3:
        head = len(whole) % 3 or 3
        whole = whole[:head] + "".join(f" {whole[i : i + 3]}" for i in range(head, len(whole), 3))
    published = f"{whole}{',' + frac if frac else ''} {unit}"
    got = strength_code("eu_fr_bdpm", published, group)
    if group not in COUNTABLE_GROUPS:
        assert got is None
    else:
        assert got == reference(value_of(a) * FR_MASS[unit], "ug", "unit")


@given(
    source=st.sampled_from(SOURCES),
    published=st.one_of(st.none(), st.text(max_size=40)),
    group=st.one_of(st.none(), st.sampled_from(GROUPS), st.text(max_size=10)),
)
def test_p5_total_and_in_pattern(source: str, published: str | None, group: str | None) -> None:
    """Feature: medication-passport, Property P5. Validates Req 6.3, 6.4: never raises; every code
    matches the request pattern; Nomenclátor and TİTCK always `None`."""
    got = strength_code(source, published, group)
    if source in ("titck", "eu_es_cima"):
        assert got is None
    if got is not None:
        assert PATTERN.fullmatch(got.amount)
        assert Fraction(got.amount) > 0
        assert got.unit in ("ug", "IU") and got.basis in ("unit", "mL", "g")
