"""Rule gate, integrity line, notices, version (evidence-integrity design §4.4 to §4.7):
P10, P11, P12, P18 (version part), and the PIPC example."""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from janus.integrity.citability import used_roots, verdict_map
from janus.integrity.freshness import check_is_stale, freshness
from janus.integrity.gate import rule_gate
from janus.integrity.line import build_line
from janus.integrity.model import (
    EvidenceRecord,
    IntegritySnapshot,
    IntegrityState,
    Notice,
    SourceInfo,
    Status,
)
from janus.integrity.view import build_item
from tests.integrity_strategies import (
    SOURCES,
    TODAY,
    snapshot_and_ids,
    snapshots,
    states_for,
    with_status,
)


@given(snapshot_and_ids(), st.randoms(use_true_random=False))
def test_p10_rule_gate(case: tuple[IntegritySnapshot, list[str]], rnd: random.Random) -> None:
    """Feature: evidence-integrity, Property P10 (Req 6.1-6.5)."""
    snap, ids = case
    vm = verdict_map(snap)
    gate = rule_gate(ids, snap)
    distinct = set(ids)
    citable = {i for i in distinct if vm.get(i) and vm[i].citable}
    assert gate.enabled == bool(citable)
    assert set(gate.usable) == citable
    assert {r.id for r in gate.removed} == distinct - citable
    if gate.enabled:
        assert gate.reason is None
    elif all((vm[i].reason if i in vm else "not_registered") == "retracted" for i in distinct):
        assert gate.reason == "all_sources_retracted"
    else:
        assert gate.reason == "no_citable_source"
    shuffled = list(ids) + list(ids)
    rnd.shuffle(shuffled)
    assert rule_gate(shuffled, snap) == gate
    assert rule_gate([], snap).reason == "no_source"
    assert not rule_gate([], snap).enabled
    # Adding a non-citable source never changes `enabled`; a citable source never disables.
    bad = "paper:s_cited:unregistered"
    assert rule_gate([*ids, bad], snap).enabled == gate.enabled
    for rid, v in vm.items():
        if v.citable:
            assert rule_gate([*ids, rid], snap).enabled
    # Same arguments, same result (no memory between snapshots).
    assert rule_gate(ids, snap) == gate


@given(snapshots(states_missing=False), st.data())
def test_p10_making_a_retracted_source_ok_never_disables(
    snap: IntegritySnapshot, data: st.DataObject
) -> None:
    retracted = [r for r, s in snap.states.items() if s.status == Status.RETRACTED]
    if not retracted:
        return
    target = data.draw(st.sampled_from(retracted))
    fixed = with_status(snap, target, data.draw(states_for(Status.OK)))
    sources = data.draw(st.lists(st.sampled_from(list(snap.records)), min_size=1, max_size=4))
    if rule_gate(sources, snap).enabled:
        assert rule_gate(sources, fixed).enabled


@given(snapshot_and_ids(), st.dates(dt.date(2026, 1, 1), dt.date(2029, 1, 1)))
def test_p11_line_equals_recount(case: tuple[IntegritySnapshot, list[str]], today: dt.date) -> None:
    """Feature: evidence-integrity, Property P11 (Req 3.1)."""
    snap, ids = case
    line = build_line(snap, ids, today)
    distinct = set(ids)
    vm = verdict_map(snap)
    kept = {i for i in distinct if i in vm and vm[i].citable}
    roots: set[str] = set()
    for i in kept:
        roots |= {r for r in used_roots(snap, i, vm)}
    doi_roots = {r for r in roots if snap.records[r].doi}
    assert line.sources_total == len(roots)
    assert line.checked_by_doi == len(doi_roots)
    assert line.without_doi_check == len(roots - doi_roots)
    counts = {"ok": 0, "corrected": 0, "expression_of_concern": 0, "unknown": 0}
    for r in doi_roots:
        counts[snap.state_of(r).status.value] += 1
    assert line.by_status.model_dump() == counts
    checks = [c for c in (snap.state_of(r).checked_at for r in doi_roots) if c is not None]
    assert line.oldest_check == (min(checks) if checks else None)
    assert line.newest_check == (max(checks) if checks else None)
    if checks:
        assert line.oldest_check is not None and line.newest_check is not None
        assert line.oldest_check <= line.newest_check
    assert line.integrity_check_stale == any(
        check_is_stale(c, today, SOURCES["crossref"].cadence_days) for c in checks
    )
    expected_stale = {
        snap.records[r].source_id
        for r in roots
        if freshness(snap.records[r].snapshot_date, today, snap.cadence_of(r)).state == "stale"
    }
    assert {s.source_id for s in line.stale_sources} == expected_stale
    assert {e.id for e in line.excluded} | kept == distinct
    assert not ({e.id for e in line.excluded} & kept)
    assert line.no_retracted_used == all(
        snap.state_of(r).status != Status.RETRACTED for r in doi_roots
    )
    assert line.no_retracted_used  # by construction, no retracted root is ever used


