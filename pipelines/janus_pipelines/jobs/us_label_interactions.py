"""`us_label_interactions` pipeline: the "Drug Interactions" section of US drug labels, from the
openFDA drug label bulk download (safety-check design §5). Data CC0 1.0; not an FDA endorsement.

The download is about 1.8 GB in 14 partitions. Each partition is written to the run's scratch
directory, read as a stream (one label in memory at a time) and removed with the scratch
directory after the run; no label data is committed. Kept: one label per active substance, of
the labels that have a "Drug Interactions" section and exactly one active substance — the most
recently effective one. The section text is kept as published. Finding ingredient names in that
text is the API's job (`janus.safety.interactions`).
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, cast

import polars as pl

from janus_pipelines.core.canonical import Row, sha256_bytes
from janus_pipelines.core.http import BULK_READ_TIMEOUT, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import (
    KIND_NULL,
    Accounting,
    ExpectedSchema,
    Field,
    SchemaMismatchError,
    SchemaReport,
    check_schema,
    kind_of,
)
from janus_pipelines.jobs.us_ndc import INDEX_URL, parse_index
from janus_pipelines.jobs.us_recalls import iso_date, text_or_none

DATASET = "label"
CHUNK = 1 << 20  # characters read from a partition at a time

LABEL_SCHEMA = ExpectedSchema(
    version="us_label_interactions-1",
    fields=(
        Field("set_id", frozenset({"str"})),
        Field("effective_time", frozenset({"str", KIND_NULL})),
        Field("version", frozenset({"str", KIND_NULL})),
        Field("openfda", frozenset({"object", KIND_NULL})),
        Field("drug_interactions", frozenset({"list", KIND_NULL})),
    ),
)

_WS = " \t\r\n"


def iter_results_stream(read: Callable[[int], str]) -> Iterator[dict[str, Any]]:
    """Yield the objects of the top-level "results" array of a JSON document that is read in
    pieces (`read(n)` returns up to n characters, "" at the end). Memory: one piece plus one
    object. Other top-level keys are skipped, like `us_ndc.iter_results`."""
    decoder = json.JSONDecoder()
    buf, pos, eof = "", 0, False

    def fill() -> None:
        nonlocal buf, pos, eof
        piece = read(CHUNK)
        if piece:
            buf, pos = buf[pos:] + piece, 0
        else:
            eof = True

    def skip(chars: str) -> str:
        """Move past `chars`; the next character, or "" at the end of the document."""
        nonlocal pos
        while True:
            while pos < len(buf) and buf[pos] in chars:
                pos += 1
            if pos < len(buf):
                return buf[pos]
            if eof:
                return ""
            fill()

    def value() -> Any:
        nonlocal pos
        while True:
            try:
                obj, end = decoder.raw_decode(buf, pos)
            except json.JSONDecodeError:
                if eof:
                    raise ValueError("label file is not valid JSON") from None
                fill()
                continue
            # A number or literal at the end of a piece may be cut short: read on first.
            if end == len(buf) and not eof and not isinstance(obj, dict | list | str):
                fill()
                continue
            pos = end
            return cast(Any, obj)

    if skip(_WS) != "{":
        raise SchemaMismatchError(SchemaReport(missing=("top-level object",)))
    pos += 1
    while True:
        if skip(_WS + ",") in ("", "}"):
            raise SchemaMismatchError(SchemaReport(missing=("results",)))
        key = value()
        if skip(_WS) != ":":
            raise ValueError("malformed JSON object")
        pos += 1
        skip(_WS)
        if key != "results":
            value()
            continue
        if buf[pos] != "[":
            raise SchemaMismatchError(SchemaReport(wrong_type=(("results", ("not array",)),)))
        pos += 1
        while True:
            nxt = skip(_WS + ",")
            if nxt == "":
                raise ValueError("label file ends inside the results array")
            if nxt == "]":
                return
            obj = value()
            if not isinstance(obj, dict):
                raise SchemaMismatchError(
                    SchemaReport(wrong_type=(("results[]", ("not object",)),))
                )
            yield cast(dict[str, Any], obj)


def iter_partition(path: Path) -> Iterator[dict[str, Any]]:
    """The label records of one downloaded partition (a zip with one JSON file)."""
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.endswith(".json")]
        if len(names) != 1:
            raise SchemaMismatchError(SchemaReport(missing=("one .json file in the zip",)))
        with zf.open(names[0]) as raw, io.TextIOWrapper(raw, encoding="utf-8") as text:
            yield from iter_results_stream(text.read)


def _strs(value: object) -> list[str]:
    if isinstance(value, list):
        return [v for v in cast(list[object], value) if isinstance(v, str)]
    return []


def label_row(rec: Mapping[str, Any]) -> tuple[Row | None, str | None]:
    """The row of a label that can be kept, or the reason it is excluded."""
    text = "\n".join(t.strip() for t in _strs(rec.get("drug_interactions")) if t.strip())
    if not text:
        return None, "no_interactions_section"
    set_id = text_or_none(rec.get("set_id"))
    if set_id is None:
        return None, "no_set_id"
    raw_openfda = rec.get("openfda")
    openfda = cast(dict[str, Any], raw_openfda) if isinstance(raw_openfda, dict) else {}
    substances = sorted({s.strip() for s in _strs(openfda.get("substance_name")) if s.strip()})
    if len(substances) != 1:
        return None, "no_substance_name" if not substances else "several_substances"
    types = _strs(openfda.get("product_type"))
    return {
        "substance_name": substances[0],
        "set_id": set_id,
        "version": text_or_none(rec.get("version")),
        "effective_date": iso_date(rec.get("effective_time")),
        "product_type": types[0] if types else None,
        "text": text,
    }, None


def newer(a: Row, b: Row) -> bool:
    """`a` replaces `b` as the label of a substance: the later effective date; for one date the
    smaller set id (so the choice does not depend on the order of the download)."""
    date_a, date_b = str(a["effective_date"] or ""), str(b["effective_date"] or "")
    return date_a > date_b or (date_a == date_b and str(a["set_id"]) < str(b["set_id"]))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_partitions(index_bytes: bytes, paths: tuple[Path, ...]) -> ParseResult:
    index = parse_index(index_bytes, DATASET)
    if len(paths) != len(index.partitions):
        raise ValueError("number of downloaded partitions differs from the index")
    acc = Accounting()
    present: dict[str, set[str]] = {}
    absent: set[str] = set()
    best: dict[str, Row] = {}
    labels_per_substance: dict[str, int] = {}
    for path in paths:
        for rec in iter_partition(path):
            acc.input_rows += 1
            for name in LABEL_SCHEMA.names:
                if name in rec:
                    present.setdefault(name, set()).add(kind_of(rec[name]))
                else:
                    absent.add(name)
            row, reason = label_row(rec)
            if row is None:
                acc.exclude(reason or "excluded")
                continue
            name = str(row["substance_name"])
            labels_per_substance[name] = labels_per_substance.get(name, 0) + 1
            if name not in best:
                best[name] = row
            else:
                acc.exclude("older_label_of_the_substance")
                if newer(row, best[name]):
                    best[name] = row
    for f in absent & present.keys():
        if f != "set_id":
            present[f].add(KIND_NULL)
    report = check_schema(LABEL_SCHEMA, {k: frozenset(v) for k, v in present.items()})
    if acc.input_rows != index.expected_records:
        raise ValueError(
            f"parsed {acc.input_rows} label records; download index lists {index.expected_records}"
        )
    rows: list[Row] = [
        {**best[name], "labels_of_substance": labels_per_substance[name]} for name in sorted(best)
    ]
    dates = sorted(str(r["effective_date"]) for r in rows if r["effective_date"])
    return ParseResult(
        rows=rows,
        input_rows=acc.input_rows,
        excluded=acc.excluded,
        schema=report,
        metrics={
            "labels": acc.input_rows,
            "substances": len(rows),
            "text_characters": sum(len(str(r["text"])) for r in rows),
            "longest_text": max((len(str(r["text"])) for r in rows), default=0),
            "without_effective_date": sum(1 for r in rows if not r["effective_date"]),
            "first_effective_date": dates[0] if dates else None,
            "last_effective_date": dates[-1] if dates else None,
        },
    )


@dataclass(frozen=True)
class Payload:
    index: bytes
    partitions: tuple[Path, ...]


class UsLabelInteractionsJob(Job[Payload]):
    name = "us_label_interactions"
    source_id = "openfda_label_interactions"
    schema = LABEL_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "substance_name": pl.String(),
        "set_id": pl.String(),
        "version": pl.String(),
        "effective_date": pl.String(),
        "product_type": pl.String(),
        "text": pl.String(),
        "labels_of_substance": pl.Int64(),
    }

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        retrieved = ctx.now()
        if "input" in ctx.options:
            # Local copies: `download.json` and the partition zips under their published names.
            folder = Path(ctx.options["input"])
            index_bytes = (folder / "download.json").read_bytes()
            index = parse_index(index_bytes, DATASET)
            paths = tuple(folder / p.url.rsplit("/", 1)[-1] for p in index.partitions)
        else:
            fetcher = make_fetcher(require_contact=False)
            index_bytes = fetcher.get(INDEX_URL).content
            index = parse_index(index_bytes, DATASET)
            scratch = ctx.scratch_dir(self.name)
            found: list[Path] = []
            for p in index.partitions:
                path = scratch / p.url.rsplit("/", 1)[-1]
                path.write_bytes(fetcher.get(p.url, read_timeout=BULK_READ_TIMEOUT).content)
                found.append(path)
            paths = tuple(found)
        digest = sha256_bytes("".join(file_sha256(p) for p in paths).encode())
        return RawInput(
            payload=Payload(index_bytes, paths),
            source_urls=(INDEX_URL, *(p.url for p in index.partitions)),
            source_sha256=digest,
            retrieved_at=retrieved,
            snapshot_date=index.export_date,
            # The partitions (1.8 GB) are not kept; the index names them and their sizes.
            raw_files={"download.json": index_bytes},
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        return parse_partitions(raw.payload.index, raw.payload.partitions)
