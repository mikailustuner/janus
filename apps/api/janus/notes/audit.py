"""The auditor (doctor-loop design §5.5, Req 5.3-5.5). Pure.

Runs on every note document before it is returned. A claim sentence is removed, in every language
of the response, when it carries no evidence id, an id that is not citable, a forbidden phrase or
reassurance word of its language, or a numeral that is not one of its own formatted inputs. A
statistic row goes with its main sentence. Fixed texts are never removed: a defect there means the
glossary loader let something through, which is a programming error (`AuditError`).
"""

from __future__ import annotations

from collections.abc import Sequence, Set
from typing import Final

from janus.notes import phrases, render
from janus.notes.model import (
    MedicineRow,
    NoteDocument,
    Removal,
    RemovalReason,
    Section,
    Sentence,
    StatRow,
)

REASON_ORDER: Final[tuple[RemovalReason, ...]] = (
    "no_evidence",
    "evidence_not_citable",
    "forbidden_phrase",
    "reassurance_word",
    "foreign_number",
)


class AuditError(RuntimeError):
    """A fixed text failed a check. The message holds the sentence id only."""


def _sentences(doc: NoteDocument) -> list[Sentence]:
    out: list[Sentence] = []
    for section in doc.sections:
        for block in section.blocks:
            if isinstance(block, Sentence):
                out.append(block)
            elif isinstance(block, StatRow):
                out += block.sentences
            elif block.abrupt_stop is not None:
                out.append(block.abrupt_stop)
    return out


def _reason(s: Sentence, lang: str, citable: Set[str]) -> RemovalReason | None:
    if not s.evidence_ids:
        return "no_evidence"
    if any(i not in citable for i in s.evidence_ids):
        return "evidence_not_citable"
    forbidden, reassurance = phrases.violations(s.text, lang)
    if forbidden:
        return "forbidden_phrase"
    if reassurance:
        return "reassurance_word"
    if any(ch.isdigit() for ch in render.residue(s.text, s.numbers)):
        return "foreign_number"
    return None


def _check_fixed(s: Sentence, lang: str) -> None:
    forbidden, reassurance = phrases.violations(s.text, lang)
    if forbidden or reassurance:
        raise AuditError(s.id)


def _keep(section: Section, removed: Set[str]) -> Section:
    blocks: list[Sentence | MedicineRow | StatRow] = []
    for block in section.blocks:
        if isinstance(block, Sentence):
            if block.id not in removed:
                blocks.append(block)
        elif isinstance(block, StatRow):
            if block.sentences and block.sentences[0].id in removed:
                continue
            kept = [s for s in block.sentences if s.id not in removed]
            blocks.append(block.model_copy(update={"sentences": kept}))
        else:
            blocks.append(block)
    return section.model_copy(update={"blocks": blocks})


def audit(
    documents: Sequence[NoteDocument], citable: Set[str]
) -> tuple[list[NoteDocument], list[Removal]]:
    reasons: dict[str, RemovalReason] = {}
    for doc in documents:
        for s in _sentences(doc):
            if s.kind == "fixed":
                _check_fixed(s, doc.language)
                continue
            r = _reason(s, doc.language, citable)
            if r is not None:
                old = reasons.get(s.id)
                if old is None or REASON_ORDER.index(r) < REASON_ORDER.index(old):
                    reasons[s.id] = r
    removed = set(reasons)
    out = [
        doc.model_copy(update={"sections": [_keep(sec, removed) for sec in doc.sections]})
        for doc in documents
    ]
    removals = [Removal(sentence_id=i, reason=reasons[i]) for i in sorted(reasons)]
    return out, removals
