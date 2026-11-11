"""Unit table and dimension analysis for pharmacokinetic values (spec model-kit, plan 6.2).

A unit string is parsed into a dimension (exponents of mass, length, time, body mass, amount of
substance) and a factor to base units (g, m, s, kg of body mass, mol). A parameter has an expected
dimension; a value is converted only when its unit has exactly that dimension. Per-kg values keep
their per-kg dimension: they are NEVER converted to a person-sized value unless a body weight is
given explicitly (`per_kg_to_absolute`). Molar units cannot become mass units without a molar
mass, so they are refused. The mean type (arithmetic, geometric, median) and the dispersion (SD,
CV %, range, interval) are separate fields of `Stat`. Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Final, Literal

# dimension = (mass, length, time, body mass, amount of substance)
Dim = tuple[int, int, int, int, int]
DIMLESS: Final[Dim] = (0, 0, 0, 0, 0)

# unit symbol -> (dimension, factor to base units g, m, s, kg body mass, mol)
_ATOMS: Final[dict[str, tuple[Dim, float]]] = {
    "g": ((1, 0, 0, 0, 0), 1.0),
    "mg": ((1, 0, 0, 0, 0), 1e-3),
    "ug": ((1, 0, 0, 0, 0), 1e-6),
    "mcg": ((1, 0, 0, 0, 0), 1e-6),
    "ng": ((1, 0, 0, 0, 0), 1e-9),
    "pg": ((1, 0, 0, 0, 0), 1e-12),
    "kg": ((1, 0, 0, 0, 0), 1e3),  # a mass; becomes body mass in a denominator (see _split)
    "l": ((0, 3, 0, 0, 0), 1e-3),
    "dl": ((0, 3, 0, 0, 0), 1e-4),
    "ml": ((0, 3, 0, 0, 0), 1e-6),
    "h": ((0, 0, 1, 0, 0), 3600.0),
    "hr": ((0, 0, 1, 0, 0), 3600.0),
    "hrs": ((0, 0, 1, 0, 0), 3600.0),
    "hour": ((0, 0, 1, 0, 0), 3600.0),
    "hours": ((0, 0, 1, 0, 0), 3600.0),
    "min": ((0, 0, 1, 0, 0), 60.0),
    "s": ((0, 0, 1, 0, 0), 1.0),
    "d": ((0, 0, 1, 0, 0), 86400.0),
    "day": ((0, 0, 1, 0, 0), 86400.0),
    "mol": ((0, 0, 0, 0, 1), 1.0),
    "mmol": ((0, 0, 0, 0, 1), 1e-3),
    "umol": ((0, 0, 0, 0, 1), 1e-6),
    "nmol": ((0, 0, 0, 0, 1), 1e-9),
    "pmol": ((0, 0, 0, 0, 1), 1e-12),
    "%": (DIMLESS, 0.01),
    "fraction": (DIMLESS, 1.0),
}
_MU: Final = str.maketrans({"µ": "u", "μ": "u"})
_MULT: Final = re.compile(r"[*·•×⋅.\s]+")  # noqa: RUF001


@dataclass(frozen=True)
class Unit:
    dim: Dim
    factor: float  # to base units


def _add(a: Dim, b: Dim, sign: int) -> Dim:
    return (
        a[0] + sign * b[0],
        a[1] + sign * b[1],
        a[2] + sign * b[2],
        a[3] + sign * b[3],
        a[4] + sign * b[4],
    )


_WORDS: Final = (
    (r"\bnanograms?\b", "ng"), (r"\bmicrograms?\b", "ug"), (r"\bmilligrams?\b", "mg"),
    (r"\bpicograms?\b", "pg"), (r"\bkilograms?\b", "kg"), (r"\bgrams?\b", "g"),
    (r"\bmilliliters?\b|\bmillilitres?\b", "ml"), (r"\bdeciliters?\b", "dl"),
    (r"\bliters?\b|\blitres?\b", "l"), (r"\bhours?\b", "h"), (r"\bminutes?\b", "min"),
    (r"\bseconds?\b", "s"), (r"\bdays?\b", "d"), (r"\bpercent(?:age)?\b", "%"),
    (r"\bper\b", "/"),
)  # fmt: skip


def _plain(text: str) -> str:
    """A unit written in words ('Hours*microgram per milliliter', 'nanogram per milliliter
    (ng/mL)') as symbols. A bracketed symbol form wins over the words in front of it."""
    s = text.strip().translate(_MU).lower()
    if m := re.search(r"\(([^()]*[/*][^()]*)\)\s*$", s):
        inner = m.group(1).strip()
        if inner:
            s = inner
    s = re.sub(r"\([^)]*\)", "", s)
    for rx, sym in _WORDS:
        s = re.sub(rx, sym, s)
    return s.replace("-", "*").replace(" / ", "/").replace("/ ", "/").replace(" /", "/")


def parse_unit(text: str) -> Unit | None:
    """The dimension and factor of a unit string such as 'ng*h/mL', 'mL/min/kg', 'ug.hr/mL';
    None when a symbol is unknown. A 'kg' after a '/' is body mass; elsewhere it is a mass."""
    s = _plain(text)
    if not s:
        return None
    parts = [p.strip() for p in s.split("/")]
    dim: Dim = DIMLESS
    factor = 1.0
    for i, part in enumerate(parts):
        if not part:
            return None
        sign = 1 if i == 0 else -1
        for sym in _MULT.split(part):
            if not sym:
                continue
            if sym not in _ATOMS:
                return None
            d, f = _ATOMS[sym]
            if sym == "kg" and sign < 0:
                d, f = (0, 0, 0, 1, 0), 1.0
            dim = _add(dim, d, sign)
            factor = factor * f if sign > 0 else factor / f
    return Unit(dim, factor)


# parameter -> (expected dimension, canonical unit, factor from base units to the canonical unit)
_M, _L, _T = (1, 0, 0, 0, 0), (0, 3, 0, 0, 0), (0, 0, 1, 0, 0)
_B = (0, 0, 0, 1, 0)
_PER_T = (0, 0, -1, 0, 0)
_CONC: Dim = (1, -3, 0, 0, 0)
_AUC: Dim = (1, -3, 1, 0, 0)
_CL: Dim = (0, 3, -1, 0, 0)
_CL_KG: Dim = (0, 3, -1, -1, 0)
_V_KG: Dim = (0, 3, 0, -1, 0)
EXPECTED: Final[dict[str, tuple[Dim, str, float]]] = {
    "cl": (_CL, "L/h", 1e3 * 3600.0),  # m3/s -> L/h
    "cl_f": (_CL, "L/h", 1e3 * 3600.0),
    "vss": (_L, "L", 1e3),
    "vd": (_L, "L", 1e3),
    "v_f": (_L, "L", 1e3),
    "t_half": (_T, "h", 1 / 3600.0),
    "tmax": (_T, "h", 1 / 3600.0),
    "f": (DIMLESS, "fraction", 1.0),
    "cmax": (_CONC, "ng/mL", 1e9 * 1e-6),  # g/m3 -> ng/mL
    "auc_inf": (_AUC, "ng*h/mL", 1e9 * 1e-6 / 3600.0),
    "auc_last": (_AUC, "ng*h/mL", 1e9 * 1e-6 / 3600.0),
    "auc_tau": (_AUC, "ng*h/mL", 1e9 * 1e-6 / 3600.0),
    "cl_per_kg": (_CL_KG, "L/h/kg", 1e3 * 3600.0),
    "vd_per_kg": (_V_KG, "L/kg", 1e3),
}
_BASE_OF_PER_KG: Final = {"cl_per_kg": "cl", "vd_per_kg": "vd"}

Issue = Literal[
    "unit_unknown",
    "dimension_mismatch",
    "molar_unit_needs_molar_mass",
    "per_kg_needs_body_weight",
    "parameter_unknown",
    "not_positive_finite",
]


@dataclass(frozen=True)
class Canonical:
    parameter: str  # the parameter the value belongs to (a per-kg unit moves cl to cl_per_kg)
    value_si: float
    unit: str  # canonical unit


@dataclass(frozen=True)
class Refused:
    issue: Issue
    detail: str


def resolve_parameter(parameter: str, unit: str) -> str:
    """A clearance or volume stated per kg of body mass is a different parameter (`cl_per_kg`,
    `vd_per_kg`): it is not an absolute clearance and not CL/F. Other parameters keep their name."""
    u = parse_unit(unit)
    if u is None or u.dim[3] != -1:
        return parameter
    if parameter in ("cl", "cl_f"):
        return "cl_per_kg"
    if parameter in ("vss", "vd", "v_f"):
        return "vd_per_kg"
    return parameter


def to_canonical(parameter: str, value: float, unit: str) -> Canonical | Refused:
    """The value in the canonical unit of its parameter after a dimension check. A per-kg unit is
    accepted only for the per-kg parameters, never converted to an absolute one."""
    if not (math.isfinite(value) and value > 0):
        return Refused("not_positive_finite", str(value))
    param = resolve_parameter(parameter, unit)
    if param not in EXPECTED:
        return Refused("parameter_unknown", parameter)
    u = parse_unit(unit)
    if u is None:
        return Refused("unit_unknown", unit)
    dim, canonical, to_unit = EXPECTED[param]
    if u.dim[4] != 0:
        return Refused("molar_unit_needs_molar_mass", unit)
    if u.dim != dim:
        if u.dim[3] != dim[3] and u.dim[:3] == dim[:3]:
            return Refused("per_kg_needs_body_weight", unit)
        return Refused("dimension_mismatch", f"{unit} is not a unit of {param}")
    scale = 1.0 if param == "f" else to_unit
    return Canonical(param, value * u.factor * scale, canonical)


def per_kg_to_absolute(
    parameter: str, value_per_kg: float, body_weight_kg: float | None
) -> tuple[str, float]:
    """A per-kg clearance or volume as an absolute `cl` or `vd` for one stated body weight. The
    weight must be given explicitly and be positive: there is no default. The result is NOT CL/F."""
    if parameter not in _BASE_OF_PER_KG:
        raise ValueError(f"{parameter!r} is not a per-kg parameter")
    if body_weight_kg is None or not (math.isfinite(body_weight_kg) and body_weight_kg > 0):
        raise ValueError("a per-kg value needs an explicit positive body weight")
    return _BASE_OF_PER_KG[parameter], value_per_kg * body_weight_kg


def from_canonical(parameter: str, value_si: float, unit: str) -> float | None:
    """Inverse of `to_canonical` for a unit of the same dimension; None if the unit does not fit."""
    u = parse_unit(unit)
    if parameter not in EXPECTED or u is None or u.dim != EXPECTED[parameter][0]:
        return None
    scale = 1.0 if parameter == "f" else EXPECTED[parameter][2]
    return value_si / (u.factor * scale)


# --- mean type and dispersion, stored separately ---------------------------------------------

Center = Literal["arithmetic", "geometric", "median", "unspecified"]
Spread = Literal["none", "sd", "cv_percent", "range", "ci95", "iqr", "se"]


@dataclass(frozen=True)
class Stat:
    center: float
    center_type: Center = "unspecified"
    spread_type: Spread = "none"
    spread_low: float | None = None  # sd / cv value, or the lower bound of a range or interval
    spread_high: float | None = None


_NUM = r"[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?"
_PM = re.compile(rf"^\s*({_NUM})\s*(?:±|\+/-|\+-)\s*({_NUM})\s*$")
_PAREN = re.compile(rf"^\s*({_NUM})\s*\(\s*([^)]*)\)\s*$")
_RANGE = re.compile(rf"^\s*({_NUM})\s*(?:-|–|to)\s*({_NUM})\s*$")


def _f(text: str) -> float:
    return float(text.replace(",", "."))


def parse_stat(cell: str, center_type: Center = "unspecified") -> Stat | None:
    """'26.2 +- 4.8' -> sd; '45 (30%)' -> cv_percent; '12 (8-16)' -> range; '12.5' -> no spread.
    The mean type is not guessed from the cell: it comes from the caption or the column header."""
    text = cell.strip().replace("−", "-")  # noqa: RUF001
    if m := _PM.match(text):
        return Stat(_f(m[1]), center_type, "sd", _f(m[2]))
    if m := _PAREN.match(text):
        inner = m[2].strip()
        if inner.endswith("%") and re.fullmatch(_NUM + r"\s*%", inner):
            return Stat(_f(m[1]), center_type, "cv_percent", _f(inner[:-1]))
        if r := _RANGE.match(inner):
            return Stat(_f(m[1]), center_type, "range", _f(r[1]), _f(r[2]))
        if re.fullmatch(_NUM, inner):
            return Stat(_f(m[1]), center_type, "sd", _f(inner))
        return None
    if re.fullmatch(_NUM, text):
        return Stat(_f(text), center_type)
    return None
