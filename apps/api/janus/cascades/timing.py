"""Start months and the timing table (cascade-engine design §4.2, Req 2.2-2.5). Pure."""

from __future__ import annotations

import re

from janus.cascades.model import Month, TimingResult

_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


class MonthError(ValueError):
    """Not a `YYYY-MM` month."""


def parse_month(text: str) -> Month:
    m = _MONTH.fullmatch(text)
    if m is None:
        raise MonthError("month must be YYYY-MM")
    return int(m.group(1)) * 12 + int(m.group(2)) - 1


def format_month(month: Month) -> str:
    return f"{month // 12:04d}-{month % 12 + 1:02d}"


def classify(
    index_start: Month | None, marker_start: Month | None, window: int
) -> TimingResult | None:
    """Status and timing of a pair; None when the marker started before the index drug."""
    if index_start is None or marker_start is None:
        return TimingResult("possible", "date_unknown", None, False)
    d = marker_start - index_start
    if d < 0:
        return None
    if d == 0:
        return TimingResult("possible", "same_month", 0, False)
    if d <= window:
        return TimingResult("probable", "within_window", d, False)
    return TimingResult("possible", "after_window", d, True)
