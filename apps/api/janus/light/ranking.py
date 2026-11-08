"""Ranking of a goal's candidates (design §6, DP5; P7, P9, P15). Pure.

Key, in order: number of signal types, number of label regions, Wilson lower bound (95 %) of the
share of the ingredient's labels that list the effect, number of such labels, FAERS reports of the
inverse signal. All descending. The ratio (ROR, PRR) never enters the key. Equal keys share a tied
rank range (competition ranking); within a tie the list order is the ingredient key, which is not a
rank.
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


type SortKey = tuple[int, int, float, int, int]


def sort_key(label: LabelSignal | None, inverse: InverseSignal | None) -> SortKey:
    """Smaller sorts first (every component is negated)."""
    types = (label is not None) + (inverse is not None)
    regions = len(label.regions) if label else 0
    share = wilson_low(label.labels_with_effect, label.labels_total) if label else 0.0
    labels = label.labels_with_effect if label else 0
    reports = inverse.stats.cells.a if inverse else 0
    return (-types, -regions, -share, -labels, -reports)


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
