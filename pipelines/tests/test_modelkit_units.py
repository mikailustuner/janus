"""Unit table, dimension checks, per-kg handling, mean type and dispersion."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.modelkit.units import (
    Canonical,
    from_canonical,
    parse_stat,
    parse_unit,
    per_kg_to_absolute,
    resolve_parameter,
    to_canonical,
)


def test_known_conversions() -> None:
    c = to_canonical("cl", 100.0, "mL/min")
    assert isinstance(c, Canonical) and c.unit == "L/h" and c.value_si == pytest.approx(6.0)
    c = to_canonical("auc_inf", 68.186, "ug*h/mL")
    assert isinstance(c, Canonical) and c.value_si == pytest.approx(68186.0)
    c = to_canonical("auc_inf", 5.0, "mg·h/L")  # mg*h/L = ug*h/mL
    assert isinstance(c, Canonical) and c.value_si == pytest.approx(5000.0)
    c = to_canonical("cmax", 2.0, "µg/L")
    assert isinstance(c, Canonical) and c.value_si == pytest.approx(2.0)
    c = to_canonical("t_half", 90.0, "min")
    assert isinstance(c, Canonical) and c.value_si == pytest.approx(1.5)
    c = to_canonical("f", 40.0, "%")
    assert isinstance(c, Canonical) and c.value_si == pytest.approx(0.4)
    c = to_canonical("v_f", 120.0, "dL")
    assert isinstance(c, Canonical) and c.value_si == pytest.approx(12.0)


def test_dimension_mismatches_are_refused() -> None:
    assert to_canonical("cl", 1.0, "L").issue == "dimension_mismatch"  # type: ignore[union-attr]
    assert to_canonical("t_half", 1.0, "ng/mL").issue == "dimension_mismatch"  # type: ignore[union-attr]
    assert to_canonical("cmax", 1.0, "ng*h/mL").issue == "dimension_mismatch"  # type: ignore[union-attr]
    assert to_canonical("auc_inf", 1.0, "ng/mL").issue == "dimension_mismatch"  # type: ignore[union-attr]
    assert to_canonical("cmax", 1.0, "nmol/mL").issue == "molar_unit_needs_molar_mass"  # type: ignore[union-attr]
    assert to_canonical("cl", 1.0, "furlongs").issue == "unit_unknown"  # type: ignore[union-attr]
    assert to_canonical("cl", -1.0, "L/h").issue == "not_positive_finite"  # type: ignore[union-attr]
    assert to_canonical("cmax", 1.0, "ng/mL/kg").issue == "per_kg_needs_body_weight"  # type: ignore[union-attr]


def test_candesartan_case_total_clearance_per_kg_is_not_cl_f() -> None:
    """Regression (pilot 2): 0.37 mL/min/kg times 70 kg was typed as an apparent oral clearance."""
    assert resolve_parameter("cl", "mL/min/kg") == "cl_per_kg"
    assert resolve_parameter("cl_f", "mL/min/kg") == "cl_per_kg"
    c = to_canonical("cl", 0.37, "mL/min/kg")
    assert isinstance(c, Canonical)
    assert c.parameter == "cl_per_kg" and c.unit == "L/h/kg"
    assert c.value_si == pytest.approx(0.37 * 0.06)
    # no body weight, no conversion; with one, the result is an absolute CL, never CL/F
    with pytest.raises(ValueError):
        per_kg_to_absolute("cl_per_kg", c.value_si, None)
    name, absolute = per_kg_to_absolute("cl_per_kg", c.value_si, 70.0)
    assert name == "cl" and absolute == pytest.approx(0.37 * 0.06 * 70.0)
    assert name != "cl_f"
    with pytest.raises(ValueError):
        per_kg_to_absolute("cl_f", 1.0, 70.0)
    with pytest.raises(ValueError):
        per_kg_to_absolute("cl_per_kg", 1.0, 0.0)


@given(
    st.sampled_from(["cl", "cl_f", "vss", "vd", "v_f", "t_half", "tmax", "cmax", "auc_inf"]),
    st.floats(1e-6, 1e6),
)
def test_canonical_round_trip(parameter: str, value: float) -> None:
    unit = {
        "cl": "mL/min", "cl_f": "L/h", "vss": "L", "vd": "mL", "v_f": "L", "t_half": "min",
        "tmax": "h", "cmax": "ug/L", "auc_inf": "ug*h/mL",
    }[parameter]  # fmt: skip
    c = to_canonical(parameter, value, unit)
    assert isinstance(c, Canonical)
    back = from_canonical(parameter, c.value_si, unit)
    assert back is not None and math.isclose(back, value, rel_tol=1e-9)


def test_unit_parser_shapes() -> None:
    for text in ("ng*h/mL", "ng•hr/mL", "h*ug/L", "ng.h/mL", "ng h/mL"):
        u = parse_unit(text)
        assert u is not None and u.dim == (1, -3, 1, 0, 0)
    assert parse_unit("mL/min/kg").dim == (0, 3, -1, -1, 0)  # type: ignore[union-attr]
    assert parse_unit("mg/kg") is None or parse_unit("mg/kg").dim == (1, 0, 0, -1, 0)  # type: ignore[union-attr]
    assert parse_unit("") is None and parse_unit("ng//mL") is None


def test_mean_type_and_dispersion_are_separate() -> None:
    s = parse_stat("26.2 ± 4.8", "arithmetic")
    assert s is not None and s.center == 26.2 and s.center_type == "arithmetic"
    assert s.spread_type == "sd" and s.spread_low == 4.8
    s = parse_stat("68186 (25%)", "geometric")
    assert s is not None and s.center_type == "geometric" and s.spread_type == "cv_percent"
    s = parse_stat("12 (8-16)", "median")
    assert s is not None and (s.spread_type, s.spread_low, s.spread_high) == ("range", 8.0, 16.0)
    s = parse_stat("6")
    assert s is not None and s.spread_type == "none" and s.center_type == "unspecified"
    assert parse_stat("n/a") is None and parse_stat("1.5 (abc)") is None
