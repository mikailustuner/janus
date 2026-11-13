"""Cross-study plausibility check for confirmed ClinicalTrials.gov values (model kit gate, phase B4).

Pre-registered in `docs/research/modelkit-gate-protocol.md` (section 3) before it was run. A value both
readers agree on can still be wrong in a way no single study shows: a posted unit that is off by a
factor of 1,000 (dasatinib, NCT00529763: CL/F posted in "mL/h", about 1,000-fold below the drug's other
study). This check compares each confirmed value with the drug's OTHER studies and withholds it when it
differs from them by more than `FACTOR`. It only withholds; it never confirms a value.

`cross_study_outliers` is the rule as a pure function; `apply` wires it into the intake after the strict
record check. The intake runs it only when asked (`read_bulk(cross_study=True)`, job environment
`JANUS_MODELKIT_CROSS_STUDY=1`): its pre-registered decision rule was not met, so it is off by default
(docs/research/modelkit-gate.md). Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from janus_pipelines.modelkit.confirm import Confirmation
from janus_pipelines.modelkit.model import DOSE_PARAMS
from janus_pipelines.modelkit.pairing import Paired
from janus_pipelines.modelkit.units import Canonical, to_canonical

FACTOR: Final = 10.0  # more than 10-fold from the other studies: withheld
REL_TOL: Final = 1e-9  # floating-point noise at the boundary; exactly FACTOR-fold is kept
REASON: Final = "cross_study_check"
_PLAIN_FORMULATIONS: Final = frozenset({"immediate_release", "solution", "unspecified"})

Key = tuple[str, ...]


@dataclass(frozen=True)
class Obs:
    """One normalised value: its comparison key, its study, the value (> 0, canonical unit, divided by
    the dose for dose-dependent parameters), whether it is a candidate to check and whether it may serve
    as a reference for other studies."""

    key: Key
    study: str
    value: float
    candidate: bool
    reference: bool = True


def _log_median(logs: Sequence[float]) -> float:
    """Median on the log scale; for an even count the mean of the two middle logs (geometric mean)."""
    s = sorted(logs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def cross_study_outliers(obs: Sequence[Obs], factor: float = FACTOR) -> frozenset[int]:
    """Indexes of the candidates that differ more than `factor`-fold from the median of the other
    studies' summaries of their key (each study summarised by the median of its reference values).
    A candidate whose key has no reference value from another study is never withheld."""
    limit = math.log(factor) * (1 + REL_TOL)
    by_study: dict[Key, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for o in obs:
        if o.reference:
            by_study[o.key][o.study].append(math.log(o.value))
    summary: dict[Key, dict[str, float]] = {
        k: {s: _log_median(v) for s, v in studies.items()} for k, studies in by_study.items()
    }
    out: set[int] = set()
    for i, o in enumerate(obs):
        if not o.candidate:
            continue
        others = [m for s, m in summary.get(o.key, {}).items() if s != o.study]
        if others and abs(math.log(o.value) - _log_median(others)) > limit:
            out.add(i)
    return frozenset(out)


def comparison_key(drug: str, parameter: str, route: str, regimen: str) -> Key:
    """(drug, parameter, route) and, for the dose-dependent parameters, the regimen."""
    route = route if route in ("oral", "iv") else "unknown"
    if parameter in DOSE_PARAMS:
        return (drug, parameter, route, regimen if regimen in ("single", "multiple") else "unknown")
    return (drug, parameter, route)


def normalised(
    parameter: str, value: float, unit: str, dose_mg: float | None
) -> tuple[str, float] | None:
    """(resolved parameter, value in the canonical unit, divided by the dose for a dose-dependent
    parameter) or None when the value cannot take part (unit refused, dose missing)."""
    c = to_canonical(parameter, value, unit)
    if not isinstance(c, Canonical):
        return None
    if c.parameter in DOSE_PARAMS:
        if dose_mg is None or not (math.isfinite(dose_mg) and dose_mg > 0):
            return None
        return c.parameter, c.value_si / dose_mg
    return c.parameter, c.value_si


def _obs(p: Paired) -> Obs | None:
    a, ctx = p.a, p.a.context
    agreed = p.result.confirmed or p.result.reason == "strict_check"  # both readers agreed
    if not agreed or a.analyte != "parent":
        return None
    n = normalised(a.parameter, a.value, a.unit, a.dose_mg)
    if n is None:
        return None
    plain = (
        not ctx.coadministered
        and ctx.population != "special"
        and ctx.formulation in _PLAIN_FORMULATIONS
    )
    key = comparison_key(a.drug_key, n[0], ctx.route, ctx.regimen)
    return Obs(key, a.study_id, n[1], candidate=p.result.confirmed, reference=plain)


def apply(pairs: list[Paired], counts: Counter[str]) -> list[Paired]:
    """Confirmed pairs that the cross-study check withholds become unconfirmed with reason
    `cross_study_check`; every other pair is returned unchanged, in the same order."""
    idx: list[int] = []
    obs: list[Obs] = []
    for i, p in enumerate(pairs):
        o = _obs(p)
        if o is not None:
            idx.append(i)
            obs.append(o)
    flagged = {idx[j] for j in cross_study_outliers(obs)}
    out: list[Paired] = []
    for i, p in enumerate(pairs):
        if i in flagged:
            counts["cross_study_check_withheld"] += 1
            out.append(
                replace(p, result=Confirmation(False, REASON, (f"more_than_{FACTOR:g}_fold",)))
            )
        else:
            out.append(p)
    return out
