"""Engine properties P1-P6, P9, P10, P14-P16 (cascade-engine design §9). Synthetic data only."""

from __future__ import annotations

import datetime as dt
import json
import re
import time
from dataclasses import asdict, replace
from typing import Any

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from janus.cascades.engine import EngineInputError, abrupt_stop_keys, evaluate
from janus.cascades.inputs import product_item
from janus.cascades.model import (
    AtcClass,
    EngineIngredient,
    EngineItem,
    EngineResult,
    Finding,
    NotChecked,
    Pattern,
    Rule,
    RuleBase,
)
from janus.cascades.patterns import class_match
from janus.resolution.model import AtcCodeOut, IngredientKey, ResolvedIngredient, SourceRef
from tests.cascades_strategies import (
    MONTH0,
    QIDS,
    REASSURANCE,
    TODAY,
    cascade_snapshot,
    engine_items,
    forbidden_phrases,
    ingredient_codes,
    months,
    rule_bases,
)


def run(items: list[EngineItem], rb: RuleBase, **kw: Any) -> EngineResult:
    return evaluate(items, rb, cascade_snapshot(rb), TODAY, **kw)


def view(f: Finding) -> tuple[Any, ...]:
    return (
        f.finding_id,
        f.status,
        f.timing,
        f.months_between,
        f.low_priority,
        f.form_confirmed,
        f.via_form_extension,
        f.priority,
        f.abrupt_stop,
        f.evidence_ids,
        f.index.items,
        f.marker.items,
        f.index.start,
        f.marker.start,
    )


@given(rb=rule_bases(), items=engine_items(), data=st.data())
def test_p1_order_independence(rb: RuleBase, items: list[EngineItem], data: st.DataObject) -> None:
    """Feature: cascade-engine, Property 1. Validates: Req 2.1, 9.6.

    Permuting the list gives the same result; renumbering the items through a permutation gives
    the same findings after mapping the numbers back.
    """
    before = run(items, rb)
    shuffled = data.draw(st.permutations(items))
    assert run(list(shuffled), rb) == before
    perm = data.draw(st.permutations(range(len(items))))
    renamed = [replace(it, index=perm[it.index]) for it in items]
    back = {perm[i]: i for i in range(len(items))}
    after = run(renamed, rb)
    remapped = sorted(
        (f.finding_id, f.status, tuple(sorted(back[i] for i in f.index.items)))
        for f in after.findings
    )
    assert remapped == sorted((f.finding_id, f.status, f.index.items) for f in before.findings)
    assert [c.chain_id for c in after.chains] == [c.chain_id for c in before.chains]


@given(rb=rule_bases(), items=engine_items(), key=st.sampled_from([*QIDS, "Q999"]), data=st.data())
def test_p2_monotonicity(
    rb: RuleBase, items: list[EngineItem], key: str, data: st.DataObject
) -> None:
    """Feature: cascade-engine, Property 2. Validates: Req 2.1.

    An item whose codes match no class (C codes; classes use A, N, R) changes no finding and no
    chain; an item with a key that is not yet in the list never changes an existing finding.
    """
    before = run(items, rb)
    c_code = data.draw(ingredient_codes(letters="C"))
    unmatched = EngineItem(
        len(items), data.draw(months()), (EngineIngredient(key, frozenset({c_code}), True),)
    )
    after = run([*items, unmatched], rb)
    assert [view(f) for f in after.findings] == [view(f) for f in before.findings]
    assert after.chains == before.chains
    new_codes = frozenset(data.draw(st.lists(ingredient_codes(), min_size=1, max_size=3)))
    newcomer = EngineItem(
        len(items), data.draw(months()), (EngineIngredient("Q998", new_codes, True),)
    )
    grown = {view(f) for f in run([*items, newcomer], rb).findings}
    assert {view(f) for f in before.findings} <= grown


@given(rb=rule_bases(), items=engine_items())
def test_p3_temporal_soundness(rb: RuleBase, items: list[EngineItem]) -> None:
    """Feature: cascade-engine, Property 3. Validates: Req 2.4."""
    for f in run(items, rb).findings:
        if f.index.start is not None and f.marker.start is not None:
            assert f.marker.start >= f.index.start


