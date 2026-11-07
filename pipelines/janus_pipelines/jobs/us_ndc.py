"""`us_ndc` pipeline: openFDA NDC directory bulk download (design §5.4, Req 8). Data CC0.

Values are kept as published; NDC normalisation happens in drug-resolution (Req 8.4).
Schema `us_ndc-2` adds `route` and `dosage_form` as published (drug-resolution DP20); the
route-to-ATC-group map that uses them lives in drug-resolution.
"""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
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

INDEX_URL = "https://api.fda.gov/download.json"

NDC_SCHEMA = ExpectedSchema(
    version="us_ndc-2",
    fields=(
        Field("product_ndc", frozenset({"str"})),
        Field("product_type", frozenset({"str", KIND_NULL})),
        Field("brand_name", frozenset({"str", KIND_NULL})),
        Field("generic_name", frozenset({"str", KIND_NULL})),
        Field("active_ingredients", frozenset({"list", KIND_NULL})),
        Field("packaging", frozenset({"list", KIND_NULL})),
        Field("openfda", frozenset({"object", KIND_NULL})),
        Field("marketing_end_date", frozenset({"str", KIND_NULL})),
        Field("route", frozenset({"list", KIND_NULL})),
        Field("dosage_form", frozenset({"str", KIND_NULL})),
    ),
)


@dataclass(frozen=True)
class Partition:
    url: str
    records: int


@dataclass(frozen=True)
class NdcIndex:
    export_date: str
    partitions: tuple[Partition, ...]

    @property
    def expected_records(self) -> int:
        return sum(p.records for p in self.partitions)


