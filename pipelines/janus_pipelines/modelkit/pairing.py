"""Pair the candidates of reader A with those of reader B and decide confirmation by code (spec
model-kit, Requirement 1.2). B is run on the same sources without seeing A's output; this module
is the only place the two meet. Candidates are matched on (drug, locator, parameter); several
candidates at one key are paired by value. Research use only. Not for clinical decisions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from janus_pipelines.modelkit.confirm import Confirmation, confirm, values_agree
from janus_pipelines.modelkit.model import Candidate


@dataclass(frozen=True)
class Paired:
    a: Candidate
    b: Candidate | None
    result: Confirmation


def pair(a_rows: list[Candidate], b_rows: list[Candidate]) -> tuple[list[Paired], list[Candidate]]:
    """(one `Paired` per candidate of A, the candidates of B that no A candidate matched)."""
    by_key: dict[tuple[str, str, str], list[Candidate]] = defaultdict(list)
    for b in b_rows:
        by_key[b.key].append(b)
    used: set[int] = set()
    out: list[Paired] = []
    for a in a_rows:
        pool = [b for b in by_key.get(a.key, []) if id(b) not in used]
        if not pool:
            out.append(Paired(a, None, Confirmation(False, "reader_b_found_nothing")))
            continue
        same = [b for b in pool if values_agree(a.value, b.value)]
        best = same[0] if same else min(pool, key=lambda b: abs(b.value - a.value))
        used.add(id(best))
        out.append(Paired(a, best, confirm(a.reading(), best.reading())))
    left = [b for b in b_rows if id(b) not in used]
    return out, left
