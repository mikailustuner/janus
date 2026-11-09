"""Minimal compartmental PK model with cited physiological parameters (design §6.3, DP-T8).

Not PBPK. One compartment, first-order absorption with a lag time, linear elimination; closed
form (Bateman), so no ODE solver is needed. Repeated doses by superposition (the model is
linear). Pure: no I/O, randomness only through the `random.Random` passed in.

Units: dose mg, volume L, clearance L/h, rate constants 1/h, time h, concentration mg/L.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

_EPS = 1e-9


@dataclass(frozen=True)
class OneCompartment:
    """`f`: oral bioavailability (0-1]; `ka`: absorption rate; `cl`: clearance; `v`: volume;
    `tlag`: absorption lag."""

    f: float
    ka: float
    cl: float
    v: float
    tlag: float = 0.0

    def __post_init__(self) -> None:
        if not (0 < self.f <= 1):
            raise ValueError("f must be in (0, 1]")
        if self.ka <= 0 or self.cl <= 0 or self.v <= 0 or self.tlag < 0:
            raise ValueError("ka, cl, v must be positive and tlag non-negative")

    @property
    def k(self) -> float:
        return self.cl / self.v

    @property
    def half_life(self) -> float:
        return math.log(2) / self.k


def _bateman(m: OneCompartment, dose: float, t: float) -> float:
    tau = t - m.tlag
    if tau <= 0:
        return 0.0
    k, ka = m.k, m.ka
    if abs(ka - k) < _EPS * max(ka, k):
        return m.f * dose * ka * tau * math.exp(-k * tau) / m.v
    c = m.f * dose * ka / (m.v * (ka - k)) * (math.exp(-k * tau) - math.exp(-ka * tau))
    return max(c, 0.0)  # rounding near t = tlag can give -1e-18


def concentration(
    m: OneCompartment, dose: float, t: float, tau: float | None = None, n: int = 1
) -> float:
    """Plasma concentration at time t after `n` doses every `tau` hours (first dose at 0)."""
    if dose < 0 or n < 1:
        raise ValueError("dose must be non-negative and n >= 1")
    if n > 1 and (tau is None or tau <= 0):
        raise ValueError("tau must be positive for repeated doses")
    step = tau or 0.0
    return sum(_bateman(m, dose, t - i * step) for i in range(n) if t - i * step > 0)


@dataclass(frozen=True)
class Amounts:
    """Where one dose is at time t (mg). Sums to the dose (mass balance)."""

    gut: float
    central: float
    eliminated: float
    not_absorbed: float


def amounts(m: OneCompartment, dose: float, t: float) -> Amounts:
    tau = max(t - m.tlag, 0.0)
    absorbable = m.f * dose
    gut = absorbable * math.exp(-m.ka * tau)
    central = _bateman(m, dose, t) * m.v
    eliminated = max(absorbable - gut - central, 0.0)
    return Amounts(gut, central, eliminated, dose - absorbable)


def tmax(m: OneCompartment) -> float:
    k, ka = m.k, m.ka
    if abs(ka - k) < _EPS * max(ka, k):
        return m.tlag + 1.0 / k
    return m.tlag + math.log(ka / k) / (ka - k)


def cmax(m: OneCompartment, dose: float) -> float:
    return _bateman(m, dose, tmax(m))


def auc_inf(m: OneCompartment, dose: float) -> float:
    """Area under the curve to infinity of one dose (mg h/L) = F D / CL."""
    return m.f * dose / m.cl


def time_to_fraction_of_steady_state(m: OneCompartment, fraction: float) -> float:
    """Hours of regular dosing until the average concentration reaches `fraction` of steady
    state: 1 - exp(-k t) = fraction (linear one-compartment model)."""
    if not (0 < fraction < 1):
        raise ValueError("fraction must be in (0, 1)")
    return -math.log(1 - fraction) / m.k


# --- uncertainty -----------------------------------------------------------------------------


@dataclass(frozen=True)
class LogNormal:
    """Parameter with a median and a geometric standard deviation (gsd >= 1)."""

    median: float
    gsd: float

    def draw(self, rng: random.Random) -> float:
        return self.median * math.exp(rng.gauss(0.0, math.log(self.gsd)))


@dataclass(frozen=True)
class Uniform:
    low: float
    high: float

    def draw(self, rng: random.Random) -> float:
        return rng.uniform(self.low, self.high)


type Dist = LogNormal | Uniform


@dataclass(frozen=True)
class ParamSpec:
    f: Dist
    ka: Dist
    cl: Dist
    v: Dist
    tlag: Dist = Uniform(0.0, 0.0)

    def draw(self, rng: random.Random) -> OneCompartment:
        f = min(max(self.f.draw(rng), 1e-6), 1.0)
        return OneCompartment(
            f, self.ka.draw(rng), self.cl.draw(rng), self.v.draw(rng), max(self.tlag.draw(rng), 0.0)
        )


def percentile(values: Sequence[float], q: float) -> float:
    """Linear-interpolation percentile, q in [0, 100]."""
    if not values:
        raise ValueError("no values")
    s = sorted(values)
    pos = (len(s) - 1) * q / 100.0
    lo = math.floor(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


@dataclass(frozen=True)
class Band:
    p5: float
    p50: float
    p95: float


def band(values: Sequence[float]) -> Band:
    return Band(percentile(values, 5), percentile(values, 50), percentile(values, 95))


def simulate(
    spec: ParamSpec,
    dose: float,
    times: Sequence[float],
    rng: random.Random,
    n: int = 500,
    tau: float | None = None,
    doses: int = 1,
) -> tuple[list[Band], Band, Band]:
    """Monte Carlo over the parameter spec: concentration band per time point, and bands of
    the peak concentration (over `times`) and of AUC to infinity of one dose."""
    curves: list[list[float]] = []
    peaks: list[float] = []
    aucs: list[float] = []
    for _ in range(n):
        m = spec.draw(rng)
        c = [concentration(m, dose, t, tau, doses) for t in times]
        curves.append(c)
        peaks.append(max(c))
        aucs.append(auc_inf(m, dose))
    per_time = [band([c[i] for c in curves]) for i in range(len(times))]
    return per_time, band(peaks), band(aucs)


def mg_per_l_to_um(c: float, mw: float) -> float:
    """mg/L to µmol/L for a molar mass in g/mol."""
    if mw <= 0:
        raise ValueError("molar mass must be positive")
    return c / mw * 1000.0
