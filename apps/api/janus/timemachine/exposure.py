"""Exposure versus potency (design §6.4, Req 4.2). Pure.

Compares the simulated peak plasma concentration band (5th-95th percentile) with a measured
in-vitro potency (IC50, EC50, Ki, AC50 …, in µM). In-vitro potencies refer to free drug, so the
comparison is made on the unbound concentration when an unbound fraction is known, and on the
total concentration otherwise (then labelled `total_only`, an upper bound on exposure).

Verdicts are about concentrations in a model, never about an effect in a person:
`reaches` (even the 5th percentile reaches the potency), `stays_below` (even the 95th percentile
stays below), `overlaps` (the band contains the potency).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from janus.timemachine.pk import Band


class Verdict(StrEnum):
    reaches = "reaches"
    overlaps = "overlaps"
    stays_below = "stays_below"


class Basis(StrEnum):
    unbound = "unbound"
    total_only = "total_only"


@dataclass(frozen=True)
class Comparison:
    verdict: Verdict
    basis: Basis
    margin_low: float  # concentration / potency at the 5th percentile
    margin_high: float  # at the 95th percentile


def compare(peak_um: Band, potency_um: float, fu: float | None) -> Comparison:
    if potency_um <= 0:
        raise ValueError("potency must be positive")
    if fu is not None and not (0 < fu <= 1):
        raise ValueError("fu must be in (0, 1]")
    factor = fu if fu is not None else 1.0
    low, high = peak_um.p5 * factor, peak_um.p95 * factor
    if low >= potency_um:
        verdict = Verdict.reaches
    elif high < potency_um:
        verdict = Verdict.stays_below
    else:
        verdict = Verdict.overlaps
    return Comparison(
        verdict,
        Basis.unbound if fu is not None else Basis.total_only,
        low / potency_um,
        high / potency_um,
    )
