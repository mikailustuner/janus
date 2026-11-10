"""`POST /safety/check`: the list read once in a read-only transaction, then the pure checks
(safety-check design §3). Nothing is written and nothing of the request is logged."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from urllib.parse import quote

import psycopg

from janus.cascades import service as cascades
from janus.cascades.model import EngineItem
from janus.cascades.schemas import EvaluateIn, NotCheckedOut
from janus.integrity.freshness import is_stale
from janus.resolution import service as resolution
from janus.resolution.model import SourceRef
from janus.resolution.names import fold
from janus.safety import burden, duplication, interactions, repository
from janus.safety.schemas import (
    DAILYMED_LABEL_URL,
    LABEL_SOURCE_URL,
    LABEL_TERMS_URL,
    NO_DUPLICATION,
    NO_LABEL_PASSAGE,
    BurdenContributionOut,
    BurdenDrugOut,
    BurdenNotice,
    BurdenOut,
    BurdenScaleOut,
    DuplicationFindingOut,
    DuplicationOut,
    IngredientRefOut,
    InteractionFindingOut,
    InteractionNotice,
    InteractionsOut,
    LabelOut,
    LabelReadOut,
    LabelSourceOut,
    MemberOut,
    PassageOut,
    SafetyCheckOut,
    StatementOut,
)
from janus.safety.store import SOURCE_ID as LABEL_SOURCE_ID
from janus.safety.store import Loaded as LoadedLabels

LABEL_CADENCE_DAYS = 30  # pipelines/sources.toml, openfda_label_interactions
LABEL_NOTICES: tuple[InteractionNotice, ...] = (
    "us_labels_only",
    "one_label_per_substance",
    "quoted_label_text_not_an_assessment",
    "names_matched_automatically",
    "passage_may_state_no_effect",
    "classes_not_matched",
    "absence_is_not_clearance",
)


class SafetyUnavailableError(RuntimeError):
    """The resolution dataset is not loaded."""


def code_sources(found: resolution.RuleInputs) -> list[SourceRef]:
    """The distinct sources (with snapshot dates) of the ATC codes of the request's items."""
    codes = [a for p in found.products.values() for ing in p.ingredients for a in ing.atc_codes]
    codes += [a for c in found.ingredients.values() for a in c.atc_codes]
    refs = {(a.source.source_id, a.source.snapshot_date, a.source.run_id): a.source for a in codes}
    return [refs[k] for k in sorted(refs)]


def duplication_out(items: list[EngineItem], sources: list[SourceRef]) -> DuplicationOut:
    findings = duplication.find(items)
    return DuplicationOut(
        rules_version=duplication.RULES_VERSION,
        findings=[
            DuplicationFindingOut(
                finding_id=f.finding_id,
                kind=f.kind,
                atc_group=f.group,
                members=[
                    MemberOut(
                        ingredient_key=m.key,
                        label_en=m.label_en,
                        items=list(m.items),
                        codes=list(m.codes),
                        form_confirmed=m.form_confirmed,
                    )
                    for m in f.members
                ],
                items=list(f.items),
                form_confirmed=f.form_confirmed,
            )
            for f in findings
        ],
        sources=sources,
        statement=None
        if findings
        else StatementOut(code="no_duplication_found", text=NO_DUPLICATION),
        notices=["between_list_items_only", "residual_groups_not_compared", "may_be_intended"],
    )


def _ref(s: interactions.Subject) -> IngredientRefOut:
    return IngredientRefOut(ingredient_key=s.key, label_en=s.label_en, items=list(s.items))


def _label(lab: interactions.Label) -> LabelOut:
    return LabelOut(
        substance_name=lab.substance_name,
        set_id=lab.set_id,
        version=lab.version,
        effective_date=dt.date.fromisoformat(lab.effective_date) if lab.effective_date else None,
        product_type=lab.product_type,
        url=DAILYMED_LABEL_URL.format(quote(lab.set_id, safe="")),
    )


def interactions_unavailable() -> InteractionsOut:
    return InteractionsOut(
        status="unavailable",
        rules_version=interactions.RULES_VERSION,
        source=None,
        findings=[],
        total_findings=0,
        truncated=False,
        labels_read=[],
        labels_not_found=[],
        statement=None,
        notices=[],
    )


