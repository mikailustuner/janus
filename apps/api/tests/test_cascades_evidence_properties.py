"""Evidence in the engine: P7, P13 and examples (cascade-engine design §4.4, §9; task 7)."""

from __future__ import annotations

from hypothesis import assume, given
from hypothesis import strategies as st

from janus.cascades.engine import evaluate
from janus.cascades.model import EngineIngredient, EngineItem, RuleBase
from janus.integrity.citability import verdict_map
from janus.integrity.model import IntegritySnapshot, Status
from tests.cascades_strategies import (
    MONTH0,
    TODAY,
    cascade_snapshot,
    doi_ids,
    engine_items,
    rule_bases,
)
from tests.integrity_strategies import with_status
from tests.test_cascades_rules_properties import real_rule_base

STATUSES = st.sampled_from(list(Status))


@st.composite
def snapshots_for(draw: st.DrawFn, rb: RuleBase) -> IntegritySnapshot:
    statuses = {i: draw(STATUSES) for i in doi_ids(rb)}
    return cascade_snapshot(rb, statuses)


@given(rb=rule_bases(), items=engine_items(), data=st.data())
def test_p7_evidence_completeness(
    rb: RuleBase, items: list[EngineItem], data: st.DataObject
) -> None:
    """Feature: cascade-engine, Property 7. Validates: Req 1.5, 2.7.

    Every finding's evidence ids are citable and registered with an https source URL, include
    the rule and the PIPC paper, and exclude every removed id.
    """
    snap = data.draw(snapshots_for(rb))
    verdicts = verdict_map(snap)
    res = evaluate(items, rb, snap, TODAY)
    for f in res.findings:
        assert f.evidence_ids
        assert f.rule.evidence_id in f.evidence_ids and rb.source_paper_id in f.evidence_ids
        for i in f.evidence_ids:
            assert verdicts[i].citable
            assert snap.records[i].source_url.startswith("https://")
        assert not {i for i, _ in f.excluded_evidence} & set(f.evidence_ids)


@given(rb=rule_bases(), items=engine_items(), data=st.data())
def test_p13_gates_only_remove(rb: RuleBase, items: list[EngineItem], data: st.DataObject) -> None:
    """Feature: cascade-engine, Property 13. Validates: Req 1.5, 2.2, 6.1, 7.4.

    Retracting any record only removes findings, priority, form extensions and `probable`;
    disabled rules yield nothing; restoring the status restores the result.
    """
    snap = data.draw(snapshots_for(rb))
    live = [i for i in doi_ids(rb) if snap.state_of(i).status != Status.RETRACTED]
    assume(live)
    target = data.draw(st.sampled_from(live))
    before = evaluate(items, rb, snap, TODAY)
    retracted = with_status(
        snap, target, cascade_snapshot(rb, {target: Status.RETRACTED}).states[target]
    )
    after = evaluate(items, rb, retracted, TODAY)
    b = {f.finding_id: f for f in before.findings}
    for f in after.findings:
        assert f.finding_id in b
        old = b[f.finding_id]
        assert f.priority is None or old.priority is not None
        assert not f.via_form_extension or old.via_form_extension
        assert f.status != "probable" or old.status == "probable"
    disabled_before = {d.rule_id for d in before.disabled}
    disabled_after = {d.rule_id for d in after.disabled}
    assert disabled_before <= disabled_after
    assert not {f.rule.rule_id for f in after.findings} & disabled_after
    for d in after.disabled:
        assert d.reason in ("no_source", "all_sources_retracted", "no_citable_source")
        assert d.removed
    restored = with_status(retracted, target, snap.state_of(target))
    assert evaluate(items, rb, restored, TODAY) == before


# --- Examples on the real curated files (task 7.3) ------------------------------------------------


def _item(index: int, start: int, qid: str, code: str, confirmed: bool = True) -> EngineItem:
    return EngineItem(index, start, (EngineIngredient(qid, frozenset({code}), confirmed),))


def test_pipc_correction_notice_on_every_finding() -> None:
    """The PIPC correction gives `corrected_notice` on every finding. Req 1.5."""
    rb = real_rule_base()
    snap = cascade_snapshot(rb, {rb.source_paper_id: Status.CORRECTED})
    items = [_item(0, MONTH0, "Q1", "C08CA01"), _item(1, MONTH0 + 4, "Q2", "C03CA01")]
    res = evaluate(items, rb, snap, TODAY)
    assert {f.rule.position for f in res.findings} >= {5}
    assert all("corrected_notice" in f.integrity_codes for f in res.findings)


