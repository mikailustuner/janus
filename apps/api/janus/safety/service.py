"""`POST /safety/check`: the list read once in a read-only transaction, then the pure checks
(safety-check design §3). Nothing is written and nothing of the request is logged."""

from __future__ import annotations

import datetime as dt

import psycopg

from janus.cascades import service as cascades
from janus.cascades.model import EngineItem
from janus.cascades.schemas import EvaluateIn, NotCheckedOut
from janus.resolution import service as resolution
from janus.resolution.model import SourceRef
from janus.safety import duplication
from janus.safety.schemas import (
    NO_DUPLICATION,
    DuplicationFindingOut,
    DuplicationOut,
    MemberOut,
    SafetyCheckOut,
    StatementOut,
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


def check(conn: psycopg.Connection, body: EvaluateIn, today: dt.date) -> SafetyCheckOut:
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
    )
