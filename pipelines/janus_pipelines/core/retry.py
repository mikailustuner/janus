"""Retry decision for external requests (design §4.3, Req 4.1). Pure."""

from __future__ import annotations

import datetime as dt
import email.utils
from dataclasses import dataclass
from typing import Literal

MAX_RETRIES = 3
DELAY_CAP_SECONDS = 120.0
BASE_DELAYS = (1.0, 2.0, 4.0)
IDEMPOTENT_METHODS = frozenset({"GET", "HEAD"})

type ErrorKind = Literal["connect", "timeout"]


@dataclass(frozen=True)
class Attempt:
    """The result of one request: an HTTP status, or a transport error kind."""

    status: int | None = None
    error: ErrorKind | None = None


def is_retryable(attempt: Attempt) -> bool:
    if attempt.error is not None:
        return True
    status = attempt.status
    return status is not None and (status == 429 or 500 <= status <= 599)


def parse_retry_after(value: str | None, now: dt.datetime) -> float | None:
    """Seconds from a Retry-After header (delta-seconds or HTTP date), or None."""
    if value is None:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.UTC)
    return max(0.0, (when - now).total_seconds())


def retry_delay(
    method: str,
    attempt: Attempt,
    retries_done: int,
    retry_after: str | None = None,
    jitter: float = 0.0,
    now: dt.datetime | None = None,
) -> float | None:
    """Seconds to wait before retrying, or None if the request must not be retried.

    Only idempotent methods, only for connection errors, timeouts, 429 and 5xx, and at most
    MAX_RETRIES times. `jitter` in [0, 1) scales the backoff up by at most 50%.
    """
    if method.upper() not in IDEMPOTENT_METHODS:
        return None
    if retries_done < 0 or retries_done >= MAX_RETRIES:
        return None
    if not is_retryable(attempt):
        return None
    server = parse_retry_after(retry_after, now or dt.datetime.now(dt.UTC))
    if server is not None:
        return min(server, DELAY_CAP_SECONDS)
    base = BASE_DELAYS[min(retries_done, len(BASE_DELAYS) - 1)]
    j = min(max(jitter, 0.0), 0.999)
    return min(base * (1.0 + 0.5 * j), DELAY_CAP_SECONDS)