def parse_index(data: bytes) -> NdcIndex:
    try:
        doc = cast(dict[str, Any], json.loads(data))
        ndc = cast(dict[str, Any], doc["results"]["drug"]["ndc"])
        partitions = tuple(
            Partition(url=str(p["file"]), records=int(p["records"]))
            for p in cast(list[dict[str, Any]], ndc["partitions"])
        )
        export_date = str(ndc["export_date"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SchemaMismatchError(
            SchemaReport(missing=(f"download.json results.drug.ndc ({exc})",))
        ) from None
    if not partitions:
        raise SchemaMismatchError(SchemaReport(missing=("download.json ndc partitions",)))
    return NdcIndex(export_date=export_date, partitions=partitions)


_WS = " \t\r\n"


def _skip(text: str, i: int, chars: str = _WS) -> int:
    n = len(text)
    while i < n and text[i] in chars:
        i += 1
    return i


def iter_results(text: str) -> Iterator[dict[str, Any]]:
    """Yield the objects of the top-level "results" array one at a time (low memory).

    Walks the top-level object key by key, so a nested "results" (openFDA's meta.results)
    is skipped like any other value.
    """
    decoder = json.JSONDecoder()
    i = _skip(text, 0)
    if i >= len(text) or text[i] != "{":
        raise SchemaMismatchError(SchemaReport(missing=("top-level object",)))
    i += 1
    while True:
        i = _skip(text, i, _WS + ",")
        if i >= len(text) or text[i] == "}":
            raise SchemaMismatchError(SchemaReport(missing=("results",)))
        key, i = decoder.raw_decode(text, i)
        i = _skip(text, i)
        if i >= len(text) or text[i] != ":":
            raise ValueError("malformed JSON object")
        i = _skip(text, i + 1)
        if key != "results":
            _, i = decoder.raw_decode(text, i)
            continue
        if text[i] != "[":
            raise SchemaMismatchError(SchemaReport(wrong_type=(("results", ("not array",)),)))
        i += 1
        while True:
            i = _skip(text, i, _WS + ",")
            if i >= len(text):
                raise ValueError("NDC file ends inside the results array")
            if text[i] == "]":
                return
            obj, i = decoder.raw_decode(text, i)
            if not isinstance(obj, dict):
                raise SchemaMismatchError(
                    SchemaReport(wrong_type=(("results[]", ("not object",)),))
                )
            yield cast(dict[str, Any], obj)


def partition_text(zip_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = [n for n in zf.namelist() if n.endswith(".json")]
        if len(names) != 1:
            raise SchemaMismatchError(SchemaReport(missing=("one .json file in the zip",)))
        return zf.read(names[0]).decode("utf-8")


def _strs(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in cast(list[object], value) if v is not None]
    return []


def record_row(rec: Mapping[str, Any]) -> Row:
    ingredients = [
        {"name": i.get("name"), "strength": i.get("strength")}
        for i in cast(list[dict[str, Any]], rec.get("active_ingredients") or [])
    ]
    packaging = cast(list[dict[str, Any]], rec.get("packaging") or [])
    openfda = cast(dict[str, Any], rec.get("openfda") or {})
    return {
        "product_ndc": str(rec["product_ndc"]).strip(),
        "package_ndcs": [str(p["package_ndc"]) for p in packaging if p.get("package_ndc")],
        "product_type": rec.get("product_type"),
        "brand_name": rec.get("brand_name"),
        "generic_name": rec.get("generic_name"),
        "active_ingredients": ingredients,
        "rxcuis": _strs(openfda.get("rxcui")),
        "marketing_end_date": rec.get("marketing_end_date"),
        "route": _strs(rec.get("route")),
        "dosage_form": rec.get("dosage_form"),
    }


type Payload = tuple[bytes, tuple[bytes, ...]]


class UsNdcJob(Job[Payload]):
    name = "us_ndc"
    source_id = "openfda_ndc"
    schema = NDC_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "product_ndc": pl.String(),
        "package_ndcs": pl.List(pl.String()),
        "product_type": pl.String(),
        "brand_name": pl.String(),
        "generic_name": pl.String(),
        "active_ingredients": pl.List(pl.Struct({"name": pl.String(), "strength": pl.String()})),
        "rxcuis": pl.List(pl.String()),
        "marketing_end_date": pl.String(),
        "route": pl.List(pl.String()),
        "dosage_form": pl.String(),
    }

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        fetcher = make_fetcher(require_contact=False)
        retrieved = ctx.now()
        index_bytes = fetcher.get(INDEX_URL).content
        index = parse_index(index_bytes)
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
        index = parse_index(index_bytes)
        if len(zips) != len(index.partitions):
            raise ValueError("number of downloaded partitions differs from the index")
        acc = Accounting()
        present: dict[str, set[str]] = {}
        absent: set[str] = set()
        rows: list[Row] = []
        for zip_bytes in zips:
            for rec in iter_results(partition_text(zip_bytes)):
                acc.input_rows += 1
                for k, v in rec.items():
                    present.setdefault(k, set()).add(kind_of(v))
                absent.update(f for f in NDC_SCHEMA.names if f not in rec)
                ndc = rec.get("product_ndc")
                if not isinstance(ndc, str) or not ndc.strip():
                    acc.exclude("missing_product_ndc")
                    continue
                rows.append(record_row(rec))
        # A field present in no record is missing; a field absent from some records is null
        # there. product_ndc absent from a record is a row exclusion, not a type change.
        for f in absent & present.keys():
            if f != "product_ndc":
                present[f].add(KIND_NULL)
        report = check_schema(NDC_SCHEMA, {k: frozenset(v) for k, v in present.items()})
        if acc.input_rows != index.expected_records:
            raise ValueError(
                f"parsed {acc.input_rows} NDC records; download index lists "
                f"{index.expected_records}"
            )
        return ParseResult(
            rows=rows,
            input_rows=acc.input_rows,
            excluded=acc.excluded,
            schema=report,
            metrics={
                "products": len(rows),
                "index_records": index.expected_records,
                "with_rxcui": sum(1 for r in rows if r["rxcuis"]),
                "multi_ingredient_products": sum(
                    1
                    for r in rows
                    if isinstance(r["active_ingredients"], list)
                    and len(r["active_ingredients"]) >= 2
                ),
            },
        )