def interactions_out(
    subs: Sequence[interactions.Subject], loaded: LoadedLabels, today: dt.date
) -> InteractionsOut:
    """The label passages for the list's ingredients on the day `today`."""
    res = interactions.find(subs, loaded.labels)
    notices = list(LABEL_NOTICES)
    if is_stale(loaded.snapshot_date, today, LABEL_CADENCE_DAYS):
        notices.append("snapshot_outdated")
    return InteractionsOut(
        status="checked",
        rules_version=interactions.RULES_VERSION,
        source=LabelSourceOut(
            source_id=LABEL_SOURCE_ID,
            run_id=loaded.run_id,
            snapshot_date=loaded.snapshot_date,
            license=loaded.license,
            url=LABEL_SOURCE_URL,
            terms_url=LABEL_TERMS_URL,
            labels=len(loaded.labels),
        ),
        findings=[
            InteractionFindingOut(
                finding_id=f.finding_id,
                label_of=_ref(f.label_of),
                names=_ref(f.names),
                matched_name=f.matched_name,
                label=_label(f.label),
                passages=[
                    PassageOut(text=p.text, cut_start=p.cut_start, cut_end=p.cut_end)
                    for p in f.passages
                ],
                total_passages=f.total_passages,
            )
            for f in res.findings
        ],
        total_findings=res.total_findings,
        truncated=res.total_findings > len(res.findings),
        labels_read=[
            LabelReadOut(**_ref(s).model_dump(), label=_label(lab)) for s, lab in res.labels_read
        ],
        labels_not_found=[_ref(s) for s in res.labels_not_found],
        statement=None
        if res.findings
        else StatementOut(code="no_label_passage_found", text=NO_LABEL_PASSAGE),
        notices=notices,
    )


BURDEN_NOTICES: tuple[BurdenNotice, ...] = (
    "published_scores_only",
    "scales_not_comparable",
    "no_threshold",
    "list_not_complete",
    "absence_is_not_clearance",
)


def burden_out(items: Sequence[EngineItem]) -> BurdenOut:
    """The published scores of the list's ingredients, one block per scale."""
    return BurdenOut(
        status="checked",
        rules_version=burden.RULES_VERSION,
        scales=[
            BurdenScaleOut(
                scale_id=r.scale.scale_id,  # type: ignore[arg-type]
                title=r.scale.title,
                citation=r.scale.citation,
                url=r.scale.url,
                license=r.scale.license,
                license_url=r.scale.license_url,
                drugs_listed=len(r.scale.drugs),
                drugs_matched=len(r.scale.by_key),
                contributions=[
                    BurdenContributionOut(
                        ingredient_key=c.key,
                        label_en=c.label_en,
                        items=list(c.items),
                        score=c.score,
                        drug=BurdenDrugOut(published_name=c.drug.published, locator=c.drug.locator),
                    )
                    for c in r.contributions
                ],
                total=r.total,
            )
            for r in burden.find(items)
        ],
        notices=list(BURDEN_NOTICES),
    )


def label_subjects(
    conn: psycopg.Connection, dataset: str, items: Sequence[EngineItem]
) -> list[interactions.Subject]:
    """The list's ingredients with the names Janus holds for them (two indexed reads)."""
    labels = {g.key: g.label_en for it in items for g in it.ingredients}
    us = repository.us_substance_names(conn, dataset, sorted(labels))
    candidates = {
        fold(c)
        for key, label in labels.items()
        for c in interactions.name_candidates(label, us.get(key, ()))
    }
    known = repository.keys_of_names(conn, dataset, sorted(candidates))
    return interactions.subjects(items, us, known)


def check(
    conn: psycopg.Connection, body: EvaluateIn, today: dt.date, labels: LoadedLabels | None
) -> SafetyCheckOut:
    """Raises `SafetyUnavailableError`, `cascades.DatasetVersionMismatchError` or
    `cascades.InvalidItemsError` (field paths only)."""
    current = resolution.current_dataset_id(conn)
    if current is None:
        raise SafetyUnavailableError
    if body.dataset_version != current:
        raise cascades.DatasetVersionMismatchError
    try:
        items, unchecked, found = cascades.engine_items(conn, body, today)
    except cascades.CascadesUnavailableError:
        raise SafetyUnavailableError from None
    return SafetyCheckOut(
        dataset_version=current,
        items=len(items),
        ingredients_checked=sum(len(i.ingredients) for i in items),
        not_checked=[
            NotCheckedOut(item=n.item, position=n.position, reason=n.reason) for n in unchecked
        ],
        duplication=duplication_out(items, code_sources(found)),
        interactions=interactions_unavailable()
        if labels is None
        else interactions_out(label_subjects(conn, current, items), labels, today),
        burden=burden_out(items),
    )
