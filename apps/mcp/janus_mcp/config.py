"""Configuration from the environment (mcp-server design §6). Errors name the variable only."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

DEFAULT_URL: Final = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT: Final = 10.0
MAX_TIMEOUT: Final = 60.0
_URL = re.compile(r"^(https?)://([A-Za-z0-9.-]+|\[::1\])(:[0-9]{1,5})?(/[A-Za-z0-9._~-]+)*/?$")
LOOPBACK: Final = frozenset({"127.0.0.1", "localhost", "[::1]", "::1"})


class ConfigError(ValueError):
    """An environment value is invalid; the message names the variable, never the value."""


@dataclass(frozen=True)
class Config:
    api_url: str
    timeout: float


def from_env(env: Mapping[str, str] | None = None) -> Config:
    e = os.environ if env is None else env
    url = (e.get("JANUS_API_URL") or DEFAULT_URL).strip()
    m = _URL.fullmatch(url)
    # Plain http only to this computer: medicine lists never cross a network unencrypted.
    if m is None or (m.group(1) == "http" and m.group(2) not in LOOPBACK):
        raise ConfigError(
            "JANUS_API_URL must be https://host[:port][/path] "
            "(http only for 127.0.0.1 or localhost)"
        )
    raw = (e.get("JANUS_API_TIMEOUT") or str(DEFAULT_TIMEOUT)).strip()
    try:
        timeout = float(raw)
    except ValueError:
        raise ConfigError("JANUS_API_TIMEOUT must be a number of seconds in (0, 60]") from None
    if not (0 < timeout <= MAX_TIMEOUT):
        raise ConfigError("JANUS_API_TIMEOUT must be a number of seconds in (0, 60]")
    return Config(url.rstrip("/"), timeout)
