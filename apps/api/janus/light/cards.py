"""Hypothesis cards: integrity filter, patient layer, codes (design §7, Req 4; P1, P3, P8, P14).

A card is a build candidate with at least one signal whose evidence ids are still citable
(`janus.integrity.citability.cite`): retracted or unregistered sources are removed and listed with
their reason, a signal left without a citable id is dropped, and a candidate left without such a
signal is not a card. The patient-reported layer joins a card as an extra signal; on its own it is a
patient-reported entry, never a card (DP7). Every card carries the rule-7 code.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from janus.integrity.citability import cite
from janus.integrity.model import IntegritySnapshot
from janus.light import messages
from janus.light.schemas import (
    CandidateOut,
    CardOut,
    CardSignalOut,
    GoalOut,
    GoalRef,
    IngredientOut,
    LightFile,
    PatientOnlyOut,
    PatientSignalOut,
    RemovedOut,
    SourceOut,
)


def source_out(snapshot: IntegritySnapshot, evidence_id: str) -> SourceOut:
    r = snapshot.records[evidence_id]
    status = snapshot.state_of(evidence_id).status.value if r.doi else "no_doi"
    return SourceOut(
        id=r.id,
        title=r.title,
        doi=r.doi,
        url=r.source_url,
        status=status,
        snapshot_date=r.snapshot_date.isoformat(),
    )


def sources_out(snapshot: IntegritySnapshot, ids: Iterable[str]) -> list[SourceOut]:
    kept = cite(snapshot, ids).kept
    return [source_out(snapshot, i) for i in kept]


@dataclass(frozen=True)
class Built:
    card: CardOut | None
    removed: tuple[RemovedOut, ...]


def ingredient_ref(light: LightFile, key: str) -> IngredientOut:
    return IngredientOut(key=key, labels=dict(light.ingredients.get(key) or {"en": key}))


def goal_ref(goal: GoalOut) -> GoalRef:
    return GoalRef(key=goal.key, labels=dict(goal.labels))


def make_card(
    light: LightFile,
    goal: GoalOut,
    cand: CandidateOut,
    snapshot: IntegritySnapshot,
    patient: Sequence[PatientSignalOut] = (),
) -> Built:
    signals: list[CardSignalOut] = []
    kept_ids: list[str] = []
    removed: dict[str, str] = {}
    if cand.label is not None:
        c = cite(snapshot, cand.label.evidence_ids)
        removed.update(dict(c.removed))
        if c.kept:
            kept_ids.extend(c.kept)
            signals.append(
                CardSignalOut(
                    type="label_effect",
                    label=cand.label,
                    codes=[
                        *messages.LABEL_CODES,
                        *(["nonspecific_term"] if cand.label.nonspecific else []),
                    ],
                )
            )
    if cand.inverse is not None:
        c = cite(snapshot, cand.inverse.evidence_ids)
        removed.update(dict(c.removed))
        if c.kept:
            kept_ids.extend(c.kept)
            signals.append(
                CardSignalOut(
                    type="inverse_faers",
                    inverse=cand.inverse,
                    codes=[
                        *messages.INVERSE_CODES,
                        *(["denominator_sensitive"] if cand.inverse.upper_bound_sensitive else []),
                    ],
                )
            )
    removed_out = tuple(RemovedOut(id=i, reason=r) for i, r in sorted(removed.items()))
    if not signals:
        return Built(None, removed_out)
    for p in patient:
        signals.append(
            CardSignalOut(type="patient_reported", patient=p, codes=list(messages.PATIENT_CODES))
        )
    seen: list[str] = []
    for i in kept_ids:
        if i not in seen:
            seen.append(i)
    return Built(
        CardOut(
            ingredient=ingredient_ref(light, cand.ingredient),
            goal=goal_ref(goal),
            rank=cand.rank,
            signals=signals,
            sources=[source_out(snapshot, i) for i in seen],
            removed_sources=list(removed_out),
            codes=list(messages.CARD_CODES),
        ),
        removed_out,
    )


@dataclass(frozen=True)
class GoalCards:
    cards: list[CardOut]
    patient_only: list[PatientOnlyOut]
    removed_by_integrity: int  # candidates that lost every citable signal


def goal_cards(
    light: LightFile,
    goal: GoalOut,
    snapshot: IntegritySnapshot,
    patient: Mapping[tuple[str, str], PatientSignalOut],
) -> GoalCards:
    """All cards of a goal in rank order, and the patient-reported entries without a card."""
    by_key: dict[str, list[PatientSignalOut]] = {}
    for (key, event), sig in sorted(patient.items()):
        if event in goal.benefit_keys:
            by_key.setdefault(key, []).append(sig)
    cards: list[CardOut] = []
    lost = 0
    with_card: set[str] = set()
    for cand in light.candidates.get(goal.key, []):
        built = make_card(light, goal, cand, snapshot, by_key.get(cand.ingredient, ()))
        if built.card is None:
            lost += 1
            continue
        cards.append(built.card)
        with_card.add(cand.ingredient)
    patient_only = [
        PatientOnlyOut(
            ingredient=ingredient_ref(light, key),
            goal=goal_ref(goal),
            signal=sig,
            codes=list(messages.PATIENT_CODES),
        )
        for key in sorted(by_key)
        if key not in with_card
        for sig in by_key[key]
    ]
    return GoalCards(cards, patient_only, lost)
