"""Historical units of mass → grams, with the spread between sources (design §6.2, Req 4.1).
Pure. The table is `data/time_machine/units.csv`; each unit has a low, central and high value
in grams and the sources for each."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


class UnitError(ValueError):
    """Unknown unit, or an amount that is not a positive number."""


@dataclass(frozen=True)
class Interval:
    low: float
    central: float
    high: float

    def __post_init__(self) -> None:
        if not (0 < self.low <= self.central <= self.high):
            raise ValueError("interval must satisfy 0 < low <= central <= high")

    def scale(self, factor: float) -> Interval:
        if factor <= 0:
            raise ValueError("factor must be positive")
        return Interval(self.low * factor, self.central * factor, self.high * factor)

    def times(self, other: Interval) -> Interval:
        """Product of two positive intervals (bounds multiply)."""
        return Interval(self.low * other.low, self.central * other.central, self.high * other.high)


@dataclass(frozen=True)
class Unit:
    key: str
    grams: Interval
    sources: tuple[str, ...]


def load_units(path: Path) -> dict[str, Unit]:
    out: dict[str, Unit] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            g = Interval(float(r["grams_low"]), float(r["grams_central"]), float(r["grams_high"]))
            out[r["unit"]] = Unit(r["unit"], g, tuple(s for s in r["sources"].split("|") if s))
    return out


def to_grams(amount: float, unit: str, units: dict[str, Unit]) -> Interval:
    """`amount` of `unit` in grams. Linear in the amount; the spread is the unit's spread."""
    if unit not in units:
        raise UnitError("unknown unit")
    if not amount > 0:
        raise UnitError("amount must be positive")
    return units[unit].grams.scale(amount)
