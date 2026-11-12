"""Note token: a signed payload of codes only (doctor-loop design §6; owner decision 2026-11-08).

The token travels in the URL fragment of the QR address and reaches the API only in a JSON body.
It carries the note's finding codes so that the server keeps no record between issue and use; it
holds no name, no free text, no start month, no product id and no date finer than a week.

Binary layout (big-endian, version 1), then canonical base64url without padding:

    version 1 | kid len 1, kid | note id 16 | issue week 2 | expiry week 2 | lang*3+region 1
    | consent len 1, consent | event count 1, (len 1, key)* | finding count 1, finding*
    | mac 16 = HMAC-SHA256(key[kid], DOMAIN + everything before)[:16]

    finding = row 1 | flags 1 | event index 1 | index key varint | marker key varint | codes 4*

Pure: no I/O, no clock (the caller passes `today`).
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import hmac
import re
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Literal

VERSION: Final = 1
DOMAIN: Final = b"janus-note-token\x00"
MAC_BYTES: Final = 16
NOTE_ID_BYTES: Final = 16
VALIDITY_WEEKS: Final = 5
EPOCH_MONDAY: Final = dt.date(1970, 1, 5)
MAX_FINDINGS: Final = 255
MAX_CODES_PER_SIDE: Final = 2
MAX_TOKEN_CHARS: Final = 4096
LANGUAGES: Final = ("en", "tr", "de", "fr", "es", "pt")
REGIONS: Final = ("TR", "EU", "US")
DIRECTIONS: Final = ("adverse", "benefit")

KID_RE: Final = re.compile(r"^[a-z0-9]{1,8}$")
CONSENT_RE: Final = re.compile(r"^[a-z0-9][a-z0-9.-]{0,31}$")
EVENT_RE: Final = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,39}$")
KEY_RE: Final = re.compile(r"^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$")
ATC_RE: Final = re.compile(r"^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$")
_B64_RE: Final = re.compile(r"^[A-Za-z0-9_-]+$")

Language = Literal["en", "tr", "de", "fr", "es", "pt"]
Region = Literal["TR", "EU", "US"]
Direction = Literal["adverse", "benefit"]


class TokenErrorCode(StrEnum):
    invalid_token = "invalid_token"  # noqa: S105 (an error code, not a secret)
    token_expired = "token_expired"  # noqa: S105


class TokenError(ValueError):
    """A token that cannot be used. The message is the code only; it never holds token bytes."""

    def __init__(self, code: TokenErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


def _invalid() -> TokenError:
    return TokenError(TokenErrorCode.invalid_token)


@dataclass(frozen=True)
class Keyring:
    """Signing keys by key id; `signing` names the key used for new tokens (design §6.3)."""

    keys: Mapping[str, bytes] = field(repr=False)
    signing: str

    def __post_init__(self) -> None:
        if not self.keys or self.signing not in self.keys:
            raise ValueError("the signing key id must name a configured key")
        for kid in self.keys:
            if not KID_RE.fullmatch(kid):
                raise ValueError("bad key id")
        object.__setattr__(self, "keys", MappingProxyType(dict(self.keys)))

    def __repr__(self) -> str:
        return f"Keyring(kids={sorted(self.keys)!r}, signing={self.signing!r})"


@dataclass(frozen=True)
class TokenFinding:
    row: int
    index_key: str
    marker_key: str
    index_codes: tuple[str, ...]
    marker_codes: tuple[str, ...]
    event: str
    direction: Direction
    form_confirmed: bool

    def __post_init__(self) -> None:
        if not 1 <= self.row <= 65:
            raise ValueError("row")
        if not (KEY_RE.fullmatch(self.index_key) and KEY_RE.fullmatch(self.marker_key)):
            raise ValueError("key")
        for codes in (self.index_codes, self.marker_codes):
            if not 1 <= len(codes) <= MAX_CODES_PER_SIDE or list(codes) != sorted(set(codes)):
                raise ValueError("codes")
            if not all(ATC_RE.fullmatch(c) for c in codes):
                raise ValueError("code")
        if not EVENT_RE.fullmatch(self.event):
            raise ValueError("event")
        if self.direction not in DIRECTIONS:
            raise ValueError("direction")


@dataclass(frozen=True)
class Payload:
    kid: str
    note_id: bytes
    issue_week: dt.date  # a Monday
    language: Language
    region: Region
    consent_version: str
    findings: tuple[TokenFinding, ...]

    def __post_init__(self) -> None:
        if not KID_RE.fullmatch(self.kid):
            raise ValueError("kid")
        if len(self.note_id) != NOTE_ID_BYTES:
            raise ValueError("note id")
        if self.issue_week.weekday() != 0 or self.issue_week < EPOCH_MONDAY:
            raise ValueError("issue week")
        if _week_number(self.issue_week) + VALIDITY_WEEKS > 0xFFFF:
            raise ValueError("issue week")
        if self.language not in LANGUAGES or self.region not in REGIONS:
            raise ValueError("language or region")
        if not CONSENT_RE.fullmatch(self.consent_version):
            raise ValueError("consent version")
        if not 1 <= len(self.findings) <= MAX_FINDINGS:
            raise ValueError("findings")

    @property
    def expires_on(self) -> dt.date:
        return self.issue_week + dt.timedelta(weeks=VALIDITY_WEEKS)

    @property
    def note_hash(self) -> bytes:
        return hashlib.sha256(self.note_id).digest()


# --- dates ------------------------------------------------------------------------------------


def monday_of(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def expiry_for(now: dt.datetime) -> dt.date:
    """Expiry of a token issued at `now`: the Monday five weeks after the issue week's Monday."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return monday_of(now.astimezone(dt.UTC).date()) + dt.timedelta(weeks=VALIDITY_WEEKS)


