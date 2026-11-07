"""`POST /cascades/evaluate`: one read-only transaction, then the pure engine (design §6.1).

Nothing is written and nothing of the request is logged. The client sends candidate ids or
ingredient keys with start months; codes come from the current resolution dataset through
`rule_input` only.
"""

from __future__ import annotations

import datetime as dt

import psycopg

from janus.cascades import repository
from janus.cascades.engine import evaluate
from janus.cascades.inputs import ChoiceError, ingredient_item, product_item
from janus.cascades.model import EngineItem, EngineResult, Finding, NotChecked, Side
from janus.cascades.schemas import (
    CascadeResult,
    ChainOut,
    DisabledOut,
    EvaluateIn,
    ExcludedOut,
    FindingOut,
    IndexSideOut,
    ItemWarningOut,
    LinkOut,
    NotCheckedOut,
    NotMatchableOut,
    PriorityOut,
    RemovedOut,
    RulesOut,
    RuleTextOut,
    SameProductOut,
    SideOut,
    StatementOut,
)
from janus.cascades.timing import format_month, parse_month
from janus.integrity import repository as integrity_repository
from janus.resolution import service as resolution
from janus.resolution.service import ResolutionUnavailableError

EARLIEST = parse_month("1900-01")


class CascadesUnavailableError(RuntimeError):
    """The rule base, the resolution dataset or the evidence is not loaded."""


class DatasetVersionMismatchError(RuntimeError):
    """The client resolved its items against another dataset version."""


class InvalidItemsError(ValueError):
    """Some items cannot be used; carries field paths only."""

    def __init__(self, fields: list[str]) -> None:
        super().__init__("invalid items")
        self.fields = fields


def _month_of(today: dt.date) -> int:
    return today.year * 12 + today.month - 1


def evaluate_request(conn: psycopg.Connection, body: EvaluateIn, today: dt.date) -> CascadeResult:
    rb = repository.current_rule_base(conn)
    current = resolution.current_dataset_id(conn)
    if rb is None or current is None:
        raise CascadesUnavailableError
    if body.dataset_version != current:
        raise DatasetVersionMismatchError
    snapshot = integrity_repository.load_snapshot(conn)
    if not snapshot.records:
        raise CascadesUnavailableError
    now = _month_of(today)
    bad: list[str] = []
    starts: list[int | None] = []
    for i, item in enumerate(body.items):
        start = None if item.started is None else parse_month(item.started)
        if start is not None and not (EARLIEST <= start <= now):
            bad.append(f"items.{i}.started")
        starts.append(start)
    products = [it.product for it in body.items if it.product is not None]
    qids = [it.ingredient for it in body.items if it.ingredient is not None]
    qids += [c.ingredient for it in body.items for c in it.choices or []]
    try:
        found = resolution.rule_inputs(conn, products, qids)
    except ResolutionUnavailableError:
        raise CascadesUnavailableError from None
    items: list[EngineItem] = []
    unchecked: list[NotChecked] = []
    for i, item in enumerate(body.items):
        if item.product is not None:
            cand = found.products.get(item.product)
            if cand is None:
                bad.append(f"items.{i}.product")
                continue
            choices = {c.position: c.ingredient for c in item.choices or []}
            key_codes = {
                q: (
                    frozenset(a.code for a in found.ingredients[q].atc_codes),
                    found.ingredients[q].ingredient_key.label_en,
                )
                for q in choices.values()
                if q in found.ingredients
            }
            try:
                engine_item, nc = product_item(i, starts[i], cand.ingredients, choices, key_codes)
            except ChoiceError:
                bad.append(f"items.{i}.choices")
                continue
        else:
            assert item.ingredient is not None  # noqa: S101 (validated: exactly one kind)
            ing = found.ingredients.get(item.ingredient)
            if ing is None:
                bad.append(f"items.{i}.ingredient")
                continue
            engine_item, nc = ingredient_item(i, starts[i], ing)
        items.append(engine_item)
        unchecked += nc
    if bad:
        raise InvalidItemsError(sorted(set(bad)))
    result = evaluate(items, rb, snapshot, today, found.combination_codes, unchecked)
    return _out(
        result, rb.version, current, snapshot.version(), format_month(now), rb.window_months
    )