def test_bmj_rows_only() -> None:
    """BMJ 2026 data sits on rows 9, 25, 26, 47, 60 and 65 only. Req 6.1."""
    rb = real_rule_base()
    assert sorted(r.position for r in rb.rules if r.priority) == [9, 25, 26, 47, 60, 65]
    snap = cascade_snapshot(rb)
    statin_then_paracetamol = [
        _item(0, MONTH0, "Q1", "C10AA05"),
        _item(1, MONTH0 + 3, "Q2", "N02BE01"),
    ]
    f9 = [
        f
        for f in evaluate(statin_then_paracetamol, rb, snap, TODAY).findings
        if f.rule.position == 9
    ]
    assert f9 and f9[0].priority is not None and f9[0].priority.value == "10.9"
    withdrawn = cascade_snapshot(rb, {"paper:bmj_2026:e100499": Status.RETRACTED})
    f9b = [
        f
        for f in evaluate(statin_then_paracetamol, rb, withdrawn, TODAY).findings
        if f.rule.position == 9
    ]
    assert f9b and f9b[0].priority is None  # the rule stays; only the priority data goes (DP5)


def test_timolol_eye_drops() -> None:
    """Eye-drop timolol starts row 3 (extension) and is never the row 17 marker. Req 7.4."""
    rb = real_rule_base()
    snap = cascade_snapshot(rb)
    eye_then_sertraline = [_item(0, MONTH0, "Q1", "S01ED01"), _item(1, MONTH0 + 6, "Q2", "N06AB06")]
    rows = {f.rule.position: f for f in evaluate(eye_then_sertraline, rb, snap, TODAY).findings}
    assert 3 in rows and rows[3].via_form_extension
    assert "paper:vander_zanden_2001:aph_18464" in rows[3].evidence_ids
    assert 4 not in rows
    risperidone_then_eye = [
        _item(0, MONTH0, "Q3", "N05AX08"),
        _item(1, MONTH0 + 2, "Q1", "S01ED01"),
    ]
    assert 17 not in {
        f.rule.position for f in evaluate(risperidone_then_eye, rb, snap, TODAY).findings
    }
    no_extension = cascade_snapshot(rb, {"paper:vander_zanden_2001:aph_18464": Status.RETRACTED})
    assert 3 not in {
        f.rule.position for f in evaluate(eye_then_sertraline, rb, no_extension, TODAY).findings
    }


def test_prednisolone_eye_drops_never_trigger_corticosteroid_rows() -> None:
    """Eye-drop prednisolone (S01BA04) never starts rows 59-61. Req 7.4."""
    rb = real_rule_base()
    snap = cascade_snapshot(rb)
    items = [
        _item(0, MONTH0, "Q1", "S01BA04"),
        _item(1, MONTH0 + 2, "Q2", "N05CF02"),
        _item(2, MONTH0 + 3, "Q3", "N05AX08"),
        _item(3, MONTH0 + 4, "Q4", "C09AA05"),
    ]
    rows = {f.rule.position for f in evaluate(items, rb, snap, TODAY).findings}
    assert not rows & {59, 60, 61}
    oral = [_item(0, MONTH0, "Q1", "H02AB06"), *items[1:]]
    assert {59, 60, 61} <= {f.rule.position for f in evaluate(oral, rb, snap, TODAY).findings}


# --- Owner decisions on the synonym review (2026-11-07) -----------------------------------------


def test_dimenhydrinate_key_keeps_its_own_classes() -> None:
    """Dimenhydrinate (Janus key J1, R06AA11) is a vestibular suppressant and an antiemetic,
    not a sleep agent (rows 56 and 2), because it keeps its own code."""
    rb = real_rule_base()
    snap = cascade_snapshot(rb)
    doxazosin = _item(0, MONTH0, "Q1", "C02CA04")
    dimen = _item(1, MONTH0 + 2, "J1", "R06AA11")
    rows = {f.rule.position for f in evaluate([doxazosin, dimen], rb, snap, TODAY).findings}
    assert {2, 56} <= rows
    statin = _item(0, MONTH0, "Q2", "C10AA05")
    assert 12 not in {f.rule.position for f in evaluate([statin, dimen], rb, snap, TODAY).findings}


def test_codeine_gets_the_abrupt_stop_warning() -> None:
    """Codeine carries only R05DA04 in Wikidata; it is on the abrupt-stop list (opioid)."""
    rb = real_rule_base()
    res = evaluate([_item(0, MONTH0, "Q174723", "R05DA04")], rb, cascade_snapshot(rb), TODAY)
    assert [(w.item, w.ingredient_key) for w in res.item_warnings] == [(0, "Q174723")]


def test_iron_sucrose_code_is_not_a_ppi_deficiency_supplement() -> None:
    """B03AB02 (intravenous iron sucrose in Wikidata) is excluded from row 49, as in row 65."""
    rb = real_rule_base()
    snap = cascade_snapshot(rb)
    omeprazole = _item(0, MONTH0, "Q1", "A02BC01")
    iv_iron = _item(1, MONTH0 + 3, "Q2", "B03AB02")
    oral_iron = _item(1, MONTH0 + 3, "Q2", "B03AA07")
    assert 49 not in {
        f.rule.position for f in evaluate([omeprazole, iv_iron], rb, snap, TODAY).findings
    }
    assert 49 in {
        f.rule.position for f in evaluate([omeprazole, oral_iron], rb, snap, TODAY).findings
    }
