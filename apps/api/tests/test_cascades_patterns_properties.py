"""Property P8: class matching (cascade-engine design §4.1, §9)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from janus.cascades.model import AtcClass
from janus.cascades.patterns import class_match, is_prefix_pattern
from tests.cascades_strategies import (
    EXTENSION_IDS,
    atc_classes,
    ingredient_codes,
    prefix_of,
    ref_class_match,
)

ACTIVE = st.frozensets(st.sampled_from(EXTENSION_IDS))


@given(cls=atc_classes(), code=ingredient_codes(), active=ACTIVE, data=st.data())
def test_class_match_follows_longest_pattern(
    cls: AtcClass, code: str, active: frozenset[str], data: st.DataObject
) -> None:
    """Feature: cascade-engine, Property 8. Validates: Req 1.2, 7.4.

    `class_match` equals the brute-force longest-prefix reference, does not depend on the
    order of the class's patterns, and an inactive extension behaves as if its pattern were
    absent.
    """
    expected = ref_class_match(code, cls, active)
    assert class_match(code, cls, active) == expected

    shuffled = AtcClass(cls.class_id, tuple(data.draw(st.permutations(cls.patterns))))
    assert class_match(code, shuffled, active) == expected

    without_inactive = AtcClass(
        cls.class_id,
        tuple(p for p in cls.patterns if p.scope == "pipc" or p.evidence_id in active),
    )
    assert class_match(code, without_inactive, frozenset(EXTENSION_IDS)) == expected


@given(code=ingredient_codes(), level=st.integers(1, 5))
def test_every_level_prefix_is_a_pattern(code: str, level: int) -> None:
    """Feature: cascade-engine, Property 8. Validates: Req 1.2 (pattern shapes)."""
    assert is_prefix_pattern(prefix_of(code, level))
    assert not is_prefix_pattern(code[:2])
    assert not is_prefix_pattern(code[:6])
    assert not is_prefix_pattern(code + "1")