def _side(s: Side) -> SideOut:
    return SideOut(
        ingredient_key=s.key,
        label_en=s.label_en,
        items=list(s.items),
        matched_codes=list(s.matched_codes),
        form_confirmed=s.form_confirmed,
        start=None if s.start is None else format_month(s.start),
    )


def _finding(f: Finding) -> FindingOut:
    r = f.rule
    p = f.priority
    return FindingOut(
        finding_id=f.finding_id,
        rule_id=r.rule_id,
        rule_evidence_id=r.evidence_id,
        rule_text=RuleTextOut(
            system=r.system,
            kind=r.kind,
            drug_a=r.drug_a,
            adverse_event=r.adverse_event,
            drug_b=r.drug_b,
            locator=r.locator,
        ),
        index=IndexSideOut(
            **_side(f.index).model_dump(), via_form_extension=f.index.via_form_extension
        ),
        marker=_side(f.marker),
        status=f.status,
        timing=f.timing,
        months_between=f.months_between,
        low_priority=f.low_priority,
        form_confirmed=f.form_confirmed,
        via_form_extension=f.via_form_extension,
        priority=None
        if p is None
        else PriorityOut(
            measure=p.measure,
            value=p.value,
            ci_low=p.ci_low,
            ci_high=p.ci_high,
            unit=p.unit,
            locator=p.locator,
            evidence_id=p.evidence_id,
        ),
        abrupt_stop=list(f.abrupt_stop),
        evidence_ids=list(f.evidence_ids),
        excluded_evidence=[ExcludedOut(id=i, reason=r_) for i, r_ in f.excluded_evidence],
        integrity_codes=list(f.integrity_codes),
    )


def _out(
    res: EngineResult, rb_version: str, dataset: str, integrity: str, month: str, window: int
) -> CascadeResult:
    return CascadeResult(
        rule_base_version=rb_version,
        dataset_version=dataset,
        integrity_version=integrity,
        as_of_month=month,
        window_months=window,
        findings=[_finding(f) for f in res.findings],
        chains=[
            ChainOut(
                chain_id=c.chain_id,
                ingredient_keys=list(c.ingredient_keys),
                links=[
                    LinkOut(
                        index_key=link.index_key,
                        marker_key=link.marker_key,
                        finding_ids=list(link.finding_ids),
                    )
                    for link in c.links
                ],
                status=c.status,
            )
            for c in res.chains
        ],
        same_product=[
            SameProductOut(
                rule_id=s.rule_id,
                index_key=s.index_key,
                marker_key=s.marker_key,
                items=list(s.items),
            )
            for s in res.same_product
        ],
        item_warnings=[
            ItemWarningOut(
                item=w.item,
                ingredient_key=w.ingredient_key,
                code="do_not_stop_suddenly",
                text=w.text,
            )
            for w in res.item_warnings
        ],
        not_checked=[
            NotCheckedOut(item=n.item, position=n.position, reason=n.reason)
            for n in res.not_checked
        ],
        rules=RulesOut(
            total=res.rules_total,
            checked=res.rules_checked,
            disabled=[
                DisabledOut(
                    rule_id=d.rule_id,
                    reason=d.reason,  # pyright: ignore[reportArgumentType]
                    removed=[
                        RemovedOut(
                            id=r.id,
                            reason=r.reason,
                            notice_types=list(r.notice_types),
                            notice_dois=list(r.notice_dois),
                        )
                        for r in d.removed
                    ],
                )
                for d in res.disabled
            ],
            not_matchable=[
                NotMatchableOut(rule_id=n.rule_id, role=n.role, reason=n.reason)  # pyright: ignore[reportArgumentType]
                for n in res.not_matchable
            ],
        ),
        statement=None
        if res.statement is None
        else StatementOut(code=res.statement.code, text=res.statement.text),
        notices=["chains_truncated"] if res.notices else [],
    )