@given(
    rb=rule_bases(), items=engine_items(), month=st.integers(MONTH0, MONTH0 + 40), data=st.data()
)
def test_p4_date_refinement(
    rb: RuleBase, items: list[EngineItem], month: int, data: st.DataObject
) -> None:
    """Feature: cascade-engine, Property 4. Validates: Req 2.2-2.5.

    Replacing an unknown start with a known month: finding ids only shrink, no `probable` is lost
    or changed, and no finding goes from `probable` to `possible`.
    """
    unknown = [it for it in items if it.start is None]
    assume(unknown)
    target = data.draw(st.sampled_from(unknown))
    refined = [replace(it, start=month) if it is target else it for it in items]
    before = {f.finding_id: f for f in run(items, rb).findings}
    after = {f.finding_id: f for f in run(refined, rb).findings}
    assert set(after) <= set(before)
    for fid, f in before.items():
        if f.status == "probable":
            assert fid in after and view(after[fid]) == view(f)
    for fid, f in after.items():
        assert not (before[fid].status == "probable" and f.status == "possible")


@given(rb=rule_bases(), items=engine_items(), data=st.data())
def test_p5_duplicate_invariance(
    rb: RuleBase, items: list[EngineItem], data: st.DataObject
) -> None:
    """Feature: cascade-engine, Property 5. Validates: Req 2.1.

    Listing an item again (e.g. the same ingredients from another region's product) gives the
    same findings; only the item lists grow.
    """
    assume(items)
    dup = data.draw(st.sampled_from(items))
    before = run(items, rb)
    after = run([*items, replace(dup, index=len(items))], rb)

    def core(f: Finding) -> tuple[Any, ...]:
        return (
            f.finding_id,
            f.status,
            f.timing,
            f.months_between,
            f.form_confirmed,
            f.evidence_ids,
        )

    assert [core(f) for f in after.findings] == [core(f) for f in before.findings]
    assert {s.rule_id + s.index_key + s.marker_key for s in after.same_product} == {
        s.rule_id + s.index_key + s.marker_key for s in before.same_product
    }


# --- P6: region invariance through the input conversion ---------------------------------------

REGION_SOURCES = {
    "TR": SourceRef(source_id="titck", run_id="r-tr", region="TR", snapshot_date="2026-11-06"),
    "US": SourceRef(
        source_id="openfda_ndc", run_id="r-us", region="US", snapshot_date="2026-11-06"
    ),
    "EU": SourceRef(source_id="bdpm", run_id="r-eu", region="EU", snapshot_date="2026-11-01"),
}
SELECTIONS = ["single_ingredient_product", "therapeutic_group", "route_group", "all_codes"]


def resolved(
    pos: int, qid: str, codes: list[str], selection: str, region: str, status: str = "mapped"
) -> ResolvedIngredient:
    src = REGION_SOURCES[region]
    return ResolvedIngredient(
        position=pos,
        published_name=f"{region.lower()} name {qid}",
        strength=None,
        status=status,  # pyright: ignore[reportArgumentType]
        reason=None if status != "unmapped" else "no_ingredient_key",
        ingredient_key=IngredientKey(qid=qid, label_en=None, labels={})
        if status == "mapped"
        else None,
        key_candidates=[qid, "Q777"] if status == "ambiguous" else [],
        match_step="tr_label" if region == "TR" else "any_label",
        atc_codes=[AtcCodeOut(code=c, source=src, product=None) for c in codes]
        if status == "mapped"
        else [],
        atc_selection=selection if status == "mapped" else None,  # pyright: ignore[reportArgumentType]
        rxcuis=[],
        rxcui_status=None,
        source=src,
    )


@given(
    rb=rule_bases(),
    spec=st.lists(
        st.tuples(
            st.lists(
                st.tuples(
                    st.sampled_from(QIDS),
                    st.lists(ingredient_codes(), min_size=1, max_size=2),
                    st.sampled_from(SELECTIONS),
                ),
                min_size=1,
                max_size=2,
                unique_by=lambda t: t[0],
            ),
            months(),
        ),
        max_size=5,
    ),
)
def test_p6_region_invariance(rb: RuleBase, spec: list[Any]) -> None:
    """Feature: cascade-engine, Property 6. Validates: Req 7.1.

    The same ingredients, codes, selections and starts from TR, US or EU products give the same
    result.
    """
    results: list[EngineResult] = []
    for region in REGION_SOURCES:
        items: list[EngineItem] = []
        for idx, (ings, start) in enumerate(spec):
            rs = [resolved(p + 1, q, codes, sel, region) for p, (q, codes, sel) in enumerate(ings)]
            item, _ = product_item(idx, start, rs, {}, {})
            items.append(item)
        results.append(run(items, rb))
    assert results[0] == results[1] == results[2]


# --- P9, P10 ----------------------------------------------------------------------------------


