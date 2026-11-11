"""`modelkit_ctgov` pipeline: ClinicalTrials.gov posted results for the drug model kit (spec
model-kit, milestone M2).

Takes the official bulk download of all study records (`ctg-studies.json.zip`, linked from the
ClinicalTrials.gov data pages; one file instead of many calls, the data API is disallowed for
crawlers by robots.txt), keeps the studies with posted results that name a drug of the pool and
have a PK outcome measure, and reads them with the resolver, the unit checker and the two
independent readers. The rows have the evidence schema and are merged into the evidence store by
the `modelkit_evidence` job. The raw file stays in the job's scratch directory (never committed)
and is removed after the run. Research use only. Not for clinical decisions.

Source: ClinicalTrials.gov. Modifications by Janus: values re-typed from the posted results, units
converted to canonical units, rows filtered by analyte, arm and population, short parts of the
posted text quoted. See `sources.toml` and `NOTICE`.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar, Final

import httpx2
import polars as pl

from janus_pipelines.core.canonical import Json, Row
from janus_pipelines.core.http import FetchError, make_fetcher
from janus_pipelines.core.runner import Job, ParseResult, RawInput, RunContext
from janus_pipelines.core.validation import ExpectedSchema, SchemaReport
from janus_pipelines.jobs.modelkit_evidence import EVIDENCE_ROW, EVIDENCE_SCHEMA, evidence_row
from janus_pipelines.modelkit.ctgov_bulk import read_bulk
from janus_pipelines.modelkit.model import ReaderStats
from janus_pipelines.modelkit.pilot import finalize_rows
from janus_pipelines.modelkit.resolver import IdentityTable

BULK_URL: Final = "https://clinicaltrials.gov/api/v2/studies/download?format=json.zip"
IDENTITY_PATH: Final = ("data", "modelkit", "identity_m2.csv")
CONNECT_TIMEOUT: Final = 30.0
READ_TIMEOUT: Final = 120.0  # between two blocks of the stream
TOTAL_TIMEOUT: Final = 3600.0  # whole download
MAX_BYTES: Final = 12 * 1024**3


def download(ctx: RunContext, target: Path) -> str:
    """Stream the bulk file to `target` (one request, timeouts, generic user agent); its sha256."""
    fetcher = make_fetcher(require_contact=False)
    digest = hashlib.sha256()
    size = 0
    t0 = time.monotonic()
    timeout = httpx2.Timeout(CONNECT_TIMEOUT, read=READ_TIMEOUT)
    try:
        with (
            fetcher.client.stream("GET", BULK_URL, timeout=timeout) as response,
            target.open("wb") as fh,
        ):
            response.raise_for_status()
            for block in response.iter_bytes(1 << 20):
                size += len(block)
                if size > MAX_BYTES or time.monotonic() - t0 > TOTAL_TIMEOUT:
                    raise FetchError("bulk download exceeded its size or time limit")
                digest.update(block)
                fh.write(block)
    except (httpx2.HTTPError, OSError) as exc:
        raise FetchError(f"bulk download failed: {exc}") from exc
    return digest.hexdigest()


class ModelkitCtgovJob(Job[Path]):
    name = "modelkit_ctgov"
    source_id = "modelkit_ctgov"
    schema: ExpectedSchema = EVIDENCE_SCHEMA
    polars_schema: ClassVar[Mapping[str, pl.DataType]] = EVIDENCE_ROW

    def fetch(self, ctx: RunContext) -> RawInput[Path]:
        local = ctx.options.get("input")
        now = ctx.now()
        if local:
            path = Path(local)
            digest = hashlib.sha256()
            with path.open("rb") as fh:
                for block in iter(lambda: fh.read(1 << 20), b""):
                    digest.update(block)
            sha = digest.hexdigest()
            date = ctx.options.get("snapshot_date") or now.date().isoformat()
            return RawInput(path, (), sha, now, date)
        target = ctx.scratch_dir(self.name) / "ctg-studies.json.zip"
        sha = download(ctx, target)
        return RawInput(target, (BULK_URL,), sha, now, now.date().isoformat(), True)

    def parse(self, raw: RawInput[Path]) -> ParseResult:
        repo = Path(__file__).resolve().parents[3]
        identity = repo.joinpath(*IDENTITY_PATH).read_text("utf-8")
        table = IdentityTable.from_csv(identity)
        counts: Counter[str] = Counter()
        stats = {"a": ReaderStats(), "b": ReaderStats()}
        cache_env = os.environ.get("JANUS_MODELKIT_CHECKPOINT_DIR")  # resumable research runs
        cache = Path(cache_env) if cache_env else None
        workers = max(1, int(os.environ.get("JANUS_MODELKIT_WORKERS", "1")))
        pairs, only_b, kept = read_bulk(raw.payload, identity, stats, counts, workers, cache)
        rows_csv, dropped = finalize_rows(pairs, table)
        date = raw.snapshot_date or raw.retrieved_at.date().isoformat()
        rows: list[Row] = []
        for r in rows_csv:
            r["extracted_at"] = date
            rows.append(evidence_row(r, "ctgov"))
        confirmed = [r for r in rows if r["confirmed"]]
        metrics: dict[str, Json] = {
            **{k: v for k, v in sorted(counts.items())},
            "pool_drugs": len(table.by_key),
            "drugs_with_candidates": len(kept),
            "candidate_values": len(pairs),
            "reader_b_only": len(only_b),
            "rows": len(rows),
            "confirmed_rows": len(confirmed),
            "drugs_with_confirmed_row": len({str(r["drug_key"]) for r in confirmed}),
            "dropped": dict(sorted(dropped.items())),
            "reader_a_skipped": dict(sorted(stats["a"].skipped.items())),
            "reader_b_skipped": dict(sorted(stats["b"].skipped.items())),
            "processing_date": date,
        }
        return ParseResult(
            rows=rows,
            input_rows=counts["studies"],
            excluded={"no_pk_result_for_a_pool_drug": counts["studies"] - len(rows)}
            if counts["studies"] > len(rows)
            else {},
            schema=SchemaReport(),
            metrics=metrics,
        )
