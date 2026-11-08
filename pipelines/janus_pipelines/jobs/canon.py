"""`canon` pipeline: OpenITI Canon Book 2 → entries and theme spans (séance design §3, Req 1).

The source is pinned to one OpenITI commit and checked against its git blob hash. Derived files
are written to the separate CC BY-NC-SA 4.0 data package `datasets/canon/`, never under
`data/` or into Apache-licensed code (Req 3.1).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar, Final

import polars as pl

from janus_pipelines.core.canonical import Row, sha256_bytes
from janus_pipelines.core.http import BULK_READ_TIMEOUT, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.store import Store
from janus_pipelines.core.validation import ExpectedSchema, Field, SchemaReport
from janus_pipelines.jobs.canon_text import (
    EXPECTED_HEADINGS,
    Entry,
    rule_extract,
    split_book2,
    theme_spans,
)
from janus_pipelines.jobs.canon_text import entry_id as make_entry_id

# Pinned version (verified 2026-11-08): OpenITI/0450AH, last commit touching the file.
OPENITI_REPO: Final = "OpenITI/0450AH"
OPENITI_COMMIT: Final = "81d1d9e0f0af42a822f0136fe4f49776471ef702"
OPENITI_COMMIT_DATE: Final = "2025-11-27"
VERSION_URI: Final = "0428IbnSina.QanunFiTibb.Shamela0010706-ara1"
FILE_PATH: Final = (
    "data/0428IbnSina/0428IbnSina.QanunFiTibb/0428IbnSina.QanunFiTibb.Shamela0010706-ara1.completed"
)
BLOB_SHA1: Final = "de2e584560c19a18c0dca75edb435c673c69fcb9"  # GitHub contents API
SOURCE_URL: Final = f"https://raw.githubusercontent.com/{OPENITI_REPO}/{OPENITI_COMMIT}/{FILE_PATH}"
RELEASE_DOI: Final = "10.5281/zenodo.17767721"  # OpenITI release 2025.1.9, licence record
LICENSE: Final = "CC BY-NC-SA 4.0"
ISSUES: Final = "MANY_TYPOS, PAGINATION, MISSING_PARTS, PRIMARY_VERSION, CLEANED_VERSION"
PACKAGE: Final = Path("datasets") / "canon"

CANON_SCHEMA = ExpectedSchema(
    version="canon-1",
    fields=(
        Field("heading", frozenset({"str"})),
        Field("level", frozenset({"int"})),
    ),
)

ENTRY_COLUMNS: Final = (
    "entry_id",
    "index",
    "level",
    "heading",
    "parent_id",
    "line_start",
    "line_end",
    "page",
    "themes",
    "spans",
)
SPAN_COLUMNS: Final = (
    "span_id",
    "entry_id",
    "section",
    "themes",
    "terms_ar",
    "conditions_en",
    "line_start",
    "line_end",
    "arabic_span",
    "rule_forms",
    "rule_vehicles",
    "rule_parts",
    "rule_actions",
)


class SourceVersionError(ValueError):
    """The downloaded file is not the pinned OpenITI version."""


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def span_id(entry_id: str, line_start: int, arabic_span: str) -> str:
    """Stable id: entry, first source line and a short hash of the span text. A changed span
    gets a new id, so a review of the old text can never attach to the new one."""
    digest = hashlib.sha256(arabic_span.encode("utf-8")).hexdigest()[:6]
    return f"{entry_id}.l{line_start}.{digest}"


def span_rows(entry: Entry) -> list[dict[str, str | int]]:
    out: list[dict[str, str | int]] = []
    for sp in theme_spans(entry):
        rule = rule_extract(entry, sp)
        text = entry.text[sp.start : sp.end]
        out.append(
            {
                "span_id": span_id(entry.entry_id, sp.line_start, text),
                "entry_id": entry.entry_id,
                "section": sp.section,
                "themes": "|".join(sp.themes),
                "terms_ar": "|".join(sp.terms),
                "conditions_en": "|".join(rule.conditions_en),
                "line_start": sp.line_start,
                "line_end": sp.line_end,
                "arabic_span": text,
                "rule_forms": "|".join(rule.forms),
                "rule_vehicles": "|".join(rule.vehicles),
                "rule_parts": "|".join(rule.parts),
                "rule_actions": "|".join(rule.actions),
            }
        )
    return out


def entry_rows(entries: list[Entry]) -> list[Row]:
    rows: list[Row] = []
    for e in entries:
        spans = span_rows(e)
        themes = sorted({t for s in spans for t in str(s["themes"]).split("|")})
        rows.append(
            {
                "entry_id": e.entry_id,
                "index": e.index,
                "level": e.level,
                "heading": e.heading,
                "parent_id": None if e.parent is None else make_entry_id(e.parent),
                "line_start": e.line_start,
                "line_end": e.line_end,
                "page": e.page,
                "themes": "|".join(themes),
                "spans": len(spans),
                "spans_json": json.dumps(spans, ensure_ascii=False, sort_keys=True),
            }
        )
    return rows


def _csv(rows: list[Mapping[str, object]], columns: tuple[str, ...]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: "" if r.get(k) is None else r.get(k) for k in columns})
    return buf.getvalue()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    os.replace(tmp, path)


class CanonJob(Job[bytes]):
    name = "canon"
    source_id = "openiti_canon"
    schema = CANON_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "entry_id": pl.String(),
        "index": pl.Int64(),
        "level": pl.Int64(),
        "heading": pl.String(),
        "parent_id": pl.String(),
        "line_start": pl.Int64(),
        "line_end": pl.Int64(),
        "page": pl.String(),
        "themes": pl.String(),
        "spans": pl.Int64(),
        "spans_json": pl.String(),
    }

    def fetch(self, ctx: RunContext) -> RawInput[bytes]:
        retrieved = ctx.now()
        if "input" in ctx.options:
            data = Path(ctx.options["input"]).read_bytes()
        else:
            fetcher = make_fetcher(require_contact=False)
            data = fetcher.get(SOURCE_URL, read_timeout=BULK_READ_TIMEOUT).content
        if git_blob_sha1(data) != BLOB_SHA1:
            raise SourceVersionError("the Canon text is not the pinned OpenITI version")
        return RawInput(
            payload=data,
            source_urls=(SOURCE_URL,),
            source_sha256=sha256_bytes(data),
            retrieved_at=retrieved,
            snapshot_date=OPENITI_COMMIT_DATE,
        )

    def parse(self, raw: RawInput[bytes]) -> ParseResult:
        entries = split_book2(raw.payload.decode("utf-8"))
        rows = entry_rows(entries)
        reasons: list[str] = []
        if len(entries) != EXPECTED_HEADINGS:
            reasons.append(f"expected {EXPECTED_HEADINGS} Book 2 headings, found {len(entries)}")
        with_spans = sum(1 for r in rows if int(str(r["spans"])) > 0)
        return ParseResult(
            rows=rows,
            input_rows=len(entries),
            excluded={},
            schema=SchemaReport(),
            metrics={
                "headings": len(entries),
                "simple_drug_headings": sum(1 for e in entries if e.level == 6),
                "entries_with_theme_spans": with_spans,
                "theme_spans": sum(int(str(r["spans"])) for r in rows),
            },
            review_reasons=reasons,
        )

    def extra_output_paths(self, ctx: RunContext) -> list[Path]:
        pkg = ctx.repo_root / PACKAGE
        return [pkg / "entries.csv", pkg / "theme_spans.csv", pkg / "source.json"]

    def on_promote(self, ctx: RunContext, store: Store, run_id: str) -> None:
        """Write the derived files of the CC BY-NC-SA data package (Req 1.1, 1.2, 3.1)."""
        manifest = store.read_manifest(run_id)
        rows = sorted(store.read_rows(run_id), key=lambda r: int(str(r["index"])))
        spans: list[Mapping[str, object]] = []
        for r in rows:
            spans.extend(json.loads(str(r["spans_json"])))
        source = {
            "source_id": self.source_id,
            "title": "Ibn Sina, al-Qanun fi al-Tibb, Book 2 (al-Adwiya al-mufrada)",
            "version_uri": VERSION_URI,
            "repository": f"https://github.com/{OPENITI_REPO}",
            "commit": OPENITI_COMMIT,
            "commit_date": OPENITI_COMMIT_DATE,
            "file": FILE_PATH,
            "source_url": SOURCE_URL,
            "git_blob_sha1": BLOB_SHA1,
            "source_sha256": manifest.source_sha256,
            "release_doi": RELEASE_DOI,
            "license": LICENSE,
            "openiti_issues": ISSUES,
            "run_id": run_id,
            "content_sha256": manifest.content_sha256,
            "code_version": manifest.code_version,
            "headings": len(rows),
            "theme_spans": len(spans),
        }
        out = self.extra_output_paths(ctx)
        _atomic_write(out[0], _csv(list(rows), ENTRY_COLUMNS))
        _atomic_write(out[1], _csv(spans, SPAN_COLUMNS))
        _atomic_write(out[2], json.dumps(source, indent=2, ensure_ascii=False) + "\n")
