"""Confirmation of an extracted value by two independent readers (spec model-kit, Requirement 1.2,
design DP-M1). Agreement is decided here, by code, not by the readers.

A value is confirmed only if both readers give the same value (within 1 %), the same unit, the same
analyte class AND the same context. Owner decision 2026-11-11: if the readers agree on the value but
differ on its context (an arm restriction such as the test or reference arm of a crossover study,
co-administration, formulation, food state, population, sex), that is a disagreement and the value
is not confirmed. Research use only. Not for clinical decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Final

from janus_pipelines.modelkit.units import parse_unit

TOLERANCE: Final = 0.01  # relative, between the two readers' values


@dataclass(frozen=True, slots=True)
class Context:
    """Study-arm context of one value, as a reader read it. `None` means the text says nothing."""

    arm: str | None = None  # "test", "reference", "treatment sequence", ...
    coadministered: str | None = None  # name of the other active drug, if any
    formulation: str = "unspecified"  # immediate_release, solution, modified_release, ...
    food: str = "unspecified"  # fasted, fed, unspecified
    population: str = "unspecified"  # healthy_adult, patients, special, unspecified
    sex: str = "all"  # all, male, female
    species: str = "human"
    route: str = "unknown"  # oral, iv, unknown
    regimen: str = "unknown"  # single, multiple, unknown

    def differences(self, other: Context) -> tuple[str, ...]:
        """The names of the context fields in which the two contexts differ."""
        out: list[str] = []
        for f in fields(self):
            a, b = getattr(self, f.name), getattr(other, f.name)
            if f.name == "coadministered":
                a, b = (
                    bool(a),
                    bool(b),
                )  # which other drug is not compared, only whether there is one
            if a != b:
                out.append(f.name)
        return tuple(out)


@dataclass(frozen=True, slots=True)
class Reading:
    """What one reader says the quoted text states for the asked quantity."""

    value: float | None
    unit: str | None
    analyte_class: str | None  # parent, metabolite, enantiomer, combination_partner, total, ...
    context: Context
    dose_mg: float | None = None  # only from a table, footnote, methods or arm definition
    center_type: str = "unspecified"  # arithmetic, geometric, median, unspecified


@dataclass(frozen=True, slots=True)
class Confirmation:
    confirmed: bool
    reason: str  # a code
    differing: tuple[str, ...] = ()  # context fields in which the readers differ


def _unit_key(unit: str | None) -> object:
    """Two spellings of one unit ('L/h', 'L/hour') are the same unit: compare dimension and factor."""
    u = None if unit is None else parse_unit(unit)
    return unit if u is None else (u.dim, round(u.factor, 12))


def values_agree(a: float, b: float, tolerance: float = TOLERANCE) -> bool:
    if a == b:
        return True
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) <= tolerance * max(a, b)


def confirm(a: Reading, b: Reading) -> Confirmation:
    """Same value (+-1 %), unit, analyte class and context; any difference is a disagreement."""
    if a.value is None or b.value is None:
        return Confirmation(False, "reader_found_no_value")
    if not values_agree(a.value, b.value):
        return Confirmation(False, "values_differ")
    if _unit_key(a.unit) != _unit_key(b.unit):
        return Confirmation(False, "units_differ")
    if a.analyte_class != b.analyte_class:
        return Confirmation(False, "analytes_differ")
    if (a.dose_mg is None) != (b.dose_mg is None) or (
        a.dose_mg is not None and b.dose_mg is not None and not values_agree(a.dose_mg, b.dose_mg)
    ):
        return Confirmation(False, "doses_differ")
    if "unspecified" not in (a.center_type, b.center_type) and a.center_type != b.center_type:
        return Confirmation(False, "mean_types_differ")
    differing = a.context.differences(b.context)
    if differing:
        # same value, different context: a disagreement (owner decision 2026-11-11)
        return Confirmation(False, "context_differs", differing)
    if a.analyte_class != "parent":
        return Confirmation(False, "not_the_parent_drug")
    return Confirmation(True, "both_readers_agree")
