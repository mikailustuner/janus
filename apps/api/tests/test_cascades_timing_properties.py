"""Property P11: the timing table (cascade-engine design §4.2, §9)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from janus.cascades.timing import classify, format_month, parse_month

MONTHS = st.one_of(st.none(), st.integers(1900 * 12, 2100 * 12))


def reference(a: int | None, b: int | None, w: int) -> tuple[str, str, int | None, bool] | None:
    if a is None or b is None:
        return ("possible", "date_unknown", None, False)
    if b < a:
        return None
    if b == a:
        return ("possible", "same_month", 0, False)
    if b - a <= w:
        return ("probable", "within_window", b - a, False)
    return ("possible", "after_window", b - a, True)


@given(a=MONTHS, b=MONTHS, w=st.integers(1, 60))
def test_p11_timing_table(a: int | None, b: int | None, w: int) -> None:
    """Feature: cascade-engine, Property 11. Validates: Req 2.2-2.5."""
    t = classify(a, b, w)
    got = None if t is None else (t.status, t.timing, t.months_between, t.low_priority)
    assert got == reference(a, b, w)


@given(a=st.integers(1900 * 12, 2100 * 12), w=st.integers(1, 60))
def test_p11_window_boundaries(a: int, w: int) -> None:
    """Feature: cascade-engine, Property 11. Validates: Req 2.2, 2.5 (d = 0, w, w + 1)."""
    same = classify(a, a, w)
    assert same is not None and (same.status, same.timing) == ("possible", "same_month")
    edge = classify(a, a + w, w)
    assert edge is not None and edge.status == "probable"
    past = classify(a, a + w + 1, w)
    assert past is not None and (past.timing, past.low_priority) == ("after_window", True)
    assert classify(a, a - 1, w) is None


@given(m=st.integers(1900 * 12, 9999 * 12 + 11))
def test_month_round_trip(m: int) -> None:
    """Feature: cascade-engine, Property 11. Validates: Req 2.2 (month parsing)."""
    assert parse_month(format_month(m)) == m