def _week_number(monday: dt.date) -> int:
    return (monday - EPOCH_MONDAY).days // 7


def new_note_id() -> bytes:
    return secrets.token_bytes(NOTE_ID_BYTES)


# --- primitive codecs -------------------------------------------------------------------------


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _key_number(key: str) -> int:
    return int(key[1:]) * 2 + (1 if key[0] == "J" else 0)


def _key_from_number(n: int) -> str:
    key = ("J" if n & 1 else "Q") + str(n >> 1)
    if not KEY_RE.fullmatch(key):
        raise _invalid()
    return key


def pack_atc(code: str) -> bytes:
    a, b, c, d = ord(code[0]) - 65, int(code[1:3]), ord(code[3]) - 65, ord(code[4]) - 65
    e = int(code[5:7])
    value = ((((a << 7 | b) << 5 | c) << 5 | d) << 7 | e) << 3
    return value.to_bytes(4, "big")


def unpack_atc(raw: bytes) -> str:
    value = int.from_bytes(raw, "big")
    if value & 0b111:
        raise _invalid()
    value >>= 3
    e = value & 0x7F
    value >>= 7
    d = value & 0x1F
    value >>= 5
    c = value & 0x1F
    value >>= 5
    b = value & 0x7F
    a = value >> 7
    if a > 25 or c > 25 or d > 25 or b > 99 or e > 99:
        raise _invalid()
    return f"{chr(65 + a)}{b:02d}{chr(65 + c)}{chr(65 + d)}{e:02d}"


def _ascii(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64decode_canonical(text: str) -> bytes:
    if not text or len(text) > MAX_TOKEN_CHARS or not _B64_RE.fullmatch(text) or len(text) % 4 == 1:
        raise _invalid()
    try:
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (binascii.Error, ValueError):
        raise _invalid() from None
    if b64encode(raw) != text:  # non-zero trailing bits
        raise _invalid()
    return raw


# --- payload codec ----------------------------------------------------------------------------


def events_of(findings: Sequence[TokenFinding]) -> list[str]:
    return sorted({f.event for f in findings})


def encode_body(p: Payload) -> bytes:
    """Everything the MAC covers (without the domain prefix)."""
    events = events_of(p.findings)
    index = {e: i for i, e in enumerate(events)}
    out = bytearray([VERSION])
    out += _ascii(p.kid)
    out += p.note_id
    week = _week_number(p.issue_week)
    out += week.to_bytes(2, "big") + (week + VALIDITY_WEEKS).to_bytes(2, "big")
    out.append(LANGUAGES.index(p.language) * 3 + REGIONS.index(p.region))
    out += _ascii(p.consent_version)
    out.append(len(events))
    for e in events:
        out += _ascii(e)
    out.append(len(p.findings))
    for f in p.findings:
        flags = (
            (0x80 if f.form_confirmed else 0)
            | (0x40 if f.direction == "benefit" else 0)
            | (len(f.index_codes) << 3)
            | len(f.marker_codes)
        )
        out += bytes([f.row, flags, index[f.event]])
        out += _varint(_key_number(f.index_key)) + _varint(_key_number(f.marker_key))
        for code in (*f.index_codes, *f.marker_codes):
            out += pack_atc(code)
    return bytes(out)


def body_length(p: Payload) -> int:
    """Byte length of the signed token (body + MAC), from the layout of design §6.1."""
    events = events_of(p.findings)
    n = 1 + 1 + len(p.kid) + NOTE_ID_BYTES + 2 + 2 + 1 + 1 + len(p.consent_version)
    n += 1 + sum(1 + len(e) for e in events) + 1
    for f in p.findings:
        n += 3 + len(_varint(_key_number(f.index_key))) + len(_varint(_key_number(f.marker_key)))
        n += 4 * (len(f.index_codes) + len(f.marker_codes))
    return n + MAC_BYTES


def _mac(key: bytes, body: bytes) -> bytes:
    return hmac.new(key, DOMAIN + body, hashlib.sha256).digest()[:MAC_BYTES]


def sign(keyring: Keyring, payload: Payload) -> str:
    if payload.kid != keyring.signing:
        raise ValueError("a payload is signed with the signing key only")
    body = encode_body(payload)
    return b64encode(body + _mac(keyring.keys[keyring.signing], body))


class _Reader:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.pos = 0

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.raw):
            raise _invalid()
        chunk = self.raw[self.pos : self.pos + n]
        self.pos += n
        return chunk

    def byte(self) -> int:
        return self.take(1)[0]

    def ascii(self, pattern: re.Pattern[str]) -> str:
        n = self.byte()
        try:
            text = self.take(n).decode("ascii")
        except UnicodeDecodeError:
            raise _invalid() from None
        if not pattern.fullmatch(text):
            raise _invalid()
        return text

    def varint(self) -> int:
        value = shift = 0
        for i in range(6):  # at most 42 bits; keys need at most 35
            b = self.byte()
            value |= (b & 0x7F) << shift
            shift += 7
            if not b & 0x80:
                if b == 0 and i > 0:  # non-minimal encoding
                    raise _invalid()
                return value
        raise _invalid()


