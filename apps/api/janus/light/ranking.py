"""Ranking of a goal's candidates (design §6, DP5, DP23; P7, P9, P15). Pure.

Key K1 (statistician pass, adopted as a post-hoc change, DP23), in order, all descending: has a
label signal, Wilson lower bound (95 %) of the share of the ingredient's labels that list the
effect, number of label regions, number of such labels, has an inverse FAERS signal, FAERS reports
of that signal. The ratio (ROR, PRR) never enters the key. Equal keys share a tied rank range
(competition ranking); within a tie the list order is the ingredient key, which is not a rank.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

from janus.light.model import InverseSignal, LabelSignal, Rank

Z: Final = 1.96


def wilson_low(k: int, n: int, z: float = Z) -> float:
    """Lower bound of the Wilson score interval for k successes in n; 0.0 when n == 0."""
    if n < 0 or k < 0 or k > n:
        raise ValueError("need 0 <= k <= n")
    if n == 0:
        return 0.0
    z2 = z * z
    centre = 2 * k + z2
    spread = z * math.sqrt(z2 + 4 * k * (n - k) / n)
    return max(0.0, (centre - spread) / (2 * (n + z2)))


type SortKey = tuple[int, float, int, int, int, int]


def sort_key(label: LabelSignal | None, inverse: InverseSignal | None) -> SortKey:
    """Smaller sorts first (every component is negated)."""
    has_label = label is not None
    share = wilson_low(label.labels_with_effect, label.labels_total) if label else 0.0
    regions = len(label.regions) if label else 0
    labels = label.labels_with_effect if label else 0
    has_inverse = inverse is not None
    reports = inverse.stats.cells.a if inverse else 0
    return (-has_label, -share, -regions, -labels, -has_inverse, -reports)


def tied_ranks(keys: Sequence[SortKey]) -> list[Rank]:
    """Rank range of each position of an already sorted key list."""
    n = len(keys)
    out: list[Rank] = []
    i = 0
    while i < n:
        j = i
        while j + 1 < n and keys[j + 1] == keys[i]:
            j += 1
        for _ in range(i, j + 1):
            out.append(Rank(best=i + 1, worst=j + 1, population=n))
        i = j + 1
    return out
