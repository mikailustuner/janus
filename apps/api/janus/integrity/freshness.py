"""Freshness rule (evidence-integrity design §4.3, Req 2). Pure.

One rule for every source: a snapshot is stale when its age in whole UTC days is greater than
twice the source's cadence (`cadence_days` in `pipelines/sources.toml`).
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Literal

_DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}")

FreshnessState = Literal["current", "stale", "not_applicable"]


def parse_snapshot_date(text: str) -> dt.date:
    """`YYYY-MM-DD`, or an ISO 8601 date-time (offset applied, UTC date taken; none = UTC)."""
    s = text.strip()
    if _DATE_ONLY.fullmatch(s):
        return dt.date.fromisoformat(s)
    parsed = dt.datetime.fromisoformat(s)
    if parsed.tzinfo is None:
        return parsed.date()
    return parsed.astimezone(dt.UTC).date()


def age_days(snapshot: dt.date, today: dt.date) -> int:
    """Whole days; a snapshot date in the future gives 0."""
    return max(0, (today - snapshot).days)


@dataclass(frozen=True)
class Freshness:
    state: FreshnessState
    age_days: int
    limit_days: int | None


def freshness(snapshot: dt.date, today: dt.date, cadence_days: int | None) -> Freshness:
    age = age_days(snapshot, today)
    if cadence_days is None:
        return Freshness("not_applicable", age, None)
    limit = 2 * cadence_days
    return Freshness("stale" if age > limit else "current", age, limit)


def is_stale(snapshot: dt.date, today: dt.date, cadence_days: int | None) -> bool:
    return freshness(snapshot, today, cadence_days).state == "stale"


def check_is_stale(
    checked_at: dt.date | None, today: dt.date, crossref_cadence_days: int | None
) -> bool:
    """The check of a DOI is older than twice the cadence of the check source (DP9)."""
    if checked_at is None:
        return False
    return is_stale(checked_at, today, crossref_cadence_days)
