"""Property tests for NDC handling (drug-resolution design §8: P4, P11, P12)."""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.resolution.gs1 import gtin_check_digit
from janus.resolution.ndc import (
    NdcError,
    NdcKey,
    canonical_package,
    layouts_of_ndc10,
    ndc_from_gtin,
    parse_ndc_input,
)
from tests.resolution_strategies import Ndc10, label_prefixes, ndc10s


def _spaced(text: str, spaces: list[int]) -> str:
    out = text
    for pos in sorted(spaces, reverse=True):
        p = pos % (len(out) + 1)
        out = out[:p] + " " + out[p:]
    return out


@given(ndc=ndc10s(), prefix=label_prefixes(), spaces=st.lists(st.integers(0, 20), max_size=3))
def test_all_forms_give_same_canonical_key(ndc: Ndc10, prefix: str, spaces: list[int]) -> None:
    """Feature: drug-resolution, Property P4. Validates Req 3.2.

    The hyphenated 10-digit form, the 11-digit form with and without hyphens, and label-prefixed
    or spaced variants all give the same canonical 11-digit key.
    """
    c = ndc.canonical11
    want = NdcKey("ndc_package11", c)
    forms = [ndc.hyphenated, c, f"{c[:5]}-{c[5:9]}-{c[9:]}"]
    for form in forms:
        assert parse_ndc_input(prefix + _spaced(form, spaces)) == {want}
    assert canonical_package(ndc.hyphenated) == c
    # Plain 10 digits: one of up to three keys is the original's.
    assert want in parse_ndc_input(prefix + ndc.digits)


@given(ndc=ndc10s(), indicator=st.integers(0, 8))
def test_ndc_gtin_round_trip(ndc: Ndc10, indicator: int) -> None:
    """Feature: drug-resolution, Property P11. Validates Req 3.1.

    Building the NDC GTIN (indicator, 03, NDC, check digit) and extracting gives the same 10
    digits, and the lookup keys contain the original's canonical form.
    """
    body = f"{indicator}03{ndc.digits}"
    gtin = body + str(gtin_check_digit(body))
    digits = ndc_from_gtin(gtin)
    assert digits is not None
    assert digits == ndc.digits
    assert NdcKey("ndc_package11", ndc.canonical11) in parse_ndc_input(digits)
    assert ndc.canonical11 == layouts_of_ndc10(digits)[ndc.layout]  # type: ignore[index]


@given(digits=st.text(alphabet="0123456789", min_size=14, max_size=14))
def test_non_ndc_gtins_give_nothing(digits: str) -> None:
    """Feature: drug-resolution, Property P11. Only `[0-8]03…` GTIN-14s carry an NDC."""
    if not re.match(r"^[0-8]03", digits):
        assert ndc_from_gtin(digits) is None


_VALID = re.compile(
    r"^(\d{4}-\d{4}-\d{2}|\d{5}-\d{3}-\d{2}|\d{5}-\d{4}-\d{1}|\d{5}-\d{4}-\d{2}"
    r"|\d{11}|\d{10}|\d{4}-\d{4}|\d{5}-\d{3}|\d{5}-\d{4})$"
)


def _reference_accepts(raw: str) -> bool:
    text = re.sub(r"\s+", "", raw)
    for prefix in ("NDC:", "NDC", "N"):
        if text.upper().startswith(prefix):
            text = text[len(prefix) :]
            break
    return bool(_VALID.match(text)) and text.isascii()


near_misses = st.one_of(
    ndc10s().map(lambda n: n.hyphenated),
    ndc10s().flatmap(
        lambda n: st.sampled_from(
            [
                n.digits[:-1],
                n.digits + "12",
                n.hyphenated + "-",
                n.hyphenated.replace("-", "--"),
                n.hyphenated[1:],
                n.hyphenated + "7",
                "X" + n.digits,
                n.digits[:4] + "-" + n.digits[4:],
            ]
        )
    ),
    st.text(alphabet="0123456789- NDCndcx:", max_size=16),
    st.text(max_size=16),
)


@given(raw=near_misses)
def test_input_domain(raw: str) -> None:
    """Feature: drug-resolution, Property P12. Validates Req 3.2.

    Accepted iff one of the listed forms after prefix and space removal; plain 10 digits give
    1-3 keys; everything else raises `ndc_malformed` (fixed message).
    """
    if _reference_accepts(raw):
        keys = parse_ndc_input(raw)
        assert 1 <= len(keys) <= 3
        digits = re.sub(r"\D", "", raw)
        if len(digits) != 10 or "-" in raw:
            assert len(keys) == 1
    else:
        with pytest.raises(NdcError) as exc:
            parse_ndc_input(raw)
        assert str(exc.value) == "ndc_malformed"


def test_examples() -> None:
    assert parse_ndc_input("NDC 71335-9682-1") == {NdcKey("ndc_package11", "71335968201")}
    assert parse_ndc_input("0002-4462-30") == {NdcKey("ndc_package11", "00002446230")}
    assert parse_ndc_input("71335-9682") == {NdcKey("ndc_product9", "713359682")}
    assert canonical_package("02") is None
    assert len(parse_ndc_input("1234567890")) == 3
