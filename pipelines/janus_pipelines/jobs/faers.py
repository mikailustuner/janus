# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""`faers` pipeline: FDA quarterly adverse-event files → one row per deduplicated report.

Design §13.3, Req 13. FDA now names the system AEMS (formerly FAERS). The four latest quarters
are read; of every case only the latest version is kept, cases listed in a DELETE file are
dropped, and removed reports go to a side table. Different cases that may describe the same
event are not merged. Ingredient names stay as published (`prod_ai` split at the backslash);
mapping them to ingredient keys is done by `janus.memory.faers_build` in `apps/api` (DP19).

Files are read as lines, split at `$` in Polars, one column set at a time, so a quarter never
needs more than a few hundred MB beyond the archive itself.
"""

from __future__ import annotations

import datetime as dt
import io
import re
import zipfile
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import ClassVar, NamedTuple
from urllib.parse import urljoin

import polars as pl

from janus_pipelines.core.canonical import Json, sha256_bytes
from janus_pipelines.core.http import BULK_READ_TIMEOUT, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import (
    ExpectedSchema,
    Field,
    SchemaMismatchError,
    SchemaReport,
)

PAGE_URL = "https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html"
WINDOW = 4

FAERS_SCHEMA = ExpectedSchema(
    version="faers-1",
    fields=(
        Field("primaryid", frozenset({"str"})),
        Field("caseid", frozenset({"str"})),
    ),
)

REQUIRED: Mapping[str, tuple[str, ...]] = {
    "DEMO": (
        "primaryid",
        "caseid",
        "caseversion",
        "fda_dt",
        "occr_country",
        "reporter_country",
    ),
    "DRUG": ("primaryid", "caseid", "drug_seq", "role_cod", "prod_ai"),
    "REAC": ("primaryid", "caseid", "pt"),
}

# --- region ------------------------------------------------------------------------------

EU27 = frozenset(
    "AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split()
)
# FDA treats the US territories as US (owner decision 2026-11-08, DP16).
US_TERRITORIES = frozenset("PR GU VI AS MP UM".split())
NOT_SPECIFIED = "COUNTRY NOT SPECIFIED"
REGIONS: tuple[str, ...] = ("TR", "EU", "US", "OTHER", "UNKNOWN")
REGION_RULE: dict[str, Json] = {
    "version": 1,
    "basis_order": ["occr_country", "reporter_country"],
    "missing_values": ["", NOT_SPECIFIED],
    "tr": ["TR"],
    "us": ["US", *sorted(US_TERRITORIES)],
    "eu": ["EU (FAERS pseudo-code)", *sorted(EU27)],
    "other": "any other present value, including GB CH NO IS LI",
    "unknown": "no present value",
}


def _present(value: str | None) -> str | None:
    if value is None:
        return None
    code = value.strip().upper()
    return None if code in ("", NOT_SPECIFIED) else code


def derive_region(occr: str | None, reporter: str | None) -> tuple[str, str]:
    """(region, basis) of a report (Req 13.6): occurrence country, else reporter country."""
    code = _present(occr)
    basis = "occr_country"
    if code is None:
        code = _present(reporter)
        basis = "reporter_country"
    if code is None:
        return "UNKNOWN", "none"
    if code == "TR":
        return "TR", basis
    if code == "US" or code in US_TERRITORIES:
        return "US", basis
    if code == "EU" or code in EU27:
        return "EU", basis
    return "OTHER", basis


def split_ai(text: str | None) -> list[str]:
    """`prod_ai` split at the backslash; parts are kept as published, empty parts dropped."""
    if not text:
        return []
    return [p for p in text.split("\\") if p != ""]


# --- quarter window ------------------------------------------------------------------------


class Quarter(NamedTuple):
    year: int
    q: int

    @property
    def label(self) -> str:
        return f"{self.year}Q{self.q}"

    @property
    def ordinal(self) -> int:
        return self.year * 4 + self.q - 1

    @property
    def end(self) -> dt.date:
        month = self.q * 3
        last = dt.date(self.year + month // 12, month % 12 + 1, 1) - dt.timedelta(days=1)
        return last


class QuarterWindowError(ValueError):
    """The listing cannot give the requested consecutive quarters."""


@dataclass(frozen=True)
class Listing:
    quarter: Quarter
    url: str
    posted: str | None


_ROW = re.compile(r"<tr>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_ASCII = re.compile(r'href="([^"]*faers_ascii_(\d{4})q([1-4])\.zip)"', re.IGNORECASE)
_POSTED = re.compile(r"posted on\s+(\d{1,2})-([A-Za-z]{3})-(\d{4})", re.IGNORECASE)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def parse_listing(html: str, base_url: str = PAGE_URL) -> list[Listing]:
    """Quarters with an ASCII archive, from the FDA page (commented-out rows are ignored).

    A posting date is kept only when it is plausible for the quarter (after the quarter ends,
    within 400 days); the page has a typo for 2025 Q4 ("posted on 27-Jan-2025").
    """
    found: dict[Quarter, Listing] = {}
    for block in _ROW.findall(_COMMENT.sub("", html)):
        m = _ASCII.search(block)
        if not m:
            continue
        quarter = Quarter(int(m.group(2)), int(m.group(3)))
        posted = None
        p = _POSTED.search(block)
        if p and p.group(2).title() in _MONTHS:
            try:
                day = dt.date(int(p.group(3)), _MONTHS[p.group(2).title()], int(p.group(1)))
            except ValueError:
                day = None
            if day and quarter.end < day <= quarter.end + dt.timedelta(days=400):
                posted = day.isoformat()
        listing = Listing(quarter, urljoin(base_url, m.group(1)), posted)
        if quarter not in found or (found[quarter].posted is None and posted):
            found[quarter] = listing
    return sorted(found.values(), key=lambda x: x.quarter)


def select_quarters(listing: Iterable[Listing], n: int = WINDOW) -> list[Listing]:
    """The `n` latest quarters, oldest first; they must be consecutive (Req 13.1)."""
    by_quarter: dict[Quarter, Listing] = {}
    for item in listing:
        by_quarter.setdefault(item.quarter, item)
    ordered = sorted(by_quarter.values(), key=lambda x: x.quarter)
    if len(ordered) < n:
        raise QuarterWindowError(f"only {len(ordered)} quarters listed; need {n}")
    window = ordered[-n:]
    for a, b in pairwise(window):
        if b.quarter.ordinal != a.quarter.ordinal + 1:
            raise QuarterWindowError(
                f"quarters {a.quarter.label} and {b.quarter.label} are not consecutive"
            )
    return window


def parse_quarter_names(text: str) -> list[Quarter]:
    out: list[Quarter] = []
    for part in text.split(","):
        m = re.fullmatch(r"\s*(\d{4})\s*[qQ]([1-4])\s*", part)
        if not m:
            raise ValueError(f"not a quarter: {part.strip()!r} (use 2026Q3)")
        out.append(Quarter(int(m.group(1)), int(m.group(2))))
    return sorted(set(out))


# --- reading archives ----------------------------------------------------------------------


@dataclass
class TableRead:
    frame: pl.DataFrame
    malformed: int
    extra: tuple[str, ...]


def _member(zf: zipfile.ZipFile, kind: str, quarter: Quarter) -> str | None:
    yy = f"{quarter.year % 100:02d}"
    pattern = re.compile(rf"(?i)(?:^|/){kind}{yy}Q{quarter.q}\.txt$")
    hits = [n for n in zf.namelist() if pattern.search(n)]
    return hits[0] if hits else None


def read_lines(data: bytes, member: str) -> pl.DataFrame:
    """One string column `line`; strict UTF-8, no quote handling, CRLF or LF."""
    try:
        return pl.read_csv(
            io.BytesIO(data),
            has_header=False,
            separator="\x1f",
            quote_char=None,
            infer_schema=False,
            new_columns=["line"],
            encoding="utf8",
        )
    except pl.exceptions.ComputeError as exc:
        raise SchemaMismatchError(
            SchemaReport(missing=(f"{member}: not valid UTF-8 ({str(exc)[:60]})",))
        ) from None


def read_table(data: bytes, member: str, required: Sequence[str]) -> TableRead:
    """Split a `$`-delimited file with a header line. A line with another field count than
    the header is malformed (Req 13.2)."""
    lines = read_lines(data, member)
    if lines.height == 0 or lines["line"][0] is None:
        raise SchemaMismatchError(SchemaReport(missing=(f"{member}: header line",)))
    header = [h.strip().lower() for h in str(lines["line"][0]).split("$")]
    missing = tuple(f"{member}: {c}" for c in required if c not in header)
    if missing:
        raise SchemaMismatchError(SchemaReport(missing=missing))
    body = lines.slice(1)
    split = body.select(p=pl.col("line").str.split("$"))
    ok = split.select(good=pl.col("p").list.len().eq(len(header)).fill_null(False))["good"]
    malformed = int((~ok).sum())
    good = split.filter(ok)
    index = {name: i for i, name in enumerate(header)}
    frame = good.select([pl.col("p").list.get(index[c]).alias(c) for c in required])
    return TableRead(frame, malformed, tuple(sorted(set(header) - set(required))))


def read_deleted(data: bytes | None, member: str) -> set[str]:
    if data is None:
        return set()
    ids: set[str] = set()
    for raw in data.decode("utf-8").split("\n"):
        text = raw.strip()
        if not text:
            continue
        if not text.isascii() or not text.isdigit():
            raise SchemaMismatchError(SchemaReport(missing=(f"{member}: a case id per line",)))
        ids.add(text)
    return ids


# --- deduplication -------------------------------------------------------------------------

REMOVED_SCHEMA: Mapping[str, pl.DataType] = {
    "primaryid": pl.String(),
    "caseid": pl.String(),
    "caseversion": pl.Int64(),
    "quarter": pl.String(),
    "reason": pl.String(),
    "kept_primaryid": pl.String(),
}

_DIGITS = r"^[0-9]+$"


def choose_kept(demo: pl.DataFrame, deleted: set[str]) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Latest version per case (Req 13.3). `demo` has string columns primaryid, caseid,
    caseversion, fda_dt, quarter (all ids numeric). Returns (kept, removed).

    Order: highest caseversion, then latest fda_dt, then highest primaryid, then latest quarter.
    Cases listed in `deleted` are removed with every version.
    """
    d = demo.with_columns(
        ver=pl.col("caseversion").cast(pl.Int64),
        pid=pl.col("primaryid").cast(pl.Int64),
        gone=pl.col("caseid").is_in(sorted(deleted)),
    )
    live = d.filter(~pl.col("gone"))
    kept = live.sort(
        ["caseid", "ver", "fda_dt", "pid", "quarter"],
        descending=[False, True, True, True, True],
    ).unique(subset="caseid", keep="first", maintain_order=True)
    winners = kept.select("caseid", kept_primaryid=pl.col("primaryid"), kept_quarter="quarter")
    superseded = (
        live.join(winners, on="caseid")
        .filter(
            (pl.col("primaryid") != pl.col("kept_primaryid"))
            | (pl.col("quarter") != pl.col("kept_quarter"))
        )
        .select(
            "primaryid",
            "caseid",
            pl.col("ver").alias("caseversion"),
            "quarter",
            pl.lit("superseded_version").alias("reason"),
            "kept_primaryid",
        )
    )
    deleted_rows = d.filter(pl.col("gone")).select(
        "primaryid",
        "caseid",
        pl.col("ver").alias("caseversion"),
        "quarter",
        pl.lit("deleted_case").alias("reason"),
        pl.lit(None, dtype=pl.String).alias("kept_primaryid"),
    )
    removed = pl.concat([superseded, deleted_rows]).cast(dict(REMOVED_SCHEMA))  # type: ignore[arg-type]
    return kept.drop("ver", "pid", "gone"), removed


