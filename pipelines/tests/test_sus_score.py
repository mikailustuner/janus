"""SUS scoring: the standard formula, bounds and rejected answers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from hypothesis import given
from hypothesis import strategies as st

TOOL = Path(__file__).resolve().parents[1] / "tools" / "sus_score.py"


def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sus_score", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T = tool()


def answers(values: list[int]) -> dict[str, str]:
    return {f"q{i}": str(v) for i, v in enumerate(values, start=1)}


def test_known_values() -> None:
    assert T.score(answers([3] * 10)) == 50.0
    assert T.score(answers([5, 1] * 5)) == 100.0
    assert T.score(answers([1, 5] * 5)) == 0.0
    # Brooke's worked pattern: 4,2,4,2,... gives 75.
    assert T.score(answers([4, 2] * 5)) == 75.0


@given(st.lists(st.integers(1, 5), min_size=10, max_size=10))
def test_score_is_within_bounds_and_a_multiple_of_2_5(values: list[int]) -> None:
    s = T.score(answers(values))
    assert 0 <= s <= 100
    assert (s / 2.5).is_integer()


def test_missing_or_out_of_range_answers_are_left_out() -> None:
    with pytest.raises(ValueError):
        T.score({**answers([3] * 10), "q4": "6"})
    scores, problems = T.summarise(
        [{"participant": "P01", **answers([3] * 10)}, {"participant": "P02", "q1": "3"}]
    )
    assert scores == [("P01", 50.0)]
    assert len(problems) == 1 and problems[0].startswith("P02")
