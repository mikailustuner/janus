"""Pipeline runner: fetch → parse → validate → hash → stage → promote (design §4.1)."""

from __future__ import annotations

import datetime as dt
import logging
import secrets
import shutil
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import ClassVar

import polars as pl

from janus_pipelines.core.canonical import Json, Row, content_hash, content_hash_stream
from janus_pipelines.core.licensing import check_output_path, git_ignored
from janus_pipelines.core.manifest import (
    Counts,
    EvidenceSource,
    Manifest,
    Outcome,
    Promotion,
    SideTable,
)
from janus_pipelines.core.registry import Registry, Source, Storage
from janus_pipelines.core.store import FaultHook, Store, file_sha256, no_fault
from janus_pipelines.core.validation import (
    DEFAULT_REVIEW_THRESHOLD,
    ExpectedSchema,
    SchemaReport,
    check_accounting,
    review_needed,
)

log = logging.getLogger("janus_pipelines")


@dataclass(frozen=True)
class RawInput[T]:
    """What fetch produced. `payload` is job-specific; `raw_files` are kept for cache sources."""

    payload: T
    source_urls: tuple[str, ...]
    source_sha256: str
    retrieved_at: dt.datetime
    snapshot_date: str | None
    snapshot_date_is_retrieval_time: bool = False
    raw_files: Mapping[str, bytes] = field(default_factory=dict[str, bytes])
    query_sha256: Mapping[str, str] = field(default_factory=dict[str, str])


@dataclass
class ParseResult:
    rows: list[Row]
    input_rows: int
    excluded: dict[str, int]
    schema: SchemaReport
    metrics: dict[str, Json] = field(default_factory=dict[str, Json])
    review_reasons: list[str] = field(default_factory=list[str])
    changes: list[dict[str, Json]] = field(default_factory=list[dict[str, Json]])
    doi: str | None = None
    # File-backed output (Req 14.2): rows already written as Parquet with the job's schema.
    # When set, `rows` stays empty and `output_rows` is the row count of the file.
    rows_file: Path | None = None
    output_rows: int = 0
    # Side tables (Req 14.3): name -> Parquet file. Not part of the content hash.
    side_tables: dict[str, Path] = field(default_factory=dict[str, Path])

    @property
    def n_output(self) -> int:
        return self.output_rows if self.rows_file is not None else len(self.rows)


@dataclass
class RunContext:
    data_dir: Path
    repo_root: Path
    registry: Registry
    code_version: str
    now: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC)
    fault: FaultHook = no_fault
    is_ignored: Callable[[Path], bool] | None = None
    options: dict[str, str] = field(default_factory=dict[str, str])

    def scratch_dir(self, pipeline: str) -> Path:
        """Working directory for a job that spills to disk; the runner removes it after the run."""
        path = Store(self.data_dir, pipeline).scratch_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def ignored(self, path: Path) -> bool:
        if self.is_ignored is not None:
            return self.is_ignored(path)
        return git_ignored(path, self.repo_root)


class Job[T](ABC):
    name: str
    source_id: str
    schema: ExpectedSchema
    polars_schema: ClassVar[Mapping[str, pl.DataType]]
    review_threshold: Fraction = DEFAULT_REVIEW_THRESHOLD

    @abstractmethod
    def fetch(self, ctx: RunContext) -> RawInput[T]: ...

    @abstractmethod
    def parse(self, raw: RawInput[T]) -> ParseResult: ...

    def extra_output_paths(self, ctx: RunContext) -> list[Path]:
        """Paths outside the data directory that on_promote writes (licence-checked)."""
        del ctx
        return []

    def on_promote(self, ctx: RunContext, store: Store, run_id: str) -> None:
        """Called after the run became current (e.g. pipc writes data/pipc.csv)."""
        del ctx, store, run_id


@dataclass(frozen=True)
class RunResult:
    run_id: str
    outcome: Outcome
    manifest: Manifest
    error: str | None = None


