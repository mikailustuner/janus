"""The time machine's minimal compartmental model over a virtual population (simulation-service
design §5, DP-S3, owner decision 2026-11-09). Pure and seeded: the same input gives the same
output, in Python and in the browser port (`apps/web/src/simulation/pk.ts`, shared fixtures).

A virtual population is the cited parameters (clearance scaled by the population's cited factor)
drawn with the cited spreads of `compartmental_pk.csv`: log-normal CL, V and ka with their gsd, F
uniform from 0.8 F to min(1.2 F, 1) (fixed when the parameters are apparent), lag uniform from 0
to 2 lag. Every output is a distribution
over the virtual individuals (5th, 50th, 95th percentile): there is no single-person curve and no
single-person figure. Concentrations in ng/mL (mg/L * 1000).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from janus.simulation.allowlist import CompartmentalCompound, Population
from janus.timemachine.pk import (
    LogNormal,
    ParamSpec,
    Uniform,
    simulate,
)

SEED = 20261109
POINTS = 385  # 384 steps: peaks within about 0.1 % up to the 360 h horizon (pharmacologist review)

LABEL = "minimal compartmental model with cited physiological parameters"


@dataclass(frozen=True)
class Params:
    """Medians of a virtual population and the spreads around them."""

    f: float
    ka: float
    cl: float
    v: float
    tlag: float
    ka_gsd: float
    cl_gsd: float
    v_gsd: float
    f_fixed: bool = False  # apparent parameters: F is already in CL/F and V/F


def horizon(doses: int, interval_h: int | None, after_last: int, cap: int) -> int:
    """Hours simulated: until `after_last` hours after the last dose, at most `cap`."""
    return min(cap, (doses - 1) * (interval_h or 0) + after_last)


def grid(hours: float) -> list[float]:
    step = hours / (POINTS - 1)
    return [round(i * step, 9) for i in range(POINTS)]


def spec(p: Params) -> ParamSpec:
    return ParamSpec(
        f=Uniform(p.f, p.f) if p.f_fixed else Uniform(p.f * 0.8, min(p.f * 1.2, 1.0)),
        ka=LogNormal(p.ka, p.ka_gsd),
        cl=LogNormal(p.cl, p.cl_gsd),
        v=LogNormal(p.v, p.v_gsd),
        tlag=Uniform(0.0, p.tlag * 2),
    )


def explore(
    p: Params,
    dose_mg: float,
    hours: float,
    samples: int,
    seed: int = SEED,
    interval_h: int | None = None,
    doses: int = 1,
) -> dict[str, Any]:
    times = grid(hours)
    bands, peak, auc = simulate(
        spec(p), dose_mg, times, random.Random(seed), n=samples, tau=interval_h, doses=doses
    )
    k = 1000.0
    return {
        "model": "compartmental",
        "label": LABEL,
        "dose_mg": dose_mg,
        "interval_h": interval_h,
        "doses": doses,
        "samples": samples,
        "seed": seed,
        "hours": times,
        "p5_ng_ml": [b.p5 * k for b in bands],
        "p50_ng_ml": [b.p50 * k for b in bands],
        "p95_ng_ml": [b.p95 * k for b in bands],
        "peak_band_ng_ml": [peak.p5 * k, peak.p50 * k, peak.p95 * k],
        "auc_single_dose_band_ng_h_ml": [auc.p5 * k, auc.p50 * k, auc.p95 * k],
    }


def params_for(c: CompartmentalCompound, population: Population) -> Params:
    """The medians of a predefined virtual population (cited clearance factor) and the spreads."""
    return Params(
        c.f,
        c.ka,
        c.cl * population.cl_factor,
        c.v,
        c.tlag,
        c.ka_gsd,
        c.cl_gsd,
        c.v_gsd,
        c.f_fixed,
    )
