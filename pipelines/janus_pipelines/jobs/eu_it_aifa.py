"""`eu_it_aifa` pipeline: AIFA open data → AIC (pack code) → pack → active ingredients.

Spec `national-products` (design §3), Req 2.7-2.10. Data: CC BY 4.0 (Agenzia Italiana del
Farmaco). Two files are read: `confezioni.csv` (one line per pack) and `PA_confezioni.csv` (one
line per active ingredient of a pack, with quantity and unit where AIFA has them). Both are
semicolon-separated with a header line and no quoting. Cells are kept exactly as published. The
job does not map names, leave out homeopathic registrations or read a strength out of the pack
description (drug-resolution and medication-passport decide what is used). The files carry no
GTIN.
"""

from __future__ import annotations

import datetime as dt
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

PAGE_URL = "https://www.aifa.gov.it/liste-dei-farmaci"
BASE_URL = "https://drive.aifa.gov.it/farmaci/"
PACKS = "confezioni"
INGREDIENTS = "PA_confezioni"
FILES: tuple[str, ...] = (PACKS, INGREDIENTS)
HEADERS: Mapping[str, tuple[str, ...]] = {
    PACKS: (
        "CODICE_AIC",
        "COD_FARMACO",
        "COD_CONFEZIONE",
        "DENOMINAZIONE",
        "DESCRIZIONE",
        "CODICE_DITTA",
        "RAGIONE_SOCIALE",
        "STATO_AMMINISTRATIVO",
        "TIPO_PROCEDURA",
        "FORMA",
        "CODICE_ATC",
        "PA_ASSOCIATI",
        "LINK",
    ),
    INGREDIENTS: ("CODICE_AIC", "PRINCIPIO_ATTIVO", "QUANTITA", "UNITA_MISURA"),
}

AIFA_SCHEMA = ExpectedSchema(
    version="eu_it_aifa-1",
    fields=(
        Field("aic", frozenset({"str", "null"})),
        Field("name", frozenset({"str"})),
    ),
)


def _mismatch(text: str) -> SchemaMismatchError:
    return SchemaMismatchError(SchemaReport(missing=(text,)))


def file_url(name: str) -> str:
    return f"{BASE_URL}{name}.csv"


@dataclass(frozen=True)
class Table:
    """The well-formed lines of one file (without the header) and the number of malformed ones."""

    lines: list[list[str]]
    malformed: int


