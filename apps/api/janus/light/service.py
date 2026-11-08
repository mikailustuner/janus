"""Light-face answers (design §9).

Pure orchestration over the build file, the integrity snapshot and the released patient layer;
the router does the I/O.
"""

from __future__ import annotations

from collections.abc import Mapping

from janus.integrity.model import IntegritySnapshot
from janus.light import messages
from janus.light.cards import GoalCards, goal_cards, goal_ref, sources_out
from janus.light.schemas import (
    CardsIn,
    CardsOut,
    ExportOut,
    ExportRowOut,
    GoalOut,
    GoalSummaryOut,
    LightFile,
    OverviewOut,
    PatientSignalOut,
    SnapshotOut,
    ValidationOut,
)
from janus.memory import messages as memory_messages


class UnknownGoalError(ValueError):
    """The goal key is not in the build. Never echoed."""


def snapshot_of(light: LightFile) -> SnapshotOut:
    i = light.inputs
    return SnapshotOut(
        build_id=light.build_id,
        onsides_release=i.onsides_release,
        onsides_date=i.onsides_date,
        faers_snapshot_date=i.faers_snapshot_date,
        faers_window=list(i.faers_window),
        openfda_date=i.openfda_date,
    )


def attribution() -> list[str]:
    return [
        messages.ATTRIBUTION_ONSIDES,
        messages.ATTRIBUTION_FAERS,
        memory_messages.MEDDRA_NOTICE,
    ]


def page_codes(light: LightFile) -> list[str]:
    return [light.validation.status, "candidate_not_treatment", *messages.PAGE_CODES]


def _common(light: LightFile) -> dict[str, object]:
    return {
        "status": light.validation.status,
        "snapshot": snapshot_of(light),
        "codes": page_codes(light),
        "disclaimer": messages.DISCLAIMER,
        "attribution": attribution(),
    }


def goal_summaries(light: LightFile) -> list[GoalSummaryOut]:
    return [
        GoalSummaryOut(
            key=g.key,
            labels=dict(g.labels),
            candidates=len(light.candidates.get(g.key, [])),
            label_terms=list(g.label_terms),
            faers_pts=list(g.faers_pts),
            benefit_keys=list(g.benefit_keys),
            inverse_tested=g.inverse_tested,
            inverse_found=g.inverse_found,
            inverse_expected_by_chance=g.inverse_expected_by_chance,
        )
        for g in light.goals
    ]


def overview(light: LightFile) -> OverviewOut:
    return OverviewOut(
        **_common(light),  # pyright: ignore[reportArgumentType]
        goals=goal_summaries(light),
        top_k=light.validation.top_k,
    )


def find_goal(light: LightFile, key: str) -> GoalOut:
    goal = next((g for g in light.goals if g.key == key), None)
    if goal is None:
        raise UnknownGoalError("unknown goal")
    return goal


def cards(
    light: LightFile,
    req: CardsIn,
    snapshot: IntegritySnapshot,
    patient: Mapping[tuple[str, str], PatientSignalOut] | None,
) -> CardsOut:
    """`patient` None = the patient layer is unavailable (no database or no noise key)."""
    goal = find_goal(light, req.goal)
    gc: GoalCards = goal_cards(light, goal, snapshot, patient or {})
    return CardsOut(
        **_common(light),  # pyright: ignore[reportArgumentType]
        goal=goal_ref(goal),
        total=len(gc.cards),
        offset=req.offset,
        cards=gc.cards[req.offset : req.offset + req.limit],
        patient_reported=gc.patient_only,
        patient_layer="ok" if patient is not None else "layer_unavailable",
        removed_by_integrity=gc.removed_by_integrity,
        warning_sources=sources_out(snapshot, messages.INVERSE_WARNING_EVIDENCE),
    )


def validation(light: LightFile, snapshot: IntegritySnapshot) -> ValidationOut:
    v = light.validation
    ids = sorted(
        {e for c in v.cases for e in c.case.evidence_ids}
        | {"dataset:onsides", "dataset:faers", "dataset:openfda_label"}
    )
    keys = sorted({c.case.ingredient_key for c in v.cases})
    return ValidationOut(
        **_common(light),  # pyright: ignore[reportArgumentType]
        top_k=v.top_k,
        cases=v.cases,
        primary=v.primary,
        sensitivity=v.sensitivity,
        goals=[goal_ref(g) for g in light.goals if any(c.case.goal == g.key for c in v.cases)],
        ingredients={k: dict(light.ingredients.get(k) or {"en": k}) for k in keys},
        sources=sources_out(snapshot, ids),
    )


def export(
    light: LightFile,
    snapshot: IntegritySnapshot,
    patient: Mapping[tuple[str, str], PatientSignalOut] | None,
) -> ExportOut:
    """Every card of every goal as a flat row (the same filter as the screens; P14)."""
    rows: list[ExportRowOut] = []
    for goal in light.goals:
        gc = goal_cards(light, goal, snapshot, patient or {})
        for card in gc.cards:
            label = next((s.label for s in card.signals if s.label is not None), None)
            inverse = next((s.inverse for s in card.signals if s.inverse is not None), None)
            pats = [s.patient for s in card.signals if s.patient is not None]
            est = inverse.stats.estimates if inverse else None
            rows.append(
                ExportRowOut(
                    goal=goal.key,
                    ingredient=card.ingredient.key,
                    ingredient_name_en=card.ingredient.labels.get("en", card.ingredient.key),
                    rank_best=card.rank.best,
                    rank_worst=card.rank.worst,
                    population=card.rank.population,
                    signal_types=[s.type for s in card.signals],
                    label_regions=list(label.regions) if label else [],
                    labels_with_effect=label.labels_with_effect if label else None,
                    labels_total=label.labels_total if label else None,
                    label_terms=list(label.terms) if label else [],
                    faers_reports=inverse.reports if inverse else None,
                    faers_ror=est.ror if est else None,
                    faers_ror_low=est.ror_ci.low if est else None,
                    faers_ror_high=est.ror_ci.high if est else None,
                    patient_reported_released=sum(p.total_of_released for p in pats)
                    if pats
                    else None,
                    source_ids=[s.id for s in card.sources],
                )
            )
    common = _common(light)
    common["codes"] = [*page_codes(light), "export_aggregated"]
    return ExportOut(
        **common,  # pyright: ignore[reportArgumentType]
        licence=messages.EXPORT_LICENCE,
        rows=rows,
        goals=goal_summaries(light),
    )