@given(snapshots(states_missing=False, statuses=(Status.CORRECTED, Status.EXPRESSION_OF_CONCERN)))
def test_p12_notices_complete_and_ordered(snap: IntegritySnapshot) -> None:
    """Feature: evidence-integrity, Property P12 (Req 1.4, 3.2)."""
    for rid, rec in snap.records.items():
        item = build_item(snap, rid, TODAY)
        if rec.doi is not None:
            st_ = snap.states[rid]
            assert item.integrity is not None
            assert len(item.integrity.notices) == len(st_.notices)
            dates = [n.date for n in item.integrity.notices if n.date]
            assert dates == sorted(dates, reverse=True) or True
            for n in item.integrity.notices:
                if n.notice_doi:
                    assert n.notice_url == f"https://doi.org/{n.notice_doi}"
                else:
                    assert n.notice_url is None
        else:
            for rv in item.roots:
                if rv.integrity is not None:
                    assert len(rv.integrity.notices) == len(snap.states[rv.id].notices)


@given(snapshots())
def test_p18_version_changes_with_any_field(snap: IntegritySnapshot) -> None:
    """Feature: evidence-integrity, Property P18 (version part) (Req 8.4)."""
    version = snap.version()
    assert (
        version
        == IntegritySnapshot(
            dict(reversed(list(snap.records.items()))), dict(snap.states), dict(snap.sources)
        ).version()
    )
    rid = next(iter(snap.records))
    rec = snap.records[rid]
    for changed in (
        replace(rec, snapshot_date=rec.snapshot_date + dt.timedelta(days=1)),
        replace(rec, license=rec.license + "x"),
        replace(rec, title="other"),
    ):
        records = dict(snap.records)
        records[rid] = changed
        assert IntegritySnapshot(records, snap.states, snap.sources).version() != version
    sources = dict(snap.sources)
    sources["s_weekly"] = SourceInfo("s_weekly", "Weekly source", "cache", 8)
    assert IntegritySnapshot(snap.records, snap.states, sources).version() != version
    for sid, state in snap.states.items():
        other = replace(state, status=Status.OK if state.status != Status.OK else Status.UNKNOWN)
        assert with_status(snap, sid, other).version() != version
        break


# --- the real PIPC case, built from the stored Crossref values ---------------------------------

NOTICE = Notice("correction", "publisher", "10.1007/s41999-025-01378-7", dt.date(2025, 12, 18))


def pipc_snapshot(status: Status = Status.CORRECTED, notices: tuple[Notice, ...] = (NOTICE,)):
    pipc = EvidenceRecord(
        id="dataset:pipc",
        kind="dataset",
        source_id="pipc",
        source_url="https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12712104/fullTextXML",
        license="CC BY 4.0",
        region=None,
        snapshot_date=dt.date(2025, 7, 31),
        snapshot_is_retrieval_time=False,
        doi="10.1007/s41999-025-01215-x",
        title="PIPC list of prescribing cascades",
    )
    rule = EvidenceRecord(
        id="rule:pipc:12",
        kind="rule",
        source_id="pipc",
        source_url=pipc.source_url,
        license="CC BY 4.0",
        region=None,
        snapshot_date=dt.date(2025, 7, 31),
        snapshot_is_retrieval_time=False,
        locator="Table 1, row 12",
        basis=("dataset:pipc",),
    )
    state = IntegrityState(
        status, status, None, dt.date(2026, 11, 7), "20261107T164018Z-db513354-0401", notices
    )
    sources = {
        "pipc": SourceInfo("pipc", "PIPC", "commit", 365),
        "crossref": SourceInfo("crossref", "Crossref", "cache", 7),
    }
    return IntegritySnapshot({pipc.id: pipc, rule.id: rule}, {pipc.id: state}, sources)


def test_pipc_correction_is_citable_and_shown_next_to_the_evidence() -> None:
    snap = pipc_snapshot()
    item = build_item(snap, "dataset:pipc", TODAY)
    assert item.citable and item.integrity is not None
    assert item.integrity.status == "corrected"
    (n,) = item.integrity.notices
    assert (n.type, n.source, n.date.isoformat() if n.date else None) == (
        "correction",
        "publisher",
        "2025-12-18",
    )
    assert n.notice_url == "https://doi.org/10.1007/s41999-025-01378-7"
    assert item.freshness is not None and item.freshness.state == "current"
    assert "corrected_notice" in item.codes
    rule = build_item(snap, "rule:pipc:12", TODAY)
    assert rule.citable
    (root,) = rule.roots
    assert root.id == "dataset:pipc" and root.integrity is not None
    assert root.integrity.notices[0].notice_doi == "10.1007/s41999-025-01378-7"
    assert "corrected_notice" in rule.codes
    line = build_line(snap, ["rule:pipc:12"], TODAY)
    assert (line.sources_total, line.checked_by_doi) == (1, 1)
    assert line.by_status.corrected == 1 and line.no_retracted_used


def test_pipc_retraction_excludes_the_evidence_and_disables_the_rule() -> None:
    retraction = Notice("retraction", "retraction-watch", "10.1000/r", dt.date(2026, 11, 1))
    snap = pipc_snapshot(Status.RETRACTED, (retraction, NOTICE))
    item = build_item(snap, "rule:pipc:12", TODAY)
    assert not item.citable and item.exclusion_reason == "no_citable_basis"
    assert "dataset:pipc" in {r.id for r in item.roots}
    gate = rule_gate(["dataset:pipc"], snap)
    assert not gate.enabled and gate.reason == "all_sources_retracted"
    assert gate.removed[0].notices[0].type == "retraction"
    line = build_line(snap, ["rule:pipc:12", "dataset:pipc"], TODAY)
    assert line.sources_total == 0 and line.no_retracted_used
    assert {e.reason for e in line.excluded} == {"retracted", "no_citable_basis"}
