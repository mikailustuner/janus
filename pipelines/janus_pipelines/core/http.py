"""HTTP client: timeouts, retries, per-host rate limit, User-Agent (design §4.3, Req 4.1)."""

from __future__ import annotations

import datetime as dt
import os
import random
import re
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

# Requests per second per host. openFDA publishes 240/min. Crossref's public pool allows
# 5 single-record requests/s with 1 concurrent request (docs checked 2026-11-07); requests here
# are sequential at 2/s. Others are conservative defaults.
DEFAULT_RATES: dict[str, float] = {
    "api.fda.gov": 4.0,
    "download.open.fda.gov": 4.0,
    "api.crossref.org": 2.0,
    "query.wikidata.org": 2.0,
    "www.ebi.ac.uk": 2.0,
    "www.titck.gov.tr": 1.0,
}


_EMAIL = re.compile(r"[^@\s;()]+@[^@\s;()]+\.[^@\s;()]+")
_URL = re.compile(r"https?://[^\s;()]+")


class ContactMissingError(Exception):
    """JANUS_CONTACT is required by the source's usage policy (Wikimedia User-Agent policy)."""


class ContactInvalidError(ValueError):
    """JANUS_CONTACT is neither an http(s) URL nor an email address."""


@dataclass(frozen=True)
class Contact:
    """Operator contact for the User-Agent: a URL or an email address (Req 4.1)."""

    value: str
    is_email: bool


def parse_contact(value: str) -> Contact:
    text = value.strip()
    if _URL.fullmatch(text):
        return Contact(text, is_email=False)
    if _EMAIL.fullmatch(text):
        return Contact(text, is_email=True)
    raise ContactInvalidError("JANUS_CONTACT must be an http(s) URL or an email address")


def contact_from_env(required: bool) -> Contact | None:
    """Read JANUS_CONTACT. Nothing is assumed when it is unset."""
    value = os.environ.get("JANUS_CONTACT", "").strip()
    if not value:
        if required:
            raise ContactMissingError(
                "set JANUS_CONTACT (a URL or an email address); Wikidata asks clients to "
                "include contact information in the User-Agent"
            )
        return None
    return parse_contact(value)


def user_agent(contact: Contact | None) -> str:
    """Wikimedia format: <client>/<version> (<contact>; ...) <library>/<version>."""
    details = f"{contact.value}; research prototype" if contact else "research prototype"
    return f"janus-pipelines-bot/{__version__} ({details}) httpx2/{httpx2.__version__}"


def mailto_params(contact: Contact | None) -> dict[str, str]:
    """Crossref `mailto` (polite pool) only when the contact is an email; else public pool."""
    return {"mailto": contact.value} if contact is not None and contact.is_email else {}


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
    contact: Contact | None = None
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
    contact = contact_from_env(required=require_contact)
    client = httpx2.Client(
        headers={"User-Agent": user_agent(contact)},
        timeout=httpx2.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT),
        follow_redirects=True,
        transport=transport,
    )
    return Fetcher(client=client, contact=contact)
