"""HTTP client: timeouts, retries, per-host rate limit, User-Agent (design §4.3, Req 4.1)."""

from __future__ import annotations

import datetime as dt
import os
import random
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx2

from janus_pipelines import __version__
from janus_pipelines.core.retry import Attempt, retry_delay

CONNECT_TIMEOUT = 10.0
READ_TIMEOUT = 60.0
BULK_READ_TIMEOUT = 300.0

# Requests per second per host. openFDA publishes 240/min; others are conservative defaults.
DEFAULT_RATES: dict[str, float] = {
    "api.fda.gov": 4.0,
    "download.open.fda.gov": 4.0,
    "api.crossref.org": 2.0,
    "query.wikidata.org": 2.0,
    "www.ebi.ac.uk": 2.0,
    "www.titck.gov.tr": 1.0,
}


class ContactEmailMissingError(Exception):
    """JANUS_CONTACT_EMAIL is required by the source's usage policy."""


def contact_email(required: bool) -> str | None:
    value = os.environ.get("JANUS_CONTACT_EMAIL", "").strip() or None
    if required and value is None:
        raise ContactEmailMissingError(
            "set JANUS_CONTACT_EMAIL; Crossref and Wikidata ask clients to identify themselves"
        )
    return value


def user_agent(email: str | None) -> str:
    contact = f"; mailto:{email}" if email else ""
    return f"janus-pipelines/{__version__} (research prototype{contact})"


@dataclass
class RateLimiter:
    """Minimum interval between requests to the same host."""

    rates: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_RATES))
    default_rate: float = 2.0
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _last: dict[str, float] = field(default_factory=dict[str, float])

    def wait(self, host: str) -> None:
        interval = 1.0 / self.rates.get(host, self.default_rate)
        last = self._last.get(host)
        now = self.clock()
        if last is not None and now - last < interval:
            self.sleep(interval - (now - last))
            now = self.clock()
        self._last[host] = now


class FetchError(Exception):
    """A request failed after the allowed retries."""


@dataclass
class Fetcher:
    """GET/HEAD only. Every request has timeouts; retries follow retry.retry_delay."""

    client: httpx2.Client
    limiter: RateLimiter = field(default_factory=RateLimiter)
    sleep: Callable[[float], None] = time.sleep
    rng: random.Random = field(default_factory=random.Random)

    def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
        read_timeout: float = READ_TIMEOUT,
        allow_status: frozenset[int] = frozenset(),
    ) -> httpx2.Response:
        """GET with retries. Statuses in `allow_status` (e.g. 404) are returned, not raised."""
        host = urlsplit(url).hostname or ""
        timeout = httpx2.Timeout(CONNECT_TIMEOUT, read=read_timeout)
        retries = 0
        while True:
            self.limiter.wait(host)
            retry_after: str | None = None
            try:
                response = self.client.get(
                    url, params=dict(params or {}), headers=dict(headers or {}), timeout=timeout
                )
            except httpx2.TimeoutException as exc:
                attempt, failure = Attempt(error="timeout"), f"timeout: {exc}"
            except httpx2.TransportError as exc:
                attempt, failure = Attempt(error="connect"), f"connection error: {exc}"
            else:
                if response.is_success or response.status_code in allow_status:
                    return response
                attempt = Attempt(status=response.status_code)
                failure = f"HTTP {response.status_code} from {host}"
                retry_after = response.headers.get("Retry-After")
            delay = retry_delay(
                "GET",
                attempt,
                retries,
                retry_after=retry_after,
                jitter=self.rng.random(),
                now=dt.datetime.now(dt.UTC),
            )
            if delay is None:
                raise FetchError(f"{failure} (after {retries} retries)")
            self.sleep(delay)
            retries += 1


def make_fetcher(
    *, require_contact: bool, transport: httpx2.BaseTransport | None = None
) -> Fetcher:
    email = contact_email(required=require_contact)
    client = httpx2.Client(
        headers={"User-Agent": user_agent(email)},
        timeout=httpx2.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT),
        follow_redirects=True,
        transport=transport,
    )
    return Fetcher(client=client)
