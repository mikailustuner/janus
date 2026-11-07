"""Evidence routes' logic (evidence-integrity design §6). Read-only; the clock is an argument."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

import psycopg

from janus.integrity import repository
from janus.integrity.citability import cite, verdict_map
from janus.integrity.line import build_line
from janus.integrity.schemas import (
    ChangesResult,
    ChangeView,
    EvidenceResolution,
    Excluded,
    StatusCountsAll,
)
from janus.integrity.view import StatusCode, build_item

_STATUS_CODES: tuple[StatusCode, ...] = (
    "ok",
    "corrected",
    "expression_of_concern",
    "retracted",
    "unknown",
)


class IntegrityUnavailableError(RuntimeError):
    """No evidence has been loaded: nothing may be treated as citable (fail closed)."""


def _code(value: str) -> StatusCode:
    for a in _STATUS_CODES:
        if a == value:
            return a
    raise ValueError("unknown status")


def resolve_evidence(
    conn: psycopg.Connection, ids: Sequence[str], today: dt.date
) -> EvidenceResolution:
    snapshot = repository.load_snapshot(conn)
    if not snapshot.records:
        raise IntegrityUnavailableError("evidence not loaded")
    distinct = sorted(set(ids))
    vm = verdict_map(snapshot)
    cited = cite(snapshot, distinct)
    return EvidenceResolution(
        integrity_version=snapshot.version(),
        as_of=today,
        items=[build_item(snapshot, i, today, vm) for i in distinct],
        citable_ids=sorted(cited.kept),
        excluded=[Excluded(id=i, reason=r) for i, r in sorted(cited.removed)],
        line=build_line(snapshot, distinct, today),
    )


def list_changes(
    conn: psycopg.Connection, since: dt.date | None, limit: int, today: dt.date
) -> ChangesResult:
    snapshot = repository.load_snapshot(conn)
    if not snapshot.records:
        raise IntegrityUnavailableError("evidence not loaded")
    effective = since if since is not None else repository.latest_observed(conn)
    rows = [] if effective is None else repository.changes_since(conn, effective, limit)
    counts = repository.status_counts(conn)
    return ChangesResult(
        integrity_version=snapshot.version(),
        as_of=today,
        since=effective,
        observed_dates=repository.observed_dates(conn),
        status_counts=StatusCountsAll(**counts),
        changes=[
            ChangeView(
                evidence_id=r.evidence_id,
                title=r.title,
                doi=r.doi,
                from_status=_code(r.from_status),
                to_status=_code(r.to_status),
                observed_on=r.observed_on,
                run_id=r.run_id,
            )
            for r in rows
        ],
    )
