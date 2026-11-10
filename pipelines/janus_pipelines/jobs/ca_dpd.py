"""`ca_dpd` pipeline: Health Canada Drug Product Database extract → DIN → product → ingredients.

Spec `national-products` (design §3), Req 2.1-2.6. Data: Open Government Licence (Canada). The job
reads the marketed extract (`allfiles.zip`: comma-separated, double-quoted, UTF-8, no header) and
joins its tables on `DRUG_CODE`. Cells are kept exactly as published. The job does not map
ingredient names, choose a class of product or normalise a strength (drug-resolution and
medication-passport do). The `UPC` column of the packaging table is kept and its fill rate is a
metric; nothing depends on it.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import zipfile
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import ClassVar

import polars as pl

from janus_pipelines.core.canonical import Json, Row, sha256_bytes
from janus_pipelines.core.http import BULK_READ_TIMEOUT, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import (
    Accounting,
    ExpectedSchema,
    Field,
    SchemaMismatchError,
    SchemaReport,
)

ZIP_URL = (
    "https://www.canada.ca/content/dam/hc-sc/documents/services/drug-product-database/allfiles.zip"
)
PAGE_URL = (
    "https://www.canada.ca/en/health-canada/services/drugs-health-products/drug-products/"
    "drug-product-database/what-data-extract-drug-product-database.html"
)
ZIP_NAME = "allfiles.zip"
DRUG, INGRED, FORM, ROUTE, PACKAGE, THER, STATUS, SCHEDULE = (
    "drug",
    "ingred",
    "form",
    "route",
    "package",
    "ther",
    "status",
    "schedule",
)
# Columns per table (Read Me file of the extract, checked 2026-11-10).
COLUMNS: Mapping[str, int] = {
    DRUG: 14,
    INGRED: 15,
    FORM: 4,
    ROUTE: 4,
    PACKAGE: 8,
    THER: 4,
    STATUS: 7,
    SCHEDULE: 3,
}
FILES: tuple[str, ...] = tuple(COLUMNS)
MAX_MEMBER_BYTES = 200 * 1024 * 1024  # the largest table is under 3 MB; refuse an absurd member

DPD_SCHEMA = ExpectedSchema(
    version="ca_dpd-1",
    fields=(
        Field("din", frozenset({"str", "null"})),
        Field("drug_code", frozenset({"str"})),
    ),
)


def _mismatch(text: str) -> SchemaMismatchError:
    return SchemaMismatchError(SchemaReport(missing=(text,)))


def unzip(data: bytes) -> dict[str, bytes]:
    """The eight tables of the archive by name. A missing or oversized member fails by name."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise _mismatch(f"{ZIP_NAME}: not a zip archive") from None
    out: dict[str, bytes] = {}
    with archive:
        members = {i.filename: i for i in archive.infolist()}
        for name in FILES:
            info = members.get(f"{name}.txt")
            if info is None:
                raise _mismatch(f"{name}.txt in {ZIP_NAME}")
            if info.file_size > MAX_MEMBER_BYTES:
                raise _mismatch(f"{name}.txt: larger than {MAX_MEMBER_BYTES} bytes")
            out[name] = archive.read(info)
    return out


@dataclass(frozen=True)
class Table:
    """The well-formed lines of one table and the number of malformed ones."""

    lines: list[list[str]]
    malformed: int


