# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""`us_labels` pipeline: "Indications and Usage" of US drug labels, openFDA bulk download
(plain-medicine-info design §4).

Data CC0 1.0. One row per label (SPL set id) that names at least one product NDC and has an
indications section. The section is kept as published, paragraph by paragraph: nothing is
trimmed inside a paragraph, joined, shortened or translated. Only this one section is carried;
dosage, warnings and every other section of the label stay out of Janus.

The product NDCs are openFDA's link from the label to the NDC directory by SPL set id. A row is
kept only when that link names the label's own set id, and only when every application number of
the label is an NDA, ANDA or BLA. Labels of OTC monograph products and of unapproved products
(homeopathic ones among them) are left out: their sections are less regular (directions for use
appear under the indications heading), and FDA has not evaluated the unapproved ones.

openFDA's disclaimer applies to every row: the labeling is what the company submitted, its
content "has neither been altered nor verified by FDA", and it "may not be the labeling on
currently distributed products or identical to the labeling that is approved".

The download is about 1.8 GB in 14 files. Each file is read and reduced before the next one is
fetched, so the run needs about 1.5 GB of memory and keeps no raw label file.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
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
    check_schema,
    kind_of,
)
from janus_pipelines.jobs.us_ndc import INDEX_URL, iter_results, parse_index, partition_text
from janus_pipelines.jobs.us_recalls import iso_date

DATASET = "label"
PRODUCT_TYPES = frozenset({"HUMAN PRESCRIPTION DRUG", "HUMAN OTC DRUG"})
# New drug, abbreviated new drug and biologics licence applications.
_APPLICATION = re.compile(r"^(NDA|ANDA|BLA)[0-9]+$")

LABEL_SCHEMA = ExpectedSchema(
    version="us_labels-1",
    fields=(
        Field("set_id", frozenset({"str"})),
        Field("version", frozenset({"str", KIND_NULL})),
        Field("effective_time", frozenset({"str", KIND_NULL})),
        Field("indications_and_usage", frozenset({"list", KIND_NULL})),
        Field("openfda", frozenset({"object", KIND_NULL})),
    ),
)
ROW_SCHEMA: Mapping[str, pl.DataType] = {
    "set_id": pl.String(),
    "version": pl.String(),
    "effective_date": pl.String(),
    "product_type": pl.String(),
    "product_ndcs": pl.List(pl.String()),
    "indications": pl.List(pl.String()),
}


@dataclass
class Reduction:
    """What reading the partitions has seen so far."""

    acc: Accounting = field(default_factory=Accounting)
    present: dict[str, set[str]] = field(default_factory=dict[str, set[str]])
    absent: set[str] = field(default_factory=set[str])
    seen: set[str] = field(default_factory=set[str])
    by_type: Counter[str] = field(default_factory=Counter[str])
    product_ndcs: int = 0


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [v for v in cast(list[object], value) if isinstance(v, str)]
    return []


def record_row(rec: Mapping[str, Any], state: Reduction) -> Row | None:
    """The row of one label, or None with the exclusion counted."""
    acc = state.acc
    set_id = rec.get("set_id")
    if not isinstance(set_id, str) or not set_id.strip():
        acc.exclude("no_set_id")
        return None
    set_id = set_id.strip()
    if set_id in state.seen:
        acc.exclude("duplicate_set_id")
        return None
    state.seen.add(set_id)
    raw_openfda = rec.get("openfda")
    openfda: Mapping[str, Any] = (
        cast(Mapping[str, Any], raw_openfda) if isinstance(raw_openfda, dict) else {}
    )
    ndcs = sorted({n.strip() for n in _strings(openfda.get("product_ndc")) if n.strip()})
    if not ndcs:
        acc.exclude("no_product_code")
        return None
    if _strings(openfda.get("spl_set_id")) != [set_id]:
        acc.exclude("set_id_not_linked")
        return None
    types = _strings(openfda.get("product_type"))
    if len(types) != 1 or types[0] not in PRODUCT_TYPES:
        acc.exclude("other_product_type")
        return None
    applications = _strings(openfda.get("application_number"))
    if not applications or not all(_APPLICATION.match(a) for a in applications):
        acc.exclude("no_approved_application")
        return None
    # Paragraphs exactly as published; a paragraph of whitespace only is not text.
    indications = [p for p in _strings(rec.get("indications_and_usage")) if p.strip()]
    if not indications:
        acc.exclude("no_indications")
        return None
    version = rec.get("version")
    state.by_type[types[0]] += 1
    state.product_ndcs += len(ndcs)
    return {
        "set_id": set_id,
        "version": version.strip() if isinstance(version, str) and version.strip() else None,
        "effective_date": iso_date(rec.get("effective_time")),
        "product_type": types[0],
        "product_ndcs": ndcs,
        "indications": indications,
    }


