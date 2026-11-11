"""Confirmation by two readers: value, unit, analyte and context must all agree."""

from __future__ import annotations

from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.modelkit.confirm import Context, Reading, confirm, values_agree

A = Reading(10.0, "L/h", "parent", Context())


def test_same_everything_is_confirmed() -> None:
    assert confirm(A, replace(A, value=10.09)).confirmed
    assert not confirm(A, replace(A, value=10.2)).confirmed  # beyond 1 %


def test_same_value_different_context_is_a_disagreement() -> None:
    """Owner decision 2026-11-11: agreeing on the value is not enough."""
    for change, field in (
        ({"arm": "crossover test arm"}, "arm"),
        ({"coadministered": "ketoconazole"}, "coadministered"),
        ({"formulation": "modified_release"}, "formulation"),
        ({"food": "fed"}, "food"),
        ({"population": "special"}, "population"),
        ({"sex": "female"}, "sex"),
    ):
        other = replace(A, context=replace(A.context, **change))
        r = confirm(A, other)
        assert not r.confirmed and r.reason == "context_differs" and r.differing == (field,)
        assert confirm(other, A) == r.__class__(False, "context_differs", (field,))


def test_value_unit_analyte_and_missing_values() -> None:
    assert confirm(A, replace(A, unit="mL/min")).reason == "units_differ"
    assert confirm(A, replace(A, analyte_class="metabolite")).reason == "analytes_differ"
    assert confirm(A, replace(A, value=None)).reason == "reader_found_no_value"
    both_meta = replace(A, analyte_class="metabolite")
    assert confirm(both_meta, both_meta).reason == "not_the_parent_drug"


@given(st.floats(1e-6, 1e6), st.floats(1e-6, 1e6))
def test_values_agree_is_symmetric(a: float, b: float) -> None:
    assert values_agree(a, b) == values_agree(b, a)
