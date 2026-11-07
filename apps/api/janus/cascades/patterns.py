"""ATC class matching (cascade-engine design §4.1, Req 1.2, 7.4). Pure.

`class_match` is the only class matcher. The engine, the abrupt-stop flags and the coverage
report all call it, so there is one definition of "this code belongs to this class".
"""

from __future__ import annotations

from collections.abc import Set

from janus.cascades.model import AtcClass, Scope
from janus.resolution.atc import ATC_PREFIX, INGREDIENT_LEVEL


def is_prefix_pattern(value: str) -> bool:
    """An ATC prefix of level 1-5: 1, 3, 4, 5 or 7 characters."""
    return bool(ATC_PREFIX.fullmatch(value))


def is_ingredient_code(value: str) -> bool:
    return bool(INGREDIENT_LEVEL.fullmatch(value))


def class_match(code: str, cls: AtcClass, active: Set[str] = frozenset()) -> Scope | None:
    """The scope of the longest pattern of `cls` that is a prefix of `code`, if it is an include.

    Form-extension patterns count only when their evidence id is in `active`. `code` may be any
    string (the coverage report passes published codes of any length).
    """
    best = None
    for p in cls.patterns:
        if p.scope == "form_extension" and p.evidence_id not in active:
            continue
        if code.startswith(p.prefix) and (best is None or len(p.prefix) > len(best.prefix)):
            best = p
    if best is None or best.match == "exclude":
        return None
    return best.scope
