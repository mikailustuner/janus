"""API settings, read from the environment once at startup (privacy design §3).

Invalid values stop the process with the variable's name. Secret values are never echoed.
"""

from __future__ import annotations

import base64
import binascii
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

K_MIN = 20
EPSILON_MAX = Fraction(10)
NOISE_KEY_MIN_BYTES = 32
CONSENT_VERSION_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,31}$")
NOTE_KEY_ID_RE = re.compile(r"^[a-z0-9]{1,8}$")
NOTE_KEY_MIN_BYTES = 32
PUBLIC_BASE_URL_MAX_BYTES = 40  # doctor-loop design §6.6: the QR size rule assumes at most 40 bytes
_PUBLIC_BASE_URL_RE = re.compile(
    r"^(https://[a-z0-9.-]+(:[0-9]{1,5})?|http://(localhost|127\.0\.0\.1)(:[0-9]{1,5})?)(/[A-Za-z0-9._~-]+)*$"
)
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
    # Outcome loop (doctor-loop design §3). Keys are never logged or returned; not in repr.
    note_keys: Mapping[str, bytes] = field(default_factory=dict[str, bytes], repr=False)
    note_signing_key_id: str | None = None
    outcome_consent_versions: frozenset[str] = frozenset()
    public_base_url: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        e = os.environ if env is None else env
        noise_key = parse_noise_key(e.get("JANUS_NOISE_KEY", ""))
        note_keys = parse_note_keys(e.get("JANUS_NOTE_KEYS", ""))
        signing = parse_signing_key_id(_optional(e, "JANUS_NOTE_SIGNING_KEY_ID"), note_keys)
        if noise_key is not None and noise_key in note_keys.values():
            raise SettingsError("JANUS_NOTE_KEYS must not reuse JANUS_NOISE_KEY")
        return cls(
            database_url=_optional(e, "DATABASE_URL"),
            donation_region=_optional(e, "JANUS_DONATION_REGION"),
            consent_versions=parse_consent_versions(e.get("JANUS_CONSENT_VERSIONS", "")),
            event_vocabulary_path=Path(_optional(e, "JANUS_EVENT_VOCABULARY") or EVENT_VOCABULARY),
            k=parse_k(e.get("JANUS_K", str(K_MIN))),
            epsilon=parse_epsilon(e.get("JANUS_DP_EPSILON", "1")),
            noise_key=noise_key,
            data_dir=_path_or_none(_optional(e, "JANUS_DATA_DIR")),
            note_keys=note_keys,
            note_signing_key_id=signing,
            outcome_consent_versions=parse_consent_versions(
                e.get("JANUS_OUTCOME_CONSENT_VERSIONS", ""), "JANUS_OUTCOME_CONSENT_VERSIONS"
            ),
            public_base_url=parse_public_base_url(e.get("JANUS_PUBLIC_BASE_URL", "")),
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


def parse_consent_versions(raw: str, name: str = "JANUS_CONSENT_VERSIONS") -> frozenset[str]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    for part in parts:
        if not CONSENT_VERSION_RE.fullmatch(part):
            raise SettingsError(f"{name} has an invalid consent version id")
    return frozenset(parts)


def _b64url_key(text: str, name: str, min_bytes: int) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise SettingsError(f"{name} must be base64url")
    try:
        key = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError) as exc:
        raise SettingsError(f"{name} must be base64url") from exc
    if len(key) < min_bytes:
        raise SettingsError(f"{name} keys must decode to at least {min_bytes} bytes")
    return key


def parse_note_keys(raw: str) -> dict[str, bytes]:
    """`kid:base64url,kid:base64url`; empty means the outcome loop is off."""
    keys: dict[str, bytes] = {}
    for part in (p.strip() for p in raw.split(",")):
        if not part:
            continue
        kid, sep, value = part.partition(":")
        if not sep or not NOTE_KEY_ID_RE.fullmatch(kid):
            raise SettingsError("JANUS_NOTE_KEYS has an invalid key id")
        if kid in keys:
            raise SettingsError("JANUS_NOTE_KEYS repeats a key id")
        key = _b64url_key(value.strip(), "JANUS_NOTE_KEYS", NOTE_KEY_MIN_BYTES)
        if key in keys.values():
            raise SettingsError("JANUS_NOTE_KEYS repeats a key")
        keys[kid] = key
    return keys


def parse_signing_key_id(kid: str | None, keys: Mapping[str, bytes]) -> str | None:
    if not keys:
        if kid is not None:
            raise SettingsError("JANUS_NOTE_SIGNING_KEY_ID needs JANUS_NOTE_KEYS")
        return None
    if kid is None:
        raise SettingsError("JANUS_NOTE_SIGNING_KEY_ID is required with JANUS_NOTE_KEYS")
    if kid not in keys:
        raise SettingsError("JANUS_NOTE_SIGNING_KEY_ID must name a key of JANUS_NOTE_KEYS")
    return kid


def parse_public_base_url(raw: str) -> str | None:
    text = raw.strip()
    if not text:
        return None
    if len(text.encode("utf-8")) > PUBLIC_BASE_URL_MAX_BYTES or not _PUBLIC_BASE_URL_RE.fullmatch(
        text
    ):
        raise SettingsError(
            "JANUS_PUBLIC_BASE_URL must be https://host[/path] (no query, fragment or trailing "
            "slash, at most 40 bytes)"
        )
    return text


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
