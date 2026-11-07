"""Property and example tests for validation."""

from __future__ import annotations

from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.validation import (
    Accounting,
    ExpectedSchema,
    Field,
    RowAccountingError,
    SchemaMismatchError,
    check_accounting,
    check_schema,
    observe,
    review_needed,
)

THRESHOLDS = st.fractions(min_value=Fraction(1, 1000), max_value=1).filter(lambda t: t > 0)


@given(st.integers(1, 10**7), st.integers(0, 2 * 10**7), THRESHOLDS)
def test_review_flag_exact(previous: int, current: int, threshold: Fraction) -> None:
    """Feature: data-pipelines, Property P5 — Validates: Req 2.2.

    Flagged iff abs(c - p) > t * p, in exact rational arithmetic.
    """
    expected = Fraction(abs(current - previous)) > threshold * previous
    assert review_needed(previous, current, threshold) is expected


@given(st.integers(0, 10**7), THRESHOLDS)
def test_review_flag_never_without_previous(current: int, threshold: Fraction) -> None:
    """Feature: data-pipelines, Property P5 — Validates: Req 2.2 (no previous artifact)."""
    assert review_needed(None, current, threshold) is False


ROW_KINDS = st.lists(
    st.one_of(
        st.just(("keep", "")),
        st.tuples(st.just("drop"), st.sampled_from(["invalid_barcode", "blank_row", "other"])),
    ),
    max_size=200,
)


@given(ROW_KINDS)
def test_row_accounting(decisions: list[tuple[str, str]]) -> None:
    """Feature: data-pipelines, Property P4 (generic) — Validates: Req 1.5.

    For any mix of kept and excluded rows, input == output + sum(excluded) and every
    exclusion has a reason; a lost row is detected.
    """
    acc = Accounting(input_rows=len(decisions))
    output = 0
    for action, reason in decisions:
        if action == "keep":
            output += 1
        else:
            acc.exclude(reason)
    check_accounting(acc.input_rows, output, acc.excluded)
    assert all(reason for reason in acc.excluded)
    with pytest.raises(RowAccountingError):
        check_accounting(acc.input_rows + 1, output, acc.excluded)


SCHEMA = ExpectedSchema(
    version="t1",
    fields=(
        Field("BARKOD", frozenset({"int", "str", "null"})),
        Field("ATC KODU", frozenset({"str", "null"})),
    ),
)


def test_schema_names_missing_and_wrong_fields() -> None:
    observed = observe([{"BARKOD": 1.5, "EXTRA": "x"}])
    with pytest.raises(SchemaMismatchError) as err:
        check_schema(SCHEMA, observed)
    assert "ATC KODU" in str(err.value)
    assert "BARKOD" in str(err.value)
    assert err.value.report.missing == ("ATC KODU",)


def test_extra_columns_do_not_fail() -> None:
    report = check_schema(SCHEMA, observe([{"BARKOD": 1, "ATC KODU": None, "NEW": 2}]))
    assert report.extra == ("NEW",)


def test_exclusion_needs_reason() -> None:
    with pytest.raises(ValueError, match="reason"):
        Accounting().exclude("")
