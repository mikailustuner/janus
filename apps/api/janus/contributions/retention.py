"""Retention (privacy design §5.7, Req 3.6, DP20): donations are kept at most 24 months."""

from __future__ import annotations

import calendar
import datetime as dt
from typing import Final

RETENTION_MONTHS: Final = 24


def retention_cutoff(today: dt.date, months: int = RETENTION_MONTHS) -> dt.date:
    """`today` minus `months` calendar months, clamped to the last day of the target month."""
    index = today.year * 12 + (today.month - 1) - months
    year, month0 = divmod(index, 12)
    last = calendar.monthrange(year, month0 + 1)[1]
    return dt.date(year, month0 + 1, min(today.day, last))


def is_expired(week: dt.date, today: dt.date) -> bool:
    """A donation is received on or after its week's Monday, so this never keeps one too long."""
    return week <= retention_cutoff(today)
