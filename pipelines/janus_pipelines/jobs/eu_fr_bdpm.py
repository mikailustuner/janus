"""`eu_fr_bdpm` pipeline: French BDPM files → CIP13 → product → composition.

Design §13.1, Req 11. Data: Licence Ouverte. The data must not be altered, so every cell is
kept exactly as decoded (no trimming, no normalisation). The three files use different
encodings (observed 2026-11-08): `CIS_bdpm` and `CIS_COMPO` Windows-1252, `CIS_CIP` UTF-8.
The pipeline does not decide between `SA` and `FT` composition lines, split or map names, or
assign ATC codes (drug-resolution does).
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar
from urllib.parse import urljoin

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

PAGE_URL = "https://base-donnees-publique.medicaments.gouv.fr/telechargement"
CIS = "CIS_bdpm"
CIP = "CIS_CIP_bdpm"
COMPO = "CIS_COMPO_bdpm"
FILES: tuple[str, ...] = (CIS, CIP, COMPO)
DECODINGS: Mapping[str, str] = {CIS: "cp1252", CIP: "utf-8", COMPO: "cp1252"}
COLUMNS: Mapping[str, int] = {CIS: 12, CIP: 13, COMPO: 8}
CIP_PREFIX = "3400"

BDPM_SCHEMA = ExpectedSchema(
    version="eu_fr_bdpm-1",
    fields=(
        Field("cip13", frozenset({"str", "null"})),
        Field("cis", frozenset({"str"})),
    ),
)

_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def file_url(page_url: str, name: str) -> str:
    return urljoin(page_url, f"/download/file/{name}.txt")


def parse_update_dates(html: str) -> dict[str, str]:
    """Read the "Date de mise à jour" that follows each file's download link (Req 11.1).

    Raises SchemaMismatchError naming the file when its link or date is missing or impossible.
    """
    dates: dict[str, str] = {}
    missing: list[str] = []
    for name in FILES:
        match = re.search(
            rf'href="[^"]*/{re.escape(name)}\.txt"[^>]*>(?P<body>.{{0,900}}?)</a>',
            html,
            flags=re.DOTALL,
        )
        found = None
        if match:
            marker = re.search(
                r"Date de mise à jour\s*:\s*(\d{2}/\d{2}/\d{4})", match.group("body")
            )
            found = marker.group(1) if marker else None
        iso = _iso_date(found) if found else None
        if iso is None:
            missing.append(f"update date of {name}")
        else:
            dates[name] = iso
    if missing:
        raise SchemaMismatchError(SchemaReport(missing=tuple(missing)))
    return dates


def _iso_date(text: str) -> str | None:
    m = _DATE.fullmatch(text)
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def decode_file(name: str, data: bytes) -> str:
    """Strict decoding with the file's own encoding. Never guesses, never replaces (Req 11.2)."""
    encoding = DECODINGS[name]
    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        raise SchemaMismatchError(
            SchemaReport(missing=(f"{name}: bytes are not valid {encoding}",))
        ) from None


