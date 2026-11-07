"""Property tests for configuration bounds (privacy design §8, P14)."""

from __future__ import annotations

import math
from decimal import Decimal
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.settings import SettingsError, parse_epsilon, parse_k, parse_noise_key


@given(st.integers(min_value=-(10**6), max_value=10**8))
def test_k_accepted_iff_at_least_20(k: int) -> None:
    """Feature: privacy, Property P14 (k). Validates Req 4.1."""
    if k >= 20:
        assert parse_k(str(k)) == k
    else:
        with pytest.raises(SettingsError):
            parse_k(str(k))


@given(
    st.decimals(
        min_value=Decimal("-20"),
        max_value=Decimal("20"),
        allow_nan=False,
        allow_infinity=False,
        places=6,
    )
)
def test_epsilon_accepted_iff_in_range(eps: Decimal) -> None:
    """Feature: privacy, Property P14 (ε). Validates Req 4.2."""
    text = format(eps, "f")
    value = Fraction(eps)
    if 0 < value <= 10:
        assert parse_epsilon(text) == value
    else:
        with pytest.raises(SettingsError):
            parse_epsilon(text)


@given(
    st.one_of(
        st.sampled_from(["", "NaN", "nan", "inf", "-inf", "1e0", "1E-3", "0x1", " ", "1,5", "+1"]),
        st.text(max_size=12),
        st.floats(allow_nan=True, allow_infinity=True).map(repr),
    )
)
def test_epsilon_rejects_non_decimal_text(text: str) -> None:
    """Feature: privacy, Property P14 (ε, malformed). Validates Req 4.2."""
    try:
        value = parse_epsilon(text)
    except SettingsError:
        return
    # Anything accepted must be a plain decimal in range.
    assert 0 < value <= 10
    assert math.isfinite(float(value))
    assert text.strip().replace(".", "", 1).isdigit()


def test_secret_value_never_in_error_message() -> None:
    secret = "c2hvcnQ"  # noqa: S105 (not a secret) base64url of "short": too short
    with pytest.raises(SettingsError) as info:
        parse_noise_key(secret)
    assert secret not in str(info.value)
