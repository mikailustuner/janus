"""Confirmation of special-population statements (spec model-kit, milestone M4, design DP-M26).

Pairs the candidates of reader A and reader B for one label by code. A pair is confirmed iff both readers found the same
population class, grade and measure, with a ratio within 1 %, both read the parent drug without any context flag
(metabolite, enantiomer, unbound, pediatric, interaction, animal, pregnancy, dose change), and both quote the same
sentence or table row. A difference in grade or context is a disagreement (spec requirement 1.2). Pure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from janus_pipelines.modelkit.sp_model import SpCandidate

RATIO_TOLERANCE = 0.01
QUOTE_SIMILARITY = 0.6


@dataclass(frozen=True)
class SpPair:
    a: SpCandidate | None
    b: SpCandidate | None
    confirmed: bool
    reason: str


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def quote_similarity(x: str, y: str) -> float:
    a, b = _words(x), _words(y)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def same_ratio(x: float, y: float) -> bool:
    return abs(x - y) <= RATIO_TOLERANCE * max(abs(x), abs(y))


def judge(a: SpCandidate, b: SpCandidate) -> tuple[bool, str]:
    if a.pop_class != b.pop_class or a.measure != b.measure:
        return False, "class_or_measure_differs"
    if not same_ratio(a.ratio, b.ratio):
        return False, "value_differs"
    if a.grade != b.grade:
        return False, "grade_differs"
    if a.flags or b.flags:
        return False, "context_flag:" + "+".join(sorted(set(a.flags) | set(b.flags)))
    if quote_similarity(a.quote, b.quote) < QUOTE_SIMILARITY:
        return False, "different_sentences"
    return True, "agree"


def pair_label(a_list: list[SpCandidate], b_list: list[SpCandidate]) -> list[SpPair]:
    """All candidates of one label, paired by class, measure and value; a leftover stays unconfirmed."""
    out: list[SpPair] = []
    used: set[int] = set()
    for a in a_list:
        best: tuple[int, SpCandidate, bool, str] | None = None
        for i, b in enumerate(b_list):
            if i in used or a.pop_class != b.pop_class or a.measure != b.measure:
                continue
            if not same_ratio(a.ratio, b.ratio):
                continue
            ok, why = judge(a, b)
            if best is None or ok:
                best = (i, b, ok, why)
            if ok:
                break
        if best is None:
            out.append(SpPair(a, None, False, "only_reader_a"))
        else:
            used.add(best[0])
            out.append(SpPair(a, best[1], best[2], best[3]))
    for i, b in enumerate(b_list):
        if i not in used:
            out.append(SpPair(None, b, False, "only_reader_b"))
    return out
