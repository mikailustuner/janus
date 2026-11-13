"""System Usability Scale scores for the usability tests (docs/research/usability-test-protocol.md).

Input: a CSV with a `participant` column and the ten answers `q1` … `q10` (1 = strongly disagree,
5 = strongly agree), as in the protocol's template. Standard scoring (Brooke 1996): odd items
contribute answer - 1, even items 5 - answer; the sum times 2.5 gives 0–100. A row with a missing
or out-of-range answer is reported and left out. Prints one score per participant, then n, mean,
median and range.

    uv run --project pipelines python pipelines/tools/sus_score.py answers.csv
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections.abc import Mapping
from pathlib import Path

ITEMS = [f"q{i}" for i in range(1, 11)]


def score(answers: Mapping[str, str]) -> float:
    """The SUS score of one questionnaire; ValueError when an answer is missing or not 1–5."""
    total = 0
    for i, item in enumerate(ITEMS, start=1):
        raw = (answers.get(item) or "").strip()
        if raw not in {"1", "2", "3", "4", "5"}:
            raise ValueError(f"{item}: {raw!r} is not an answer from 1 to 5")
        a = int(raw)
        total += a - 1 if i % 2 else 5 - a
    return total * 2.5


def summarise(rows: list[Mapping[str, str]]) -> tuple[list[tuple[str, float]], list[str]]:
    scores: list[tuple[str, float]] = []
    problems: list[str] = []
    for r in rows:
        who = r.get("participant", "?")
        try:
            scores.append((who, score(r)))
        except ValueError as e:
            problems.append(f"{who}: {e}")
    return scores, problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("answers", type=Path)
    a = ap.parse_args()
    with a.answers.open(encoding="utf-8-sig", newline="") as f:
        scores, problems = summarise(list(csv.DictReader(f)))
    for who, s in scores:
        print(f"{who}\t{s:.1f}")
    for p in problems:
        print(f"left out: {p}")
    if scores:
        values = [s for _, s in scores]
        print(
            f"n={len(values)} mean={statistics.mean(values):.1f} "
            f"median={statistics.median(values):.1f} range={min(values):.1f}–{max(values):.1f}"
        )


if __name__ == "__main__":
    main()
