"""`pipc` pipeline: PIPC Table 1 from Europe PMC → data/pipc.csv (design §5.1, Req 5)."""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar
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

PMCID = "PMC12712104"
SOURCE_URL = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML"
TABLE_ID = "Tab1"
EXPECTED_CASCADES = 65
HEADER = ("Drug A", "Adverse event", "Drug B")
KINDS = {"Drug Class": "drug_class", "Individual Drug": "individual_drug"}
ATTRIBUTION = (
    "Rochon PA et al. Potentially inappropriate prescribing cascades (PIPC) list. "
    "Eur Geriatr Med 2025;16(5):1573–1584. PMC12712104. doi:10.1007/s41999-025-01215-x. "
    "Table 1, CC BY 4.0."
)
CSV_COLUMNS = ("position", "system", "kind", "drug_a", "adverse_event", "drug_b", "locator")

_WS = re.compile(r"\s+")


def collapse(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _local(tag: object) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _cells(tr: Element) -> list[str]:
    return [collapse("".join(c.itertext())) for c in tr if _local(c.tag) in ("td", "th")]


@dataclass(frozen=True)
class Cascade:
    system: str
    kind: str
    drug_a: str
    adverse_event: str
    drug_b: str


@dataclass(frozen=True)
class TableParse:
    cascades: list[Cascade]
    excluded: dict[str, int]
    input_rows: int
    schema: SchemaReport


class TableShapeError(ValueError):
    """Table 1 rows do not follow the expected structure."""


PIPC_SCHEMA = ExpectedSchema(
    version="pipc-1", fields=tuple(Field(name, frozenset({"str"})) for name in HEADER)
)


def find_table(root: Element) -> Element:
    for tw in root.iter():
        if _local(tw.tag) == "table-wrap" and tw.get("id") == TABLE_ID:
            return tw
    raise SchemaMismatchError(SchemaReport(missing=(f"table-wrap#{TABLE_ID}",)))


def parse_table(table_wrap: Element) -> TableParse:
    """Walk Table 1 rows with the (system, kind) state machine; merge split rows."""
    trs = [e for e in table_wrap.iter() if _local(e.tag) == "tr"]
    excluded: dict[str, int] = {}

    def exclude(reason: str) -> None:
        excluded[reason] = excluded.get(reason, 0) + 1

    header_at = next((i for i, tr in enumerate(trs) if tuple(_cells(tr)) == HEADER), None)
    observed_header = (
        _cells(trs[header_at]) if header_at is not None else (_cells(trs[0]) if trs else [])
    )
    report = check_schema(PIPC_SCHEMA, {name: frozenset({"str"}) for name in observed_header})
    if header_at is None:  # pragma: no cover - check_schema raised already
        raise SchemaMismatchError(SchemaReport(missing=HEADER))

    for _ in range(header_at):
        exclude("before_header")
    exclude("header_row")

    cascades: list[Cascade] = []
    system: str | None = None
    kind: str | None = None
    pending: list[str] | None = None

    def emit(values: list[str]) -> None:
        if system is None or kind is None:
            raise TableShapeError("cascade row before its system or drug-class/individual row")
        cascades.append(Cascade(system, kind, values[0], values[1], values[2]))

    for tr in trs[header_at + 1 :]:
        cells = _cells(tr)
        values = [c for c in cells if c]
        if pending is not None:
            pending.extend(values)
            exclude("merged_into_previous")
            if len(pending) > 3:
                raise TableShapeError("a split row has more than three cells")
            if len(pending) == 3:
                emit(pending)
                pending = None
            continue
        if not values:
            exclude("blank_row")
        elif len(values) == 1 and cells and cells[0]:
            if values[0] in KINDS:
                kind = KINDS[values[0]]
            else:
                system, kind = values[0], None
            exclude("section_row")
        elif len(values) == 3:
            emit(values)
        elif len(values) == 2:
            pending = list(values)
        else:
            raise TableShapeError(f"a table row has {len(values)} non-empty cells")
    if pending is not None:
        raise TableShapeError("the table ends inside a split row")
    return TableParse(cascades, excluded, len(trs), report)


def article_doi(root: Element) -> str | None:
    for e in root.iter():
        if _local(e.tag) == "article-id" and e.get("pub-id-type") == "doi" and e.text:
            return e.text.strip().lower()
    return None


def publication_date(root: Element) -> str | None:
    """Latest pub-date in the article metadata, as YYYY-MM-DD (missing day/month → 01)."""
    dates: list[str] = []
    for e in root.iter():
        if _local(e.tag) != "pub-date":
            continue
        parts = {_local(c.tag): (c.text or "").strip() for c in e}
        year = parts.get("year", "")
        if not year.isdigit():
            continue
        month = parts.get("month", "1")
        day = parts.get("day", "1")
        month = month if month.isdigit() else "1"
        day = day if day.isdigit() else "1"
        dates.append(f"{int(year):04d}-{int(month):02d}-{int(day):02d}")
    return max(dates) if dates else None


def cascade_rows(cascades: list[Cascade]) -> list[Row]:
    return [
        {
            "position": i,
            "system": c.system,
            "kind": c.kind,
            "drug_a": c.drug_a,
            "adverse_event": c.adverse_event,
            "drug_b": c.drug_b,
            "locator": f"Table 1, row {i}",
        }
        for i, c in enumerate(cascades, start=1)
    ]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    os.replace(tmp, path)


class PipcJob(Job[bytes]):
    name = "pipc"
    source_id = "pipc"
    schema = PIPC_SCHEMA
    expected_cascades = EXPECTED_CASCADES
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = {
        "position": pl.Int64(),
        "system": pl.String(),
        "kind": pl.String(),
        "drug_a": pl.String(),
        "adverse_event": pl.String(),
        "drug_b": pl.String(),
        "locator": pl.String(),
    }

    def fetch(self, ctx: RunContext) -> RawInput[bytes]:
        retrieved = ctx.now()
        if "input" in ctx.options:
            data = Path(ctx.options["input"]).read_bytes()
        else:
            fetcher = make_fetcher(require_contact=False)
            data = fetcher.get(SOURCE_URL, read_timeout=BULK_READ_TIMEOUT).content
        root = ElementTree.fromstring(data)
        published = publication_date(root)
        return RawInput(
            payload=data,
            source_urls=(SOURCE_URL,),
            source_sha256=sha256_bytes(data),
            retrieved_at=retrieved,
            snapshot_date=published or retrieved.date().isoformat(),
            snapshot_date_is_retrieval_time=published is None,
        )

    def parse(self, raw: RawInput[bytes]) -> ParseResult:
        root = ElementTree.fromstring(raw.payload)
        table = parse_table(find_table(root))
        if len(table.cascades) != self.expected_cascades:
            found = len(table.cascades)
            raise TableShapeError(
                f"expected {self.expected_cascades} cascades in Table 1, found {found}"
            )
        rows = cascade_rows(table.cascades)
        return ParseResult(
            rows=rows,
            input_rows=table.input_rows,
            excluded=table.excluded,
            schema=table.schema,
            metrics={
                "cascades": len(rows),
                "drug_class_rows": sum(1 for c in table.cascades if c.kind == "drug_class"),
                "individual_drug_rows": sum(
                    1 for c in table.cascades if c.kind == "individual_drug"
                ),
                "systems": len({c.system for c in table.cascades}),
            },
            doi=article_doi(root),
        )

    def extra_output_paths(self, ctx: RunContext) -> list[Path]:
        data = ctx.repo_root / "data"
        return [data / "pipc.csv", data / "pipc.meta.json"]

    def on_promote(self, ctx: RunContext, store: Store, run_id: str) -> None:
        """Write the committed copy: data/pipc.csv and its metadata file (Req 5.6)."""
        manifest = store.read_manifest(run_id)
        rows = sorted(store.read_rows(run_id), key=lambda r: int(str(r["position"])))
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in CSV_COLUMNS})
        evidence = store.current_evidence()
        retrieved = manifest.retrieved_at or dt.datetime.now(dt.UTC)
        meta = {
            "source_id": self.source_id,
            "file": "data/pipc.csv",
            "source_url": SOURCE_URL,
            "doi": evidence.doi if evidence else None,
            "pmcid": PMCID,
            "license": manifest.license,
            "attribution": ATTRIBUTION,
            "snapshot_date": manifest.snapshot_date,
            "retrieved_date": retrieved.date().isoformat(),
            "content_sha256": manifest.content_sha256,
            "run_id": run_id,
            "note": "Cell text as published in Table 1; only whitespace was changed.",
        }
        out = self.extra_output_paths(ctx)
        _atomic_write(out[0], buf.getvalue())
        _atomic_write(out[1], json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
