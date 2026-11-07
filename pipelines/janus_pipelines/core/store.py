"""Artifact store: staging, runs and the atomic `current` pointer (design §3.1, §4.2, Req 4.2).

Layout under the data directory:
    staging/<pipeline>/<run_id>/          written during a run
    artifacts/<pipeline>/runs/<run_id>/   rows.parquet, manifest.json, evidence_source.json
    artifacts/<pipeline>/current          symlink -> runs/<run_id>
    raw/<pipeline>/<run_id>/              downloaded bytes (cache-rule sources only)
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import polars as pl

from janus_pipelines.core.canonical import Row
from janus_pipelines.core.manifest import EvidenceSource, Manifest, Promotion, dump

ROWS = "rows.parquet"
MANIFEST = "manifest.json"
EVIDENCE = "evidence_source.json"
PROMOTION = "promotion.json"

# Fault-injection hook for tests: called with a step name before that step runs.
type FaultHook = Callable[[str], None]


def no_fault(_step: str) -> None:
    return None


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())


class Store:
    def __init__(self, data_dir: Path, pipeline: str, fault: FaultHook = no_fault) -> None:
        self.data_dir = data_dir
        self.pipeline = pipeline
        self.fault = fault

    # --- paths ---------------------------------------------------------------
    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts" / self.pipeline

    @property
    def runs_dir(self) -> Path:
        return self.artifacts_dir / "runs"

    @property
    def current_link(self) -> Path:
        return self.artifacts_dir / "current"

    def staging_dir(self, run_id: str) -> Path:
        return self.data_dir / "staging" / self.pipeline / run_id

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def raw_dir(self, run_id: str) -> Path:
        return self.data_dir / "raw" / self.pipeline / run_id

    def planned_paths(self, run_id: str) -> list[Path]:
        """Every path a run may write; checked by the licence guard before writing."""
        return [
            self.staging_dir(run_id) / ROWS,
            self.run_dir(run_id) / ROWS,
            self.current_link,
        ]

    # --- reading -------------------------------------------------------------
    def current_run_id(self) -> str | None:
        if not self.current_link.is_symlink():
            return None
        return Path(os.readlink(self.current_link)).name

    def read_manifest(self, run_id: str) -> Manifest:
        return Manifest.model_validate_json(
            (self.run_dir(run_id) / MANIFEST).read_text(encoding="utf-8")
        )

    def read_rows(self, run_id: str) -> list[dict[str, object]]:
        return pl.read_parquet(self.run_dir(run_id) / ROWS).to_dicts()

    def current_manifest(self) -> Manifest | None:
        run_id = self.current_run_id()
        return None if run_id is None else self.read_manifest(run_id)

    def current_evidence(self) -> EvidenceSource | None:
        run_id = self.current_run_id()
        if run_id is None:
            return None
        path = self.run_dir(run_id) / EVIDENCE
        if not path.exists():
            return None
        return EvidenceSource.model_validate_json(path.read_text(encoding="utf-8"))

    # --- writing -------------------------------------------------------------
    def stage(
        self,
        run_id: str,
        rows: Sequence[Row],
        polars_schema: Mapping[str, pl.DataType],
        manifest: Manifest,
        evidence: EvidenceSource | None,
    ) -> None:
        staging = self.staging_dir(run_id)
        staging.mkdir(parents=True, exist_ok=False)
        self.fault("write_rows")
        df = pl.DataFrame(list(rows), schema=dict(polars_schema), orient="row")
        df.write_parquet(staging / ROWS)
        self.fault("write_manifest")
        _write_text(staging / MANIFEST, dump(manifest))
        if evidence is not None:
            _write_text(staging / EVIDENCE, dump(evidence))
        _fsync_dir(staging)

    def finish(self, run_id: str) -> None:
        """Move a staged run into runs/ (atomic rename on one filesystem)."""
        self.fault("finish")
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        os.replace(self.staging_dir(run_id), self.run_dir(run_id))
        _fsync_dir(self.runs_dir)

    def promote(self, run_id: str) -> None:
        """Point `current` at runs/<run_id> in one atomic step."""
        if not (self.run_dir(run_id) / MANIFEST).exists():
            raise FileNotFoundError(f"run {run_id} has no manifest")
        self.fault("promote_link")
        tmp = self.artifacts_dir / f"current.tmp-{run_id}"
        if tmp.is_symlink():
            tmp.unlink()
        os.symlink(Path("runs") / run_id, tmp)
        self.fault("promote_replace")
        os.replace(tmp, self.current_link)
        _fsync_dir(self.artifacts_dir)

    def write_failed_manifest(self, manifest: Manifest) -> None:
        """Record a failed run. Never touches `current` or another run's files."""
        target = self.run_dir(manifest.run_id)
        staging = self.staging_dir(manifest.run_id)
        if staging.exists():
            shutil.rmtree(staging)
        target.mkdir(parents=True, exist_ok=True)
        rows = target / ROWS
        if rows.exists():
            rows.unlink()
        evidence = target / EVIDENCE
        if evidence.exists():
            evidence.unlink()
        _write_text(target / MANIFEST, dump(manifest))

    def write_promotion(self, promotion: Promotion) -> None:
        _write_text(self.run_dir(promotion.run_id) / PROMOTION, dump(promotion))

    def write_raw(self, run_id: str, files: Mapping[str, bytes]) -> None:
        raw = self.raw_dir(run_id)
        raw.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            if "/" in name or name in ("", ".", ".."):
                raise ValueError(f"invalid raw file name {name!r}")
            (raw / name).write_bytes(data)
