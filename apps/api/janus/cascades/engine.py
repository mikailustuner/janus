"""The cascade engine (cascade-engine design §4.4-4.6). Pure: no I/O, no clock, no logging.

Deterministic code decides whether a cascade pattern exists. The integrity snapshot decides
which rules, priorities, form extensions and `probable` labels may be used; `today` only enters
the integrity codes (freshness).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence, Set

from janus.cascades.chains import chains
from janus.cascades.exposure import exposures
from janus.cascades.model import (
    CHAINS_TRUNCATED,
    NO_PATTERN_TEXT,
    RULE_BASE_UNAVAILABLE_TEXT,
    TIMING_ORDER,
    AtcClass,
    DisabledRule,
    EngineItem,
    EngineResult,
    Exposure,
    Finding,
    ItemWarning,
    NotChecked,
    NotMatchable,
    RemovedSource,
    Role,
    RuleBase,
    SameProduct,
    Side,
    Statement,
)
from janus.cascades.patterns import class_match, is_ingredient_code
from janus.cascades.timing import classify
from janus.integrity.citability import Verdict, verdict_map
from janus.integrity.gate import rule_gate
from janus.integrity.model import IntegritySnapshot
from janus.integrity.view import build_item
from janus.memory.evidence import FAERS_EVIDENCE_ID, EventRef, faers_locator

NOT_REGISTERED = Verdict(False, "not_registered")


class EngineInputError(ValueError):
    """A code given to the engine is not an ingredient-level code or is a combination code.

    This is a programming error upstream (codes come only from `rule_input`); the request fails
    loudly. The message never contains the code.
    """


def _validate(items: Sequence[EngineItem], combination_codes: Set[str]) -> None:
    for item in items:
        for ing in item.ingredients:
            for code in ing.codes:
                if not is_ingredient_code(code) or code in combination_codes:
                    raise EngineInputError("non-ingredient or combination code in engine input")


def _cite(
    verdicts: Mapping[str, Verdict], ids: Iterable[str]
) -> tuple[list[str], list[tuple[str, str]]]:
    """Same rule as `integrity.citability.cite`, on precomputed verdicts."""
    kept: list[str] = []
    removed: list[tuple[str, str]] = []
    for i in dict.fromkeys(ids):
        v = verdicts.get(i, NOT_REGISTERED)
        if v.citable:
            kept.append(i)
        else:
            removed.append((i, v.reason or "not_registered"))
    return kept, removed


def _side(e: Exposure) -> Side:
    return Side(
        key=e.key,
        label_en=e.label_en,
        items=tuple(sorted(e.items)),
        matched_codes=e.matched_codes,
        form_confirmed=e.form_confirmed,
        via_form_extension=e.via_extension,
        start=e.start,
    )


def abrupt_stop_keys(items: Sequence[EngineItem], rb: RuleBase) -> frozenset[str]:
    """Ingredient keys with any code on the abrupt-stop list (systemic forms; no extensions)."""
    return frozenset(
        ing.key
        for item in items
        for ing in item.ingredients
        if any(class_match(c, rb.abrupt_stop) is not None for c in ing.codes)
    )


def _sort_key(f: Finding) -> tuple[object, ...]:
    return (
        f.status != "probable",
        TIMING_ORDER.index(f.timing),
        not f.form_confirmed,
        f.priority is None,
        f.rule.position,
        f.index.key,
        f.marker.key,
    )


def evaluate(
    items: Sequence[EngineItem],
    rb: RuleBase,
    snapshot: IntegritySnapshot,
    today: dt.date,
    combination_codes: Set[str] = frozenset(),
    not_checked: Sequence[NotChecked] = (),
) -> EngineResult:
    _validate(items, combination_codes)
    verdicts = verdict_map(snapshot)
    ext_ids = {i for c in rb.classes.values() for i in c.extension_ids}
    active = frozenset(i for i in ext_ids if verdicts.get(i, NOT_REGISTERED).citable)
    window_ok = verdicts.get(rb.window_evidence_id, NOT_REGISTERED).citable
    on_list = abrupt_stop_keys(items, rb)

    codes_cache: dict[str, tuple[str, ...]] = {}

    def integrity_codes(ids: Iterable[str]) -> tuple[str, ...]:
        out: set[str] = set()
        for i in ids:
            if i not in codes_cache:
                codes_cache[i] = tuple(build_item(snapshot, i, today, verdicts).codes)
            out.update(codes_cache[i])
        return tuple(sorted(out))

    exp_cache: dict[tuple[str, bool], dict[str, Exposure]] = {}

    def exp(cls: AtcClass, with_extensions: bool) -> dict[str, Exposure]:
        k = (cls.class_id, with_extensions)
        if k not in exp_cache:
            exp_cache[k] = exposures(items, cls, active if with_extensions else frozenset())
        return exp_cache[k]

    findings: list[Finding] = []
    same: list[SameProduct] = []
    disabled: list[DisabledRule] = []
    unmatchable: list[NotMatchable] = []
    checked = 0
    for rule in rb.rules:
        if rule.unmatchable is not None:
            unmatchable.append(NotMatchable(rule.rule_id, *rule.unmatchable))
            continue
        gate = rule_gate([rule.evidence_id], snapshot, verdicts)
        if not gate.enabled:
            disabled.append(
                DisabledRule(
                    rule.rule_id,
                    gate.reason or "no_citable_source",
                    tuple(
                        RemovedSource(
                            r.id,
                            r.reason,
                            tuple(n.type for n in r.notices),
                            tuple(n.notice_doi for n in r.notices if n.notice_doi),
                        )
                        for r in gate.removed
                    ),
                )
            )
            continue
        checked += 1
        event_key = rb.faers_event_keys.get(rule.position)
        assert rule.index_class is not None and rule.marker_class is not None  # noqa: S101
        index_exp = exp(rb.classes[rule.index_class], True)
        marker_exp = exp(rb.classes[rule.marker_class], False)
        for a in index_exp.values():
            for b in marker_exp.values():
                if a.key == b.key:
                    continue
                if a.items == b.items:
                    same.append(SameProduct(rule.rule_id, a.key, b.key, tuple(sorted(a.items))))
                    continue
                t = classify(a.start, b.start, rb.window_months)
                if t is None:
                    continue
                ext_evidence = sorted(
                    p.evidence_id
                    for p in rb.classes[rule.index_class].patterns
                    if p.evidence_id is not None
                    and p.evidence_id in active
                    and any(c.startswith(p.prefix) for c in a.matched_codes)
                )
                ids = [
                    rule.evidence_id,
                    rb.source_paper_id,
                    *([rb.window_evidence_id] if t.timing == "within_window" else []),
                    *([rule.priority.evidence_id] if rule.priority else []),
                    *rule.supporting,
                    *(ext_evidence if a.via_extension else []),
                    *([FAERS_EVIDENCE_ID] if event_key else []),
                ]
                kept, removed = _cite(verdicts, ids)
                locator = (
                    faers_locator((a.key,), EventRef(key=event_key), "ALL", "suspect")
                    if event_key and FAERS_EVIDENCE_ID in kept
                    else None
                )
                status = t.status if (t.timing != "within_window" or window_ok) else "possible"
                priority = (
                    rule.priority
                    if rule.priority is not None and rule.priority.evidence_id in kept
                    else None
                )
                roles: list[Role] = []
                if a.key in on_list:
                    roles.append("index")
                if b.key in on_list:
                    roles.append("marker")
                findings.append(
                    Finding(
                        finding_id=f"{rule.rule_id}:{a.key}:{b.key}",
                        rule=rule,
                        index=_side(a),
                        marker=_side(b),
                        status=status,
                        timing=t.timing,
                        months_between=t.months_between,
                        low_priority=t.low_priority,
                        form_confirmed=a.form_confirmed and b.form_confirmed,
                        via_form_extension=a.via_extension,
                        priority=priority,
                        abrupt_stop=tuple(roles),
                        evidence_ids=tuple(kept),
                        excluded_evidence=tuple(removed),
                        integrity_codes=integrity_codes(kept),
                        faers_locator=locator,
                    )
                )
    findings.sort(key=_sort_key)
    chain_list, truncated = chains(findings)
    warnings = sorted(
        {(item.index, ing.key) for item in items for ing in item.ingredients if ing.key in on_list}
    )
    if checked == 0:
        statement: Statement | None = Statement("rule_base_unavailable", RULE_BASE_UNAVAILABLE_TEXT)
    elif not findings:
        statement = Statement("no_pattern_found", NO_PATTERN_TEXT)
    else:
        statement = None
    return EngineResult(
        findings=tuple(findings),
        chains=chain_list,
        same_product=tuple(
            sorted(same, key=lambda s: (int(s.rule_id.split(":")[1]), s.index_key, s.marker_key))
        ),
        item_warnings=tuple(ItemWarning(i, k) for i, k in warnings),
        not_checked=tuple(sorted(not_checked, key=lambda n: (n.item, n.position))),
        rules_total=len(rb.rules),
        rules_checked=checked,
        disabled=tuple(disabled),
        not_matchable=tuple(unmatchable),
        statement=statement,
        notices=(CHAINS_TRUNCATED,) if truncated else (),
    )
