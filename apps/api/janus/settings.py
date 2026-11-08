"""API settings, read from the environment once at startup (privacy design §3).

Invalid values stop the process with the variable's name. Secret values are never echoed.
"""

from __future__ import annotations

import base64
import binascii
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

K_MIN = 20
EPSILON_MAX = Fraction(10)
NOISE_KEY_MIN_BYTES = 32
CONSENT_VERSION_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,31}$")
# The Janus event vocabulary ships inside the package (collective-memory DP23).
EVENT_VOCABULARY = Path(__file__).parent / "memory" / "memory_events.csv"


class SettingsError(ValueError):
    """A configuration value is invalid. The message names the variable, never a secret."""


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    donation_region: str | None
    consent_versions: frozenset[str]
    event_vocabulary_path: Path
    k: int
    epsilon: Fraction
    noise_key: bytes | None
    data_dir: Path | None = None  # resolution loader only (drug-resolution design §6)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        return cls(
            database_url=_optional(e, "DATABASE_URL"),
            donation_region=_optional(e, "JANUS_DONATION_REGION"),
            consent_versions=parse_consent_versions(e.get("JANUS_CONSENT_VERSIONS", "")),
            event_vocabulary_path=Path(_optional(e, "JANUS_EVENT_VOCABULARY") or EVENT_VOCABULARY),
            k=parse_k(e.get("JANUS_K", str(K_MIN))),
            epsilon=parse_epsilon(e.get("JANUS_DP_EPSILON", "1")),
            noise_key=parse_noise_key(e.get("JANUS_NOISE_KEY", "")),
            data_dir=_path_or_none(_optional(e, "JANUS_DATA_DIR")),
        )


def _path_or_none(value: str | None) -> Path | None:
    return Path(value) if value else None


def _optional(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name, "").strip()
    return value or None


def parse_k(raw: str) -> int:
    text = raw.strip()
    if not re.fullmatch(r"[0-9]{1,9}", text):
        raise SettingsError("JANUS_K must be an integer >= 20")
    value = int(text)
    if value < K_MIN:
        raise SettingsError("JANUS_K must be an integer >= 20")
    return value


def parse_epsilon(raw: str) -> Fraction:
    """Parse ε exactly as a decimal; accept only 0 < ε <= 10."""
    text = raw.strip()
    if not re.fullmatch(r"[0-9]{1,3}(\.[0-9]{1,6})?", text):
        raise SettingsError("JANUS_DP_EPSILON must be a decimal in (0, 10]")
    try:
        value = Fraction(Decimal(text))
    except (InvalidOperation, ValueError) as exc:
        raise SettingsError("JANUS_DP_EPSILON must be a decimal in (0, 10]") from exc
    if not (0 < value <= EPSILON_MAX):
        raise SettingsError("JANUS_DP_EPSILON must be a decimal in (0, 10]")
    return value


def parse_consent_versions(raw: str) -> frozenset[str]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for part in parts:
        if not CONSENT_VERSION_RE.fullmatch(part):
            raise SettingsError("JANUS_CONSENT_VERSIONS has an invalid consent version id")
    return frozenset(parts)


def parse_noise_key(raw: str) -> bytes | None:
    text = raw.strip()
    if not text:
        return None
    try:
        key = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError) as exc:
        raise SettingsError("JANUS_NOISE_KEY must be base64url") from exc
    if len(key) < NOISE_KEY_MIN_BYTES:
        raise SettingsError("JANUS_NOISE_KEY must decode to at least 32 bytes")
    return key
