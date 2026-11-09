"""Document builder and auditor: P10-P16, P18 (doctor-loop design §4, §5.5, §13)."""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus.notes import phrases, render
from janus.notes.audit import AuditError, audit
from janus.notes.build import LanguageUnavailableError, build_document
from janus.notes.model import MedicineRow, NoteDocument, NoteInputs, Section, Sentence, StatRow
from janus.notes.templates import CATALOGUE
from tests.notes_strategies import (
    GLOSSARY_LANGS,
    all_ids,
    note_glossary,
    note_inputs,
    synthetic_glossary,
)

GLOSSARY = note_glossary()
EVERY_ID = frozenset(all_ids(list(range(1, 66))))
DISCLAIMERS = {lang: GLOSSARY.text("disclaimer", lang) for lang in GLOSSARY_LANGS}


def sentences(doc: NoteDocument) -> list[Sentence]:
    out: list[Sentence] = []
    for sec in doc.sections:
        for b in sec.blocks:
            if isinstance(b, Sentence):
                out.append(b)
            elif isinstance(b, StatRow):
                out += b.sentences
            elif b.abrupt_stop is not None:
                out.append(b.abrupt_stop)
    return out


def docs(inputs: NoteInputs) -> list[NoteDocument]:
    return [build_document(inputs, GLOSSARY, lang) for lang in GLOSSARY_LANGS]


def projection(doc: NoteDocument) -> Any:
    """Everything but the words: ids, kinds, evidence, numbers as values, data fields."""

    def value(n: str, lang: str) -> str:
        del lang
        return "".join(sorted(ch for ch in n if ch.isdigit()))  # language-free form

    out: list[Any] = []
    for sec in doc.sections:
        blocks: list[Any] = []
        for b in sec.blocks:
            if isinstance(b, Sentence):
                blocks.append(
                    (
                        b.id,
                        b.template,
                        b.kind,
                        b.evidence_ids,
                        [value(n, doc.language) for n in b.numbers],
                    )
                )
            elif isinstance(b, StatRow):
                blocks.append(
                    (
                        b.id,
                        b.finding_ids,
                        b.reports,
                        b.estimates,
                        b.citation,
                        [(s.id, s.evidence_ids) for s in b.sentences],
                    )
                )
            else:
                blocks.append(
                    (
                        b.item,
                        [
                            (i.key, i.atc) for i in b.ingredients
                        ],  # name_basis depends on the language
                        [n.reason for n in b.not_checked],
                        b.abrupt_stop is not None,
                    )
                )
        out.append((sec.id, blocks))
    return out


# --- P10 --------------------------------------------------------------------------------------


