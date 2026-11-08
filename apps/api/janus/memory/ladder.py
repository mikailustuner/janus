"""The combination ladder (collective-memory design §4.4, Req 2.2). Pure: no I/O.

combination (all ingredients named in a report) -> pairwise (every two-ingredient subset that
reaches the display threshold) -> single (each ingredient on its own). A level is shown only when
its count reaches the threshold; every level skipped on the way is named with a reason.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations
from typing import Final

from janus.memory.model import Level

REASON: Final = "below_display_threshold"


@dataclass(frozen=True)
class Choice:
    level: Level
    skipped: tuple[tuple[Level, str], ...]
    pairs: tuple[tuple[str, str], ...]  # the pairs that reach the threshold (level pairwise)


def all_pairs(keys: list[str]) -> list[tuple[str, str]]:
    return list(combinations(sorted(set(keys)), 2))


def choose_level(
    n_ingredients: int,
    combination_count: int,
    pair_counts: Mapping[tuple[str, str], int],
    threshold: int,
) -> Choice:
    """The highest level whose count reaches `threshold`.

    `pair_counts` is only consulted for sets of 3 or more ingredients: for two ingredients the
    pair *is* the combination, so there is no pairwise level.
    """
    if combination_count >= threshold:
        return Choice("combination", (), ())
    skipped: list[tuple[Level, str]] = [("combination", REASON)]
    if n_ingredients >= 3:
        reaching = tuple(sorted(p for p, n in pair_counts.items() if n >= threshold))
        if reaching:
            return Choice("pairwise", tuple(skipped), reaching)
        skipped.append(("pairwise", REASON))
    return Choice("single", tuple(skipped), ())
