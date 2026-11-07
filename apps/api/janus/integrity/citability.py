"""Citability (evidence-integrity design §4.2, Req 5). Pure.

A record is citable when it may back a patient-facing finding, a note sentence or a hypothesis
card. Only `retracted` removes a record (DP4); `corrected`, `expression_of_concern` and
`unknown` stay citable and travel with their notice or status.

The citable set is the least fixed point of: a record with a DOI is citable unless its status is
`retracted`; a record without DOI and without basis is citable; a record without DOI is citable
if a basis record is. This is order independent and ends on any graph; a basis cycle is
citable only when something outside the cycle supports it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from janus.integrity.model import ExclusionReason, IntegritySnapshot, Status


@dataclass(frozen=True)
class Verdict:
    citable: bool
    reason: ExclusionReason | None


def verdict_map(snapshot: IntegritySnapshot) -> dict[str, Verdict]:
    """Verdicts of every registered record."""
    recs = snapshot.records
    citable: set[str] = set()
    retracted: set[str] = set()
    pending: list[str] = []
    for rid, r in recs.items():
        if r.doi is not None:
            if snapshot.state_of(rid).status == Status.RETRACTED:
                retracted.add(rid)
            else:
                citable.add(rid)
        elif not r.basis:
            citable.add(rid)
        else:
            pending.append(rid)
    changed = True
    while changed:
        changed = False
        for rid in pending:
            if rid not in citable and any(b in citable for b in recs[rid].basis):
                citable.add(rid)
                changed = True
    out: dict[str, Verdict] = {}
    for rid in recs:
        if rid in citable:
            out[rid] = Verdict(True, None)
        elif rid in retracted:
            out[rid] = Verdict(False, "retracted")
        else:
            out[rid] = Verdict(False, "no_citable_basis")
    return out


def verdict(snapshot: IntegritySnapshot, evidence_id: str) -> Verdict:
    return verdict_map(snapshot).get(evidence_id, Verdict(False, "not_registered"))


def roots(snapshot: IntegritySnapshot, evidence_id: str) -> tuple[str, ...]:
    """The DOI-bearing records, or records without basis, that a record rests on (sorted)."""
    recs = snapshot.records
    if evidence_id not in recs:
        return ()
    found: set[str] = set()
    seen: set[str] = set()
    stack = [evidence_id]
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in recs:
            continue
        seen.add(cur)
        r = recs[cur]
        if r.doi is not None or not r.basis:
            found.add(cur)
        else:
            stack.extend(r.basis)
    return tuple(sorted(found))


def used_roots(
    snapshot: IntegritySnapshot,
    evidence_id: str,
    verdicts: dict[str, Verdict] | None = None,
) -> tuple[str, ...]:
    """The citable roots of a citable record; empty for a record that is not citable."""
    vm = verdicts if verdicts is not None else verdict_map(snapshot)
    if not vm.get(evidence_id, Verdict(False, "not_registered")).citable:
        return ()
    return tuple(r for r in roots(snapshot, evidence_id) if vm[r].citable)


@dataclass(frozen=True)
class Cited:
    kept: tuple[str, ...]
    removed: tuple[tuple[str, ExclusionReason], ...]


def cite(snapshot: IntegritySnapshot, ids: Iterable[str]) -> Cited:
    """Keep the citable ids (input order, no repeats); list the others with their reason."""
    vm = verdict_map(snapshot)
    kept: list[str] = []
    removed: list[tuple[str, ExclusionReason]] = []
    seen: set[str] = set()
    for i in ids:
        if i in seen:
            continue
        seen.add(i)
        v = vm.get(i, Verdict(False, "not_registered"))
        if v.citable:
            kept.append(i)
        else:
            removed.append((i, v.reason or "not_registered"))
    return Cited(tuple(kept), tuple(removed))


def keep_output(snapshot: IntegritySnapshot, ids: Sequence[str]) -> bool:
    """A finding, sentence or card stays only if at least one of its evidence ids is citable."""
    return bool(cite(snapshot, ids).kept)
