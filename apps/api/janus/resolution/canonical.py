"""Canonical row serialisation and content hash (drug-resolution design §6.2). Pure.

Same algorithm as `pipelines/janus_pipelines/core/canonical.py` (the API image does not include
the pipelines project). Both test suites assert the same golden vector so they cannot drift.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import tempfile
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

type Json = bool | int | float | str | Sequence[Json] | Mapping[str, Json] | None
type Row = Mapping[str, Json]


def canonical_value(value: Json) -> Json:
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        return {unicodedata.normalize("NFC", k): canonical_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical_value(v) for v in value]
    return value


def canonical_line(row: Row) -> str:
    return json.dumps(
        canonical_value(row),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def content_hash(rows: Iterable[Row], schema_version: str) -> str:
    lines = sorted((canonical_line(r) for r in rows), key=lambda s: s.encode("utf-8"))
    digest = hashlib.sha256()
    digest.update(schema_version.encode("utf-8"))
    digest.update(b"\n")
    digest.update("\n".join(lines).encode("utf-8"))
    return digest.hexdigest()


DEFAULT_CHUNK = 100_000


def content_hash_stream(
    rows: Iterable[Row],
    schema_version: str,
    *,
    chunk: int = DEFAULT_CHUNK,
    tmp_dir: Path | None = None,
) -> str:
    """Same hash as `content_hash`, with memory bounded by `chunk` canonical lines (design §12.1).

    Lines are sorted in chunks on disk and merged, so the digest sees exactly the bytes the
    in-memory function feeds it. Canonical lines never contain a raw newline (JSON escapes it).
    """
    if chunk < 1:
        raise ValueError("chunk must be at least 1")
    digest = hashlib.sha256()
    digest.update(schema_version.encode("utf-8"))
    digest.update(b"\n")
    with tempfile.TemporaryDirectory(dir=tmp_dir, prefix="hash-") as work:
        parts: list[Path] = []
        buffer: list[bytes] = []

        def flush() -> None:
            if not buffer:
                return
            buffer.sort()
            path = Path(work) / f"part-{len(parts)}"
            with path.open("wb") as f:
                f.write(b"\n".join(buffer))
                f.write(b"\n")
            parts.append(path)
            buffer.clear()

        for row in rows:
            buffer.append(canonical_line(row).encode("utf-8"))
            if len(buffer) >= chunk:
                flush()
        flush()
        files = [p.open("rb") for p in parts]
        try:
            first = True
            for line in heapq.merge(*files):
                if not first:
                    digest.update(b"\n")
                digest.update(line.rstrip(b"\n"))
                first = False
        finally:
            for f in files:
                f.close()
    return digest.hexdigest()


# Golden vector shared with pipelines/tests/test_canonical_properties.py.
GOLDEN_SCHEMA = "golden-1"
GOLDEN_ROWS: tuple[Row, ...] = (
    {"barcode": "8680199094206", "ingredients": ["b", "a"], "atc_code": "C09BB03", "n": 1},
    {"barcode": None, "name_only": True, "product_name": "İ\u0307ç", "x": {"k": [1.5, False]}},
)
