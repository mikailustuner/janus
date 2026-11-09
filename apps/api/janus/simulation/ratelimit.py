"""Rate limits of the simulation routes without storing IP addresses (simulation-service design
§7, DP-S7; privacy.md).

The client address is turned into a key with HMAC-SHA256 under a random secret made when the
process starts and never written anywhere; only the first 16 bytes of the MAC are kept, in
memory, with the times of the client's recent requests. Entries expire after the longest window
(at most one hour) and the table is bounded, so nothing outlives a short TTL and a restart forgets
everything. A global window bounds the total load whatever the keys (address rotation).

Pure apart from the clock and the secret passed in; thread-safe.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import math
import os
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Window:
    limit: int
    seconds: float


@dataclass(frozen=True)
class Decision:
    allowed: bool
    retry_after: int  # seconds; 0 when allowed


@dataclass
class Limiter:
    per_client: tuple[Window, ...]
    global_: tuple[Window, ...] = ()
    max_keys: int = 10_000
    clock: Callable[[], float] = time.monotonic
    secret: bytes = field(default_factory=lambda: os.urandom(32), repr=False)
    _hits: dict[bytes, deque[float]] = field(default_factory=dict[bytes, deque[float]], repr=False)
    _all: deque[float] = field(default_factory=deque[float], repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def ttl(self) -> float:
        return max(w.seconds for w in (*self.per_client, *self.global_))

    def key(self, client: str) -> bytes:
        return hmac.new(self.secret, client.encode(), hashlib.sha256).digest()[:16]

    @staticmethod
    def _wait(hits: deque[float], windows: tuple[Window, ...], now: float) -> float:
        wait = 0.0
        for w in windows:
            inside = [t for t in hits if t > now - w.seconds]
            if len(inside) >= w.limit:
                # The oldest hit that must leave the window before one more is allowed.
                oldest = inside[len(inside) - w.limit]
                wait = max(wait, oldest + w.seconds - now)
        return wait

    def _prune(self, now: float) -> None:
        horizon = now - self.ttl
        while self._all and self._all[0] <= horizon:
            self._all.popleft()
        for k in [k for k, d in self._hits.items() if not d or d[-1] <= horizon]:
            del self._hits[k]
        while len(self._hits) >= self.max_keys:  # bounded memory: forget the stalest client
            stalest = min(self._hits, key=lambda k: self._hits[k][-1])
            del self._hits[stalest]

    def check(self, client: str) -> Decision:
        """Count one request of `client` if allowed; otherwise say how long to wait."""
        now = self.clock()
        k = self.key(client)
        with self._lock:
            self._prune(now)
            hits = self._hits.get(k, deque())
            wait = max(
                self._wait(hits, self.per_client, now), self._wait(self._all, self.global_, now)
            )
            if wait > 0:
                return Decision(False, max(1, math.ceil(wait)))
            hits.append(now)
            self._hits[k] = hits
            self._all.append(now)
            return Decision(True, 0)

    def size(self) -> int:
        with self._lock:
            return len(self._hits)


def client_address(headers: dict[str, str], peer: str | None, trust_cf: bool) -> str:
    """The client the limits count. With `trust_cf` (the deployment: the API is reachable only
    through the Cloudflare tunnel and the web app, and Cloudflare overwrites the header),
    Cloudflare's `cf-connecting-ip`; otherwise the socket peer, never a header a client could set.
    An IPv6 address counts as its /64 network, so rotating addresses inside one allocation does not
    give a fresh bucket (safety review F2)."""
    value = headers.get("cf-connecting-ip", "").strip() if trust_cf else ""
    raw = value or peer or "unknown"
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return raw[:64]
    if ip.version == 6:
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return str(ip)
