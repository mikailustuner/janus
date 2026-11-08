"""Synthetic inputs for light-face tests: labels, mappings, signals and curated files.

Keys are sentinel Wikidata-like ids (Q1…Q30); terms and goals are invented. No real data.
"""

from __future__ import annotations

from collections.abc import Mapping

from hypothesis import strategies as st

from janus.light.inverse import Counts
from janus.light.model import InverseSignal, Label, LabelSignal, MappingRow
from janus.memory.stats import Sensitivity, Stats, cells_from_counts, evaluate

PAPER = "paper:yang_2011:pone.0028025"
PAPER2 = "paper:zappacosta_1980:nejm198012183032516"
KEYS = [f"Q{i}" for i in range(1, 31)]
ONSIDES_IDS = [str(1000 + i) for i in range(1, 31)]
KEY_OF: Mapping[str, str] = dict(zip(ONSIDES_IDS, KEYS, strict=True))
TERMS = ("Term alpha", "Term beta", "Term gamma")
GOALS = ("goal_a", "goal_b")
SECTIONS = ("AR", "WP", "BW", "NA")
REGIONS = ("US", "EU", "UK", "JP")

MAPPING: Mapping[str, MappingRow] = {
    "Term alpha": MappingRow("Term alpha", "goal_a", "active", (PAPER,), "r"),
    "Term beta": MappingRow("Term beta", "goal_a", "active", (PAPER, PAPER2), "r", True),
    "Term gamma": MappingRow("Term gamma", "goal_b", "active", (PAPER,), "r"),
}


@st.composite
def labels(
    draw: st.DrawFn,
    ids: tuple[str, ...] = tuple(ONSIDES_IDS[:8]),
    max_size: int = 40,
    terms: tuple[str, ...] = (*TERMS, "Unmapped term"),
) -> list[Label]:
    n = draw(st.integers(0, max_size))
    out: list[Label] = []
    for i in range(n):
        ingredients = draw(
            st.one_of(
                st.tuples(st.sampled_from(ids)),
                st.lists(st.sampled_from([*ids, "OMOP9"]), min_size=1, max_size=3).map(tuple),
            )
        )
        effects = draw(
            st.lists(st.tuples(st.sampled_from(terms), st.sampled_from(SECTIONS)), max_size=4)
        )
        out.append(
            Label(
                label_id=i + 1,
                source=draw(st.sampled_from(REGIONS)),
                set_id=f"set-{i + 1}",
                ingredients=tuple(sorted(set(ingredients))),
                effects=tuple(sorted(set(effects))),
            )
        )
    return out


def stats_for(a: int, ingredient: int, event: int, n: int) -> tuple[Stats, Sensitivity]:
    primary = evaluate(cells_from_counts(a, ingredient, event, n))
    sens = Sensitivity(evaluate(cells_from_counts(a, ingredient, event, n + 10)), False)
    return primary, sens


@st.composite
def counts(draw: st.DrawFn) -> Counts:
    n_mapped = draw(st.integers(10, 5_000_000))
    ingredient = draw(st.integers(1, n_mapped))
    event = draw(st.integers(0, n_mapped))
    hi = min(ingredient, event)
    lo = max(0, ingredient + event - n_mapped)
    a = draw(st.integers(lo, max(lo, hi)))
    extra = draw(st.integers(0, 1000))
    ev_all = event + draw(st.integers(0, extra))
    return Counts(a, ingredient, event, ev_all, n_mapped, n_mapped + extra)


@st.composite
def label_signals(draw: st.DrawFn, goal: str = "goal_a", max_size: int = 12) -> list[LabelSignal]:
    keys = draw(st.lists(st.sampled_from(KEYS), unique=True, max_size=max_size))
    out: list[LabelSignal] = []
    for k in keys:
        total = draw(st.integers(1, 30))
        with_effect = draw(st.integers(1, total))
        regions = tuple(r for r in REGIONS if draw(st.booleans())) or ("US",)
        out.append(
            LabelSignal(k, goal, regions, with_effect, total, ("AR",), ("Term alpha",), (PAPER,))
        )
    return out


@st.composite
def inverse_signals(
    draw: st.DrawFn, goal: str = "goal_a", max_size: int = 12
) -> list[InverseSignal]:
    keys = draw(st.lists(st.sampled_from(KEYS), unique=True, max_size=max_size))
    out: list[InverseSignal] = []
    for k in keys:
        a = draw(st.integers(3, 50))
        st_, se = stats_for(a, a * 100, 10_000, 1_000_000)
        out.append(InverseSignal(k, goal, st_, se, ("Pt",)))
    return out
