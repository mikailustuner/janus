"""Integrity line for the doctor note (evidence-integrity design §4.6, Req 3.1). Pure.

The line describes sources only. It says nothing about a person's medicines.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from janus.integrity.citability import cite, used_roots, verdict_map
from janus.integrity.freshness import check_is_stale, freshness
from janus.integrity.model import ExclusionReason, IntegritySnapshot, Status


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StatusCounts(_Out):
    ok: int = 0
    corrected: int = 0
    expression_of_concern: int = 0
    unknown: int = 0


class StaleSource(_Out):
    source_id: str
    snapshot_date: dt.date
    age_days: int
    limit_days: int


class Excluded(_Out):
    id: str
    reason: Literal["retracted", "not_registered", "no_citable_basis"]


class IntegrityLine(_Out):
    sources_total: int
    checked_by_doi: int
    without_doi_check: int
    by_status: StatusCounts
    oldest_check: dt.date | None
    newest_check: dt.date | None
    stale_sources: list[StaleSource]
    integrity_check_stale: bool
    excluded: list[Excluded]
    no_retracted_used: bool


def crossref_cadence(snapshot: IntegritySnapshot) -> int | None:
    src = snapshot.sources.get("crossref")
    return None if src is None else src.cadence_days


def build_line(snapshot: IntegritySnapshot, ids: Iterable[str], today: dt.date) -> IntegrityLine:
    distinct = sorted(set(ids))
    vm = verdict_map(snapshot)
    cited = cite(snapshot, distinct)
    roots: set[str] = set()
    for i in cited.kept:
        roots.update(used_roots(snapshot, i, vm))
    doi_roots = sorted(r for r in roots if snapshot.records[r].doi is not None)
    counts = {"ok": 0, "corrected": 0, "expression_of_concern": 0, "unknown": 0}
    checks: list[dt.date] = []
    check_stale = False
    cadence = crossref_cadence(snapshot)
    for r in doi_roots:
        st = snapshot.state_of(r)
        if st.status != Status.RETRACTED:
            counts[st.status.value] += 1
        if st.checked_at is not None:
            checks.append(st.checked_at)
            check_stale = check_stale or check_is_stale(st.checked_at, today, cadence)
    stale: dict[str, StaleSource] = {}
    for r in sorted(roots):
        rec = snapshot.records[r]
        f = freshness(rec.snapshot_date, today, snapshot.cadence_of(r))
        if f.state == "stale" and f.limit_days is not None:
            cur = stale.get(rec.source_id)
            if cur is None or rec.snapshot_date < cur.snapshot_date:
                stale[rec.source_id] = StaleSource(
                    source_id=rec.source_id,
                    snapshot_date=rec.snapshot_date,
                    age_days=f.age_days,
                    limit_days=f.limit_days,
                )
    excluded_pairs: list[tuple[str, ExclusionReason]] = sorted(cited.removed)
    return IntegrityLine(
        sources_total=len(roots),
        checked_by_doi=len(doi_roots),
        without_doi_check=len(roots) - len(doi_roots),
        by_status=StatusCounts(**counts),
        oldest_check=min(checks) if checks else None,
        newest_check=max(checks) if checks else None,
        stale_sources=[stale[k] for k in sorted(stale)],
        integrity_check_stale=check_stale,
        excluded=[Excluded(id=i, reason=r) for i, r in excluded_pairs],
        no_retracted_used=all(snapshot.state_of(r).status != Status.RETRACTED for r in doi_roots),
    )
