"""Property P12: chains (cascade-engine design §4.5, §9)."""

from __future__ import annotations

import itertools
from dataclasses import replace
from functools import cache

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.cascades import chains as chains_module
from janus.cascades.chains import chains
from janus.cascades.engine import evaluate
from janus.cascades.model import EngineItem, Finding, RuleBase, Side
from tests.cascades_strategies import TODAY, cascade_snapshot, engine_items, rule_bases

NODES = ["Q1", "Q2", "Q3", "Q4", "Q5"]


def _side(key: str) -> Side:
    return Side(key, None, (0,), (), True, False, None)


def finding(a: str, b: str, rule: int, status: str, template: Finding) -> Finding:
    return replace(
        template,
        finding_id=f"pipc:{rule}:{a}:{b}",
        index=_side(a),
        marker=_side(b),
        status=status,  # pyright: ignore[reportArgumentType]
    )


def reference(fs: list[Finding]) -> set[tuple[str, ...]]:
    edges = {(f.index.key, f.marker.key) for f in fs}
    nodes = sorted({k for e in edges for k in e})
    paths: set[tuple[str, ...]] = set()
    for n in range(3, len(nodes) + 1):
        for perm in itertools.permutations(nodes, n):
            if all((a, b) in edges for a, b in itertools.pairwise(perm)):
                paths.add(perm)

    def inside(q: tuple[str, ...], p: tuple[str, ...]) -> bool:
        return any(q[i : i + len(p)] == p for i in range(len(q) - len(p) + 1))

    return {p for p in paths if not any(len(q) > len(p) and inside(q, p) for q in paths)}


@st.composite
def link_graphs(draw: st.DrawFn, template: Finding) -> list[Finding]:
    pairs = draw(
        st.lists(
            st.tuples(st.sampled_from(NODES), st.sampled_from(NODES)).filter(
                lambda t: t[0] != t[1]
            ),
            max_size=10,
        )
    )
    return [
        finding(
            a, b, draw(st.integers(1, 3)), draw(st.sampled_from(["probable", "possible"])), template
        )
        for a, b in pairs
    ]


@cache
def _template() -> Finding:
    from janus.cascades.model import EngineIngredient
    from tests.test_cascades_engine_properties import row5_base

    rb = row5_base()
    items = [
        EngineItem(0, 24000, (EngineIngredient("Q1", frozenset({"C08CA01"}), True),)),
        EngineItem(1, 24003, (EngineIngredient("Q2", frozenset({"C03AA03"}), True),)),
    ]
    return evaluate(items, rb, cascade_snapshot(rb), TODAY).findings[0]


@given(data=st.data())
def test_p12_chains_equal_reference(data: st.DataObject) -> None:
    """Feature: cascade-engine, Property 12. Validates: Req 2.6.

    Chains are the maximal simple paths with two or more links, weakest-link status, and
    depend only on the findings.
    """
    fs = data.draw(link_graphs(_template()))
    got, truncated = chains(fs)
    assert not truncated
    assert {c.ingredient_keys for c in got} == reference(fs)
    for c in got:
        assert len(c.links) >= 2 and len(set(c.ingredient_keys)) == len(c.ingredient_keys)
        link_probable = [
            any(
                f.status == "probable"
                for f in fs
                if (f.index.key, f.marker.key) == (link.index_key, link.marker_key)
            )
            for link in c.links
        ]
        assert (c.status == "probable") == all(link_probable)
    shuffled = data.draw(st.permutations(fs))
    assert chains(list(shuffled)) == (got, truncated)


@given(rb=rule_bases(), items=engine_items(), data=st.data())
def test_p12_chains_from_engine_ignore_item_order(
    rb: RuleBase, items: list[EngineItem], data: st.DataObject
) -> None:
    """Feature: cascade-engine, Property 12. Validates: Req 2.6."""
    snap = cascade_snapshot(rb)
    a = evaluate(items, rb, snap, TODAY)
    b = evaluate(list(data.draw(st.permutations(items))), rb, snap, TODAY)
    assert a.chains == b.chains
    found = {(f.index.key, f.marker.key) for f in a.findings}
    for c in a.chains:
        assert all((link.index_key, link.marker_key) in found for link in c.links)


def test_p12_bounds_give_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature: cascade-engine, Property 12. Validates: Req 2.6 (bounded, never silent)."""
    t = _template()
    complete = [finding(a, b, 1, "possible", t) for a in NODES for b in NODES if a != b]
    monkeypatch.setattr(chains_module, "MAX_CHAINS", 3)
    got, truncated = chains(complete)
    assert truncated and len(got) == 3
    monkeypatch.setattr(chains_module, "MAX_CHAINS", 100)
    monkeypatch.setattr(chains_module, "MAX_PATHS", 5)
    _, truncated = chains(complete)
    assert truncated