def split_lines(text: str) -> list[list[str]]:
    """Tab-separated cells per line. Only a final `\\r` of each line is removed; no stripping."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return [(ln[:-1] if ln.endswith("\r") else ln).split("\t") for ln in lines]


@dataclass(frozen=True)
class Table:
    """The well-formed lines of one file and the number of malformed ones."""

    lines: list[list[str]]
    malformed: int


def read_table(name: str, data: bytes) -> Table:
    cells = split_lines(decode_file(name, data))
    expected = COLUMNS[name]
    if cells:
        modal = Counter(len(c) for c in cells).most_common(1)[0][0]
        if modal != expected:
            raise SchemaMismatchError(
                SchemaReport(missing=(f"{name}: {expected} columns (found {modal})",))
            )
    good = [c for c in cells if len(c) == expected]
    return Table(good, len(cells) - len(good))


def ean13_ok(digits: str) -> bool:
    if len(digits) != 13 or not digits.isascii() or not digits.isdigit():
        return False
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == int(digits[12])


def valid_cip13(value: str) -> bool:
    """13 digits, prefix 3400, correct EAN-13 check digit (Req 11.5)."""
    return value.startswith(CIP_PREFIX) and ean13_ok(value)


def parse_bdpm(files: Mapping[str, bytes], dates: Mapping[str, str]) -> ParseResult:
    tables = {name: read_table(name, files[name]) for name in FILES}
    specialties: dict[str, list[str]] = {}
    for cells in tables[CIS].lines:
        if cells[0] in specialties:
            raise ValueError(f"{CIS} lists a CIS twice; refusing to choose between the lines")
        specialties[cells[0]] = cells
    composition: dict[str, list[dict[str, Json]]] = {}
    ft_lines = 0
    for c in tables[COMPO].lines:
        composition.setdefault(c[0], []).append(
            {
                "form": c[1],
                "substance_code": c[2],
                "substance_name": c[3],
                "dosage": c[4],
                "reference": c[5],
                "nature": c[6],
                "link": c[7],
            }
        )
        ft_lines += c[6] == "FT"
    acc = Accounting(input_rows=len(tables[CIP].lines) + tables[CIP].malformed)
    if tables[CIP].malformed:
        acc.exclude("malformed_row", tables[CIP].malformed)
    rows: list[Row] = []
    for c in tables[CIP].lines:
        valid = valid_cip13(c[6])
        spec = specialties.get(c[0])
        rows.append(
            {
                "cip13": c[6] if valid else None,
                "name_only": not valid,
                "cip7": c[1],
                "cis": c[0],
                "presentation_label": c[2],
                "presentation_status": c[3],
                "presentation_commercialisation": c[4],
                "presentation_declaration_date": c[5],
                "specialty_missing": spec is None,
                "denomination": spec[1] if spec else None,
                "pharmaceutical_form": spec[2] if spec else None,
                "routes": spec[3] if spec else None,
                "authorisation_status": spec[4] if spec else None,
                "procedure": spec[5] if spec else None,
                "commercialisation_status": spec[6] if spec else None,
                "authorisation_date": spec[7] if spec else None,
                "holder": spec[10] if spec else None,
                "composition": composition.get(c[0], []),
            }
        )
    counts = Counter(r["cip13"] for r in rows if r["cip13"] is not None)
    active = sum(1 for r in rows if r["presentation_status"] == "Présentation active")
    return ParseResult(
        rows=rows,
        input_rows=acc.input_rows,
        excluded=acc.excluded,
        schema=SchemaReport(),
        metrics={
            "presentations": len(rows),
            "name_only_rows": sum(1 for r in rows if r["name_only"]),
            "duplicate_cip13": sum(1 for n in counts.values() if n > 1),
            "specialty_missing": sum(1 for r in rows if r["specialty_missing"]),
            "cis_without_composition": len(set(specialties) - set(composition)),
            "ft_lines": ft_lines,
            "active_presentation_share": round(active / len(rows), 4) if rows else 0.0,
            "file_dates": dict(sorted(dates.items())),
            "lines_per_file": {n: len(tables[n].lines) for n in FILES},
            "malformed_lines_per_file": {n: tables[n].malformed for n in FILES},
        },
    )


type Payload = tuple[Mapping[str, bytes], Mapping[str, str]]


class EuFrBdpmJob(Job[Payload]):
    name = "eu_fr_bdpm"
    source_id = "bdpm"
    schema = BDPM_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "cip13": pl.String(),
        "name_only": pl.Boolean(),
        "cip7": pl.String(),
        "cis": pl.String(),
        "presentation_label": pl.String(),
        "presentation_status": pl.String(),
        "presentation_commercialisation": pl.String(),
        "presentation_declaration_date": pl.String(),
        "specialty_missing": pl.Boolean(),
        "denomination": pl.String(),
        "pharmaceutical_form": pl.String(),
        "routes": pl.String(),
        "authorisation_status": pl.String(),
        "procedure": pl.String(),
        "commercialisation_status": pl.String(),
        "authorisation_date": pl.String(),
        "holder": pl.String(),
        "composition": pl.List(
            pl.Struct(
                {
                    "form": pl.String(),
                    "substance_code": pl.String(),
                    "substance_name": pl.String(),
                    "dosage": pl.String(),
                    "reference": pl.String(),
                    "nature": pl.String(),
                    "link": pl.String(),
                }
            )
        ),
    }

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        retrieved = ctx.now()
        if "input" in ctx.options:
            folder = Path(ctx.options["input"])
            files = {n: (folder / f"{n}.txt").read_bytes() for n in FILES}
            date = ctx.options.get("snapshot_date")
            if not date:
                raise ValueError("pass --snapshot-date (the update date of the local files)")
            dates = dict.fromkeys(FILES, date)
            urls: tuple[str, ...] = (PAGE_URL, f"local files in {folder.name}")
        else:
            fetcher = make_fetcher(require_contact=False)
            page = fetcher.get(PAGE_URL)
            dates = parse_update_dates(page.text)
            files = {
                n: fetcher.get(file_url(str(page.url), n), read_timeout=BULK_READ_TIMEOUT).content
                for n in FILES
            }
            urls = (PAGE_URL, *(file_url(str(page.url), n) for n in FILES))
        digest = sha256_bytes("".join(sha256_bytes(files[n]) for n in FILES).encode())
        return RawInput(
            payload=(files, dates),
            source_urls=urls,
            source_sha256=digest,
            retrieved_at=retrieved,
            snapshot_date=min(dates.values()),
            raw_files={f"{n}.txt": files[n] for n in FILES},
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        files, dates = raw.payload
        return parse_bdpm(files, dates)
