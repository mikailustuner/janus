"""An in-memory job for testing the runner and store."""

from __future__ import annotations

import datetime as dt
import json
import tempfile
from collections.abc import Callable, Mapping
from fractions import Fraction
from pathlib import Path
from typing import ClassVar

import polars as pl

from janus_pipelines.core.canonical import Json, Row, sha256_bytes
from janus_pipelines.core.registry import parse_registry
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import ExpectedSchema, Field, check_schema, observe

STUB_SCHEMA = ExpectedSchema(
    version="stub-1",
    fields=(
        Field("id", frozenset({"str"})),
        Field("n", frozenset({"int", "null"})),
        Field("names", frozenset({"list"})),
        Field("flag", frozenset({"bool"})),
    ),
)

type Records = list[dict[str, Json]]

FIXED_NOW = dt.datetime(2026, 11, 7, 12, 0, tzinfo=dt.UTC)


class StubJob(Job[Records]):
    name = "stub"
    source_id = "stub_source"
    schema = STUB_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "id": pl.String(),
        "n": pl.Int64(),
        "names": pl.List(pl.String()),
        "flag": pl.Boolean(),
    }

    def __init__(
        self,
        threshold: Fraction = Fraction(1000),
        review_reasons: list[str] | None = None,
    ) -> None:
        self.review_threshold = threshold
        self.review_reasons = review_reasons or []

    def fetch(self, ctx: RunContext) -> RawInput[Records]:
        raise AssertionError("tests pass raw input directly; no network")

    def parse(self, raw: RawInput[Records]) -> ParseResult:
        report = check_schema(self.schema, observe(raw.payload))
        rows: list[Row] = [dict(r) for r in raw.payload]
        return ParseResult(
            rows=rows,
            input_rows=len(raw.payload),
            excluded={},
            schema=report,
            review_reasons=list(self.review_reasons),
        )


def raw_input(records: Records) -> RawInput[Records]:
    blob = json.dumps(records, sort_keys=True, ensure_ascii=False).encode()
    return RawInput(
        payload=records,
        source_urls=("https://example.org/stub",),
        source_sha256=sha256_bytes(blob),
        retrieved_at=FIXED_NOW,
        snapshot_date="2026-11-07",
    )


STUB_REGISTRY = parse_registry(
    {
        "sections": [{"id": "s", "title": "S"}],
        "sources": [
            {
                "id": "stub_source",
                "section": "s",
                "name": "Stub",
                "license": "CC0",
                "storage": "cache",
                "urls": ["https://example.org/stub"],
            }
        ],
    }
)


def context(
    data_dir: Path,
    repo_root: Path | None = None,
    fault: Callable[[str], None] | None = None,
) -> RunContext:
    ctx = RunContext(
        data_dir=data_dir,
        repo_root=repo_root or Path(tempfile.gettempdir()) / "janus-test-repo-unused",
        registry=STUB_REGISTRY,
        code_version="test",
        now=lambda: FIXED_NOW,
        is_ignored=lambda _p: True,
    )
    if fault is not None:
        ctx.fault = fault
    return ctx


def snapshot_tree(root: Path) -> dict[str, bytes]:
    """All regular files and symlink targets under root, for byte-for-byte comparison."""
    out: dict[str, bytes] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            out[rel] = b"-> " + str(p.readlink()).encode()
        elif p.is_file():
            out[rel] = p.read_bytes()
    return out