@given(
    rb=rule_bases(),
    items=engine_items(),
    bad=st.sampled_from(["C09BB03", "A01", "a01ab01", "N02AB0"]),
)
def test_p9_input_guard(rb: RuleBase, items: list[EngineItem], bad: str) -> None:
    """Feature: cascade-engine, Property 9. Validates: Req 1.3."""
    poisoned = [
        *items,
        EngineItem(len(items), None, (EngineIngredient("Q500", frozenset({bad}), True),)),
    ]
    with pytest.raises(EngineInputError) as err:
        run(poisoned, rb, combination_codes=frozenset({"C09BB03"}))
    assert bad not in str(err.value)


@given(rb=rule_bases(), items=engine_items())
def test_p10_pair_rules(rb: RuleBase, items: list[EngineItem]) -> None:
    """Feature: cascade-engine, Property 10. Validates: Req 2.1."""
    res = run(items, rb)
    same = {(s.rule_id, s.index_key, s.marker_key) for s in res.same_product}
    for f in res.findings:
        assert f.index.key != f.marker.key
        assert set(f.index.items) != set(f.marker.items)
        assert (f.rule.rule_id, f.index.key, f.marker.key) not in same
        assert f.rule.index_class is not None and f.rule.marker_class is not None
        ext = rb.classes[f.rule.index_class].extension_ids
        assert all(
            class_match(c, rb.classes[f.rule.index_class], ext) for c in f.index.matched_codes
        )
        assert all(class_match(c, rb.classes[f.rule.marker_class]) for c in f.marker.matched_codes)
    for s in res.same_product:
        assert s.index_key != s.marker_key


# --- P14: abrupt stop ---------------------------------------------------------------------------


@given(rb=rule_bases(), items=engine_items())
def test_p14_abrupt_stop(rb: RuleBase, items: list[EngineItem]) -> None:
    """Feature: cascade-engine, Property 14. Validates: Req 4.1."""
    ref = {
        ing.key
        for it in items
        for ing in it.ingredients
        if any(class_match(c, rb.abrupt_stop) for c in ing.codes)
    }
    assert abrupt_stop_keys(items, rb) == ref
    res = run(items, rb)
    for f in res.findings:
        expected = tuple(
            r for r, k in (("index", f.index.key), ("marker", f.marker.key)) if k in ref
        )
        assert f.abrupt_stop == expected
    expected_warnings = sorted(
        {(it.index, ing.key) for it in items for ing in it.ingredients if ing.key in ref}
    )
    assert [(w.item, w.ingredient_key) for w in res.item_warnings] == expected_warnings
    assert all(w.text == "Do not stop this medicine suddenly." for w in res.item_warnings)


# --- P15: statements and wording ---------------------------------------------------------------

PHRASES = forbidden_phrases()


def _text(res: EngineResult) -> str:
    return json.dumps(asdict(res), ensure_ascii=False, default=str).lower()


@given(rb=rule_bases(), items=engine_items(), all_disabled=st.booleans())
def test_p15_statements_and_wording(
    rb: RuleBase, items: list[EngineItem], all_disabled: bool
) -> None:
    """Feature: cascade-engine, Property 15. Validates: Req 4.2, 4.3."""
    from janus.integrity.model import Status

    statuses = {rb.source_paper_id: Status.RETRACTED} if all_disabled else None
    res = evaluate(items, rb, cascade_snapshot(rb, statuses), TODAY)
    enabled = res.rules_checked
    if enabled == 0:
        assert res.statement is not None and res.statement.code == "rule_base_unavailable"
        assert res.findings == ()
    elif not res.findings:
        assert res.statement is not None and res.statement.code == "no_pattern_found"
        assert res.statement.text == (
            "Janus found no pattern from its rule list. "
            "This does not mean your medicines are free of problems."
        )
    else:
        assert res.statement is None
    text = _text(res)
    for phrase in [*PHRASES, *REASSURANCE]:
        assert re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is None, phrase


# --- P16: not checked and form labels ------------------------------------------------------------