def read_table(name: str, data: bytes) -> Table:
    """Strict UTF-8, comma-separated, double-quoted. Cells are not trimmed (Req 2.2)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise _mismatch(f"{name}: bytes are not valid utf-8") from None
    try:
        cells = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error:
        raise _mismatch(f"{name}: not comma-separated, double-quoted text") from None
    cells = [c for c in cells if c]  # a blank line is not a row
    expected = COLUMNS[name]
    if cells:
        modal = Counter(len(c) for c in cells).most_common(1)[0][0]
        if modal != expected:
            raise _mismatch(f"{name}: {expected} columns (found {modal})")
    good = [c for c in cells if len(c) == expected]
    return Table(good, len(cells) - len(good))


def valid_din(value: str) -> bool:
    """A Drug Identification Number: exactly eight ASCII digits (Req 2.4)."""
    return len(value) == 8 and value.isascii() and value.isdigit()


def _group(table: Table) -> dict[str, list[list[str]]]:
    out: dict[str, list[list[str]]] = {}
    for cells in table.lines:
        out.setdefault(cells[0], []).append(cells)
    return out


def parse_dpd(files: Mapping[str, bytes]) -> ParseResult:
    tables = {name: read_table(name, files[name]) for name in FILES}
    by = {name: _group(tables[name]) for name in FILES if name != DRUG}
    acc = Accounting(input_rows=len(tables[DRUG].lines) + tables[DRUG].malformed)
    if tables[DRUG].malformed:
        acc.exclude("malformed_row", tables[DRUG].malformed)
    seen: set[str] = set()
    rows: list[Row] = []
    for d in tables[DRUG].lines:
        code = d[0]
        if code in seen:
            raise ValueError("drug.txt lists a DRUG_CODE twice; refusing to choose between lines")
        seen.add(code)
        valid = valid_din(d[3])
        current = [s for s in by[STATUS].get(code, []) if s[1] == "Y"]
        ingredients: list[Json] = [
            {
                "code": i[1],
                "name": i[2],
                "strength": i[4],
                "strength_unit": i[5],
                "strength_type": i[6],
                "dosage_value": i[7],
                "base": i[8],
                "dosage_unit": i[9],
            }
            for i in by[INGRED].get(code, [])
        ]
        rows.append(
            {
                "din": d[3] if valid else None,
                "name_only": not valid,
                "drug_code": code,
                "product_class": d[2],
                "brand_name": d[4],
                "descriptor": d[5],
                "number_of_ais": d[8],
                "last_update_date": d[9],
                "ai_group_no": d[10],
                "forms": [f[2] for f in by[FORM].get(code, [])],
                "routes": [r[2] for r in by[ROUTE].get(code, [])],
                "atc": [{"code": t[1], "description": t[2]} for t in by[THER].get(code, [])],
                # Exactly one current status line is expected; anything else is kept as unknown.
                "status": current[0][2] if len(current) == 1 else None,
                "status_date": current[0][3] if len(current) == 1 else None,
                "schedules": [s[1] for s in by[SCHEDULE].get(code, [])],
                "upcs": [p[1] for p in by[PACKAGE].get(code, []) if p[1].strip()],
                "ingredients": ingredients,
            }
        )
    packages = tables[PACKAGE].lines
    with_upc = sum(1 for p in packages if p[1].strip())
    dins = Counter(r["din"] for r in rows if r["din"] is not None)
    return ParseResult(
        rows=rows,
        input_rows=acc.input_rows,
        excluded=acc.excluded,
        schema=SchemaReport(),
        metrics={
            "products": len(rows),
            "products_by_class": dict(
                sorted(Counter(str(r["product_class"]) for r in rows).items())
            ),
            "name_only_rows": sum(1 for r in rows if r["name_only"]),
            "duplicate_din": sum(1 for n in dins.values() if n > 1),
            "products_without_ingredients": sum(1 for r in rows if not r["ingredients"]),
            "products_without_current_status": sum(1 for r in rows if r["status"] is None),
            "package_lines": len(packages),
            "package_lines_with_upc": with_upc,
            "package_lines_with_upc_share": round(with_upc / len(packages), 4) if packages else 0.0,
            "products_with_upc": sum(1 for r in rows if r["upcs"]),
            "lines_per_file": {n: len(tables[n].lines) for n in FILES},
            "malformed_lines_per_file": {n: tables[n].malformed for n in FILES},
        },
    )


def last_modified_date(header: str | None) -> str:
    """The ISO date of an HTTP `Last-Modified` header (Req 2.6); missing or unreadable fails."""
    try:
        return parsedate_to_datetime(header or "").astimezone(dt.UTC).date().isoformat()
    except (TypeError, ValueError):
        raise _mismatch(f"update date of {ZIP_NAME} (Last-Modified header)") from None


type Payload = Mapping[str, bytes]


class CaDpdJob(Job[Payload]):
    name = "ca_dpd"
    source_id = "dpd"
    schema = DPD_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "din": pl.String(),
        "name_only": pl.Boolean(),
        "drug_code": pl.String(),
        "product_class": pl.String(),
        "brand_name": pl.String(),
        "descriptor": pl.String(),
        "number_of_ais": pl.String(),
        "last_update_date": pl.String(),
        "ai_group_no": pl.String(),
        "forms": pl.List(pl.String()),
        "routes": pl.List(pl.String()),
        "atc": pl.List(pl.Struct({"code": pl.String(), "description": pl.String()})),
        "status": pl.String(),
        "status_date": pl.String(),
        "schedules": pl.List(pl.String()),
        "upcs": pl.List(pl.String()),
        "ingredients": pl.List(
            pl.Struct(
                {
                    "code": pl.String(),
                    "name": pl.String(),
                    "strength": pl.String(),
                    "strength_unit": pl.String(),
                    "strength_type": pl.String(),
                    "dosage_value": pl.String(),
                    "base": pl.String(),
                    "dosage_unit": pl.String(),
                }
            )
        ),
    }

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        retrieved = ctx.now()
        if "input" in ctx.options:
            path = Path(ctx.options["input"])
            data = path.read_bytes()
            date = ctx.options.get("snapshot_date")
            if not date:
                raise ValueError("pass --snapshot-date (the update date of the local file)")
            urls: tuple[str, ...] = (PAGE_URL, f"local file {path.name}")
        else:
            response = make_fetcher(require_contact=False).get(
                ZIP_URL, read_timeout=BULK_READ_TIMEOUT
            )
            data = response.content
            date = last_modified_date(response.headers.get("Last-Modified"))
            urls = (PAGE_URL, ZIP_URL)
        return RawInput(
            payload=unzip(data),
            source_urls=urls,
            source_sha256=sha256_bytes(data),
            retrieved_at=retrieved,
            snapshot_date=date,
            raw_files={ZIP_NAME: data},
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        return parse_dpd(raw.payload)