def _header(raw: bytes) -> tuple[str, int]:
    """Version and key id; returns (kid, offset after kid)."""
    r = _Reader(raw)
    if r.byte() != VERSION:
        raise _invalid()
    return r.ascii(KID_RE), r.pos


def _parse(body: bytes) -> Payload:
    r = _Reader(body)
    r.byte()
    kid = r.ascii(KID_RE)
    note_id = r.take(NOTE_ID_BYTES)
    week = int.from_bytes(r.take(2), "big")
    if int.from_bytes(r.take(2), "big") != week + VALIDITY_WEEKS:
        raise _invalid()
    lr = r.byte()
    if lr >= len(LANGUAGES) * len(REGIONS):
        raise _invalid()
    language, region = LANGUAGES[lr // 3], REGIONS[lr % 3]
    consent = r.ascii(CONSENT_RE)
    events = [r.ascii(EVENT_RE) for _ in range(r.byte())]
    if not events or events != sorted(set(events)):
        raise _invalid()
    n = r.byte()
    findings: list[TokenFinding] = []
    used: set[int] = set()
    for _ in range(n):
        row, flags, ev = r.byte(), r.byte(), r.byte()
        n_index, n_marker = (flags >> 3) & 0b111, flags & 0b111
        if not (1 <= n_index <= MAX_CODES_PER_SIDE and 1 <= n_marker <= MAX_CODES_PER_SIDE):
            raise _invalid()
        if ev >= len(events):
            raise _invalid()
        index_key = _key_from_number(r.varint())
        marker_key = _key_from_number(r.varint())
        index_codes = tuple(unpack_atc(r.take(4)) for _ in range(n_index))
        marker_codes = tuple(unpack_atc(r.take(4)) for _ in range(n_marker))
        used.add(ev)
        try:
            findings.append(
                TokenFinding(
                    row,
                    index_key,
                    marker_key,
                    index_codes,
                    marker_codes,
                    events[ev],
                    "benefit" if flags & 0x40 else "adverse",
                    bool(flags & 0x80),
                )
            )
        except ValueError:
            raise _invalid() from None
    if r.pos != len(body) or used != set(range(len(events))):
        raise _invalid()
    try:
        return Payload(
            kid,
            note_id,
            EPOCH_MONDAY + dt.timedelta(weeks=week),
            language,  # pyright: ignore[reportArgumentType]
            region,  # pyright: ignore[reportArgumentType]
            consent,
            tuple(findings),
        )
    except ValueError:
        raise _invalid() from None


def verify_signature_only(keyring: Keyring, token: str) -> Payload:
    """Steps 1-4 of design §6.2 (withdrawal uses this: expiry does not matter)."""
    raw = b64decode_canonical(token)
    if len(raw) <= MAC_BYTES:
        raise _invalid()
    body, mac = raw[:-MAC_BYTES], raw[-MAC_BYTES:]
    kid, _ = _header(body)
    key = keyring.keys.get(kid)
    if key is None:
        raise _invalid()
    if not hmac.compare_digest(mac, _mac(key, body)):
        raise _invalid()
    return _parse(body)


def verify(keyring: Keyring, token: str, today: dt.date) -> Payload:
    """Steps 1-5 of design §6.2. Raises `TokenError`; never touches a database."""
    payload = verify_signature_only(keyring, token)
    if not today < payload.expires_on:
        raise TokenError(TokenErrorCode.token_expired)
    return payload


def deletion_hash(note_id: bytes, ref: int) -> bytes:
    """Per-outcome deletion hash (design §7.5): unlinkable without the note id."""
    return hashlib.sha256(b"janus-outcome\x00" + note_id + ref.to_bytes(1, "big")).digest()
