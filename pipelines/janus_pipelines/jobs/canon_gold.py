"""`canon_gold` pipeline: PMC3941892 Tables 1-2 → the identification gold table (séance design
§3.5, Req 1.4, 4.1).

Only the three name columns are kept (name in the Canon, common name, scientific name); the
article is CC BY 3.0 and the effect column paraphrases a copyrighted translation, so it is
not stored.
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar, Final
from xml.etree.ElementTree import Element

import polars as pl
from defusedxml import ElementTree

from janus_pipelines.core.canonical import Row, sha256_bytes
from janus_pipelines.core.http import BULK_READ_TIMEOUT, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.store import Store
from janus_pipelines.core.validation import (
    ExpectedSchema,
    Field,
    SchemaMismatchError,
    SchemaReport,
    check_schema,
)
from janus_pipelines.jobs.pipc import collapse

PMCID: Final = "PMC3941892"
DOI: Final = "10.17795/jjnpp-11686"
SOURCE_URL: Final = (
    "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/?verb=GetRecord"
    "&identifier=oai:pubmedcentral.nih.gov:3941892&metadataPrefix=pmc"
)
PUBLISHED: Final = "2013-11-02"  # Crossref published date of the DOI
HEADER: Final = ("Name in Canon", "Common Name", "Scientific Name")
EXPECTED_TABLES: Final = 2
ATTRIBUTION: Final = (
    "Aliasl J, Khoshzaban F. Traditional Herbal Remedies for Burn Wound Healing in Canon of "
    "Avicenna. Jundishapur J Nat Pharm Prod 2013;8(4):192-196. doi:10.17795/jjnpp-11686. "
    "PMC3941892, Tables 1 and 2 (name columns only), CC BY 3.0."
)
CSV_COLUMNS: Final = ("gold_id", "table", "row", "name_in_canon", "common_name", "scientific_name")
OUT_CSV: Final = Path("data") / "canon_gold_pmc3941892.csv"
OUT_META: Final = Path("data") / "canon_gold_pmc3941892.meta.json"

GOLD_SCHEMA = ExpectedSchema(
    version="canon-gold-1", fields=tuple(Field(n, frozenset({"str"})) for n in HEADER)
)


class GoldShapeError(ValueError):
    """The tables do not have the expected structure."""


def _local(tag: object) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _cells(tr: Element) -> list[str]:
    return [collapse("".join(c.itertext())) for c in tr if _local(c.tag) in ("td", "th")]


def parse_tables(root: Element) -> tuple[list[Row], int, dict[str, int]]:
    tables = [e for e in root.iter() if _local(e.tag) == "table-wrap"]
    if len(tables) != EXPECTED_TABLES:
        raise GoldShapeError(f"expected {EXPECTED_TABLES} tables, found {len(tables)}")
    rows: list[Row] = []
    excluded: dict[str, int] = {}
    seen = 0
    for t_no, tw in enumerate(tables, start=1):
        trs = [e for e in tw.iter() if _local(e.tag) == "tr"]
        seen += len(trs)
        if not trs:
            raise GoldShapeError("a table has no rows")
        head = _cells(trs[0])[:3]
        check_schema(GOLD_SCHEMA, {h: frozenset({"str"}) for h in head})
        if tuple(head) != HEADER:
            raise SchemaMismatchError(SchemaReport(missing=HEADER))
        excluded["header_row"] = excluded.get("header_row", 0) + 1
        for r_no, tr in enumerate(trs[1:], start=1):
            cells = _cells(tr)
            if len(cells) < 3 or not cells[0]:
                excluded["blank_row"] = excluded.get("blank_row", 0) + 1
                continue
            rows.append(
                {
                    "gold_id": f"pmc3941892.t{t_no}.r{r_no:02d}",
                    "table": t_no,
                    "row": r_no,
                    "name_in_canon": cells[0],
                    "common_name": cells[1],
                    "scientific_name": cells[2],
                }
            )
    return rows, seen, excluded


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    os.replace(tmp, path)


class CanonGoldJob(Job[bytes]):
    name = "canon_gold"
    source_id = "pmc3941892"
    schema = GOLD_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "gold_id": pl.String(),
        "table": pl.Int64(),
        "row": pl.Int64(),
        "name_in_canon": pl.String(),
        "common_name": pl.String(),
        "scientific_name": pl.String(),
    }

    def fetch(self, ctx: RunContext) -> RawInput[bytes]:
        retrieved = ctx.now()
        if "input" in ctx.options:
            data = Path(ctx.options["input"]).read_bytes()
        else:
            fetcher = make_fetcher(require_contact=False)
            data = fetcher.get(SOURCE_URL, read_timeout=BULK_READ_TIMEOUT).content
        return RawInput(
            payload=data,
            source_urls=(SOURCE_URL,),
            source_sha256=sha256_bytes(data),
            retrieved_at=retrieved,
            snapshot_date=PUBLISHED,
        )

    def parse(self, raw: RawInput[bytes]) -> ParseResult:
        root = ElementTree.fromstring(raw.payload)
        rows, seen, excluded = parse_tables(root)
        return ParseResult(
            rows=rows,
            input_rows=seen,
            excluded=excluded,
            schema=SchemaReport(),
            metrics={"gold_rows": len(rows)},
            doi=DOI,
        )

    def extra_output_paths(self, ctx: RunContext) -> list[Path]:
        return [ctx.repo_root / OUT_CSV, ctx.repo_root / OUT_META]

    def on_promote(self, ctx: RunContext, store: Store, run_id: str) -> None:
        manifest = store.read_manifest(run_id)
        rows = sorted(store.read_rows(run_id), key=lambda r: str(r["gold_id"]))
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in CSV_COLUMNS})
        meta = {
            "source_id": self.source_id,
            "file": OUT_CSV.as_posix(),
            "source_url": SOURCE_URL,
            "doi": DOI,
            "pmcid": PMCID,
            "license": manifest.license,
            "attribution": ATTRIBUTION,
            "snapshot_date": manifest.snapshot_date,
            "retrieved_date": (manifest.retrieved_at or ctx.now()).date().isoformat(),
            "content_sha256": manifest.content_sha256,
            "run_id": run_id,
            "note": "Name columns only; cell text as published, whitespace collapsed.",
        }
        out = self.extra_output_paths(ctx)
        _atomic_write(out[0], buf.getvalue())
        _atomic_write(out[1], json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
