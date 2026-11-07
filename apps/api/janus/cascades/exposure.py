"""Exposures: an ingredient key's list items that match a class (design §4.3, DP10). Pure."""

from __future__ import annotations

from collections.abc import Sequence, Set

from janus.cascades.model import AtcClass, EngineItem, Exposure, Month
from janus.cascades.patterns import class_match


def exposures(
    items: Sequence[EngineItem], cls: AtcClass, active: Set[str] = frozenset()
) -> dict[str, Exposure]:
    """Per ingredient key, the copies whose codes match `cls`.

    The start is the earliest start of the matching copies when all of them are known, and
    unknown otherwise: a copy of unknown start could have begun before the other drug.
    """
    copies: dict[str, list[tuple[int, Month | None, bool, bool, tuple[str, ...], str | None]]] = {}
    for item in items:
        for ing in item.ingredients:
            matched: list[str] = []
            pipc = False
            for code in sorted(ing.codes):
                scope = class_match(code, cls, active)
                if scope is not None:
                    matched.append(code)
                    pipc = pipc or scope == "pipc"
            if matched:
                copies.setdefault(ing.key, []).append(
                    (item.index, item.start, ing.form_confirmed, pipc, tuple(matched), ing.label_en)
                )
    out: dict[str, Exposure] = {}
    for key in sorted(copies):
        cs = copies[key]
        starts = [c[1] for c in cs]
        known = [s for s in starts if s is not None]
        labels = sorted({c[5] for c in cs if c[5] is not None})
        out[key] = Exposure(
            key=key,
            items=frozenset(c[0] for c in cs),
            start=min(known) if len(known) == len(starts) else None,
            form_confirmed=any(c[2] for c in cs),
            via_extension=not any(c[3] for c in cs),
            matched_codes=tuple(sorted({code for c in cs for code in c[4]})),
            label_en=labels[0] if labels else None,
        )
    return out
