"""Property and example tests for the retry policy and the HTTP fetcher."""

from __future__ import annotations

import datetime as dt

import httpx2
import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.http import Fetcher, FetchError, RateLimiter, user_agent
from janus_pipelines.core.retry import (
    DELAY_CAP_SECONDS,
    MAX_RETRIES,
    Attempt,
    retry_delay,
)

METHODS = st.sampled_from(["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "get", "OPTIONS"])
ATTEMPTS = st.one_of(
    st.builds(Attempt, status=st.integers(100, 599)),
    st.builds(Attempt, error=st.sampled_from(["connect", "timeout"])),
)
RETRY_AFTER = st.one_of(
    st.none(),
    st.integers(0, 10**6).map(str),
    st.just("Wed, 21 Oct 2026 07:28:00 GMT"),
    st.just("not a date"),
)


@given(METHODS, ATTEMPTS, st.integers(-2, 10), RETRY_AFTER, st.floats(-1, 2))
def test_only_idempotent_bounded_retries(
    method: str, attempt: Attempt, retries_done: int, retry_after: str | None, jitter: float
) -> None:
    """Feature: data-pipelines, Property P9 — Validates: Req 4.1.

    A retry is allowed only for GET/HEAD, only on connection error / timeout / 429 / 5xx,
    never after MAX_RETRIES; any delay is within [0, cap].
    """
    now = dt.datetime(2026, 11, 7, tzinfo=dt.UTC)
    delay = retry_delay(method, attempt, retries_done, retry_after, jitter, now)
    retryable_outcome = attempt.error is not None or (
        attempt.status is not None and (attempt.status == 429 or 500 <= attempt.status <= 599)
    )
    allowed = (
        method.upper() in {"GET", "HEAD"} and 0 <= retries_done < MAX_RETRIES and retryable_outcome
    )
    if allowed:
        assert delay is not None and 0.0 <= delay <= DELAY_CAP_SECONDS
    else:
        assert delay is None


class _NoWait(RateLimiter):
    def wait(self, host: str) -> None:
        return None


def _fetcher(handler: httpx2.MockTransport) -> tuple[Fetcher, list[float]]:
    slept: list[float] = []
    client = httpx2.Client(transport=handler)
    return Fetcher(client=client, limiter=_NoWait(), sleep=slept.append), slept


def test_503_then_200_succeeds() -> None:
    """Validates: Req 4.1."""
    calls: list[str] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.method)
        return httpx2.Response(503 if len(calls) == 1 else 200, text="ok")

    fetcher, slept = _fetcher(httpx2.MockTransport(handle))
    assert fetcher.get("https://api.example.org/x").text == "ok"
    assert calls == ["GET", "GET"]
    assert len(slept) == 1


def test_404_not_retried() -> None:
    calls: list[int] = []

    def handle(_r: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(404)

    fetcher, _ = _fetcher(httpx2.MockTransport(handle))
    with pytest.raises(FetchError, match="404"):
        fetcher.get("https://api.example.org/x")
    assert len(calls) == 1
    assert (
        fetcher.get("https://api.example.org/x", allow_status=frozenset({404})).status_code == 404
    )


def test_retry_limit_and_retry_after() -> None:
    calls: list[int] = []

    def handle(_r: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(429, headers={"Retry-After": "7"})

    fetcher, slept = _fetcher(httpx2.MockTransport(handle))
    with pytest.raises(FetchError, match="after 3 retries"):
        fetcher.get("https://api.example.org/x")
    assert len(calls) == 1 + MAX_RETRIES
    assert slept == [7.0, 7.0, 7.0]


def test_connection_errors_retried() -> None:
    calls: list[int] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        if len(calls) < 3:
            raise httpx2.ConnectError("refused", request=request)
        return httpx2.Response(200)

    fetcher, _ = _fetcher(httpx2.MockTransport(handle))
    assert fetcher.get("https://api.example.org/x").status_code == 200
    assert len(calls) == 3


def test_rate_limiter_spaces_requests() -> None:
    t = [0.0]
    slept: list[float] = []

    def sleep(s: float) -> None:
        slept.append(s)
        t[0] += s

    limiter = RateLimiter(rates={"h": 4.0}, clock=lambda: t[0], sleep=sleep)
    limiter.wait("h")
    limiter.wait("h")
    assert slept == [0.25]


def test_user_agent_has_contact() -> None:
    assert "mailto:a@b.org" in user_agent("a@b.org")
    assert "mailto" not in user_agent(None)
