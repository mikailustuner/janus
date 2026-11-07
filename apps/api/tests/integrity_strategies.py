"""Hypothesis strategies and reference implementations for evidence integrity
(evidence-integrity design §7). Synthetic data only.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from hypothesis import strategies as st

from janus.integrity.model import (
    KINDS,
    EvidenceRecord,
    IntegritySnapshot,
    IntegrityState,
    Notice,
    SourceInfo,
    Status,
)

TODAY = dt.date(2026, 11, 7)

SOURCES: dict[str, SourceInfo] = {
    "s_weekly": SourceInfo("s_weekly", "Weekly source", "cache", 7),
    "s_yearly": SourceInfo("s_yearly", "Yearly source", "commit", 365),
    "s_cited": SourceInfo("s_cited", "Cited source", "cited_only", None),
    "crossref": SourceInfo("crossref", "Crossref", "cache", 7),
}
SOURCE_IDS = sorted(SOURCES)

NOTICE_TYPES = [
    "retraction",
    "correction",
    "expression_of_concern",
    "erratum",
    "withdrawal",
    "new_version",
]
REASONS = ["check_failed", "not_found", "unreadable_response", "http_503", "http_429"]
DOI_SUFFIX = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789.-_", min_size=1, max_size=12)


def dois() -> st.SearchStrategy[str]:
    def make(n: int, s: str) -> str:
        return f"10.{n}/{s}"

    return st.builds(make, st.integers(1000, 99999999), DOI_SUFFIX)


def dates(
    lo: dt.date = dt.date(2024, 1, 1), hi: dt.date = dt.date(2027, 6, 1)
) -> st.SearchStrategy[dt.date]:
    return st.dates(lo, hi)


def notices() -> st.SearchStrategy[Notice]:
    return st.builds(
        Notice,
        st.sampled_from(NOTICE_TYPES),
        st.sampled_from(["publisher", "retraction-watch", None]),
        st.one_of(st.none(), dois()),
        st.one_of(st.none(), dates()),
    )


def states_for(status: Status) -> st.SearchStrategy[IntegrityState]:
    run = st.sampled_from(["20261107T164018Z-aaaaaaaa-0001", None])
    if status == Status.UNKNOWN:
        return st.builds(
            IntegrityState,
            st.just(Status.UNKNOWN),
            st.just(Status.UNKNOWN),
            st.sampled_from([*REASONS, "not_yet_checked"]),
            st.one_of(st.none(), dates()),
            run,
            st.just(()),
        )
    if status == Status.OK:
        return st.builds(
            IntegrityState,
            st.just(Status.OK),
            st.just(Status.OK),
            st.none(),
            dates(),
            run,
            st.just(()),
        )
    return st.builds(
        IntegrityState,
        st.just(status),
        st.just(status),
        st.none(),
        dates(),
        run,
        st.lists(notices(), min_size=1, max_size=3).map(tuple),
    )


def any_state() -> st.SearchStrategy[IntegrityState]:
    return st.sampled_from(list(Status)).flatmap(states_for)


@st.composite
def snapshots(
    draw: st.DrawFn,
    max_records: int = 9,
    states_missing: bool = True,
    statuses: tuple[Status, ...] | None = None,
) -> IntegritySnapshot:
    """A random acyclic evidence graph with a state for (most) DOI-bearing records."""
    n = draw(st.integers(1, max_records))
    ids: list[str] = []
    records: dict[str, EvidenceRecord] = {}
    for i in range(n):
        has_basis = bool(ids) and draw(st.booleans())
        basis: tuple[str, ...] = ()
        if has_basis:
            basis = tuple(draw(st.lists(st.sampled_from(ids), min_size=1, max_size=3, unique=True)))
        has_doi = draw(st.booleans()) if not (has_basis and draw(st.booleans())) else False
        kind = draw(st.sampled_from([k for k in KINDS if k != "rule" or basis]))
        source_id = draw(st.sampled_from(SOURCE_IDS))
        rid = f"{kind}:{source_id}:k{i}"
        records[rid] = EvidenceRecord(
            id=rid,
            kind=kind,
            source_id=source_id,
            source_url=f"https://example.org/{i}",
            license="CC0 1.0",
            region=draw(st.sampled_from([None, "TR", "EU", "US"])),
            snapshot_date=draw(dates()),
            snapshot_is_retrieval_time=draw(st.booleans()),
            doi=draw(dois()) if has_doi else None,
            title=f"Title {i}",
            basis=basis,
        )
        ids.append(rid)
    states: dict[str, IntegrityState] = {}
    for rid, rec in records.items():
        if rec.doi is None:
            continue
        if states_missing and draw(st.integers(0, 5)) == 0:
            continue
        status = draw(st.sampled_from(list(statuses or tuple(Status))))
        states[rid] = draw(states_for(status))
    return IntegritySnapshot(records, states, dict(SOURCES))


@st.composite
def snapshot_and_ids(draw: st.DrawFn, **kwargs: Any) -> tuple[IntegritySnapshot, list[str]]:
    snap = draw(snapshots(**kwargs))
    pool = [*snap.records, "paper:s_cited:unregistered", "rule:s_weekly:nope"]
    ids = draw(st.lists(st.sampled_from(pool), min_size=1, max_size=6))
    return snap, ids


def with_status(snap: IntegritySnapshot, rid: str, state: IntegrityState) -> IntegritySnapshot:
    states = dict(snap.states)
    states[rid] = state
    return IntegritySnapshot(snap.records, states, snap.sources)


def as_cyclic(snap: IntegritySnapshot, extra: list[tuple[int, int]]) -> IntegritySnapshot:
    """Add basis edges (possibly backwards or to self) to a snapshot."""
    ids = list(snap.records)
    recs = dict(snap.records)
    for a, b in extra:
        x, y = ids[a % len(ids)], ids[b % len(ids)]
        r = recs[x]
        if y not in r.basis:
            recs[x] = replace(r, basis=(*r.basis, y))
    return IntegritySnapshot(recs, snap.states, snap.sources)


# --- reference implementations (written differently from the code under test) -------------------


def ref_citable(snap: IntegritySnapshot, rid: str) -> bool:
    """Path-based reference: a record is citable iff it is a base case, or a path of DOI-less
    records with basis leads to a base case."""
    rec = snap.records.get(rid)
    if rec is None:
        return False

    def base(r: EvidenceRecord) -> bool:
        if r.doi is not None:
            return (
                snap.states.get(r.id, None) is None or snap.states[r.id].status != Status.RETRACTED
            )
        return not r.basis

    seen: set[str] = set()
    stack = [rid]
    while stack:
        cur = snap.records[stack.pop()]
        if cur.id in seen:
            continue
        seen.add(cur.id)
        if base(cur):
            return True
        if cur.doi is not None:
            continue  # a DOI-bearing record is judged by its own status only
        stack.extend(b for b in cur.basis if b in snap.records)
    return False


def ref_roots(snap: IntegritySnapshot, rid: str) -> set[str]:
    out: set[str] = set()
    seen: set[str] = set()
    stack = [rid]
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in snap.records:
            continue
        seen.add(cur)
        r = snap.records[cur]
        if r.doi is not None or not r.basis:
            out.add(cur)
        else:
            stack.extend(r.basis)
    return out


# --- incoming rows ------------------------------------------------------------------------------


def row_for(state: IntegrityState, doi: str = "10.1000/x") -> Mapping[str, Any]:
    return {
        "doi": doi,
        "check_status": state.check_status.value,
        "effective_status": state.status.value,
        "last_completed_status": None,
        "reason": state.reason,
        "notices": [
            {
                "type": n.type,
                "source": n.source,
                "notice_doi": n.notice_doi,
                "date": n.date.isoformat() if n.date else None,
            }
            for n in state.notices
        ],
        "checked_at": f"{(state.checked_at or TODAY).isoformat()}T10:00:00+00:00",
    }


def valid_rows() -> st.SearchStrategy[Mapping[str, Any]]:
    """A valid `retractions` row: completed checks, or a failed check (sticky or not)."""
    completed = any_state().filter(lambda s: s.status != Status.UNKNOWN).map(row_for)
    failed = st.tuples(
        st.sampled_from(REASONS), st.sampled_from([Status.UNKNOWN, Status.RETRACTED])
    ).map(
        lambda t: {
            **row_for(IntegrityState(Status.UNKNOWN, Status.UNKNOWN, t[0], TODAY, None, ())),
            "effective_status": t[1].value,
        }
    )
    return st.one_of(completed, failed)