def _run_id(now: dt.datetime, source_sha256: str | None) -> str:
    stamp = now.astimezone(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    digest = (source_sha256 or "nohash")[:8]
    return f"{stamp}-{digest}-{secrets.token_hex(2)}"


def _check_paths[T](job: Job[T], source: Source, ctx: RunContext, store: Store) -> None:
    """Refuse before anything is written if a path breaks the storage rule (Req 3.1)."""
    probe = "probe"
    paths = [*store.planned_paths(probe), *job.extra_output_paths(ctx)]
    if source.storage is Storage.CACHE:
        paths.append(store.raw_dir(probe) / "file")
    for path in paths:
        check_output_path(path, source.storage, ctx.repo_root, ctx.ignored)


def run_job[T](job: Job[T], ctx: RunContext, raw: RawInput[T] | None = None) -> RunResult:
    """Run one pipeline. Raises UnknownSourceError / LicenceViolationError before writing."""
    source = ctx.registry.get(job.source_id)
    store = Store(ctx.data_dir, job.name, ctx.fault)
    _check_paths(job, source, ctx, store)

    started = ctx.now()
    previous = store.current_manifest()
    manifest = Manifest(
        run_id=_run_id(started, None),
        pipeline=job.name,
        source_id=source.id,
        source_urls=list(source.urls),
        license=source.license,
        region=source.region,
        schema_version=job.schema.version,
        code_version=ctx.code_version,
        outcome=Outcome.FAILED,
        previous_run_id=previous.run_id if previous else None,
        started_at=started,
    )
    try:
        if raw is None:
            raw = job.fetch(ctx)
        manifest.run_id = _run_id(started, raw.source_sha256)
        manifest.source_urls = list(raw.source_urls)
        manifest.source_sha256 = raw.source_sha256
        manifest.retrieved_at = raw.retrieved_at
        manifest.snapshot_date = raw.snapshot_date
        manifest.snapshot_date_is_retrieval_time = raw.snapshot_date_is_retrieval_time
        manifest.query_sha256 = dict(raw.query_sha256)

        result = job.parse(raw)
        manifest.extra_columns = list(result.schema.extra)
        n_out = result.n_output
        manifest.counts = Counts(
            input=result.input_rows, output=n_out, excluded=dict(result.excluded)
        )
        manifest.metrics = result.metrics
        manifest.changes = result.changes
        check_accounting(result.input_rows, n_out, result.excluded)
        if n_out == 0:
            raise ValueError("the run produced no output rows")
        if result.rows_file is not None:
            manifest.content_sha256 = content_hash_stream(
                iter_parquet_rows(result.rows_file),
                job.schema.version,
                tmp_dir=store.scratch_dir_created(),
            )
            manifest.side_tables = [
                SideTable(name=name, rows=parquet_rows(path), sha256=file_sha256(path))
                for name, path in sorted(result.side_tables.items())
            ]
        else:
            manifest.content_sha256 = content_hash(result.rows, job.schema.version)
        reasons = list(result.review_reasons)
        prev_count = previous.counts.output if previous else None
        if review_needed(prev_count, n_out, job.review_threshold):
            reasons.append(
                f"output rows changed from {prev_count} to {n_out} "
                f"(threshold {float(job.review_threshold):.0%})"
            )
        manifest.review_reasons = reasons
        manifest.outcome = Outcome.NEEDS_REVIEW if reasons else Outcome.SUCCEEDED
        manifest.finished_at = ctx.now()

        evidence = EvidenceSource(
            source_id=source.id,
            source_url=manifest.source_urls[0] if manifest.source_urls else "",
            license=source.license,
            region=source.region,
            snapshot_date=manifest.snapshot_date,
            run_id=manifest.run_id,
            doi=result.doi,
        )
        if source.storage is Storage.CACHE and raw.raw_files:
            store.write_raw(manifest.run_id, raw.raw_files)
        if result.rows_file is not None:
            store.stage_file(
                manifest.run_id, result.rows_file, result.side_tables, manifest, evidence
            )
        else:
            store.stage(manifest.run_id, result.rows, job.polars_schema, manifest, evidence)
        store.finish(manifest.run_id)
        if manifest.outcome is Outcome.SUCCEEDED:
            store.promote(manifest.run_id)
    except Exception as exc:
        if store.current_run_id() == manifest.run_id:
            # Promotion already happened; the run is current and complete.
            log.warning("pipeline=%s run_id=%s step=after_promote", job.name, manifest.run_id)
        else:
            _cleanup_tmp_links(store)
            shutil.rmtree(store.scratch_dir(), ignore_errors=True)
            manifest.outcome = Outcome.FAILED
            manifest.errors = [f"{type(exc).__name__}: {exc}"]
            manifest.finished_at = ctx.now()
            store.write_failed_manifest(manifest)
            log.info(
                "pipeline=%s run_id=%s outcome=failed error=%s",
                job.name,
                manifest.run_id,
                type(exc).__name__,
            )
            return RunResult(manifest.run_id, Outcome.FAILED, manifest, manifest.errors[0])

    shutil.rmtree(store.scratch_dir(), ignore_errors=True)
    error: str | None = None
    if manifest.outcome is Outcome.SUCCEEDED:
        try:
            job.on_promote(ctx, store, manifest.run_id)
        except Exception as exc:
            error = f"after promotion: {type(exc).__name__}: {exc}"
    log.info(
        "pipeline=%s run_id=%s outcome=%s input=%d output=%d",
        job.name,
        manifest.run_id,
        manifest.outcome.value,
        manifest.counts.input,
        manifest.counts.output,
    )
    return RunResult(manifest.run_id, manifest.outcome, manifest, error)


BATCH_ROWS = 50_000


def parquet_rows(path: Path) -> int:
    frame: pl.LazyFrame = pl.scan_parquet(path)
    counted: pl.DataFrame = frame.select(pl.len().alias("n")).collect()  # pyright: ignore[reportUnknownMemberType]
    return int(counted["n"][0])


def iter_parquet_rows(path: Path, batch: int = BATCH_ROWS) -> Iterator[Row]:
    """Rows of a Parquet file as plain dicts, a batch at a time (Req 14.2)."""
    for frame in pl.scan_parquet(path).collect_batches(chunk_size=batch):
        yield from frame.to_dicts()


def _cleanup_tmp_links(store: Store) -> None:
    if store.artifacts_dir.exists():
        for tmp in store.artifacts_dir.glob("current.tmp-*"):
            if tmp.is_symlink():
                tmp.unlink()


class ToolUnavailableError(RuntimeError):
    """A local model tool (e.g. Rscript with httk, or a pinned model environment) is not
    installed. The run is refused: artifacts are precomputed offline and CI never needs them."""


class PromotionError(Exception):
    pass


def promote_run[T](job: Job[T], ctx: RunContext, run_id: str, by: str) -> Promotion:
    """Explicitly promote a run that ended as needs_review (Req 2.2, DP4)."""
    if not by.strip():
        raise PromotionError("--by is required: who is promoting this run")
    store = Store(ctx.data_dir, job.name, ctx.fault)
    manifest = store.read_manifest(run_id)
    if manifest.outcome is Outcome.FAILED:
        raise PromotionError(f"run {run_id} failed; it cannot be promoted")
    if not (store.run_dir(run_id) / "rows.parquet").exists():
        raise PromotionError(f"run {run_id} has no rows")
    previous = store.current_run_id()
    store.promote(run_id)
    promotion = Promotion(
        run_id=run_id, promoted_by=by.strip(), promoted_at=ctx.now(), previous_run_id=previous
    )
    store.write_promotion(promotion)
    job.on_promote(ctx, store, run_id)
    return promotion
