"""Property and example tests for the retry policy and the HTTP fetcher."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import httpx2
import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.http import (
    ContactInvalidError,
    ContactMissingError,
    Fetcher,
    FetchError,
    RateLimiter,
    contact_from_env,
    mailto_params,
    parse_contact,
    user_agent,
)
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


GITHUB = "https://github.com/mikailustuner"


def test_user_agent_with_url_contact() -> None:
    """Validates: Req 4.1 — Wikimedia format with a URL as contact, no email."""
    ua = user_agent(parse_contact(GITHUB))
    assert ua.startswith("janus-pipelines-bot/")
    assert f"({GITHUB}; research prototype)" in ua
    assert "@" not in ua and "mailto" not in ua
    assert "httpx2/" in ua


def test_user_agent_without_contact() -> None:
    ua = user_agent(None)
    assert "(research prototype)" in ua and "@" not in ua


def test_mailto_only_for_email_contact() -> None:
    """Validates: Req 4.1 — Crossref mailto only when JANUS_CONTACT is an email."""
    assert mailto_params(parse_contact(GITHUB)) == {}
    assert mailto_params(None) == {}
    assert mailto_params(parse_contact("ops@example.org")) == {"mailto": "ops@example.org"}


@pytest.mark.parametrize("bad", ["", "github.com/x", "not an address", "ftp://x.org", "a@b"])
def test_invalid_contact_rejected(bad: str) -> None:
    with pytest.raises(ContactInvalidError):
        parse_contact(bad)


def test_contact_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JANUS_CONTACT", raising=False)
    assert contact_from_env(required=False) is None
    with pytest.raises(ContactMissingError):
        contact_from_env(required=True)
    monkeypatch.setenv("JANUS_CONTACT", f"  {GITHUB} ")
    contact = contact_from_env(required=True)
    assert contact is not None and contact.value == GITHUB and not contact.is_email


def _one_doi(_data_dir: object) -> list[str]:
    return ["10.1000/x"]


def _no_papers(_repo_root: Path) -> list[str]:
    return []


def test_crossref_request_has_no_mailto_for_url_contact(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validates: Req 4.1, 9.2 — with a URL contact, Crossref gets no mailto (public pool)."""
    from pathlib import Path

    from janus_pipelines.core.registry import load_registry
    from janus_pipelines.core.runner import RunContext
    from janus_pipelines.jobs import retractions

    seen: list[httpx2.Request] = []

    def handle(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json={"status": "ok", "message": {}})

    real_make = retractions.make_fetcher

    def fake_make(*, require_contact: bool) -> Fetcher:
        f = real_make(require_contact=require_contact, transport=httpx2.MockTransport(handle))
        f.limiter = _NoWait()
        return f

    monkeypatch.setenv("JANUS_CONTACT", GITHUB)
    monkeypatch.setattr(retractions, "make_fetcher", fake_make)
    monkeypatch.setattr(retractions.RetractionsJob, "collect_dois", staticmethod(_one_doi))
    # The curated paper list is a second DOI input; leave it out so only the stub DOI is fetched.
    monkeypatch.setattr(retractions.RetractionsJob, "paper_dois", staticmethod(_no_papers))
    repo = Path(__file__).resolve().parents[2]
    ctx = RunContext(
        data_dir=Path("/nonexistent-janus-test"),
        repo_root=repo,
        registry=load_registry(repo / "pipelines" / "sources.toml"),
        code_version="test",
    )
    retractions.RetractionsJob().fetch(ctx)
    assert len(seen) == 1
    assert "mailto" not in str(seen[0].url)
    assert "@" not in seen[0].headers["User-Agent"]
    assert GITHUB in seen[0].headers["User-Agent"]
