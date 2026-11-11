"""`modelkit_special_populations` pipeline: exposure of special populations from US labels for the
drug model kit (spec model-kit, milestone M4).

Reads the openFDA drug label bulk files (about 1.8 GB in 14 files, CC0 1.0), one file at a time,
keeps the human prescription labels with an approved application number and a single active
substance that is a drug of the pool, and reads the sections on older adults (8.5), special
populations (8), pharmacokinetics (12.3) and clinical pharmacology with two independent automated
readers (`sp_a`, `sp_b`). A statement is the exposure change (AUC or Cmax ratio) of older adults, of
patients with renal impairment or of patients with hepatic impairment, with the quoted sentence and
the label's set id and version. The two readers' results are paired by code (`sp_confirm`). The
confirmed statements are written to `data/modelkit/special_populations.csv`. The raw files stay
outside the repository.
Research use only. Not for clinical decisions.

Source: openFDA drug labels (CC0 1.0), https://open.fda.gov. Not an FDA endorsement. The labeling is
what the company submitted; openFDA has not altered or verified it.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Final, cast

import polars as pl

from janus_pipelines.core.canonical import Json, Row
from janus_pipelines.core.http import BULK_READ_TIMEOUT, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.store import Store
from janus_pipelines.core.validation import ExpectedSchema, SchemaReport
from janus_pipelines.jobs.us_ndc import INDEX_URL, iter_results, parse_index, partition_text
from janus_pipelines.modelkit import sp_a, sp_b
from janus_pipelines.modelkit.resolver import IdentityTable
from janus_pipelines.modelkit.sp_confirm import pair_label
from janus_pipelines.modelkit.sp_model import (
    POP_CLASSES,
    SECTION_FIELDS,
    TABLE_FIELDS,
    SpLabel,
    SpStats,
)

DATASET: Final = "label"
IDENTITY_PATH: Final = ("data", "modelkit", "identity_m2.csv")
OUT_PATH: Final = ("data", "modelkit", "special_populations.csv")
APPLICATION = re.compile(r"^(NDA|ANDA|BLA)[0-9]+$")
SCHEMA = ExpectedSchema(version="modelkit_sp-1", fields=())
CSV_COLUMNS: Final = (
    "drug_key",
    "pop_class",
    "grade",
    "measure",
    "ratio",
    "ratio_text",
    "definition",
    "reference",
    "quote",
    "set_id",
    "version",
    "effective_date",
    "section",
    "n_labels",
    "from_table",
)
ROW_SCHEMA: Mapping[str, pl.DataType] = {
    "drug_key": pl.String(),
    "set_id": pl.String(),
    "version": pl.String(),
    "effective_date": pl.String(),
    "section": pl.String(),
    "pop_class": pl.String(),
    "grade": pl.String(),
    "measure": pl.String(),
    "ratio": pl.Float64(),
    "ratio_b": pl.Float64(),
    "ratio_text": pl.String(),
    "definition": pl.String(),
    "reference": pl.String(),
    "quote": pl.String(),
    "quote_b": pl.String(),
    "flags": pl.String(),
    "from_table": pl.Boolean(),
    "confirmed": pl.Boolean(),
    "reason": pl.String(),
    "reader_a": pl.String(),
    "reader_b": pl.String(),
}
_STRINGS = frozenset({"set_id", "version"})


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [v for v in cast(list[object], value) if isinstance(v, str)]
    return []


def _date(value: object) -> str:
    s = str(value or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if re.fullmatch(r"\d{8}", s) else s


@dataclass
class Payload:
    rows: list[Row] = field(default_factory=lambda: list[Row]())
    counts: Counter[str] = field(default_factory=Counter[str])
    stats: SpStats = field(default_factory=SpStats)
    labels_with_text: dict[str, int] = field(default_factory=lambda: dict[str, int]())
    drugs_with_text: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    drugs: set[str] = field(default_factory=lambda: set[str]())
    index_bytes: bytes = b""
    sha256: str = ""
    urls: tuple[str, ...] = ()
    date: str | None = None


def label_of(
    rec: Mapping[str, object], table: IdentityTable, counts: Counter[str]
) -> SpLabel | None:
    """The label as the readers get it, or None with the reason counted."""
    openfda_raw = rec.get("openfda")
    openfda: Mapping[str, object] = (
        cast(Mapping[str, object], openfda_raw) if isinstance(openfda_raw, dict) else {}
    )
    set_id = rec.get("set_id")
    if not isinstance(set_id, str) or _strings(openfda.get("spl_set_id")) != [set_id]:
        counts["skip_set_id_not_linked"] += 1
        return None
    types = _strings(openfda.get("product_type"))
    if types != ["HUMAN PRESCRIPTION DRUG"]:
        counts["skip_not_human_prescription"] += 1
        return None
    apps = _strings(openfda.get("application_number"))
    if not apps or not all(APPLICATION.match(a) for a in apps):
        counts["skip_no_approved_application"] += 1
        return None
    substances = _strings(openfda.get("substance_name"))
    if len(substances) != 1:
        counts["skip_not_single_substance"] += 1
        return None
    keys = table.drugs_in(substances[0])
    if len(keys) != 1:
        counts["skip_not_a_pool_drug"] += 1
        return None
    sections = {f: tuple(_strings(rec.get(f))) for f in SECTION_FIELDS if _strings(rec.get(f))}
    tables = {f: tuple(_strings(rec.get(f))) for f in TABLE_FIELDS if _strings(rec.get(f))}
    if not sections and not tables:
        counts["skip_no_section_text"] += 1
        return None
    version = rec.get("version")
    return SpLabel(
        set_id,
        str(version).strip() if version is not None else "",
        _date(rec.get("effective_time")),
        keys[0],
        sections,
        tables,
    )


def read_one(label: SpLabel, payload: Payload) -> None:
    counts = payload.counts
    counts["labels_matched"] += 1
    payload.drugs.add(label.drug_key)
    text = " ".join(t for ts in label.sections.values() for t in ts)
    for cls in POP_CLASSES:
        if sp_a._POP[cls].search(text):  # pyright: ignore[reportPrivateUsage]
            payload.labels_with_text[cls] = payload.labels_with_text.get(cls, 0) + 1
            payload.drugs_with_text[cls].add(label.drug_key)
    a = sp_a.read_label(label, payload.stats)
    b = sp_b.read_label(label, payload.stats)
    pairs = pair_label(a, b)
    counts["labels_with_a_candidate" if pairs else "skip_matched_label_without_a_candidate"] += 1
    for p in pairs:
        c = p.a or p.b
        assert c is not None  # noqa: S101 - a pair has at least one side
        payload.rows.append(
            {
                "drug_key": label.drug_key,
                "set_id": label.set_id,
                "version": label.version,
                "effective_date": label.effective_date,
                "section": c.section,
                "pop_class": c.pop_class,
                "grade": c.grade,
                "measure": c.measure,
                "ratio": p.a.ratio if p.a else None,
                "ratio_b": p.b.ratio if p.b else None,
                "ratio_text": c.ratio_text,
                "definition": c.definition,
                "reference": (
                    p.a.reference if p.a and p.a.reference else p.b.reference if p.b else ""
                ),
                "quote": p.a.quote if p.a else "",
                "quote_b": p.b.quote if p.b else "",
                "flags": "a:"
                + "+".join(p.a.flags if p.a else ())
                + "|b:"
                + "+".join(p.b.flags if p.b else ()),
                "from_table": c.from_table,
                "confirmed": p.confirmed,
                "reason": p.reason,
                "reader_a": "found" if p.a else "none",
                "reader_b": "found" if p.b else "none",
            }
        )


def names_population(row: Mapping[str, Any]) -> bool:
    """The quote itself names the population of its class (display rule, fixed in advance, PREREG addendum 3): a
    statement whose class came only from a sub-section heading is kept in the run but not shown."""
    return sp_a._POP[str(row["pop_class"])].search(str(row["quote"])) is not None  # pyright: ignore[reportPrivateUsage]


def read_partition(zip_bytes: bytes, table: IdentityTable, payload: Payload) -> None:
    for rec in iter_results(partition_text(zip_bytes)):
        payload.counts["labels_read"] += 1
        label = label_of(rec, table, payload.counts)
        if label is not None:
            read_one(label, payload)


def _local_partitions(folder: Path) -> Iterator[tuple[str, bytes]]:
    for z in sorted(folder.glob("drug-label-*.json.zip")):
        yield z.name, z.read_bytes()


class ModelkitSpecialPopulationsJob(Job[Payload]):
    name = "modelkit_special_populations"
    source_id = "modelkit_special_populations"
    schema: ExpectedSchema = SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = ROW_SCHEMA

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        repo = ctx.repo_root
        table = IdentityTable.from_csv(repo.joinpath(*IDENTITY_PATH).read_text("utf-8"))
        payload = Payload()
        digest = hashlib.sha256()
        local = ctx.options.get("input")
        retrieved = ctx.now()
        if local:
            folder = Path(local)
            payload.index_bytes = (folder / "download.json").read_bytes()
            index = parse_index(payload.index_bytes, DATASET)
            parts: Iterable[tuple[str, bytes]] = _local_partitions(folder)
            urls: tuple[str, ...] = ()
        else:
            fetcher = make_fetcher(require_contact=False)
            payload.index_bytes = fetcher.get(INDEX_URL).content
            index = parse_index(payload.index_bytes, DATASET)
            urls = (INDEX_URL, *(p.url for p in index.partitions))

            def downloaded() -> Iterator[tuple[str, bytes]]:
                for p in index.partitions:
                    yield p.url, fetcher.get(p.url, read_timeout=BULK_READ_TIMEOUT).content

            parts = downloaded()
        n = 0
        for _name, content in parts:  # one file at a time: about 1.5 GB of memory at the peak
            digest.update(hashlib.sha256(content).digest())
            read_partition(content, table, payload)
            n += 1
        if n != len(index.partitions):
            raise ValueError("number of partitions read differs from the download index")
        if payload.counts["labels_read"] != index.expected_records:
            raise ValueError(
                f"read {payload.counts['labels_read']} label records; "
                f"the index lists {index.expected_records}"
            )
        payload.sha256 = digest.hexdigest()
        payload.urls = urls
        payload.date = index.export_date
        return RawInput(
            payload=payload,
            source_urls=urls,
            source_sha256=payload.sha256,
            retrieved_at=retrieved,
            snapshot_date=index.export_date,
            raw_files={"download.json": payload.index_bytes},
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        p = raw.payload
        date = raw.snapshot_date or raw.retrieved_at.date().isoformat()
        rows = p.rows
        confirmed = [r for r in rows if r["confirmed"]]
        by_class = Counter(str(r["pop_class"]) for r in confirmed)
        by_measure = Counter(f"{r['pop_class']}:{r['measure']}" for r in confirmed)
        metrics: dict[str, Json] = {
            **{k: v for k, v in sorted(p.counts.items())},
            "drugs_with_a_matched_label": len(p.drugs),
            "labels_with_class_text": dict(sorted(p.labels_with_text.items())),
            "drugs_with_class_text": {k: len(v) for k, v in sorted(p.drugs_with_text.items())},
            "candidate_pairs": len(rows),
            "confirmed": len(confirmed),
            "confirmed_displayed": sum(1 for r in confirmed if names_population(r)),
            "confirmed_by_class": dict(sorted(by_class.items())),
            "confirmed_by_class_and_measure": dict(sorted(by_measure.items())),
            "drugs_with_a_confirmed_statement": len({str(r["drug_key"]) for r in confirmed}),
            "reasons": dict(sorted(Counter(str(r["reason"]).split(":")[0] for r in rows).items())),
            "reader_counts": dict(sorted(p.stats.counts.items())),
            "label_export_date": date,
        }
        return ParseResult(
            rows=rows,
            input_rows=p.counts["labels_read"],
            excluded={
                k.removeprefix("skip_"): v
                for k, v in sorted(p.counts.items())
                if k.startswith("skip_")
            },
            schema=SchemaReport(),
            metrics=metrics,
        )

    def extra_output_paths(self, ctx: RunContext) -> list[Path]:
        return [ctx.repo_root.joinpath(*OUT_PATH)]

    def on_promote(self, ctx: RunContext, store: Store, run_id: str) -> None:
        """Write the committed copy data/modelkit/special_populations.csv (confirmed statements)."""
        rows = [r for r in store.read_rows(run_id) if r["confirmed"] and names_population(r)]
        text = aggregate_csv(rows)
        out = self.extra_output_paths(ctx)[0]
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(out)


def aggregate_csv(rows: Iterable[Mapping[str, Any]]) -> str:
    """One row per drug, class, grade, measure and ratio; the label with the latest effective date
    is the quoted source, `n_labels` counts the labels that state the same ratio. Sorted."""
    groups: dict[tuple[str, str, str, str, float], list[Mapping[str, Any]]] = defaultdict(list)
    for r in rows:
        key = (
            str(r["drug_key"]),
            str(r["pop_class"]),
            str(r["grade"]),
            str(r["measure"]),
            round(float(r["ratio"]), 3),
        )
        groups[key].append(r)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    w.writeheader()
    for key in sorted(groups):
        best = sorted(groups[key], key=lambda r: (str(r["effective_date"]), str(r["set_id"])))[-1]
        w.writerow(
            {
                "drug_key": key[0],
                "pop_class": key[1],
                "grade": key[2],
                "measure": key[3],
                "ratio": f"{float(best['ratio']):.4g}",
                "ratio_text": best["ratio_text"],
                "definition": best["definition"],
                "reference": best["reference"],
                "quote": best["quote"],
                "set_id": best["set_id"],
                "version": best["version"],
                "effective_date": best["effective_date"],
                "section": best["section"],
                "n_labels": len({str(x["set_id"]) for x in groups[key]}),
                "from_table": "true" if best["from_table"] else "false",
            }
        )
    return buf.getvalue()