@given(
    rb=rule_bases(),
    spec=st.lists(
        st.tuples(
            st.lists(
                st.tuples(
                    st.sampled_from(QIDS),
                    st.lists(ingredient_codes(), min_size=1, max_size=2),
                    st.sampled_from(SELECTIONS),
                    st.sampled_from(["mapped", "mapped", "ambiguous", "unmapped"]),
                ),
                min_size=1,
                max_size=3,
                unique_by=lambda t: t[0],
            ),
            months(),
        ),
        max_size=5,
    ),
)
def test_p16_not_checked_and_form_labels(rb: RuleBase, spec: list[Any]) -> None:
    """Feature: cascade-engine, Property 16. Validates: Req 2.10, 7.2, 7.3."""
    items: list[EngineItem] = []
    mapped_only: list[EngineItem] = []
    unchecked_all: list[NotChecked] = []
    expected_unchecked: set[tuple[int, int]] = set()
    for idx, (ings, start) in enumerate(spec):
        rs = [
            resolved(p + 1, q, c, sel, "TR", status) for p, (q, c, sel, status) in enumerate(ings)
        ]
        item, unchecked = product_item(idx, start, rs, {}, {})
        items.append(item)
        unchecked_all += unchecked
        expected_unchecked |= {(idx, r.position) for r in rs if r.status != "mapped"}
        mapped_only.append(
            product_item(idx, start, [r for r in rs if r.status == "mapped"], {}, {})[0]
        )
    assert {(n.item, n.position) for n in unchecked_all} == expected_unchecked
    res = run(items, rb, not_checked=unchecked_all)
    assert {(n.item, n.position) for n in res.not_checked} == expected_unchecked
    assert run(mapped_only, rb).findings == res.findings

    def ref_confirmed(key: str, cls: AtcClass, active: frozenset[str]) -> bool:
        """Some copy of `key` whose codes match `cls` is form-confirmed."""
        return any(
            ing.form_confirmed
            for it in items
            for ing in it.ingredients
            if ing.key == key and any(class_match(c, cls, active) for c in ing.codes)
        )

    for f in res.findings:
        assert f.rule.index_class is not None and f.rule.marker_class is not None
        icls = rb.classes[f.rule.index_class]
        expected = ref_confirmed(f.index.key, icls, icls.extension_ids) and ref_confirmed(
            f.marker.key, rb.classes[f.rule.marker_class], frozenset()
        )
        assert f.form_confirmed == expected
    for a, b in zip(res.findings, res.findings[1:], strict=False):
        if (a.status, a.timing) == (b.status, b.timing):
            assert a.form_confirmed >= b.form_confirmed


# --- Examples (task 6.14) -------------------------------------------------------------------------

CCB = AtcClass("ccb", (Pattern("C08", "include"),))
DIURETIC = AtcClass("diuretic", (Pattern("C03", "include"),))
ABRUPT = AtcClass("abrupt_stop", (Pattern("C07", "include"),))


def row5_base() -> RuleBase:
    rule = Rule(
        5,
        "Cardiovascular system",
        "drug_class",
        "Calcium channel blocker",
        "Peripheral edema",
        "Diuretic",
        "Table 1, row 5",
        "ccb",
        "diuretic",
        None,
        (),
        None,
    )
    return RuleBase(12, (rule,), {"ccb": CCB, "diuretic": DIURETIC}, ABRUPT, (), "test")


def test_combination_product_alone_is_same_product() -> None:
    """Amlodipine + hydrochlorothiazide in one product: `same_product`, no finding. Req 2.1."""
    rb = row5_base()
    amlo = EngineIngredient("Q412616", frozenset({"C08CA01"}), True)
    hctz = EngineIngredient("Q423819", frozenset({"C03AA03"}), True)
    res = run([EngineItem(0, MONTH0, (amlo, hctz))], rb)
    assert res.findings == ()
    assert [(s.rule_id, s.items) for s in res.same_product] == [("pipc:5", (0,))]
    later = EngineItem(1, MONTH0 + 6, (hctz,))
    res2 = run([EngineItem(0, MONTH0, (amlo,)), later], rb)
    assert [(f.rule.rule_id, f.status, f.months_between) for f in res2.findings] == [
        ("pipc:5", "probable", 6)
    ]


def test_fifteen_items_under_one_second() -> None:
    """A 15-item list over the real-size rule base evaluates in under one second. Req 9.7."""
    from tests.test_cascades_rules_properties import real_rule_base

    rb = real_rule_base()
    codes = (
        "C08CA01 C03AA03 C09AA03 N06AB06 A06AD11 N05BA12 C10AA05 N02BE01 "
        "A02BC01 M01AE01 N03AX09 A10BA02 B03AA07 R06AE07 N05CF02"
    ).split()
    items = [
        EngineItem(i, MONTH0 + i, (EngineIngredient(f"Q{900 + i}", frozenset({c}), True),))
        for i, c in enumerate(codes)
    ]
    snap = cascade_snapshot(rb)
    t0 = time.perf_counter()
    res = evaluate(items, rb, snap, dt.date(2026, 11, 7))
    assert time.perf_counter() - t0 < 1.0
    assert res.rules_checked == 63
