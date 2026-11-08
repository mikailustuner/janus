"""Retrospective validation on fixed, cited cases (design §8, Req 5, DP9, DP17, DP24). Pure.

Runs per case:
- **primary_indication**: US labels only; the case drug's labels whose openFDA indications text
  names the later use (any of the case's phrases, whole words, case-insensitive) are removed.
- **primary_strict**: as above, and the case drug's labels that openFDA does not have are removed
  too (their indication cannot be read).
- **primary** (published): the worse of the two; a hit only when both are hits (statistician pass
  C4: dropping unreadable labels can raise the case drug's label share, so it must never help it).
- **sensitivity**: every label of every region, nothing removed (the list a researcher sees).
Every other drug keeps all its labels. FAERS inverse signals are the same in every run: the FAERS
artifact has no indication field, so the window includes the later use (reported, never hidden).
A hit is a worst tied rank within the top `TOP_K`; it is informative only when the goal has more
than `TOP_K` candidates. The light face is `experimental` when no case is an informative hit in the
published primary run. The chance of a hit for a random candidate is `TOP_K / population`.
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
    case: Case, label: Label, openfda: Mapping[str, str], drop_missing: bool
) -> str | None:
    """Why a case-drug label is removed in a primary run: "indication", "not_in_openfda" or None."""
    text = openfda.get(label.set_id)
    if text is None:
        return "not_in_openfda" if drop_missing else None
    return "indication" if mentions(text, case.indication_terms) else None


def chance(population: int, top_k: int) -> float | None:
    """Probability that a random candidate of the goal lands in the top `top_k`."""
    return None if population == 0 else min(1.0, top_k / population)


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
    """One run; `run` is `primary_indication`, `primary_strict` or `sensitivity`."""
    primary = run != "sensitivity"
    drop_missing = run == "primary_strict"
    goal_terms = {t: m for t, m in mapping.items() if m.goal == case.goal}
    removed = {"indication": 0, "not_in_openfda": 0}
    used: set[int] = set()

    def keep(label: Label) -> bool:
        if primary and label.source != "US":
            return False
        if single_key(label, key_of) != case.ingredient_key:
            return True
        if primary:
            why = _removal(case, label, openfda, drop_missing)
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
        types = cand.signal_types
        rank = cand.rank
    else:
        hit, rank, types = False, None, ()
        if not goal_terms:
            reason = "no_label_mapping"
        elif not used:
            reason = "not_evaluable"
        else:
            reason = "not_a_candidate"
    return CaseRun(
        run=run,
        rank=rank,
        population=population,
        hit=hit,
        informative=informative,
        labels_used=len(used),
        labels_removed_indication=removed["indication"],
        labels_removed_not_in_openfda=removed["not_in_openfda"],
        signal_types=types,
        reason=reason,
        chance_hit=chance(population, top_k),
        percentile=None if rank is None else rank.worst / population,
    )


_SEVERITY: dict[Reason, int] = {
    "hit": 0,
    "ranked_below_top": 1,
    "not_a_candidate": 2,
    "not_evaluable": 3,
    "no_label_mapping": 4,
}


def worse(a: CaseRun, b: CaseRun) -> CaseRun:
    """The published primary run: the worse of the two variants, a hit only if both are."""

    def badness(r: CaseRun) -> tuple[int, float]:
        return (_SEVERITY[r.reason], 2.0 if r.percentile is None else r.percentile)

    w = max((a, b), key=badness)
    return CaseRun(
        run="primary",
        rank=w.rank,
        population=w.population,
        hit=a.hit and b.hit,
        informative=a.informative and b.informative,
        labels_used=w.labels_used,
        labels_removed_indication=w.labels_removed_indication,
        labels_removed_not_in_openfda=w.labels_removed_not_in_openfda,
        signal_types=w.signal_types,
        reason=w.reason if not (a.hit and b.hit) else "hit",
        chance_hit=w.chance_hit,
        percentile=w.percentile,
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
        expected_hits_by_chance=sum(
            r.chance_hit or 0.0 for r in runs if r.rank is not None and r.informative
        ),
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

        def run(name: RunName, case: Case = case, inv: Sequence[InverseSignal] = inv) -> CaseRun:
            return run_case(case, name, ordered, mapping, key_of, inv, openfda, top_k)

        a, b = run("primary_indication"), run("primary_strict")
        results.append(CaseResult(case, worse(a, b), a, b, run("sensitivity"), faers.get(case.id)))
    primary = summarise(r.primary for r in results)
    sensitivity = summarise(r.sensitivity for r in results)
    return Validation(top_k, tuple(results), primary, sensitivity, status_of(primary))
