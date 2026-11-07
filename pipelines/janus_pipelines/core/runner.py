"""Pipeline runner: fetch → parse → validate → hash → stage → promote (design §4.1)."""

from __future__ import annotations

import datetime as dt
import logging
import secrets
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import ClassVar

import polars as pl

from janus_pipelines.core.canonical import Json, Row, content_hash
from janus_pipelines.core.licensing import check_output_path, git_ignored
from janus_pipelines.core.manifest import Counts, EvidenceSource, Manifest, Outcome, Promotion
from janus_pipelines.core.registry import Registry, Source, Storage
from janus_pipelines.core.store import FaultHook, Store, no_fault
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
        manifest.counts = Counts(
            input=result.input_rows, output=len(result.rows), excluded=dict(result.excluded)
        )
        manifest.metrics = result.metrics
        manifest.changes = result.changes
        check_accounting(result.input_rows, len(result.rows), result.excluded)
        if not result.rows:
            raise ValueError("the run produced no output rows")
        manifest.content_sha256 = content_hash(result.rows, job.schema.version)

        reasons = list(result.review_reasons)
        prev_count = previous.counts.output if previous else None
        if review_needed(prev_count, len(result.rows), job.review_threshold):
            reasons.append(
                f"output rows changed from {prev_count} to {len(result.rows)} "
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


def _cleanup_tmp_links(store: Store) -> None:
    if store.artifacts_dir.exists():
        for tmp in store.artifacts_dir.glob("current.tmp-*"):
            if tmp.is_symlink():
                tmp.unlink()


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
