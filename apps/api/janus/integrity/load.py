"""Loader: pipeline artifacts → evidence tables (evidence-integrity design §5, Req 8).

`python -m janus.integrity.load [--data-dir PATH] [--registry PATH] [--papers PATH]`

Reads the `current` artifact of every pipeline: the evidence source record of each becomes a
`dataset:<source>` record, the `retractions` rows become integrity states, and the curated paper
list adds `paper:` records. Everything is verified first and written in one transaction; a
failure leaves the stored state as it was. Evidence is never deleted. This module and the
validated `register_records` function are the only writers of the evidence tables.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from janus.db.pool import Database
from janus.integrity.model import (
    NOT_YET_CHECKED,
    STATUS_NAMES,
    EvidenceRecord,
    IntegrityState,
    Notice,
    SourceInfo,
    Status,
)
from janus.integrity.records import (
    RecordError,
    record_from_evidence_source,
    records_from_papers,
    validate_records,
)
from janus.integrity.registry import read_sources
from janus.integrity.status import (
    Incoming,
    InvalidIncomingError,
    incoming_from_row,
    merge_status,
)
from janus.observability.logging import LogEvent, configure_logging, log_event
from janus.resolution import canonical
from janus.resolution.atc import DATA_DIR
from janus.resolution.load import LoadError, read_rows
from janus.settings import Settings

REGISTRY_FILE = DATA_DIR.parent / "pipelines" / "sources.toml"
PAPERS_FILE = DATA_DIR / "evidence_papers.csv"
RETRACTIONS = "retractions"
type Hook = Callable[[str], None]


@dataclass(frozen=True)
class LoadInputs:
    records: tuple[EvidenceRecord, ...]
    sources: Mapping[str, SourceInfo]
    incoming: Mapping[str, Incoming]  # doi -> row of the current retractions artifact
    check_run_id: str | None


@dataclass(frozen=True)
class LoadResult:
    records: int
    doi_records: int
    changes: int
    by_status: Mapping[str, int]
    not_yet_checked: int
    unmatched_rows: int


def _read_papers(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        expected = ["key", "doi", "source_id", "title", "verified_on", "note"]
        if reader.fieldnames != expected:
            raise LoadError("evidence_papers.csv: header must be " + ",".join(expected))
        return [{k: (v or "") for k, v in row.items()} for row in reader]


def _read_current(data_dir: Path, pipeline: str) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    run = data_dir / "artifacts" / pipeline / "current"
    try:
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
        evidence = json.loads((run / "evidence_source.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LoadError(f"{pipeline}: current artifact cannot be read") from exc
    outcome = manifest.get("outcome")
    if outcome == "needs_review" and not (run / "promotion.json").exists():
        raise LoadError(f"{pipeline}: needs_review run was not promoted")
    if outcome not in ("succeeded", "needs_review"):
        raise LoadError(f"{pipeline}: run did not succeed")
    if manifest.get("run_id") != evidence.get("run_id"):
        raise LoadError(f"{pipeline}: manifest and evidence record name different runs")
    return manifest, evidence


def gather(
    data_dir: Path, registry: Path = REGISTRY_FILE, papers: Path = PAPERS_FILE
) -> LoadInputs:
    """Read and verify every input. Raises `LoadError` or `RecordError`; touches no database."""
    try:
        sources = read_sources(registry)
    except (OSError, ValueError) as exc:
        raise LoadError("source registry (pipelines/sources.toml) cannot be read") from exc
    artifacts = data_dir / "artifacts"
    pipelines = (
        sorted(p.name for p in artifacts.iterdir() if (p / "current").exists())
        if artifacts.is_dir()
        else []
    )
    records: list[EvidenceRecord] = []
    incoming: dict[str, Incoming] = {}
    check_run: str | None = None
    for pipeline in pipelines:
        manifest, evidence = _read_current(data_dir, pipeline)
        records.append(record_from_evidence_source(evidence, manifest, sources))
        if pipeline == RETRACTIONS:
            rows = read_rows(data_dir / "artifacts" / pipeline / "current" / "rows.parquet")
            digest = canonical.content_hash(rows, str(manifest["schema_version"]))
            if digest != manifest.get("content_sha256"):
                raise LoadError("retractions: rows do not match the manifest content hash")
            check_run = str(manifest["run_id"])
            for row in rows:
                try:
                    inc = incoming_from_row(row)
                except InvalidIncomingError as exc:
                    raise LoadError(f"retractions: a row is invalid ({exc.code})") from exc
                incoming[inc.doi] = inc
    records.extend(records_from_papers(_read_papers(papers), sources))
    return LoadInputs(tuple(records), sources, incoming, check_run)


def _state_from_row(row: Sequence[Any], notices: Sequence[Notice]) -> IntegrityState:
    return IntegrityState(
        Status(str(row[0])), Status(str(row[1])), row[2], row[3], row[4], tuple(notices)
    )


def _known_basis(conn: psycopg.Connection) -> dict[str, tuple[str, ...]]:
    known: dict[str, list[str]] = {
        str(r[0]): [] for r in conn.execute("SELECT id FROM evidence").fetchall()
    }
    for ev, b in conn.execute("SELECT evidence_id, basis_id FROM evidence_basis").fetchall():
        known[str(ev)].append(str(b))
    return {k: tuple(sorted(v)) for k, v in known.items()}


def _db_sources(conn: psycopg.Connection) -> dict[str, SourceInfo]:
    return {
        str(r[0]): SourceInfo(str(r[0]), str(r[1]), str(r[2]), r[3])
        for r in conn.execute(
            "SELECT source_id, name, storage, cadence_days FROM evidence_source"
        ).fetchall()
    }


def _upsert_sources(conn: psycopg.Connection, sources: Mapping[str, SourceInfo]) -> None:
    for s in sorted(sources.values(), key=lambda x: x.source_id):
        conn.execute(
            "INSERT INTO evidence_source (source_id, name, storage, cadence_days) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (source_id) DO UPDATE SET "
            "name = EXCLUDED.name, storage = EXCLUDED.storage, "
            "cadence_days = EXCLUDED.cadence_days",
            (s.source_id, s.name, s.storage, s.cadence_days),
        )


def _upsert_records(
    conn: psycopg.Connection, records: Sequence[EvidenceRecord], hook: Hook | None
) -> None:
    for r in records:
        conn.execute(
            "INSERT INTO evidence (id, kind, source_id, source_url, license, region, "
            "snapshot_date, snapshot_is_retrieval_time, doi, locator, title) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET kind = EXCLUDED.kind, source_id = EXCLUDED.source_id, "
            "source_url = EXCLUDED.source_url, license = EXCLUDED.license, "
            "region = EXCLUDED.region, snapshot_date = EXCLUDED.snapshot_date, "
            "snapshot_is_retrieval_time = EXCLUDED.snapshot_is_retrieval_time, "
            "doi = EXCLUDED.doi, locator = EXCLUDED.locator, title = EXCLUDED.title",
            (
                r.id,
                r.kind,
                r.source_id,
                r.source_url,
                r.license,
                r.region,
                r.snapshot_date,
                r.snapshot_is_retrieval_time,
                r.doi,
                r.locator,
                r.title,
            ),
        )
    if hook:
        hook("records")
    ids = [r.id for r in records]
    conn.execute("DELETE FROM evidence_basis WHERE evidence_id = ANY(%s)", (ids,))
    for r in records:
        for b in sorted(set(r.basis)):
            conn.execute(
                "INSERT INTO evidence_basis (evidence_id, basis_id) VALUES (%s, %s)", (r.id, b)
            )
    if hook:
        hook("basis")


def _write_state(conn: psycopg.Connection, evidence_id: str, s: IntegrityState) -> None:
    conn.execute(
        "INSERT INTO evidence_integrity (evidence_id, status, check_status, reason, checked_at, "
        "check_run_id) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (evidence_id) DO UPDATE SET "
        "status = EXCLUDED.status, check_status = EXCLUDED.check_status, "
        "reason = EXCLUDED.reason, checked_at = EXCLUDED.checked_at, "
        "check_run_id = EXCLUDED.check_run_id",
        (evidence_id, s.status.value, s.check_status.value, s.reason, s.checked_at, s.run_id),
    )
    conn.execute("DELETE FROM evidence_notice WHERE evidence_id = %s", (evidence_id,))
    for pos, n in enumerate(s.notices):
        conn.execute(
            "INSERT INTO evidence_notice (evidence_id, position, type, source, notice_doi, "
            "notice_date) VALUES (%s, %s, %s, %s, %s, %s)",
            (evidence_id, pos, n.type, n.source, n.notice_doi, n.date),
        )


def _stored_states(conn: psycopg.Connection) -> dict[str, IntegrityState]:
    notices: dict[str, list[Notice]] = {}
    for r in conn.execute(
        "SELECT evidence_id, type, source, notice_doi, notice_date FROM evidence_notice "
        "ORDER BY evidence_id, position"
    ).fetchall():
        notices.setdefault(str(r[0]), []).append(Notice(str(r[1]), r[2], r[3], r[4]))
    out: dict[str, IntegrityState] = {}
    for r in conn.execute(
        "SELECT evidence_id, status, check_status, reason, checked_at, check_run_id "
        "FROM evidence_integrity"
    ).fetchall():
        out[str(r[0])] = _state_from_row(r[1:], notices.get(str(r[0]), ()))
    return out


def _merge_all(
    conn: psycopg.Connection,
    incoming: Mapping[str, Incoming],
    check_run_id: str | None,
    today: dt.date,
    hook: Hook | None,
) -> tuple[int, int]:
    """Merge the incoming rows into the stored states; returns (DOI records, changes)."""
    stored = _stored_states(conn)
    doi_records = conn.execute(
        "SELECT id, doi FROM evidence WHERE doi IS NOT NULL ORDER BY id"
    ).fetchall()
    changes = 0
    for rid, doi in doi_records:
        prev = stored.get(str(rid))
        new = merge_status(prev, incoming.get(str(doi)), check_run_id)
        if prev is not None and new == prev:
            continue
        _write_state(conn, str(rid), new)
        if prev is None or prev.status != new.status:
            conn.execute(
                "INSERT INTO evidence_status_change (evidence_id, from_status, to_status, "
                "observed_on, run_id) VALUES (%s, %s, %s, %s, %s)",
                (
                    str(rid),
                    None if prev is None else prev.status.value,
                    new.status.value,
                    today,
                    new.run_id,
                ),
            )
            changes += 1
    if hook:
        hook("integrity")
    return len(doi_records), changes


def load(
    db: Database, inputs: LoadInputs, today: dt.date, *, hook: Hook | None = None
) -> LoadResult:
    with db.write_tx() as conn:
        conn.execute("LOCK TABLE evidence_integrity IN SHARE ROW EXCLUSIVE MODE")
        validate_records(inputs.records, _known_basis(conn), inputs.sources)
        _upsert_sources(conn, inputs.sources)
        if hook:
            hook("sources")
        _upsert_records(conn, inputs.records, hook)
        doi_records, changes = _merge_all(conn, inputs.incoming, inputs.check_run_id, today, hook)
        total = int(conn.execute("SELECT count(*) FROM evidence").fetchone()[0])  # type: ignore[index]
        stored = _stored_states(conn)
        dois = {
            str(r[0])
            for r in conn.execute("SELECT doi FROM evidence WHERE doi IS NOT NULL").fetchall()
        }
    counts: dict[str, int] = {s: 0 for s in STATUS_NAMES}
    for s in stored.values():
        counts[s.status.value] += 1
    return LoadResult(
        records=total,
        doi_records=doi_records,
        changes=changes,
        by_status=counts,
        not_yet_checked=sum(1 for s in stored.values() if s.reason == NOT_YET_CHECKED),
        unmatched_rows=sum(1 for d in inputs.incoming if d not in dois),
    )


def register_records(
    conn: psycopg.Connection,
    records: Sequence[EvidenceRecord],
    today: dt.date,
    *,
    hook: Hook | None = None,
) -> int:
    """For other specs' loaders: validate and store records inside the caller's transaction.

    DOI-bearing records without a state become `unknown / not_yet_checked` (a first sighting).
    Sources must exist already (run the integrity loader once first). Returns the number of
    first-sighting changes.
    """
    validate_records(records, _known_basis(conn), _db_sources(conn))
    _upsert_records(conn, records, hook)
    _, changes = _merge_all(conn, {}, None, today, hook)
    return changes


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m janus.integrity.load")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--registry", type=Path, default=REGISTRY_FILE)
    parser.add_argument("--papers", type=Path, default=PAPERS_FILE)
    args = parser.parse_args(argv)
    configure_logging()
    settings = Settings.from_env()
    if not settings.database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    data_dir = args.data_dir or settings.data_dir
    if data_dir is None:
        print("set --data-dir or JANUS_DATA_DIR", file=sys.stderr)
        return 2
    db = Database(settings.database_url)
    db.open()
    try:
        inputs = gather(data_dir, args.registry, args.papers)
        today = dt.datetime.now(dt.UTC).date()
        result = load(db, inputs, today)
        log_event(LogEvent.integrity_load, count=result.records)
        by = ", ".join(f"{k} {v}" for k, v in result.by_status.items() if v)
        print(
            f"loaded {result.records} evidence records "
            f"({result.doi_records} with a DOI: {by or 'none'}); "
            f"{result.changes} status changes; {result.not_yet_checked} not yet checked; "
            f"{result.unmatched_rows} check rows without a record"
        )
        return 0
    except (LoadError, RecordError) as exc:
        print(f"load refused: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
