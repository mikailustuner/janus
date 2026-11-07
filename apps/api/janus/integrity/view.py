"""Item view of one evidence record for the evidence view and the note (design §3.4, §4.6). Pure.

Fixed codes and data only: no sentences. Item fields are copied from the stored state and never
remapped, so an `unknown` status is never shown as `ok`.
"""

from __future__ import annotations

import datetime as dt
from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict

from janus.integrity.citability import Verdict, roots, verdict_map
from janus.integrity.freshness import age_days, check_is_stale, freshness
from janus.integrity.line import crossref_cadence
from janus.integrity.model import (
    EvidenceRecord,
    IntegritySnapshot,
    IntegrityState,
    Notice,
    Status,
)

StatusCode = Literal["ok", "corrected", "expression_of_concern", "retracted", "unknown"]
ItemCode = Literal[
    "corrected_notice",
    "expression_of_concern_notice",
    "integrity_unknown",
    "source_may_be_outdated",
    "integrity_check_may_be_out_of_date",
    "excluded_retracted",
    "not_registered",
]
ITEM_CODE_ORDER: tuple[ItemCode, ...] = (
    "excluded_retracted",
    "not_registered",
    "expression_of_concern_notice",
    "corrected_notice",
    "integrity_unknown",
    "source_may_be_outdated",
    "integrity_check_may_be_out_of_date",
)


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NoticeView(_Out):
    type: str
    source: str | None
    date: dt.date | None
    notice_doi: str | None
    notice_url: str | None


class IntegrityView(_Out):
    status: StatusCode
    check_status: StatusCode
    reason: str | None
    checked_at: dt.date | None
    check_age_days: int | None
    check_stale: bool
    notices: list[NoticeView]


class FreshnessView(_Out):
    state: Literal["current", "stale", "not_applicable"]
    age_days: int
    limit_days: int | None


class SourceView(_Out):
    source_id: str
    name: str | None
    source_url: str
    license: str
    region: str | None
    snapshot_date: dt.date
    snapshot_is_retrieval_time: bool


class RootView(_Out):
    id: str
    title: str | None
    doi: str | None
    citable: bool
    integrity: IntegrityView | None
    freshness: FreshnessView | None


class EvidenceItem(_Out):
    id: str
    registered: bool
    kind: str | None = None
    title: str | None = None
    doi: str | None = None
    locator: str | None = None
    source: SourceView | None = None
    freshness: FreshnessView | None = None
    doi_check: Literal["checked", "not_applicable"] = "not_applicable"
    integrity: IntegrityView | None = None
    roots: list[RootView] = []
    citable: bool
    exclusion_reason: Literal["retracted", "not_registered", "no_citable_basis"] | None = None
    codes: list[ItemCode] = []


def notice_view(n: Notice) -> NoticeView:
    return NoticeView(
        type=n.type,
        source=n.source,
        date=n.date,
        notice_doi=n.notice_doi,
        notice_url=None
        if n.notice_doi is None
        else "https://doi.org/" + quote(n.notice_doi, safe="/"),
    )


def integrity_view(
    state: IntegrityState, today: dt.date, crossref_cadence_days: int | None
) -> IntegrityView:
    return IntegrityView(
        status=state.status.value,
        check_status=state.check_status.value,
        reason=state.reason,
        checked_at=state.checked_at,
        check_age_days=None if state.checked_at is None else age_days(state.checked_at, today),
        check_stale=check_is_stale(state.checked_at, today, crossref_cadence_days),
        notices=[notice_view(n) for n in state.notices],
    )


def _freshness(snapshot: IntegritySnapshot, rec: EvidenceRecord, today: dt.date) -> FreshnessView:
    f = freshness(rec.snapshot_date, today, snapshot.cadence_of(rec.id))
    return FreshnessView(state=f.state, age_days=f.age_days, limit_days=f.limit_days)


def build_item(
    snapshot: IntegritySnapshot,
    evidence_id: str,
    today: dt.date,
    verdicts: dict[str, Verdict] | None = None,
) -> EvidenceItem:
    vm = verdicts if verdicts is not None else verdict_map(snapshot)
    rec = snapshot.records.get(evidence_id)
    if rec is None:
        return EvidenceItem(
            id=evidence_id,
            registered=False,
            citable=False,
            exclusion_reason="not_registered",
            codes=["not_registered"],
        )
    v = vm[evidence_id]
    cadence = crossref_cadence(snapshot)
    own = (
        integrity_view(snapshot.state_of(evidence_id), today, cadence)
        if rec.doi is not None
        else None
    )
    root_views: list[RootView] = []
    if rec.doi is None:
        for r in roots(snapshot, evidence_id):
            if r == evidence_id:
                continue
            rr = snapshot.records[r]
            root_views.append(
                RootView(
                    id=r,
                    title=rr.title,
                    doi=rr.doi,
                    citable=vm[r].citable,
                    integrity=(
                        integrity_view(snapshot.state_of(r), today, cadence)
                        if rr.doi is not None
                        else None
                    ),
                    freshness=_freshness(snapshot, rr, today),
                )
            )
    own_fresh = _freshness(snapshot, rec, today)
    codes: set[ItemCode] = set()
    considered: list[IntegrityView] = [] if own is None else [own]
    stale_source = own_fresh.state == "stale"
    if v.citable:
        for rv in root_views:
            if rv.citable:
                if rv.integrity is not None:
                    considered.append(rv.integrity)
                stale_source = stale_source or (
                    rv.freshness is not None and rv.freshness.state == "stale"
                )
    for iv in considered:
        if iv.status == Status.CORRECTED.value:
            codes.add("corrected_notice")
        elif iv.status == Status.EXPRESSION_OF_CONCERN.value:
            codes.add("expression_of_concern_notice")
        elif iv.status == Status.UNKNOWN.value:
            codes.add("integrity_unknown")
        if iv.check_stale:
            codes.add("integrity_check_may_be_out_of_date")
    if stale_source:
        codes.add("source_may_be_outdated")
    if v.reason == "retracted":
        codes.add("excluded_retracted")
    return EvidenceItem(
        id=rec.id,
        registered=True,
        kind=rec.kind,
        title=rec.title,
        doi=rec.doi,
        locator=rec.locator,
        source=SourceView(
            source_id=rec.source_id,
            name=(
                snapshot.sources[rec.source_id].name if rec.source_id in snapshot.sources else None
            ),
            source_url=rec.source_url,
            license=rec.license,
            region=rec.region,
            snapshot_date=rec.snapshot_date,
            snapshot_is_retrieval_time=rec.snapshot_is_retrieval_time,
        ),
        freshness=own_fresh,
        doi_check="checked" if rec.doi is not None else "not_applicable",
        integrity=own,
        roots=root_views,
        citable=v.citable,
        exclusion_reason=v.reason,
        codes=[c for c in ITEM_CODE_ORDER if c in codes],
    )