# --- parse ---------------------------------------------------------------------------------

DRUG_STRUCT = pl.Struct(
    {"drug_seq": pl.String(), "role": pl.String(), "ingredients": pl.List(pl.String())}
)

ROW_SCHEMA: Mapping[str, pl.DataType] = {
    "primaryid": pl.String(),
    "caseid": pl.String(),
    "caseversion": pl.Int64(),
    "quarter": pl.String(),
    "fda_dt": pl.String(),
    "occr_country": pl.String(),
    "reporter_country": pl.String(),
    "region": pl.String(),
    "region_basis": pl.String(),
    "drugs": pl.List(DRUG_STRUCT),
    "events": pl.List(pl.String()),
}


@dataclass
class Payload:
    archives: dict[str, bytes]
    quarters: tuple[Quarter, ...]
    scratch: Path
    posted: dict[str, str | None] = field(default_factory=dict[str, str | None])
    snapshot_from_last_modified: bool = False


@dataclass
class LineCounts:
    lines: int = 0
    kept: int = 0
    of_removed_report: int = 0
    orphan: int = 0
    malformed: int = 0

    def as_json(self) -> dict[str, Json]:
        return {
            "lines": self.lines,
            "kept": self.kept,
            "of_removed_report": self.of_removed_report,
            "orphan": self.orphan,
            "malformed": self.malformed,
        }


