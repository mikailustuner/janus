"""Deletion tokens (privacy design §5.3, DP9): 256 random bits, only a SHA-256 hash is stored."""

from __future__ import annotations

import base64
import hashlib
import secrets

PREFIX = "jdt_"


def new_token() -> str:
    raw = secrets.token_bytes(32)
    return PREFIX + base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()
