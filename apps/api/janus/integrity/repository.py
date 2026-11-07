"""Read-only queries over the evidence tables (evidence-integrity design §3.3).

Every function takes a connection inside `read_only_tx()` (REPEATABLE READ, READ ONLY), so one
request sees one consistent snapshot.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import psycopg

from janus.integrity.model import (
    STATUS_NAMES,
    EvidenceRecord,
    IntegritySnapshot,
    IntegrityState,
    Notice,
    SourceInfo,
    Status,
)

MAX_RECORDS = 5000


class TooManyRecordsError(RuntimeError):
    """The evidence table is larger than the snapshot is built for (design DP18)."""


def is_loaded(conn: psycopg.Connection) -> bool:
    return bool(conn.execute("SELECT EXISTS (SELECT 1 FROM evidence)").fetchone()[0])  # type: ignore[index]


def load_snapshot(conn: psycopg.Connection) -> IntegritySnapshot:
    n = int(conn.execute("SELECT count(*) FROM evidence").fetchone()[0])  # type: ignore[index]
    if n > MAX_RECORDS:
        raise TooManyRecordsError("evidence table exceeds the snapshot limit")
    sources = {
        str(r[0]): SourceInfo(str(r[0]), str(r[1]), str(r[2]), r[3])
        for r in conn.execute(
            "SELECT source_id, name, storage, cadence_days FROM evidence_source ORDER BY source_id"
        ).fetchall()
    }
    basis: dict[str, list[str]] = {}
    for ev, b in conn.execute(
        "SELECT evidence_id, basis_id FROM evidence_basis ORDER BY evidence_id, basis_id"
    ).fetchall():
        basis.setdefault(str(ev), []).append(str(b))
    records: dict[str, EvidenceRecord] = {}
    for r in conn.execute(
        "SELECT id, kind, source_id, source_url, license, region, snapshot_date, "
        "snapshot_is_retrieval_time, doi, locator, title FROM evidence ORDER BY id"
    ).fetchall():
        records[str(r[0])] = EvidenceRecord(
            id=str(r[0]),
            kind=str(r[1]),
            source_id=str(r[2]),
            source_url=str(r[3]),
            license=str(r[4]),
            region=r[5],
            snapshot_date=r[6],
            snapshot_is_retrieval_time=bool(r[7]),
            doi=r[8],
            locator=r[9],
            title=r[10],
            basis=tuple(basis.get(str(r[0]), ())),
        )
    notices: dict[str, list[Notice]] = {}
    for r in conn.execute(
        "SELECT evidence_id, type, source, notice_doi, notice_date FROM evidence_notice "
        "ORDER BY evidence_id, position"
    ).fetchall():
        notices.setdefault(str(r[0]), []).append(Notice(str(r[1]), r[2], r[3], r[4]))
    states: dict[str, IntegrityState] = {}
    for r in conn.execute(
        "SELECT evidence_id, status, check_status, reason, checked_at, check_run_id "
        "FROM evidence_integrity ORDER BY evidence_id"
    ).fetchall():
        states[str(r[0])] = IntegrityState(
            Status(str(r[1])),
            Status(str(r[2])),
            r[3],
            r[4],
            r[5],
            tuple(notices.get(str(r[0]), ())),
        )
    return IntegritySnapshot(records, states, sources)


@dataclass(frozen=True)
class ChangeRow:
    evidence_id: str
    title: str | None
    doi: str | None
    from_status: str
    to_status: str
    observed_on: dt.date
    run_id: str | None


def latest_observed(conn: psycopg.Connection) -> dt.date | None:
    row = conn.execute(
        "SELECT max(observed_on) FROM evidence_status_change WHERE from_status IS NOT NULL"
    ).fetchone()
    return None if row is None else row[0]


def observed_dates(conn: psycopg.Connection, limit: int = 20) -> list[dt.date]:
    rows = conn.execute(
        "SELECT DISTINCT observed_on FROM evidence_status_change "
        "WHERE from_status IS NOT NULL ORDER BY observed_on DESC LIMIT %s",
        (limit,),
    ).fetchall()
    return [r[0] for r in rows]


def changes_since(conn: psycopg.Connection, since: dt.date, limit: int) -> list[ChangeRow]:
    rows = conn.execute(
        "SELECT c.evidence_id, e.title, e.doi, c.from_status, c.to_status, c.observed_on, c.run_id "
        "FROM evidence_status_change c JOIN evidence e ON e.id = c.evidence_id "
        "WHERE c.from_status IS NOT NULL AND c.observed_on >= %s "
        "ORDER BY c.observed_on DESC, c.evidence_id, c.to_status LIMIT %s",
        (since, limit),
    ).fetchall()
    return [ChangeRow(str(r[0]), r[1], r[2], str(r[3]), str(r[4]), r[5], r[6]) for r in rows]


def status_counts(conn: psycopg.Connection) -> dict[str, int]:
    counts: dict[str, int] = {s: 0 for s in STATUS_NAMES}
    for status, n in conn.execute(
        "SELECT status, count(*) FROM evidence_integrity GROUP BY status"
    ).fetchall():
        counts[str(status)] = int(n)
    return counts
