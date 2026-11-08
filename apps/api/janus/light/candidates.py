"""Candidates per goal: merge the signals and rank them (design §6, Req 4.4; P1, P2, P7). Pure.

A candidate is (ingredient key, goal) with at least one signal; no other path creates one. The
patient-reported layer is added at request time and never enters the rank (DP5).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from janus.light.model import Candidate, InverseSignal, LabelSignal
from janus.light.ranking import sort_key, tied_ranks


def rank_goal(
    goal: str,
    labels: Iterable[LabelSignal],
    inverse: Iterable[InverseSignal],
) -> list[Candidate]:
    by_key_l = {s.key: s for s in labels if s.goal == goal}
    by_key_i = {s.key: s for s in inverse if s.goal == goal}
    keys = sorted(set(by_key_l) | set(by_key_i))
    entries = [(sort_key(by_key_l.get(k), by_key_i.get(k)), k) for k in keys]
    entries.sort()
    ranks = tied_ranks([e[0] for e in entries])
    return [
        Candidate(k, goal, by_key_l.get(k), by_key_i.get(k), r)
        for (_, k), r in zip(entries, ranks, strict=True)
    ]


def rank_all(
    goals: Iterable[str],
    labels: Mapping[tuple[str, str], LabelSignal],
    inverse: Mapping[tuple[str, str], InverseSignal],
) -> dict[str, list[Candidate]]:
    return {g: rank_goal(g, labels.values(), inverse.values()) for g in sorted(goals)}


def find(candidates: Iterable[Candidate], key: str) -> Candidate | None:
    return next((c for c in candidates if c.key == key), None)