def _regions(kept: pl.DataFrame) -> pl.DataFrame:
    pairs = kept.select("occr_country", "reporter_country").unique()
    derived = [(o, r, *derive_region(o, r)) for o, r in pairs.iter_rows()]
    mapping = pl.DataFrame(
        derived,
        schema={
            "occr_country": pl.String(),
            "reporter_country": pl.String(),
            "region": pl.String(),
            "region_basis": pl.String(),
        },
        orient="row",
    )
    return kept.join(mapping, on=["occr_country", "reporter_country"], how="left")


def _lines_of_kept(
    table: pl.DataFrame,
    all_ids: set[str],
    kept_ids: set[str],
    malformed: int,
) -> tuple[pl.DataFrame, LineCounts]:
    """Keep the lines of kept reports; count the rest (Req 13.5)."""
    counts = LineCounts(lines=table.height + malformed, malformed=malformed)
    in_demo = table["primaryid"].is_in(sorted(all_ids))
    counts.orphan = int((~in_demo).sum())
    keep = table["primaryid"].is_in(sorted(kept_ids))
    counts.kept = int(keep.sum())
    counts.of_removed_report = table.height - counts.orphan - counts.kept
    return table.filter(keep), counts


def parse_archives(
    archives: Mapping[str, bytes], quarters: Sequence[Quarter], scratch: Path
) -> ParseResult:
    """Parse the archives (label → bytes) of the given quarters (oldest first)."""
    scratch.mkdir(parents=True, exist_ok=True)
    zips = {q.label: zipfile.ZipFile(io.BytesIO(archives[q.label])) for q in quarters}
    extra: set[str] = set()
    demo_frames: list[pl.DataFrame] = []
    demo_ids: dict[str, set[str]] = {}
    deleted: set[str] = set()
    missing_delete: list[str] = []
    malformed_demo = 0
    quarter_stats: list[dict[str, Json]] = []
    for q in quarters:
        zf = zips[q.label]
        member = _member(zf, "DEMO", q)
        if member is None:
            raise SchemaMismatchError(SchemaReport(missing=(f"{q.label}: DEMO file",)))
        table = read_table(zf.read(member), member, REQUIRED["DEMO"])
        extra.update(table.extra)
        frame = table.frame
        numeric = (
            pl.col("primaryid").str.contains(_DIGITS)
            & pl.col("caseid").str.contains(_DIGITS)
            & pl.col("caseversion").str.contains(_DIGITS)
        )
        bad = frame.filter(~numeric).height
        frame = frame.filter(numeric).with_columns(quarter=pl.lit(q.label))
        malformed_demo += table.malformed + bad
        quarter_stats.append(
            {"label": q.label, "demo_rows": frame.height, "demo_malformed": table.malformed + bad}
        )
        demo_ids[q.label] = set(frame["primaryid"].to_list())
        demo_frames.append(frame)
        deleted_name = next(
            (n for n in zf.namelist() if re.search(rf"(?i)(?:^|/)DELETE\d{{2}}Q{q.q}\.txt$", n)),
            None,
        )
        if deleted_name is None:
            missing_delete.append(q.label)
        else:
            deleted |= read_deleted(zf.read(deleted_name), deleted_name)
    demo = pl.concat(demo_frames)
    kept, removed = choose_kept(demo, deleted)
    kept = _regions(kept)
    kept_ids: dict[str, set[str]] = {
        q.label: set(kept.filter(pl.col("quarter") == q.label)["primaryid"].to_list())
        for q in quarters
    }

    drug_counts, reac_counts = LineCounts(), LineCounts()
    parts: list[Path] = []
    no_drugs = no_events = 0
    blank_ai = 0
    for q in quarters:
        zf = zips[q.label]
        lines: dict[str, tuple[pl.DataFrame, LineCounts]] = {}
        for kind in ("DRUG", "REAC"):
            member = _member(zf, kind, q)
            if member is None:
                raise SchemaMismatchError(SchemaReport(missing=(f"{q.label}: {kind} file",)))
            table = read_table(zf.read(member), member, REQUIRED[kind])
            extra.update(table.extra)
            lines[kind] = _lines_of_kept(
                table.frame, demo_ids[q.label], kept_ids[q.label], table.malformed
            )
            del table
        drug, dc = lines["DRUG"]
        reac, rc = lines["REAC"]
        for total, add in ((drug_counts, dc), (reac_counts, rc)):
            total.lines += add.lines
            total.kept += add.kept
            total.of_removed_report += add.of_removed_report
            total.orphan += add.orphan
            total.malformed += add.malformed
        blank_ai += int((drug["prod_ai"] == "").sum())
        drugs = (
            drug.select(
                "primaryid",
                pl.struct(
                    pl.col("drug_seq"),
                    pl.col("role_cod").alias("role"),
                    pl.col("prod_ai")
                    .str.split("\\")
                    .list.eval(pl.element().filter(pl.element() != ""))
                    .alias("ingredients"),
                ).alias("drug"),
            )
            .group_by("primaryid", maintain_order=True)
            .agg(pl.col("drug").alias("drugs"))
        )
        events = reac.group_by("primaryid", maintain_order=True).agg(pl.col("pt").alias("events"))
        rows = (
            kept.filter(pl.col("quarter") == q.label)
            .select(
                "primaryid",
                "caseid",
                pl.col("caseversion").cast(pl.Int64),
                "quarter",
                "fda_dt",
                "occr_country",
                "reporter_country",
                "region",
                "region_basis",
            )
            .join(drugs, on="primaryid", how="left")
            .join(events, on="primaryid", how="left")
            .with_columns(
                pl.col("drugs").fill_null(pl.lit([], dtype=pl.List(DRUG_STRUCT))),
                pl.col("events").fill_null(pl.lit([], dtype=pl.List(pl.String()))),
            )
            .select(list(ROW_SCHEMA))
        )
        no_drugs += int((rows["drugs"].list.len() == 0).sum())
        no_events += int((rows["events"].list.len() == 0).sum())
        part = scratch / f"rows-{q.label}.parquet"
        rows.write_parquet(part, row_group_size=100_000)
        parts.append(part)
        del drug, reac, drugs, events, rows, lines

    rows_file = scratch / "rows-all.parquet"
    pl.concat([pl.scan_parquet(p) for p in parts]).sink_parquet(rows_file, row_group_size=100_000)
    removed_file = scratch / "removed.parquet"
    removed.write_parquet(removed_file)

    n_kept = kept.height
    removed_by_reason = Counter(removed["reason"].to_list())
    excluded = {k: v for k, v in removed_by_reason.items() if v}
    if malformed_demo:
        excluded["malformed_row"] = malformed_demo
    per_quarter = kept.group_by("quarter").len().sort("quarter")
    kept_per_q = dict(zip(per_quarter["quarter"], per_quarter["len"], strict=True))
    for stat in quarter_stats:
        stat["kept_rows"] = kept_per_q.get(str(stat["label"]), 0)
    by_region = Counter(kept["region"].to_list())
    follow_up = int((kept["caseversion"].cast(pl.Int64) > 1).sum())
    input_rows = demo.height + malformed_demo
    return ParseResult(
        rows=[],
        rows_file=rows_file,
        output_rows=n_kept,
        side_tables={"removed": removed_file},
        input_rows=input_rows,
        excluded=excluded,
        schema=SchemaReport(extra=tuple(sorted(extra))),
        metrics={
            "quarters": list(quarter_stats),
            "reports_by_region": {r: by_region.get(r, 0) for r in REGIONS},
            "removed_by_reason": dict(removed_by_reason),
            "unknown_region_share": round(by_region.get("UNKNOWN", 0) / n_kept, 6)
            if n_kept
            else 0.0,
            "reports_without_drugs": no_drugs,
            "reports_without_events": no_events,
            "follow_up_share": round(follow_up / n_kept, 4) if n_kept else 0.0,
            "blank_prod_ai_lines": blank_ai,
            "line_accounting": {
                "DRUG": drug_counts.as_json(),
                "REAC": reac_counts.as_json(),
            },
            "delete_files_missing": list(missing_delete),
            "deleted_case_ids": len(deleted),
            "region_rule": REGION_RULE,
            "not_deduplicated_across_cases": True,
        },
    )


