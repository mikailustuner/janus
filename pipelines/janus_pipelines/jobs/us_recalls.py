"""`us_recalls` pipeline: openFDA drug enforcement reports, bulk download (recall-check design §3).

Data CC0 1.0. One row per record (one recalled product of one recall event). Text is kept as
published; dates become ISO dates. Reading NDCs and lot codes out of the free text is the API's
job (`janus.recalls.codes`), next to the NDC rules it shares with drug resolution.

FDA's own limits of this data (https://open.fda.gov/apis/drug/enforcement/): it is not meant as a
way to issue alerts to the public, and a recall's status is not updated after classification.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any, ClassVar

import polars as pl

from janus_pipelines.core.canonical import Row, sha256_bytes
from janus_pipelines.core.http import BULK_READ_TIMEOUT, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import (
    KIND_NULL,
    Accounting,
    ExpectedSchema,
    Field,
    check_schema,
    kind_of,
)
from janus_pipelines.jobs.us_ndc import INDEX_URL, iter_results, parse_index, partition_text

DATASET = "enforcement"
_TEXT = frozenset({"str", KIND_NULL})

RECALL_SCHEMA = ExpectedSchema(
    version="us_recalls-1",
    fields=(
        Field("recall_number", frozenset({"str"})),
        Field("event_id", _TEXT),
        Field("status", _TEXT),
        Field("classification", _TEXT),
        Field("product_description", _TEXT),
        Field("code_info", _TEXT),
        Field("reason_for_recall", _TEXT),
        Field("recalling_firm", _TEXT),
        Field("recall_initiation_date", _TEXT),
        Field("report_date", _TEXT),
    ),
)

# Read when present; absent from many records (kept null there).
OPTIONAL_TEXT = ("more_code_info",)
OPTIONAL_DATES = ("center_classification_date", "termination_date")
DATE_FIELDS = ("recall_initiation_date", "report_date", *OPTIONAL_DATES)

# Most numbers read `D-0233-2025`; about fifty older ones are irregular (`D1151-2015`,
# `D-66403-012`) and are kept as published. Empty and `N/A` are not identifiers.
RECALL_NUMBER = re.compile(r"^[A-Z][A-Z0-9-]{2,19}$")
_YYYYMMDD = re.compile(r"^[0-9]{8}$")


def text_or_none(value: object) -> str | None:
    """A published text without surrounding whitespace; empty or not a string → None."""
    if not isinstance(value, str):
        return None
    return value.strip() or None


def iso_date(value: object) -> str | None:
    """`YYYYMMDD` as published → `YYYY-MM-DD`; anything else, or an impossible date → None."""
    if not isinstance(value, str) or not _YYYYMMDD.match(value.strip()):
        return None
    text = value.strip()
    try:
        return dt.date(int(text[:4]), int(text[4:6]), int(text[6:])).isoformat()
    except ValueError:
        return None


def record_row(rec: Mapping[str, Any]) -> Row:
    row: dict[str, Any] = {
        "recall_number": str(rec["recall_number"]).strip(),
        "event_id": text_or_none(rec.get("event_id")),
        "status": text_or_none(rec.get("status")),
        "classification": text_or_none(rec.get("classification")),
        "product_description": text_or_none(rec.get("product_description")),
        "code_info": text_or_none(rec.get("code_info")),
        "more_code_info": text_or_none(rec.get("more_code_info")),
        "reason_for_recall": text_or_none(rec.get("reason_for_recall")),
        "recalling_firm": text_or_none(rec.get("recalling_firm")),
    }
    for name in DATE_FIELDS:
        row[name] = iso_date(rec.get(name))
    return row


type Payload = tuple[bytes, tuple[bytes, ...]]


class UsRecallsJob(Job[Payload]):
    name = "us_recalls"
    source_id = "openfda_enforcement"
    schema = RECALL_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "recall_number": pl.String(),
        "event_id": pl.String(),
        "status": pl.String(),
        "classification": pl.String(),
        "product_description": pl.String(),
        "code_info": pl.String(),
        "more_code_info": pl.String(),
        "reason_for_recall": pl.String(),
        "recalling_firm": pl.String(),
        "recall_initiation_date": pl.String(),
        "report_date": pl.String(),
        "center_classification_date": pl.String(),
        "termination_date": pl.String(),
    }

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        fetcher = make_fetcher(require_contact=False)
        retrieved = ctx.now()
        index_bytes = fetcher.get(INDEX_URL).content
        index = parse_index(index_bytes, DATASET)
        zips = tuple(
            fetcher.get(p.url, read_timeout=BULK_READ_TIMEOUT).content for p in index.partitions
        )
        files = {"download.json": index_bytes}
        files |= {p.url.rsplit("/", 1)[-1]: z for p, z in zip(index.partitions, zips, strict=True)}
        return RawInput(
            payload=(index_bytes, zips),
            source_urls=(INDEX_URL, *(p.url for p in index.partitions)),
            source_sha256=sha256_bytes(b"".join(sha256_bytes(z).encode() for z in zips)),
            retrieved_at=retrieved,
            snapshot_date=index.export_date,
            raw_files=files,
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        index_bytes, zips = raw.payload
        index = parse_index(index_bytes, DATASET)
        if len(zips) != len(index.partitions):
            raise ValueError("number of downloaded partitions differs from the index")
        acc = Accounting()
        present: dict[str, set[str]] = {}
        absent: set[str] = set()
        rows: list[Row] = []
        seen: set[str] = set()
        invalid_dates = 0
        for zip_bytes in zips:
            for rec in iter_results(partition_text(zip_bytes)):
                acc.input_rows += 1
                for k, v in rec.items():
                    present.setdefault(k, set()).add(kind_of(v))
                absent.update(f for f in RECALL_SCHEMA.names if f not in rec)
                number = rec.get("recall_number")
                if not isinstance(number, str) or not RECALL_NUMBER.match(number.strip()):
                    acc.exclude("invalid_recall_number")
                    continue
                if number.strip() in seen:
                    acc.exclude("duplicate_recall_number")
                    continue
                seen.add(number.strip())
                row = record_row(rec)
                invalid_dates += sum(
                    1 for name in DATE_FIELDS if text_or_none(rec.get(name)) and row[name] is None
                )
                rows.append(row)
        # A field present in no record is missing; a field absent from some records is null
        # there. A bad recall number is a row exclusion, not a type change.
        for f in absent & present.keys():
            if f != "recall_number":
                present[f].add(KIND_NULL)
        report = check_schema(RECALL_SCHEMA, {k: frozenset(v) for k, v in present.items()})
        if acc.input_rows != index.expected_records:
            raise ValueError(
                f"parsed {acc.input_rows} enforcement records; download index lists "
                f"{index.expected_records}"
            )
        report_dates = sorted(str(r["report_date"]) for r in rows if r["report_date"])
        return ParseResult(
            rows=rows,
            input_rows=acc.input_rows,
            excluded=acc.excluded,
            schema=report,
            metrics={
                "records": len(rows),
                "index_records": index.expected_records,
                "by_status": dict(sorted(Counter(str(r["status"]) for r in rows).items())),
                "by_classification": dict(
                    sorted(Counter(str(r["classification"]) for r in rows).items())
                ),
                "invalid_dates": invalid_dates,
                "first_report_date": report_dates[0] if report_dates else None,
                "last_report_date": report_dates[-1] if report_dates else None,
            },
        )
