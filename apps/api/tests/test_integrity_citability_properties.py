"""Citability (evidence-integrity design §4.2): P1, P2, P3, P9."""

from __future__ import annotations

import json
import random
from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from janus.integrity.citability import cite, keep_output, roots, used_roots, verdict_map
from janus.integrity.gate import rule_gate
from janus.integrity.model import IntegritySnapshot, Status
from janus.integrity.view import build_item
from tests.integrity_strategies import (
    TODAY,
    as_cyclic,
    ref_citable,
    ref_roots,
    snapshot_and_ids,
    snapshots,
    states_for,
    with_status,
)


@given(snapshot_and_ids())
def test_p1_no_retracted_only_backing(case: tuple[IntegritySnapshot, list[str]]) -> None:
    """Feature: evidence-integrity, Property P1 (Req 1.3, 5.2, 5.4)."""
    snap, ids = case
    cited = cite(snap, ids)
    assert set(cited.kept) == {i for i in ids if ref_citable(snap, i)}
    for i in cited.kept:
        used = used_roots(snap, i)
        assert used, "a citable record rests on at least one citable root"
        assert all(snap.state_of(r).status != Status.RETRACTED for r in used if snap.records[r].doi)
    assert keep_output(snap, ids) == bool(cited.kept)
    if all(not ref_citable(snap, i) for i in ids):
        assert not keep_output(snap, ids)


@given(snapshots())
def test_p2_unknown_is_never_ok(snap: IntegritySnapshot) -> None:
    """Feature: evidence-integrity, Property P2 (Req 1.1, 1.5, 3.2, 5.3)."""
    from janus.integrity.line import build_line

    for rid, rec in snap.records.items():
        item = build_item(snap, rid, TODAY)
        stored = snap.states.get(rid)
        if rec.doi is None:
            assert item.integrity is None
            assert item.doi_check == "not_applicable"
        else:
            assert item.integrity is not None
            if stored is None:
                assert item.integrity.status == "unknown"
                assert item.integrity.reason == "not_yet_checked"
            else:
                assert item.integrity.status == stored.status.value
            if item.integrity.status == "unknown":
                assert "ok" not in {item.integrity.status, item.integrity.check_status}
                if item.citable:
                    assert "integrity_unknown" in item.codes
    line = build_line(snap, list(snap.records), TODAY)
    ok_roots = {
        r
        for i in snap.records
        for r in used_roots(snap, i)
        if snap.records[r].doi and snap.state_of(r).status == Status.OK
    }
    assert line.by_status.ok == len(ok_roots)
    dumped = json.dumps([build_item(snap, r, TODAY).model_dump(mode="json") for r in snap.records])
    assert dumped.count('"status": "ok"') == sum(
        1 for r, rec in snap.records.items() if rec.doi and snap.state_of(r).status == Status.OK
    ) + sum(
        1
        for r, rec in snap.records.items()
        if rec.doi is None
        for rv in build_item(snap, r, TODAY).roots
        if rv.integrity and rv.integrity.status == "ok"
    )


@given(
    snapshot_and_ids(states_missing=False, statuses=(Status.OK, Status.CORRECTED, Status.UNKNOWN)),
    st.data(),
)
def test_p3_retraction_removes_never_adds(
    case: tuple[IntegritySnapshot, list[str]], data: st.DataObject
) -> None:
    """Feature: evidence-integrity, Property P3 (Req 1.3, 5.5, 6.2)."""
    snap, ids = case
    doi_ids = [r for r, rec in snap.records.items() if rec.doi]
    if not doi_ids:
        return
    target = data.draw(st.sampled_from(doi_ids))
    retracted = with_status(snap, target, data.draw(states_for(Status.RETRACTED)))
    before, after = verdict_map(snap), verdict_map(retracted)
    assert {i for i, v in after.items() if v.citable} <= {i for i, v in before.items() if v.citable}
    assert set(cite(retracted, ids).kept) <= set(cite(snap, ids).kept)
    if not keep_output(snap, ids):
        assert not keep_output(retracted, ids)
    sources = data.draw(st.lists(st.sampled_from(ids), max_size=4))
    if rule_gate(sources, retracted).enabled:
        assert rule_gate(sources, snap).enabled
    from janus.integrity.line import build_line

    assert build_line(retracted, ids, TODAY).no_retracted_used


@given(snapshot_and_ids(), st.randoms(use_true_random=False))
def test_p9_verdicts_equal_reference_for_any_order(
    case: tuple[IntegritySnapshot, list[str]], rnd: random.Random
) -> None:  # type: ignore[no-untyped-def]
    """Feature: evidence-integrity, Property P9 (Req 5.2)."""
    snap, ids = case
    vm = verdict_map(snap)
    for rid in snap.records:
        assert vm[rid].citable == ref_citable(snap, rid)
        assert set(roots(snap, rid)) == ref_roots(snap, rid)
    keys = list(snap.records)
    rnd.shuffle(keys)
    shuffled = IntegritySnapshot(
        {
            k: replace(
                snap.records[k],
                basis=tuple(rnd.sample(snap.records[k].basis, len(snap.records[k].basis))),
            )
            for k in keys
        },
        dict(reversed(list(snap.states.items()))),
        snap.sources,
    )
    assert {k: v for k, v in verdict_map(shuffled).items()} == vm
    shuffled_ids = list(ids)
    rnd.shuffle(shuffled_ids)
    assert set(cite(snap, ids + ids).kept) == set(cite(snap, shuffled_ids).kept)


@given(snapshots(), st.lists(st.tuples(st.integers(0, 50), st.integers(0, 50)), max_size=6))
def test_p9_terminates_on_cycles(snap: IntegritySnapshot, extra: list[tuple[int, int]]) -> None:
    cyc = as_cyclic(snap, extra)
    vm = verdict_map(cyc)
    for rid in cyc.records:
        assert vm[rid].citable == ref_citable(cyc, rid)
    # A cycle of DOI-less records with no outside support is not citable.
    for rid, rec in cyc.records.items():
        if rec.doi is None and rec.basis and not vm[rid].citable:
            assert all(not vm[b].citable for b in rec.basis)
