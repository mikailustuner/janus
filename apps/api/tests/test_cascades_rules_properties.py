"""Every PIPC rule against the real curated files (cascade-engine design §9, P18; task 8)."""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from functools import cache
from pathlib import Path

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from janus.cascades.engine import evaluate
from janus.cascades.model import AtcClass, EngineIngredient, EngineItem, Rule, RuleBase
from janus.cascades.patterns import class_match
from janus.cascades.rulebase import RuleBaseInputs, build_rule_base
from tests.cascades_strategies import MONTH0, TODAY, cascade_snapshot

DATA = Path(__file__).resolve().parents[3] / "data"


def _read(name: str) -> str:
    return (DATA / name).read_text(encoding="utf-8")


@cache
def real_rule_base() -> RuleBase:
    """The rule base built from the curated files in `data/` (they are in git)."""
    return build_rule_base(
        RuleBaseInputs(
            pipc_csv=_read("pipc.csv"),
            pipc_meta_json=_read("pipc.meta.json"),
            classes_csv=_read("cascade_classes.csv"),
            rules_csv=_read("pipc_rules.csv"),
            priority_csv=_read("cascade_priority.csv"),
            abrupt_csv=_read("abrupt_stop_classes.csv"),
            combination_csv=_read("atc_combination_rules.csv"),
            papers_csv=_read("evidence_papers.csv"),
        )
    )


# --- P18 and the per-rule example table (task 8) ----------------------------------------------


LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
DIGITS = [f"{n:02d}" for n in range(1, 20)]  # outside the WHO combination numbering
OUTSIDE = "Z01AA01"  # a well-formed code in no class


def complete(prefix: str, letters: Sequence[str], digits: Sequence[str]) -> str:
    """Extend an ATC prefix to a 7-character ingredient code."""
    code = prefix
    if len(code) == 1:
        code += digits[0]
    if len(code) == 3:
        code += letters[0]
    if len(code) == 4:
        code += letters[1]
    if len(code) == 5:
        code += digits[1]
    return code


def members(cls: AtcClass, active: frozenset[str]) -> st.SearchStrategy[str]:
    includes = [p.prefix for p in cls.patterns if p.match == "include"]
    return st.builds(
        complete,
        st.sampled_from(includes),
        st.tuples(st.sampled_from(LETTERS), st.sampled_from(LETTERS)),
        st.tuples(st.sampled_from(DIGITS), st.sampled_from(DIGITS)),
    ).filter(lambda c: class_match(c, cls, active) is not None)


MATCHABLE = [r for r in real_rule_base().rules if r.matchable]


def _fires(rule: Rule, index_code: str, marker_code: str, d: int) -> list[str]:
    rb = real_rule_base()
    items = [
        EngineItem(0, MONTH0, (EngineIngredient("Q1", frozenset({index_code}), True),)),
        EngineItem(1, MONTH0 + d, (EngineIngredient("Q2", frozenset({marker_code}), True),)),
    ]
    res = evaluate(items, rb, cascade_snapshot(rb), TODAY)
    return [f.status for f in res.findings if f.rule.position == rule.position]


@given(rule=st.sampled_from(MATCHABLE), data=st.data())
def test_p18_every_rule_fires_only_in_its_classes(rule: Rule, data: st.DataObject) -> None:
    """Feature: cascade-engine, Property 18. Validates: Req 5.2, 10.4.

    Codes inside the rule's classes with the marker started within the window give the rule's
    finding as `probable`; a marker outside its class, or started first, gives none.
    """
    rb = real_rule_base()
    assert rule.index_class is not None and rule.marker_class is not None
    icls, mcls = rb.classes[rule.index_class], rb.classes[rule.marker_class]
    index_code = data.draw(members(icls, icls.extension_ids))
    marker_code = data.draw(members(mcls, frozenset()))
    assume(index_code != marker_code)
    d = data.draw(st.integers(1, rb.window_months))
    assert _fires(rule, index_code, marker_code, d) == ["probable"]
    assert _fires(rule, index_code, OUTSIDE, d) == []
    assert _fires(rule, index_code, marker_code, -d) == []


def test_p18_not_matchable_rules_never_fire() -> None:
    """Feature: cascade-engine, Property 18. Validates: Req 5.2 (rows 27 and 57)."""
    rb = real_rule_base()
    unmatchable = [r for r in rb.rules if not r.matchable]
    assert [r.position for r in unmatchable] == [27, 57]
    res = evaluate([], rb, cascade_snapshot(rb), TODAY)
    assert [(n.rule_id, n.role) for n in res.not_matchable] == [
        ("pipc:27", "marker"),
        ("pipc:57", "marker"),
    ]
    assert res.rules_checked == 63


def _first_member(cls: AtcClass) -> str:
    for p in cls.patterns:
        if p.match != "include":
            continue
        for ls, ds in itertools.product(
            itertools.product("AB", repeat=2), itertools.product(DIGITS[:3], repeat=2)
        ):
            code = complete(p.prefix, ls, ds)
            if class_match(code, cls, cls.extension_ids) is not None:
                return code
    raise AssertionError("class without a member code")


@pytest.mark.parametrize("position", [r.position for r in MATCHABLE])
def test_rule_examples(position: int) -> None:
    """One positive and one negative example per rule (PLAN.md §1). Req 10.4."""
    rb = real_rule_base()
    rule = rb.rules[position - 1]
    assert rule.index_class is not None and rule.marker_class is not None
    index_code = _first_member(rb.classes[rule.index_class])
    marker_code = _first_member(rb.classes[rule.marker_class])
    assert _fires(rule, index_code, marker_code, 3) == ["probable"]
    assert _fires(rule, index_code, marker_code, -3) == []
