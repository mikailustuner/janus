"""`titck` pipeline: TİTCK licensed products list → barcode, product, ingredients, ATC.

Design §5.2, Req 2.3, 6. Storage rule `runtime_only`: the list is fetched at runtime and its
rows live only in the data directory; nothing is cached in raw/ or committed.
"""

from __future__ import annotations

import datetime as dt
import io
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar
from urllib.parse import urljoin

import polars as pl
from openpyxl import load_workbook

from janus_pipelines.core.canonical import Json, Row, sha256_bytes
from janus_pipelines.core.http import BULK_READ_TIMEOUT, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import (
    Accounting,
    ExpectedSchema,
    Field,
    SchemaMismatchError,
    SchemaReport,
    check_schema,
    kind_of,
)

LIST_PAGE = "https://www.titck.gov.tr/dinamikmodul/85"
SHEET = "RUHSATLI ÜRÜNLER LİSTESİ"
COL_BARCODE = "BARKOD"
COL_NAME = "ÜRÜN ADI"
COL_INGREDIENT = "ETKİN MADDE"
COL_ATC = "ATC KODU"
SUSPENSION_PREFIX = "RUHSATI ASKIDA"
HEADER_SCAN_ROWS = 10

TITCK_SCHEMA = ExpectedSchema(
    version="titck-1",
    fields=(
        Field(COL_BARCODE, frozenset({"int", "str", "null"})),
        Field(COL_NAME, frozenset({"str", "null"})),
        Field(COL_INGREDIENT, frozenset({"str", "null"})),
        Field(COL_ATC, frozenset({"str", "null"})),
    ),
)

# Separators seen in ETKİN MADDE (06.11.2026): "," "/" " ve " "+" ";". "ve" counts as a
# separator only as a word of its own (bounded by whitespace, another separator or the text
# edge). A run of separators, e.g. ", ve ", is one split point (P12 counterexample: the comma
# pattern consumed the space before "ve", so "x, ve y" gave "ve y").
_SEP_PATTERN = r"(?:[,;/+]|(?<![^\s,;/+])ve(?![^\s,;/+]))"
_SPLIT = re.compile(rf"(?:\s*{_SEP_PATTERN}\s*)+")
_DATE_IN_NAME = re.compile(r"(?<!\d)(\d{2})[._-]?(\d{2})[._-]?(\d{4})(?!\d)")


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def split_ingredients(text: str | None) -> list[str]:
    """Split the published ingredient text into names. Only separators and whitespace at the
    ends of each name are removed (Req 6.6). Salt and ATC handling is in drug-resolution."""
    if text is None:
        return []
    return [part.strip() for part in _SPLIT.split(text) if part.strip()]


def ean13_valid(code: str) -> bool:
    if len(code) != 13 or not code.isascii() or not code.isdigit():
        return False
    digits = [int(c) for c in code]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == digits[12]


def date_from_name(name: str) -> str | None:
    """`ruhsatli_06112026.xlsx` → 2026-11-06 (dd mm yyyy, optional . _ - separators)."""
    for day, month, year in _DATE_IN_NAME.findall(name):
        try:
            return dt.date(int(year), int(month), int(day)).isoformat()
        except ValueError:
            continue
    return None


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text)))
            self._href = None


def newest_list_link(html: str, base_url: str) -> tuple[str, str]:
    """(absolute .xlsx URL, ISO date) of the newest list on the TİTCK page."""
    parser = _Links()
    parser.feed(html)
    candidates: list[tuple[str, str]] = []
    for href, text in parser.links:
        if ".xlsx" not in href.lower():
            continue
        date = date_from_name(href.rsplit("/", 1)[-1]) or date_from_name(text)
        if date:
            candidates.append((date, urljoin(base_url, href)))
    if not candidates:
        raise ValueError("no dated .xlsx link found on the TİTCK list page")
    date, url = max(candidates)
    return url, date


def _header_name(value: object) -> str:
    return nfc(str(value)).strip() if value is not None else ""


def _is_blank(values: Sequence[object]) -> bool:
    return all(v is None or (isinstance(v, str) and not v.strip()) for v in values)


