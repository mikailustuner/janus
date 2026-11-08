"""QR address and size rule (doctor-loop design §6.4, §6.6; owner decision 2026-11-08).

The token goes only into the URL fragment. The whole address must fit a QR code of version 25 or
lower at error correction level M in byte mode, which prints legibly on A4 at 50 mm or more
(125 modules with the quiet zone, 0.4 mm per module). When the note's findings do not all fit,
the token keeps the longest prefix that does.

Capacity: data codewords per version at level M (ISO/IEC 18004). Checked on 2026-11-08 against
`segno` 1.6.6 (byte capacities 14 ... 2,331 = codewords minus mode and count bits); not a
dependency.
"""

from __future__ import annotations

import dataclasses
from typing import Final

from janus.notes.token import Keyring, Payload, b64encode, encode_body, sign

CODEWORDS_M: Final[dict[int, int]] = {
    1: 16, 2: 28, 3: 44, 4: 64, 5: 86, 6: 108, 7: 124, 8: 154, 9: 182, 10: 216,
    11: 254, 12: 290, 13: 334, 14: 365, 15: 415, 16: 453, 17: 507, 18: 563, 19: 627, 20: 669,
    21: 714, 22: 782, 23: 860, 24: 914, 25: 1000, 26: 1062, 27: 1128, 28: 1193, 29: 1267,
    30: 1373, 31: 1455, 32: 1541, 33: 1631, 34: 1725, 35: 1812, 36: 1914, 37: 1992, 38: 2102,
    39: 2216, 40: 2334,
}  # fmt: skip
MAX_VERSION: Final = 25
MAX_BASE_URL_BYTES: Final = 40
OUTCOME_PATH: Final = "/o#"
MIN_GUARANTEED_FINDINGS: Final = 11  # with every field at its maximum (design §6.6, P33)


def byte_mode_bits(n_bytes: int, version: int) -> int:
    """Bits of one byte-mode segment: mode indicator, character count, data."""
    return 4 + (8 if version <= 9 else 16) + 8 * n_bytes


def qr_version(content: str) -> int | None:
    """Smallest version at level M whose capacity holds `content` in byte mode."""
    n = len(content.encode("utf-8"))
    for version, codewords in CODEWORDS_M.items():
        if byte_mode_bits(n, version) <= 8 * codewords:
            return version
    return None


def outcome_url(base: str, token: str) -> str:
    """The QR address: the token only in the fragment, never in the path or query."""
    return base + OUTCOME_PATH + token


def token_length(payload: Payload) -> int:
    """Characters of the base64url token for `payload` (no key needed)."""
    return len(b64encode(encode_body(payload) + bytes(16)))


def fits(payload: Payload) -> bool:
    """Whether the address with the longest allowed base fits `MAX_VERSION`."""
    n = MAX_BASE_URL_BYTES + len(OUTCOME_PATH) + token_length(payload)
    version = qr_version("x" * n)
    return version is not None and version <= MAX_VERSION


def fit_findings(keyring: Keyring, payload: Payload) -> tuple[str, int]:
    """Sign the longest prefix of `payload.findings` that fits; return (token, findings kept)."""
    lo, hi = 0, len(payload.findings)
    while lo < hi:  # largest k in [1, n] with fits(prefix k); prefixes grow monotonically
        mid = (lo + hi + 1) // 2
        if fits(dataclasses.replace(payload, findings=payload.findings[:mid])):
            lo = mid
        else:
            hi = mid - 1
    if lo == 0:
        raise ValueError("not even one finding fits the QR code")
    kept = dataclasses.replace(payload, findings=payload.findings[:lo])
    return sign(keyring, kept), lo
