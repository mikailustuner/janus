"""Helpers for database-backed evidence-integrity tests: synthetic artifacts and dumps."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import duckdb
import psycopg

from janus.integrity.registry import read_sources
from janus.resolution.canonical import content_hash
from janus.resolution.load import read_rows

REPO = Path(__file__).resolve().parents[3]
REGISTRY = REPO / "pipelines" / "sources.toml"
SOURCES = read_sources(REGISTRY)

PIPC_DOI = "10.1007/s41999-025-01215-x"
NOTICE_DOI = "10.1007/s41999-025-01378-7"
CORRECTION = {
    "type": "correction",
    "source": "publisher",
    "notice_doi": NOTICE_DOI,
    "date": "2025-12-18",
}

# pipeline directory -> (source id, snapshot date, doi)
DATASETS: dict[str, tuple[str, str, str | None]] = {
    "pipc": ("pipc", "2025-07-31", PIPC_DOI),
    "titck": ("titck", "2026-11-06", None),
    "us_ndc": ("openfda_ndc", "2026-11-06", None),
    "wikidata_ingredients": ("wikidata", "2026-11-07T16:39:17.898888+00:00", None),
}

EVIDENCE_TABLES = (
    "evidence_source",
    "evidence",
    "evidence_basis",
    "evidence_integrity",
    "evidence_notice",
)


def retraction_row(
    doi: str,
    status: str,
    notices: Sequence[Mapping[str, Any]] = (),
    *,
    reason: str | None = None,
    effective: str | None = None,
    checked_at: str = "2026-11-07T16:40:18.333144+00:00",
) -> dict[str, Any]:
    return {
        "doi": doi,
        "check_status": status,
        "effective_status": effective or status,
        "last_completed_status": None if status == "unknown" else status,
        "reason": reason,
        "notices": [dict(n) for n in notices],
        "checked_at": checked_at,
    }


def _write_run(
    root: Path,
    pipeline: str,
    source_id: str,
    snapshot: str,
    doi: str | None,
    run: str,
    rows: Sequence[Mapping[str, Any]] | None,
    outcome: str,
    tamper: bool,
    promoted: bool,
) -> None:
    pdir = root / "artifacts" / pipeline
    rdir = pdir / "runs" / f"{run}-{pipeline}"
    rdir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "run_id": f"{run}-{pipeline}",
        "pipeline": pipeline,
        "source_id": source_id,
        "schema_version": f"{pipeline}-1",
        "snapshot_date": snapshot,
        "snapshot_date_is_retrieval_time": "T" in snapshot,
        "outcome": outcome,
        "content_sha256": "0" * 64,
    }
    if rows is not None:
        con = duckdb.connect()
        src = rdir / "rows.json"
        src.write_text(json.dumps(list(rows)), encoding="utf-8")
        target = rdir / "rows.parquet"
        con.execute(
            "COPY (SELECT * FROM read_json_auto(?, columns={doi: 'VARCHAR', "
            "check_status: 'VARCHAR', "
            "effective_status: 'VARCHAR', last_completed_status: 'VARCHAR', reason: 'VARCHAR', "
            "notices: 'STRUCT(type VARCHAR, source VARCHAR, notice_doi VARCHAR, date VARCHAR)[]', "
            "checked_at: 'VARCHAR'})) TO ? (FORMAT parquet)",
            [str(src), str(target)],
        )
        con.close()
        stored = read_rows(target)
        manifest["content_sha256"] = content_hash(stored, str(manifest["schema_version"]))
        if tamper:
            manifest["content_sha256"] = "f" * 64
    evidence = {
        "kind": "dataset",
        "source_id": source_id,
        "source_url": f"https://example.org/{source_id}",
        "license": SOURCES[source_id].license or "L",
        "region": SOURCES[source_id].region,
        "snapshot_date": snapshot,
        "run_id": manifest["run_id"],
        "doi": doi,
    }
    (rdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (rdir / "evidence_source.json").write_text(json.dumps(evidence), encoding="utf-8")
    if promoted:
        (rdir / "promotion.json").write_text("{}", encoding="utf-8")
    current = pdir / "current"
    if current.is_symlink() or current.exists():
        current.unlink()
    current.symlink_to(rdir)


def write_artifacts(
    root: Path,
    *,
    retractions: Sequence[Mapping[str, Any]] | None,
    datasets: Sequence[str] = tuple(DATASETS),
    run: str = "r1",
    snapshot_override: str | None = None,
    outcome: str = "succeeded",
    tamper: bool = False,
    promoted: bool = False,
) -> Path:
    """A data directory with current artifacts. `retractions=None` writes no retractions run."""
    for pipeline in datasets:
        sid, snap, doi = DATASETS[pipeline]
        _write_run(
            root,
            pipeline,
            sid,
            snapshot_override or snap,
            doi,
            run,
            None,
            "succeeded",
            False,
            False,
        )
    if retractions is not None:
        _write_run(
            root,
            "retractions",
            "crossref",
            "2026-11-07T16:40:18.333144+00:00",
            None,
            run,
            retractions,
            outcome,
            tamper,
            promoted,
        )
    return root


def reset(conn: psycopg.Connection) -> None:
    for table in (
        "evidence_status_change",
        "evidence_notice",
        "evidence_integrity",
        "evidence_basis",
        "evidence",
        "evidence_source",
    ):
        conn.execute(f"DELETE FROM {table}")  # noqa: S608 (fixed table names)


def dump(conn: psycopg.Connection) -> dict[str, list[tuple[Any, ...]]]:
    out: dict[str, list[tuple[Any, ...]]] = {}
    for table in EVIDENCE_TABLES:
        out[table] = sorted(
            (tuple(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()),  # noqa: S608
            key=repr,
        )
    out["changes"] = sorted(
        (
            tuple(r)
            for r in conn.execute(
                "SELECT evidence_id, from_status, to_status, observed_on, run_id "
                "FROM evidence_status_change"
            ).fetchall()
        ),
        key=repr,
    )
    return out