def reduce_partition(zip_bytes: bytes, state: Reduction) -> list[Row]:
    rows: list[Row] = []
    for rec in iter_results(partition_text(zip_bytes)):
        state.acc.input_rows += 1
        for name in LABEL_SCHEMA.names:
            if name in rec:
                state.present.setdefault(name, set()).add(kind_of(rec[name]))
            else:
                state.absent.add(name)
        row = record_row(rec, state)
        if row is not None:
            rows.append(row)
    return rows


def reduce_to_parts(zips: Iterable[bytes], scratch: Path) -> tuple[tuple[Path, ...], Reduction]:
    """Reduce each partition to a small Parquet file in `scratch`, one at a time."""
    state = Reduction()
    parts: list[Path] = []
    for n, zip_bytes in enumerate(zips):
        part = scratch / f"part-{n:04d}.parquet"
        pl.DataFrame(reduce_partition(zip_bytes, state), schema=dict(ROW_SCHEMA)).write_parquet(
            part
        )
        parts.append(part)
    return tuple(parts), state


@dataclass(frozen=True)
class Payload:
    index: bytes
    parts: tuple[Path, ...]
    state: Reduction
    scratch: Path


class UsLabelsJob(Job[Payload]):
    name = "us_labels"
    source_id = "openfda_label_indications"
    schema = LABEL_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = ROW_SCHEMA

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        fetcher = make_fetcher(require_contact=False)
        retrieved = ctx.now()
        index_bytes = fetcher.get(INDEX_URL).content
        index = parse_index(index_bytes, DATASET)
        scratch = ctx.scratch_dir(self.name)
        hashes: list[str] = []

        def zips() -> Iterable[bytes]:
            for p in index.partitions:
                content = fetcher.get(p.url, read_timeout=BULK_READ_TIMEOUT).content
                hashes.append(sha256_bytes(content))
                yield content

        parts, state = reduce_to_parts(zips(), scratch)
        return RawInput(
            payload=Payload(index_bytes, parts, state, scratch),
            source_urls=(INDEX_URL, *(p.url for p in index.partitions)),
            source_sha256=sha256_bytes("".join(hashes).encode()),
            retrieved_at=retrieved,
            snapshot_date=index.export_date,
            raw_files={"download.json": index_bytes},
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        p = raw.payload
        index = parse_index(p.index, DATASET)
        state = p.state
        if len(p.parts) != len(index.partitions):
            raise ValueError("number of downloaded partitions differs from the index")
        if state.acc.input_rows != index.expected_records:
            raise ValueError(
                f"parsed {state.acc.input_rows} label records; download index lists "
                f"{index.expected_records}"
            )
        # A field present in no record is missing; a field absent from some is null there.
        present = {k: set(v) for k, v in state.present.items()}
        for name in state.absent & present.keys():
            if name != "set_id":
                present[name].add(KIND_NULL)
        report = check_schema(LABEL_SCHEMA, {k: frozenset(v) for k, v in present.items()})
        rows = pl.concat([pl.read_parquet(part) for part in p.parts]).sort("set_id")
        rows_file = p.scratch / "rows.parquet"
        rows.write_parquet(rows_file, row_group_size=2_000)
        dates = rows["effective_date"].drop_nulls()
        return ParseResult(
            rows=[],
            rows_file=rows_file,
            output_rows=rows.height,
            input_rows=state.acc.input_rows,
            excluded=state.acc.excluded,
            schema=report,
            metrics={
                "labels": rows.height,
                "index_records": index.expected_records,
                "by_product_type": dict(sorted(state.by_type.items())),
                "product_ndcs": state.product_ndcs,
                "labels_without_effective_date": rows.height - dates.len(),
                "last_effective_date": cast(str | None, dates.max()),
            },
        )