def read_table(name: str, data: bytes) -> Table:
    """Strict UTF-8; the first line must be the expected header; cells are not trimmed. The
    files use no quoting, so a line is split at every `;` (Req 2.8)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise _mismatch(f"{name}: bytes are not valid utf-8") from None
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    cells = [(ln[:-1] if ln.endswith("\r") else ln).split(";") for ln in lines]
    header = HEADERS[name]
    if not cells or tuple(cells[0]) != header:
        raise _mismatch(f"{name}: header {';'.join(header)}")
    body = cells[1:]
    good = [c for c in body if len(c) == len(header)]
    return Table(good, len(body) - len(good))


def valid_aic(value: str) -> bool:
    """An AIC pack code: exactly nine ASCII digits (Req 2.9)."""
    return len(value) == 9 and value.isascii() and value.isdigit()


def parse_aifa(files: Mapping[str, bytes]) -> ParseResult:
    tables = {name: read_table(name, files[name]) for name in FILES}
    composition: dict[str, list[Json]] = {}
    for c in tables[INGREDIENTS].lines:
        composition.setdefault(c[0], []).append({"name": c[1], "quantity": c[2], "unit": c[3]})
    packs = tables[PACKS]
    acc = Accounting(input_rows=len(packs.lines) + packs.malformed)
    if packs.malformed:
        acc.exclude("malformed_row", packs.malformed)
    rows: list[Row] = []
    for c in packs.lines:
        valid = valid_aic(c[0])
        rows.append(
            {
                "aic": c[0] if valid else None,
                "name_only": not valid,
                "medicine_code": c[1],
                "pack_code": c[2],
                "name": c[3],
                "description": c[4],
                "holder": c[6],
                "status": c[7],
                "procedure": c[8],
                "form": c[9],
                "atc_code": c[10],
                "ingredients_text": c[11],
                "ingredients": composition.get(c[0], []) if valid else [],
            }
        )
    aics = Counter(r["aic"] for r in rows if r["aic"] is not None)
    listed = {c[0] for c in packs.lines}
    return ParseResult(
        rows=rows,
        input_rows=acc.input_rows,
        excluded=acc.excluded,
        schema=SchemaReport(),
        metrics={
            "packs": len(rows),
            "packs_by_procedure": dict(sorted(Counter(str(r["procedure"]) for r in rows).items())),
            "packs_by_status": dict(sorted(Counter(str(r["status"]) for r in rows).items())),
            "name_only_rows": sum(1 for r in rows if r["name_only"]),
            "duplicate_aic": sum(1 for n in aics.values() if n > 1),
            "packs_without_ingredient_lines": sum(1 for r in rows if not r["ingredients"]),
            "ingredient_lines": len(tables[INGREDIENTS].lines),
            "ingredient_lines_of_unlisted_packs": sum(
                1 for c in tables[INGREDIENTS].lines if c[0] not in listed
            ),
            "lines_per_file": {n: len(tables[n].lines) for n in FILES},
            "malformed_lines_per_file": {n: tables[n].malformed for n in FILES},
        },
    )


def last_modified_date(name: str, header: str | None) -> str:
    """The ISO date of a file's HTTP `Last-Modified` header (Req 2.10); missing fails by name."""
    try:
        return parsedate_to_datetime(header or "").astimezone(dt.UTC).date().isoformat()
    except (TypeError, ValueError):
        raise _mismatch(f"update date of {name}.csv (Last-Modified header)") from None


type Payload = Mapping[str, bytes]


class EuItAifaJob(Job[Payload]):
    name = "eu_it_aifa"
    source_id = "aifa"
    schema = AIFA_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "aic": pl.String(),
        "name_only": pl.Boolean(),
        "medicine_code": pl.String(),
        "pack_code": pl.String(),
        "name": pl.String(),
        "description": pl.String(),
        "holder": pl.String(),
        "status": pl.String(),
        "procedure": pl.String(),
        "form": pl.String(),
        "atc_code": pl.String(),
        "ingredients_text": pl.String(),
        "ingredients": pl.List(
            pl.Struct({"name": pl.String(), "quantity": pl.String(), "unit": pl.String()})
        ),
    }

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        retrieved = ctx.now()
        if "input" in ctx.options:
            folder = Path(ctx.options["input"])
            files = {n: (folder / f"{n}.csv").read_bytes() for n in FILES}
            date = ctx.options.get("snapshot_date")
            if not date:
                raise ValueError("pass --snapshot-date (the update date of the local files)")
            urls: tuple[str, ...] = (PAGE_URL, f"local files in {folder.name}")
        else:
            fetcher = make_fetcher(require_contact=False)
            files = {}
            dates: list[str] = []
            for n in FILES:
                response = fetcher.get(file_url(n), read_timeout=BULK_READ_TIMEOUT)
                files[n] = response.content
                dates.append(last_modified_date(n, response.headers.get("Last-Modified")))
            date = min(dates)
            urls = (PAGE_URL, *(file_url(n) for n in FILES))
        digest = sha256_bytes("".join(sha256_bytes(files[n]) for n in FILES).encode())
        return RawInput(
            payload=files,
            source_urls=urls,
            source_sha256=digest,
            retrieved_at=retrieved,
            snapshot_date=date,
            raw_files={f"{n}.csv": files[n] for n in FILES},
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        return parse_aifa(raw.payload)
