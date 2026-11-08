"""Retrospective validation on fixed, cited cases (design §8, Req 5, DP9, DP17; P4, P11). Pure.

Two runs per case:
- **primary**: US labels only; the case drug's labels are removed when openFDA does not have their
  set id or when their indications text names the later use (any of the case's phrases, whole
  words, case-insensitive). Every other drug keeps its US labels.
- **sensitivity**: every label of every region, nothing removed (the list a researcher sees).
FAERS inverse signals are the same in both runs: the FAERS artifact has no indication field, so the
window includes the later use (reported per case, never hidden).
A hit is a worst tied rank within the top `TOP_K`; it is informative only when the goal has more
than `TOP_K` candidates. The light face is `experimental` when no case is an informative hit in the
primary run.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence

from janus.light.candidates import find, rank_goal
from janus.light.labels import label_signals, single_key
from janus.light.model import (
    TOP_K,
    Case,
    CaseFaers,
    CaseResult,
    CaseRun,
    InverseSignal,
    Label,
    LightStatus,
    MappingRow,
    Reason,
    RunName,
    RunSummary,
    Validation,
)


def mentions(text: str, phrases: Iterable[str]) -> bool:
    low = text.lower()
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(p.lower())}(?![a-z0-9])", low) is not None
        for p in phrases
    )


def _removal(
    case: Case, label: Label, openfda: Mapping[str, str]
) -> str | None:  # "indication" | "not_in_openfda" | None
    text = openfda.get(label.set_id)
    if text is None:
        return "not_in_openfda"
    return "indication" if mentions(text, case.indication_terms) else None


def run_case(
    case: Case,
    run: RunName,
    labels: Sequence[Label],
    mapping: Mapping[str, MappingRow],
    key_of: Mapping[str, str],
    inverse: Sequence[InverseSignal],
    openfda: Mapping[str, str],
    top_k: int = TOP_K,
) -> CaseRun:
    goal_terms = {t: m for t, m in mapping.items() if m.goal == case.goal}
    removed = {"indication": 0, "not_in_openfda": 0}
    used: set[int] = set()

    def keep(label: Label) -> bool:
        if run == "primary" and label.source != "US":
            return False
        if single_key(label, key_of) != case.ingredient_key:
            return True
        if run == "primary":
            why = _removal(case, label, openfda)
            if why is not None:
                removed[why] += 1
                return False
        used.add(label.label_id)
        return True

    signals = label_signals(labels, goal_terms, key_of, keep)
    candidates = rank_goal(case.goal, signals.values(), inverse)
    cand = find(candidates, case.ingredient_key)
    population = len(candidates)
    informative = population > top_k
    reason: Reason
    if cand is not None:
        hit = cand.rank.worst <= top_k
        reason = "hit" if hit else "ranked_below_top"
        return CaseRun(
            run,
            cand.rank,
            population,
            hit,
            informative,
            len(used),
            removed["indication"],
            removed["not_in_openfda"],
            cand.signal_types,
            reason,
        )
    if not goal_terms:
        reason = "no_label_mapping"
    elif not used:
        reason = "not_evaluable"
    else:
        reason = "not_a_candidate"
    return CaseRun(
        run,
        None,
        population,
        False,
        informative,
        len(used),
        removed["indication"],
        removed["not_in_openfda"],
        (),
        reason,
    )


def summarise(runs: Iterable[CaseRun]) -> RunSummary:
    runs = list(runs)
    return RunSummary(
        hits=sum(r.hit for r in runs),
        informative_hits=sum(r.hit and r.informative for r in runs),
        misses=sum(
            r.reason in ("ranked_below_top", "not_a_candidate", "no_label_mapping") for r in runs
        ),
        not_evaluable=sum(r.reason == "not_evaluable" for r in runs),
    )


def status_of(primary: RunSummary) -> LightStatus:
    return "experimental" if primary.informative_hits == 0 else "prototype"


def evaluate(
    cases: Sequence[Case],
    labels: Sequence[Label],
    mapping: Mapping[str, MappingRow],
    key_of: Mapping[str, str],
    inverse_by_goal: Mapping[str, Sequence[InverseSignal]],
    openfda: Mapping[str, str],
    faers: Mapping[str, CaseFaers | None],
    top_k: int = TOP_K,
) -> Validation:
    """`mapping` holds the active rows by term; `faers` the per-case FAERS numbers by case id."""
    ordered = sorted(labels, key=lambda lb: lb.label_id)
    results: list[CaseResult] = []
    for case in sorted(cases, key=lambda c: c.id):
        inv = inverse_by_goal.get(case.goal, ())
        runs = {
            run: run_case(case, run, ordered, mapping, key_of, inv, openfda, top_k)
            for run in ("primary", "sensitivity")
        }
        results.append(CaseResult(case, runs["primary"], runs["sensitivity"], faers.get(case.id)))
    primary = summarise(r.primary for r in results)
    sensitivity = summarise(r.sensitivity for r in results)
    return Validation(top_k, tuple(results), primary, sensitivity, status_of(primary))
