# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""`faers_onset` pipeline: time to onset per (report, drug) from the FAERS quarterly files.

Time-machine design §6.1, Req 6. The `faers` artifact keeps one row per deduplicated report and
does not carry dates. This job reads the raw archives of the *current* `faers` run (no network)
and, for every (report, drug) of that artifact, takes the therapy start (`THER.start_dt`, matched
on `dsg_drug_seq`) and the event date (`DEMO.event_dt`, one per report) and computes the interval
in days. Only complete dates (YYYYMMDD) are used; partial dates, missing dates, negative and
implausibly long intervals are excluded and counted by reason (data-quality report).

The `faers` artifact and its contract are not changed. FAERS is spontaneous reporting: a time to
onset here is the interval a reporter wrote down, not a measured one.
"""

from __future__ import annotations

import datetime as dt
import json
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

import polars as pl

from janus_pipelines.core.canonical import sha256_bytes
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import ExpectedSchema, Field, SchemaReport
from janus_pipelines.jobs.faers import (
    Quarter,
    _member,  # pyright: ignore[reportPrivateUsage]
    parse_quarter_names,
    read_table,
)

# Longest interval kept (10 years). Longer intervals in spontaneous reports are mostly start
# dates of long-standing therapy, not onset (design DP-T3).
MAX_DAYS = 3650


class Exclusion(StrEnum):
    no_therapy_start = "no_therapy_start"
    start_date_partial = "start_date_partial"
    event_date_missing = "event_date_missing"
    event_date_partial = "event_date_partial"
    negative_interval = "negative_interval"
    interval_over_max = "interval_over_max"


def full_date(text: str | None) -> dt.date | None:
    """A complete FAERS date `YYYYMMDD`, or None for missing, partial (`YYYY`, `YYYYMM`) or
    impossible ones (e.g. `20260231`)."""
    if text is None or len(text) != 8 or not text.isdigit():
        return None
    try:
        return dt.date(int(text[:4]), int(text[4:6]), int(text[6:]))
    except ValueError:
        return None


def classify(starts: list[str], event: str | None) -> int | Exclusion:
    """Interval in days from the earliest complete therapy start to the event date, or the
    reason the pair is excluded. Pure; the same rule as the Polars expression in `extract`."""
    present = [s for s in starts if s]
    if not present:
        return Exclusion.no_therapy_start
    full = [d for d in (full_date(s) for s in present) if d is not None]
    if not full:
        return Exclusion.start_date_partial
    if not event:
        return Exclusion.event_date_missing
    ev = full_date(event)
    if ev is None:
        return Exclusion.event_date_partial
    days = (ev - min(full)).days
    if days < 0:
        return Exclusion.negative_interval
    if days > MAX_DAYS:
        return Exclusion.interval_over_max
    return days


ONSET_SCHEMA = ExpectedSchema(
    version="faers-onset-1",
    fields=(
        Field("primaryid", frozenset({"str"})),
        Field("drug_seq", frozenset({"str"})),
    ),
)

ROW_SCHEMA: Mapping[str, pl.DataType] = {
    "primaryid": pl.String(),
    "drug_seq": pl.String(),
    "role": pl.String(),
    "ingredients": pl.List(pl.String()),
    "start_dt": pl.String(),
    "event_dt": pl.String(),
    "onset_days": pl.Int64(),
}


@dataclass(frozen=True)
class Payload:
    rows_parquet: Path
    archives: dict[str, Path]
    quarters: tuple[Quarter, ...]
    scratch: Path
    faers_run_id: str


def _date_expr(col: str) -> pl.Expr:
    c = pl.col(col)
    return (
        pl.when(c.str.contains(r"^[0-9]{8}$"))
        .then(c.str.to_date("%Y%m%d", strict=False))
        .otherwise(None)
    )


def extract(p: Payload) -> ParseResult:
    pairs = (
        pl.scan_parquet(p.rows_parquet)
        .select("primaryid", "drugs")
        .explode("drugs")
        .drop_nulls("drugs")
        .select(
            "primaryid",
            pl.col("drugs").struct.field("drug_seq").alias("drug_seq"),
            pl.col("drugs").struct.field("role").alias("role"),
            pl.col("drugs").struct.field("ingredients").alias("ingredients"),
        )
        .unique(["primaryid", "drug_seq"], keep="first")
        .collect()
    )
    kept = pairs.select("primaryid").unique()
    ther_parts: list[pl.DataFrame] = []
    demo_parts: list[pl.DataFrame] = []
    malformed = 0
    for q in p.quarters:
        with zipfile.ZipFile(p.archives[q.label]) as zf:
            for kind, cols, sink in (
                ("THER", ("primaryid", "dsg_drug_seq", "start_dt"), ther_parts),
                ("DEMO", ("primaryid", "event_dt"), demo_parts),
            ):
                member = _member(zf, kind, q)
                if member is None:
                    raise ValueError(f"{q.label}: no {kind} file")
                read = read_table(zf.read(member), member, cols)
                malformed += read.malformed
                sink.append(read.frame.join(kept, on="primaryid", how="semi"))
    ther = (
        pl.concat(ther_parts)
        .rename({"dsg_drug_seq": "drug_seq"})
        .with_columns(pl.col("start_dt").str.strip_chars())
        .filter(pl.col("start_dt").str.len_chars() > 0)
        .with_columns(_date_expr("start_dt").alias("start"))
        .group_by("primaryid", "drug_seq")
        .agg(
            pl.len().alias("n_start"),
            pl.col("start").min().alias("start"),
            pl.col("start_dt").filter(pl.col("start").is_not_null()).min().alias("start_dt"),
        )
    )
    demo = (
        pl.concat(demo_parts)
        .unique("primaryid", keep="first")
        .with_columns(pl.col("event_dt").str.strip_chars())
        .with_columns(_date_expr("event_dt").alias("event"))
    )
    joined = pairs.join(ther, on=["primaryid", "drug_seq"], how="left").join(
        demo, on="primaryid", how="left"
    )
    days = (pl.col("event") - pl.col("start")).dt.total_days()
    reason = (
        pl.when(pl.col("n_start").is_null())
        .then(pl.lit(Exclusion.no_therapy_start.value))
        .when(pl.col("start").is_null())
        .then(pl.lit(Exclusion.start_date_partial.value))
        .when(pl.col("event_dt").is_null() | (pl.col("event_dt").str.len_chars() == 0))
        .then(pl.lit(Exclusion.event_date_missing.value))
        .when(pl.col("event").is_null())
        .then(pl.lit(Exclusion.event_date_partial.value))
        .when(days < 0)
        .then(pl.lit(Exclusion.negative_interval.value))
        .when(days > MAX_DAYS)
        .then(pl.lit(Exclusion.interval_over_max.value))
        .otherwise(None)
    )
    joined = joined.with_columns(reason.alias("reason"), days.alias("onset_days"))
    counts = joined.group_by("reason").len()
    excluded = {str(r): int(n) for r, n in zip(counts["reason"], counts["len"], strict=True) if r}
    out = (
        joined.filter(pl.col("reason").is_null())
        .select(list(ROW_SCHEMA))
        .cast(pl.Schema(dict(ROW_SCHEMA)))
    )
    p.scratch.mkdir(parents=True, exist_ok=True)
    rows_file = p.scratch / "onset.parquet"
    out.sort("primaryid", "drug_seq").write_parquet(rows_file)

    reports = kept.height
    reports_with_event = int(demo.filter(pl.col("event").is_not_null()).height)
    by_role = out.group_by("role").len()
    usable_reports = out.select("primaryid").unique().height
    metrics: dict[str, object] = {
        "faers_run_id": p.faers_run_id,
        "window": [q.label for q in p.quarters],
        "reports": reports,
        "report_drug_pairs": pairs.height,
        "usable_pairs": out.height,
        "usable_pair_share": round(out.height / pairs.height, 4) if pairs.height else 0.0,
        "reports_with_usable_pair": usable_reports,
        "reports_with_complete_event_date": reports_with_event,
        "complete_event_date_share": round(reports_with_event / reports, 4) if reports else 0.0,
        "usable_pairs_by_role": {
            str(r): int(n) for r, n in zip(by_role["role"], by_role["len"], strict=True)
        },
        "malformed_lines": malformed,
        "max_days": MAX_DAYS,
        "rule": "earliest complete THER.start_dt of the drug; DEMO.event_dt; 0 <= days <= max",
        "spontaneous_reporting": True,
    }
    return ParseResult(
        rows=[],
        rows_file=rows_file,
        output_rows=out.height,
        input_rows=pairs.height,
        excluded=excluded,
        schema=SchemaReport(),
        metrics=json.loads(json.dumps(metrics)),
    )


class FaersOnsetJob(Job[Payload]):
    name = "faers_onset"
    source_id = "faers"
    schema = ONSET_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = ROW_SCHEMA

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        """Local input only: the current `faers` run and the raw archives it stored."""
        current = ctx.data_dir / "artifacts" / "faers" / "current"
        if not current.exists():
            raise FileNotFoundError("no current faers run; run `faers` first")
        run_dir = current.resolve()
        manifest = json.loads((run_dir / "manifest.json").read_text())
        run_id = str(manifest["run_id"])
        quarters = tuple(parse_quarter_names(",".join(manifest["metrics"]["window"])))
        raw_dir = ctx.data_dir / "raw" / "faers" / run_id
        archives = {q.label: raw_dir / f"faers_ascii_{q.label}.zip" for q in quarters}
        absent = [str(a) for a in archives.values() if not a.is_file()]
        if absent:
            raise FileNotFoundError(f"raw archives of the faers run are missing: {absent}")
        digest = sha256_bytes((run_id + str(manifest.get("source_sha256", ""))).encode("utf-8"))
        return RawInput(
            payload=Payload(
                rows_parquet=run_dir / "rows.parquet",
                archives=archives,
                quarters=quarters,
                scratch=ctx.scratch_dir(self.name),
                faers_run_id=run_id,
            ),
            source_urls=tuple(manifest.get("source_urls", ())),
            source_sha256=digest,
            retrieved_at=ctx.now(),
            snapshot_date=manifest.get("snapshot_date"),
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        return extract(raw.payload)
