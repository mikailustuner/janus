"""Precision of reviewed samples with study clusters (phase B3a protocol,
`docs/research/modelkit-precision-protocol.md`).

An item is one sampled value with two review verdicts ("correct", "incorrect", "cannot_judge"), the
study it comes from (the cluster) and its sampling stratum. Precision is agreed correct / agreed
(both verdicts equal and not "cannot_judge"), per stratum, combined with fixed stratum weights (the
frame counts). Intervals: Wilson (assumes independent values), a stratified study-level cluster
bootstrap (percentile), and Wilson with the effective sample size n / design effect. The
cluster-aware lower bound used by the acceptance rule is the smaller of the bootstrap and the
adjusted Wilson lower bounds. When the design effect cannot be estimated (no error, so no variance),
it is set to the mean number of agreed values per study (intra-cluster correlation 1, the
conservative bound). Pure functions, no I/O. Research use only. Not for clinical decisions."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

Z95: Final = 1.959964
VERDICTS: Final = ("correct", "incorrect", "cannot_judge")


@dataclass(frozen=True)
class Item:
    cluster: str
    stratum: str
    verdict_1: str
    verdict_2: str

    @property
    def agreed(self) -> bool:
        return self.verdict_1 == self.verdict_2 and self.verdict_1 in ("correct", "incorrect")

    @property
    def correct(self) -> bool:
        return self.agreed and self.verdict_1 == "correct"


def wilson(k: float, n: float, z: float = Z95) -> tuple[float, float] | None:
    """Wilson score interval; `n` may be an effective (non-integer) sample size."""
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def kappa(a: Sequence[str], b: Sequence[str]) -> float | None:
    """Cohen's kappa of two verdict lists (three categories)."""
    n = len(a)
    if n == 0 or n != len(b):
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pe = sum((list(a).count(c) / n) * (list(b).count(c) / n) for c in VERDICTS)
    return 1.0 if pe >= 1 else (po - pe) / (1 - pe)


def _by_stratum(items: Sequence[Item]) -> dict[str, list[Item]]:
    out: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        out[it.stratum].append(it)
    return out


def estimate(items: Sequence[Item], weights: Mapping[str, float] | None = None) -> float | None:
    """Stratum-weighted precision (strata without an agreed item drop out, weights renormalised).
    Without weights: pooled agreed correct / agreed."""
    if weights is None:
        n = sum(it.agreed for it in items)
        return sum(it.correct for it in items) / n if n else None
    num = den = 0.0
    for s, its in _by_stratum(items).items():
        n = sum(it.agreed for it in its)
        if n and weights.get(s, 0) > 0:
            num += weights[s] * sum(it.correct for it in its) / n
            den += weights[s]
    return num / den if den else None


def _srs_variance(items: Sequence[Item], weights: Mapping[str, float] | None) -> float:
    if weights is None:
        n = sum(it.agreed for it in items)
        p = estimate(items) or 0.0
        return p * (1 - p) / n if n else 0.0
    strata = {
        s: its
        for s, its in _by_stratum(items).items()
        if any(i.agreed for i in its) and weights.get(s, 0) > 0
    }
    total = sum(weights[s] for s in strata)
    v = 0.0
    for s, its in strata.items():
        n = sum(i.agreed for i in its)
        p = sum(i.correct for i in its) / n
        v += (weights[s] / total) ** 2 * p * (1 - p) / n
    return v


def _n_eff_srs(items: Sequence[Item], weights: Mapping[str, float] | None) -> float:
    """Effective n of the stratified estimate under independence: 1 / sum(w_h^2 / n_h)."""
    if weights is None:
        return float(sum(it.agreed for it in items))
    strata = {
        s: sum(i.agreed for i in its)
        for s, its in _by_stratum(items).items()
        if weights.get(s, 0) > 0
    }
    strata = {s: n for s, n in strata.items() if n}
    total = sum(weights[s] for s in strata)
    inv = sum((weights[s] / total) ** 2 / n for s, n in strata.items())
    return 1 / inv if inv else 0.0


def cluster_bootstrap(
    items: Sequence[Item],
    weights: Mapping[str, float] | None = None,
    resamples: int = 4000,
    seed: int = 20261113,
) -> tuple[tuple[float, float] | None, float]:
    """Percentile 95 % interval and variance of the (weighted) precision when whole studies are
    resampled with replacement within each stratum."""
    rnd = random.Random(seed)  # noqa: S311 - resampling, not cryptography
    plan: list[list[list[Item]]] = []
    for _, its in sorted(_by_stratum(items).items()):
        by: dict[str, list[Item]] = defaultdict(list)
        for it in its:
            by[it.cluster].append(it)
        plan.append([by[c] for c in sorted(by)])
    stats: list[float] = []
    for _ in range(resamples):
        draw: list[Item] = []
        for clusters in plan:
            for _ in range(len(clusters)):
                draw += clusters[rnd.randrange(len(clusters))]
        e = estimate(draw, weights)
        if e is not None:
            stats.append(e)
    if not stats:
        return None, 0.0
    stats.sort()
    lo = stats[math.floor(0.025 * (len(stats) - 1))]
    hi = stats[math.ceil(0.975 * (len(stats) - 1))]
    mean = sum(stats) / len(stats)
    var = sum((x - mean) ** 2 for x in stats) / max(1, len(stats) - 1)
    return (lo, hi), var


@dataclass(frozen=True)
class Summary:
    items: int
    agreed: int
    correct: int
    studies: int
    precision: float | None
    conservative: float | None
    wilson: tuple[float, float] | None
    bootstrap: tuple[float, float] | None
    design_effect: float | None
    design_effect_estimated: bool
    n_effective: float | None
    wilson_adjusted: tuple[float, float] | None
    cluster_lower: float | None
    kappa: float | None


def summarise(
    items: Sequence[Item],
    weights: Mapping[str, float] | None = None,
    resamples: int = 4000,
    seed: int = 20261113,
) -> Summary:
    agreed = [it for it in items if it.agreed]
    k = sum(it.correct for it in items)
    p = estimate(items, weights)
    n_srs = _n_eff_srs(items, weights)
    w = wilson(p * n_srs, n_srs) if p is not None and n_srs else None
    boot, var_boot = cluster_bootstrap(items, weights, resamples, seed)
    var_srs = _srs_variance(items, weights)
    studies = {it.cluster for it in agreed}
    estimated = var_srs > 0
    if not agreed:
        deff = None
    elif estimated:
        deff = max(1.0, var_boot / var_srs)
    else:
        deff = max(1.0, len(agreed) / len(studies))
    n_eff = n_srs / deff if deff else None
    wa = wilson(p * n_eff, n_eff) if p is not None and n_eff else None
    lows = [x[0] for x in (boot, wa) if x is not None]
    return Summary(
        items=len(items),
        agreed=len(agreed),
        correct=k,
        studies=len(studies),
        precision=p,
        conservative=k / len(items) if items else None,
        wilson=w,
        bootstrap=boot,
        design_effect=deff,
        design_effect_estimated=estimated,
        n_effective=n_eff,
        wilson_adjusted=wa,
        cluster_lower=min(lows) if lows else None,
        kappa=kappa([it.verdict_1 for it in items], [it.verdict_2 for it in items]),
    )


def accepted(s: Summary, threshold: float = 0.90) -> bool:
    """The pre-registered rule: the cluster-aware lower bound is at least the threshold."""
    return s.cluster_lower is not None and s.cluster_lower >= threshold