def _barcode(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        return None
    return text if ean13_valid(text) else None


def _suspension(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = nfc(str(value)).strip()
    return text or None


def parse_workbook(data: bytes) -> ParseResult:
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        if SHEET not in wb.sheetnames:
            raise SchemaMismatchError(SchemaReport(missing=(f"sheet {SHEET}",)))
        all_rows = list(wb[SHEET].iter_rows(values_only=True))
    finally:
        wb.close()

    required = TITCK_SCHEMA.names
    header_index: int | None = None
    best: tuple[int, list[str]] = (-1, [])
    for i, raw_row in enumerate(all_rows[:HEADER_SCAN_ROWS]):
        names = [_header_name(v) for v in raw_row]
        hits = sum(1 for r in required if r in names)
        if hits > best[0]:
            best = (hits, names)
        if hits == len(required):
            header_index = i
            break
    if header_index is None:
        observed = {n: frozenset({"str"}) for n in best[1] if n}
        check_schema(TITCK_SCHEMA, observed)  # raises with the missing column names
        raise SchemaMismatchError(SchemaReport(missing=required))  # pragma: no cover

    header = [_header_name(v) for v in all_rows[header_index]]
    col = {name: header.index(name) for name in required}
    suspension_col = next(
        (i for i, n in enumerate(header) if n.upper().startswith(SUSPENSION_PREFIX)), None
    )
    data_rows = all_rows[header_index + 1 :]

    observed_kinds: dict[str, set[str]] = {n: set() for n in header if n}
    for raw_row in data_rows:
        for name, i in col.items():
            observed_kinds[name].add(kind_of(raw_row[i] if i < len(raw_row) else None))
    report = check_schema(TITCK_SCHEMA, {k: frozenset(v) for k, v in observed_kinds.items()})

    acc = Accounting(input_rows=len(data_rows))
    rows: list[Row] = []
    for raw_row in data_rows:

        def cell(i: int | None, r: Sequence[object] = raw_row) -> object:
            return r[i] if i is not None and i < len(r) else None

        if _is_blank(raw_row):
            acc.exclude("blank_row")
            continue
        barcode = _barcode(cell(col[COL_BARCODE]))
        if barcode is None:
            acc.exclude("invalid_barcode")
            continue
        name = _text(cell(col[COL_NAME]))
        if name is None:
            acc.exclude("missing_product_name")
            continue
        ingredient_text = _text(cell(col[COL_INGREDIENT]))
        rows.append(
            {
                "barcode": barcode,
                "product_name": name,
                "ingredient_text": ingredient_text,
                "ingredients": split_ingredients(ingredient_text),
                "atc_code": _text(cell(col[COL_ATC])),
                "suspension_status": _suspension(cell(suspension_col)),
            }
        )
    return ParseResult(
        rows=rows,
        input_rows=acc.input_rows,
        excluded=acc.excluded,
        schema=report,
        metrics=titck_metrics(rows, acc.excluded),
    )


def titck_metrics(
    rows: Sequence[Mapping[str, Json]], excluded: Mapping[str, int]
) -> dict[str, Json]:
    """Req 2.3: ATC share, multi-ingredient products, duplicate barcodes, invalid barcodes."""
    output = len(rows)
    with_atc = sum(1 for r in rows if r["atc_code"])
    multi = 0
    for r in rows:
        ingredients = r["ingredients"]
        if isinstance(ingredients, list) and len(ingredients) >= 2:
            multi += 1
    counts = Counter(r["barcode"] for r in rows)
    return {
        "output_rows": output,
        "rows_with_atc": with_atc,
        "atc_share": round(with_atc / output, 4) if output else 0.0,
        "multi_ingredient_products": multi,
        "duplicate_barcodes": sum(1 for n in counts.values() if n > 1),
        "rows_with_duplicate_barcode": sum(n for n in counts.values() if n > 1),
        "invalid_barcode": int(excluded.get("invalid_barcode", 0)),
    }


class TitckJob(Job[bytes]):
    name = "titck"
    source_id = "titck"
    schema = TITCK_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "barcode": pl.String(),
        "product_name": pl.String(),
        "ingredient_text": pl.String(),
        "ingredients": pl.List(pl.String()),
        "atc_code": pl.String(),
        "suspension_status": pl.Int64(),
    }

    def fetch(self, ctx: RunContext) -> RawInput[bytes]:
        retrieved = ctx.now()
        if "input" in ctx.options:
            path = Path(ctx.options["input"])
            data = path.read_bytes()
            date = ctx.options.get("snapshot_date") or date_from_name(path.name)
            urls: tuple[str, ...] = (LIST_PAGE, f"local file {path.name}")
        else:
            fetcher = make_fetcher(require_contact=False)
            page = fetcher.get(LIST_PAGE)
            url, date = newest_list_link(page.text, str(page.url))
            data = fetcher.get(url, read_timeout=BULK_READ_TIMEOUT).content
            urls = (url, LIST_PAGE)
        if not date:
            raise ValueError("publication date of the TİTCK list unknown; pass --snapshot-date")
        return RawInput(
            payload=data,
            source_urls=urls,
            source_sha256=sha256_bytes(data),
            retrieved_at=retrieved,
            snapshot_date=date,
        )

    def parse(self, raw: RawInput[bytes]) -> ParseResult:
        return parse_workbook(raw.payload)
