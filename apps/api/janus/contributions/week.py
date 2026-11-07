"""Report week (privacy design §5.3, Req 3.2): the Monday of the UTC ISO week of receipt."""

from __future__ import annotations

import datetime as dt


def report_week(now: dt.datetime) -> dt.date:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    day = now.astimezone(dt.UTC).date()
    return day - dt.timedelta(days=day.weekday())
