"""Canonical row serialisation and content hash (design §3.3, Req 1.3).

The hash depends only on the rows and the schema version: not on input row order, file
format, run id, timestamps or code version.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterable, Mapping, Sequence

type Json = bool | int | float | str | Sequence[Json] | Mapping[str, Json] | None
type Row = Mapping[str, Json]


def canonical_value(value: Json) -> Json:
    """Return the value with every string NFC-normalised; lists keep their order."""
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        return {unicodedata.normalize("NFC", k): canonical_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical_value(v) for v in value]
    return value


def canonical_line(row: Row) -> str:
    """One row as compact JSON with sorted keys."""
    return json.dumps(
        canonical_value(row),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_lines(rows: Iterable[Row]) -> list[str]:
    """All rows as canonical lines, sorted by their UTF-8 bytes."""
    return sorted((canonical_line(r) for r in rows), key=lambda s: s.encode("utf-8"))


def content_hash(rows: Iterable[Row], schema_version: str) -> str:
    """SHA-256 over the schema version and the sorted canonical lines."""
    digest = hashlib.sha256()
    digest.update(schema_version.encode("utf-8"))
    digest.update(b"\n")
    digest.update("\n".join(canonical_lines(rows)).encode("utf-8"))
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