@given(inputs=note_inputs(), data=st.data())
def test_p10_every_claim_has_citable_evidence(inputs: NoteInputs, data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P10 (seed: no sentence without non-retracted evidence).
    Validates Req 1.3, 5.1, 5.3, 10.1."""
    citable = frozenset(data.draw(st.sets(st.sampled_from(sorted(EVERY_ID)))))
    out, removals = audit(docs(inputs), citable)
    for doc in out:
        for s in sentences(doc):
            if s.kind == "claim":
                assert s.evidence_ids and set(s.evidence_ids) <= citable, s.id
    # Retracting one more record only removes sentences.
    if citable:
        less = citable - {data.draw(st.sampled_from(sorted(citable)))}
        out2, _ = audit(docs(inputs), less)
        before = {s.id for s in sentences(out[0])}
        after = {s.id for s in sentences(out2[0])}
        assert after <= before
    assert len({r.sentence_id for r in removals}) == len(removals)


# --- P11 --------------------------------------------------------------------------------------


@given(inputs=note_inputs())
def test_p11_disclaimer_and_no_forbidden_phrase(inputs: NoteInputs) -> None:
    """Feature: doctor-loop, Property P11 (seed: disclaimer and phrases per language).
    Validates Req 1.4, 1.10, 14.1, 14.2."""
    out, _ = audit(docs(inputs), EVERY_ID)
    for doc in out:
        header = doc.sections[0]
        assert header.id == "header"
        texts = [s.text for s in sentences(doc)]
        assert [
            b.text for b in header.blocks if isinstance(b, Sentence) and b.template == "disclaimer"
        ] == [DISCLAIMERS[doc.language]]
        assert texts.count(DISCLAIMERS[doc.language]) == 1
        for t in texts:
            assert phrases.violations(t, doc.language) == ([], [])


# --- P12 --------------------------------------------------------------------------------------


@given(
    inputs=note_inputs(),
    pair=st.lists(st.sampled_from(GLOSSARY_LANGS), min_size=2, max_size=2, unique=True),
)
def test_p12_language_never_changes_content(inputs: NoteInputs, pair: list[str]) -> None:
    """Feature: doctor-loop, Property P12 (seed: language invariance). Req 1.5, 1.6, 4.5."""
    a, b = (build_document(inputs, GLOSSARY, lang) for lang in pair)
    assert projection(a) == projection(b)
    (a2, b2), _ = audit([a, b], EVERY_ID - {"dataset:faers"})
    assert projection(a2) == projection(b2)


# --- P13 (document part) ----------------------------------------------------------------------


@given(inputs=note_inputs())
def test_p13_numbers_come_from_inputs(inputs: NoteInputs) -> None:
    """Feature: doctor-loop, Property P13 (document). Validates Req 5.2, 5.3."""
    for doc in docs(inputs):
        for s in sentences(doc):
            if s.kind == "claim":
                assert not any(ch.isdigit() for ch in render.residue(s.text, s.numbers))
                template = GLOSSARY.text(s.template, doc.language)
                assert not any(ch.isdigit() for ch in template)


# --- P14 --------------------------------------------------------------------------------------


@given(inputs=note_inputs(), data=st.data())
def test_p14_auditor_removes_exactly_the_defects(inputs: NoteInputs, data: st.DataObject) -> None:
    """Feature: doctor-loop, Property P14. Validates Req 5.3-5.5."""
    built = docs(inputs)
    clean, none = audit(built, EVERY_ID)
    assert none == [] and clean == built  # an accepted glossary and full evidence remove nothing
    claims = [s for s in sentences(built[0]) if s.kind == "claim"]
    if not claims:
        return
    target = data.draw(st.sampled_from(claims))
    defect = data.draw(st.sampled_from(["no_evidence", "forbidden_phrase", "foreign_number"]))
    lang_index = data.draw(st.integers(0, len(built) - 1))
    lang = built[lang_index].language

    def damage(s: Sentence) -> Sentence:
        if s.id != target.id:
            return s
        if defect == "no_evidence":
            return s.model_copy(update={"evidence_ids": []})
        if defect == "forbidden_phrase":
            return s.model_copy(update={"text": s.text + " " + phrases.FORBIDDEN[lang][0]})
        return s.model_copy(update={"text": s.text + " 7777"})

    hurt = list(built)
    hurt[lang_index] = _map_sentences(built[lang_index], damage)
    out, removals = audit(hurt, EVERY_ID)
    assert [(r.sentence_id, r.reason) for r in removals] == [(target.id, defect)]
    for doc, orig in zip(out, built, strict=True):
        ids = {s.id for s in sentences(doc)}
        orig_ids = {s.id for s in sentences(orig)}
        assert target.id not in ids
        # Everything else stays, except the rest of a statistic row whose main sentence went.
        lost = orig_ids - ids - {target.id}
        assert all(i.startswith(target.id.rsplit(":", 1)[0]) for i in lost)
    again, more = audit(out, EVERY_ID)
    assert again == out and more == []


def _map_sentences(doc: NoteDocument, fn: Callable[[Sentence], Sentence]) -> NoteDocument:
    sections: list[Section] = []
    for sec in doc.sections:
        blocks: list[Any] = []
        for b in sec.blocks:
            if isinstance(b, Sentence):
                blocks.append(fn(b))
            elif isinstance(b, StatRow):
                blocks.append(b.model_copy(update={"sentences": [fn(s) for s in b.sentences]}))
            else:
                blocks.append(b)
        sections.append(sec.model_copy(update={"blocks": blocks}))
    return doc.model_copy(update={"sections": sections})


@given(inputs=note_inputs())
def test_p14_fixed_text_defect_raises(inputs: NoteInputs) -> None:
    built = docs(inputs)
    bad = _map_sentences(
        built[0],
        lambda s: (
            s.model_copy(update={"text": s.text + " cure"}) if s.template == "disclaimer" else s
        ),
    )
    with pytest.raises(AuditError):
        audit([bad], EVERY_ID)


# --- P15 --------------------------------------------------------------------------------------


@given(inputs=note_inputs())
def test_p15_medicine_rows(inputs: NoteInputs) -> None:
    """Feature: doctor-loop, Property P15. Validates Req 1.1, 8.1, 8.3."""
    warned = {w.item for w in inputs.result.item_warnings}
    for doc in docs(inputs):
        meds = next(s for s in doc.sections if s.id == "medicines")
        rows = [b for b in meds.blocks if isinstance(b, MedicineRow)]
        assert [r.item for r in rows] == [it.item for it in inputs.items]
        for r in rows:
            assert (r.abrupt_stop is not None) == (r.item in warned)
            if r.abrupt_stop is not None:
                assert r.abrupt_stop.text == GLOSSARY.text("abrupt_stop", doc.language)
                assert r.abrupt_stop.kind == "fixed"
            expected = sorted(
                (n.position, n.reason) for n in inputs.result.not_checked if n.item == r.item
            )
            assert [(n.position, n.reason) for n in r.not_checked] == expected
            assert r.product_name_slot is True
            for ing in r.ingredients:
                assert ing.atc
                assert (ing.tag is None) == (ing.name_basis == "glossary")
    # The abrupt-stop line survives any evidence state.
    out, _ = audit(docs(inputs), frozenset())
    for doc in out:
        lines = [s for s in sentences(doc) if s.template == "abrupt_stop"]
        assert len(lines) == len(warned)


# --- P16 --------------------------------------------------------------------------------------


@given(inputs=note_inputs())
def test_p16_each_finding_in_one_section(inputs: NoteInputs) -> None:
    """Feature: doctor-loop, Property P16. Validates Req 8.2."""
    doc = build_document(inputs, GLOSSARY, "en")
    where: dict[str, list[str]] = {}
    for sec in doc.sections:
        for b in sec.blocks:
            if isinstance(b, Sentence) and b.template == "finding.cascade":
                where.setdefault(b.id.rsplit(":", 1)[0], []).append(sec.id)
    for f in inputs.result.findings:
        assert where[f.finding_id] == [
            "findings" if f.form_confirmed else "findings_form_unconfirmed"
        ]
    ids = [s.id for s in doc.sections]
    unconfirmed = any(not f.form_confirmed for f in inputs.result.findings)
    assert ("findings_form_unconfirmed" in ids) == unconfirmed
    if unconfirmed:
        sec = next(s for s in doc.sections if s.id == "findings_form_unconfirmed")
        first = sec.blocks[0]
        assert (
            isinstance(first, Sentence)
            and first.template == "findings_form_unconfirmed.explanation"
        )


# --- P18 --------------------------------------------------------------------------------------


@given(inputs=note_inputs())
def test_p18_safety_lines_first(inputs: NoteInputs) -> None:
    """Feature: doctor-loop, Property P18. Validates Req 9.5."""
    expected = sorted(
        {
            inputs.safety_lines[k]
            for f in inputs.result.findings
            if (k := inputs.event_keys[int(f.rule_id.split(":")[1])]) in inputs.safety_lines
        }
    )
    for doc in docs(inputs):
        ids = [s.id for s in doc.sections]
        if not expected:
            assert "safety" not in ids
            continue
        assert ids.index("safety") < ids.index("findings")
        sec = doc.sections[ids.index("safety")]
        templates = [b.template for b in sec.blocks if isinstance(b, Sentence)]
        assert templates == ["safety.emergency_first", *(f"safety.{line}" for line in expected)]
        number = GLOSSARY.text(f"emergency.{inputs.user_region}", doc.language)
        first = sec.blocks[0]
        assert isinstance(first, Sentence) and number in first.text


def test_unavailable_language_is_refused() -> None:
    proposed = synthetic_glossary(status="proposed")
    with pytest.raises(LanguageUnavailableError):
        build_document(_example(), proposed, "en")


def _example() -> NoteInputs:
    from hypothesis import find

    return find(note_inputs(), lambda i: bool(i.result.findings))


def test_catalogue_kinds_cover_the_builder() -> None:
    assert all(s.kind != "claim" or s.evidence for s in CATALOGUE.values())


# --- owner decisions of 2026-11-08 (P35-P38) ----------------------------------------------------


@given(inputs=note_inputs())
def test_p35_timing_cites_the_window_and_row_49_is_explained(inputs: NoteInputs) -> None:
    """Feature: doctor-loop, Property P35 (decisions 6 and 8). Validates Req 1.3, 5.1."""
    doc = build_document(inputs, GLOSSARY, "en")
    for f in inputs.result.findings:
        timing = [s for s in sentences(doc) if s.id == f"{f.finding_id}:timing"]
        assert len(timing) == 1
        if f.timing in ("within_window", "after_window"):
            assert inputs.roles.window in timing[0].evidence_ids  # both cite the window paper
            assert f"rule:pipc:{int(f.rule_id.split(':')[1])}" in timing[0].evidence_ids
            assert str(f.months_between) in timing[0].numbers
            assert str(inputs.result.window_months) in timing[0].numbers
        row49 = [s for s in sentences(doc) if s.id == f"{f.finding_id}:row49"]
        assert len(row49) == (1 if f.rule_id == "pipc:49" else 0)
        for s in row49:
            assert {"dataset:pipc", "rule:pipc:49"} <= set(s.evidence_ids)
    # Retracting the window paper removes the timing sentences of dated findings only.
    citable = EVERY_ID - {inputs.roles.window}
    _, removals = audit([doc], citable)
    gone = {r.sentence_id for r in removals}
    dated = {
        f"{f.finding_id}:timing"
        for f in inputs.result.findings
        if f.timing in ("within_window", "after_window")
    }
    assert dated <= gone
    cites = {s.id: s.evidence_ids for s in sentences(doc)}
    assert all(inputs.roles.window in cites[i] for i in gone)  # only sentences resting on it go


@given(inputs=note_inputs())
def test_p36_statistics_use_the_clinical_event_name(inputs: NoteInputs) -> None:
    """Feature: doctor-loop, Property P36 (decision 7). Validates Req 9.1."""
    findings = {f.finding_id: f for f in inputs.result.findings}
    for lang in GLOSSARY_LANGS:
        doc = build_document(inputs, GLOSSARY, lang)
        for sec in doc.sections:
            for b in sec.blocks:
                if not isinstance(b, StatRow):
                    continue
                f = findings[b.finding_ids[0]]
                clinical = inputs.rule_texts[int(f.rule_id.split(":")[1])]
                want = clinical[1] if lang == "en" else f"{clinical[1]} {lang}"
                main = b.sentences[0]
                assert want in main.text
                assert inputs.event_labels[b.event_key][lang] not in main.text


@given(inputs=note_inputs(), data=st.data())
def test_p37_a_reviewed_combination_code_is_labelled(
    inputs: NoteInputs, data: st.DataObject
) -> None:
    """Feature: doctor-loop, Property P37 (decision 10). Validates Req 1.1."""
    pairs = {(ing.key, code) for it in inputs.items for ing in it.ingredients for code in ing.codes}
    chosen = frozenset(data.draw(st.sets(st.sampled_from(sorted(pairs)))))
    doc = build_document(dataclasses.replace(inputs, component_pairs=chosen), GLOSSARY, "de")
    meds = next(s for s in doc.sections if s.id == "medicines")
    for row in meds.blocks:
        if not isinstance(row, MedicineRow):
            continue
        for ing in row.ingredients:
            labelled = any((ing.key, c) in chosen for c in ing.atc)
            assert (ing.combination_code is not None) == labelled
            if labelled:
                assert ing.combination_code is not None
                assert ing.combination_code.text == GLOSSARY.text("name.combination_code", "de")
    plain = build_document(inputs, GLOSSARY, "de")
    assert all(
        ing.combination_code is None
        for row in next(s for s in plain.sections if s.id == "medicines").blocks
        if isinstance(row, MedicineRow)
        for ing in row.ingredients
    )


@given(inputs=note_inputs())
def test_p39_medicines_count_splits_fully_and_partly_checked(inputs: NoteInputs) -> None:
    """Feature: doctor-loop, Property P39 (DP42, owner decision 2026-11-09): the medicines
    section opens with one count sentence; its numbers are the rows, the rows without a
    not-checked entry and the rows with one."""
    for doc in docs(inputs):
        meds = next(s for s in doc.sections if s.id == "medicines")
        first = meds.blocks[0]
        assert isinstance(first, Sentence)
        assert first.id == "medicines:count" and first.kind == "fixed"
        rows = [b for b in meds.blocks if isinstance(b, MedicineRow)]
        partly = sum(1 for r in rows if r.not_checked)
        want = [len(rows), len(rows) - partly, partly]
        assert [int(n) for n in first.numbers] == want
        assert sum(1 for b in meds.blocks if isinstance(b, Sentence)) == 1


def test_p38_the_note_only_texts_are_not_the_shared_patient_texts() -> None:
    """Feature: doctor-loop, Property P38 (decision 6). Validates Req 14.1."""
    for tid in ("stat.absence", "stat.denominator"):
        assert CATALOGUE[tid].shared is None
    from janus.notes import glossary as gl

    real = gl.load()
    for lang in GLOSSARY_LANGS:
        assert "your medicines" not in real.text("stat.absence", lang).lower() or lang != "en"
        assert real.text("stat.denominator", lang)
    assert "Figures for all reports" not in real.text("stat.denominator", "en")
    assert "patient's medicines" in real.text("stat.absence", "en")