def file_sha(archives: Mapping[str, bytes], quarters: Sequence[Quarter]) -> str:
    return sha256_bytes("".join(sha256_bytes(archives[q.label]) for q in quarters).encode())


class FaersJob(Job[Payload]):
    name = "faers"
    source_id = "faers"
    schema = FAERS_SCHEMA
    review_threshold = Fraction(15, 100)
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = ROW_SCHEMA

    def fetch(self, ctx: RunContext) -> RawInput[Payload]:
        retrieved = ctx.now()
        fetcher = make_fetcher(require_contact=False)
        page = fetcher.get(PAGE_URL)
        listing = parse_listing(page.text, str(page.url))
        if "quarters" in ctx.options:
            wanted = parse_quarter_names(ctx.options["quarters"])
            known = {x.quarter: x for x in listing}
            absent = [q.label for q in wanted if q not in known]
            if absent:
                raise QuarterWindowError(f"not listed with an ASCII archive: {', '.join(absent)}")
            window = [known[q] for q in wanted]
        else:
            window = select_quarters(listing)
        archives: dict[str, bytes] = {}
        last_modified: dict[str, str | None] = {}
        for item in window:
            response = fetcher.get(item.url, read_timeout=BULK_READ_TIMEOUT)
            archives[item.quarter.label] = response.content
            last_modified[item.quarter.label] = response.headers.get("Last-Modified")
        newest = window[-1]
        snapshot = newest.posted
        fallback = False
        if snapshot is None:
            header = last_modified[newest.quarter.label]
            if not header:
                raise ValueError(
                    f"no posting date for {newest.quarter.label} and no Last-Modified header"
                )
            snapshot = parsedate_to_datetime(header).date().isoformat()
            fallback = True
        quarters = tuple(x.quarter for x in window)
        payload = Payload(
            archives=archives,
            quarters=quarters,
            scratch=ctx.scratch_dir(self.name),
            posted={x.quarter.label: x.posted for x in window},
            snapshot_from_last_modified=fallback,
        )
        return RawInput(
            payload=payload,
            source_urls=(PAGE_URL, *(x.url for x in window)),
            source_sha256=file_sha(archives, quarters),
            retrieved_at=retrieved,
            snapshot_date=snapshot,
            raw_files={f"faers_ascii_{q.label}.zip": archives[q.label] for q in quarters},
        )

    def parse(self, raw: RawInput[Payload]) -> ParseResult:
        p = raw.payload
        result = parse_archives(p.archives, p.quarters, p.scratch)
        result.metrics["window"] = [q.label for q in p.quarters]
        result.metrics["posted"] = dict(p.posted)
        result.metrics["snapshot_from_last_modified"] = p.snapshot_from_last_modified
        return result
