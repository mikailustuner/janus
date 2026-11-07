"""Rule gate for the cascade engine (evidence-integrity design §4.4, Req 6). Pure, no I/O.

The gate depends only on its arguments. It stores nothing, so a rule comes back as soon as a
snapshot makes one of its sources citable again.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from janus.integrity.citability import Verdict, roots, verdict_map
from janus.integrity.model import ExclusionReason, IntegritySnapshot, Notice, Status

GateReason = Literal["no_source", "all_sources_retracted", "no_citable_source"]


@dataclass(frozen=True)
class Removed:
    id: str
    reason: ExclusionReason
    notices: tuple[Notice, ...]


@dataclass(frozen=True)
class RuleGate:
    enabled: bool
    reason: GateReason | None
    usable: tuple[str, ...]
    removed: tuple[Removed, ...]


def _retraction_notices(snapshot: IntegritySnapshot, evidence_id: str) -> tuple[Notice, ...]:
    out: list[Notice] = []
    for r in roots(snapshot, evidence_id):
        rec = snapshot.records[r]
        if rec.doi is not None:
            st = snapshot.state_of(r)
            if st.status == Status.RETRACTED:
                for n in st.notices:
                    if n not in out:
                        out.append(n)
    return tuple(out)


def rule_gate(
    sources: Sequence[str],
    snapshot: IntegritySnapshot,
    verdicts: dict[str, Verdict] | None = None,
) -> RuleGate:
    vm = verdicts if verdicts is not None else verdict_map(snapshot)
    distinct = sorted(set(sources))
    if not distinct:
        return RuleGate(False, "no_source", (), ())
    usable: list[str] = []
    removed: list[Removed] = []
    for s in distinct:
        v = vm.get(s, Verdict(False, "not_registered"))
        if v.citable:
            usable.append(s)
        else:
            reason: ExclusionReason = v.reason or "not_registered"
            removed.append(Removed(s, reason, _retraction_notices(snapshot, s)))
    if usable:
        return RuleGate(True, None, tuple(usable), tuple(removed))
    all_retracted = all(r.reason == "retracted" for r in removed)
    return RuleGate(
        False,
        "all_sources_retracted" if all_retracted else "no_citable_source",
        (),
        tuple(removed),
    )
