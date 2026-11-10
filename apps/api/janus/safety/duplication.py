"""Therapeutic duplication on a medicine list (safety-check design §4, Req 2). Pure.

Two findings, both between different list items only:
- `same_ingredient`: one ingredient key in two or more items (the certain case);
- `same_group`: two different keys with an ingredient-level ATC code of one chemical subgroup
  (ATC 4th level, five characters). A statement that the medicines belong to one group, not that
  they overlap in effect.

Codes come from `rule_input` through the engine items, so a combination product's own code is
never compared. Residual subgroups (4th-level letter X, WHO's "other" groups) are not classes
and are skipped.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from janus.cascades.model import EngineItem
from janus.resolution.atc import is_ingredient_level

RULES_VERSION = "duplication-1"
GROUP_LENGTH = 5  # ATC 4th level: chemical subgroup
Kind = Literal["same_ingredient", "same_group"]


@dataclass(frozen=True)
class Member:
    """One ingredient key of a finding with the list items that contain it."""

    key: str
    label_en: str | None
    items: tuple[int, ...]  # ascending
    codes: tuple[str, ...]  # codes of the finding's subgroup (same_group); else all codes
    form_confirmed: bool


@dataclass(frozen=True)
class Finding:
    kind: Kind
    group: str | None  # the chemical subgroup of a same_group finding
    members: tuple[Member, ...]  # one for same_ingredient; two or more keys for same_group

    @property
    def items(self) -> tuple[int, ...]:
        return tuple(sorted({i for m in self.members for i in m.items}))

    @property
    def form_confirmed(self) -> bool:
        return all(m.form_confirmed for m in self.members)

    @property
    def finding_id(self) -> str:
        return f"{self.kind}:{self.group or self.members[0].key}"


def group_of(code: str) -> str | None:
    """The chemical subgroup of an ingredient-level code; None for a residual subgroup or a code
    that is not ingredient-level."""
    if not is_ingredient_level(code) or code[GROUP_LENGTH - 1] == "X":
        return None
    return code[:GROUP_LENGTH]


def find(items: Sequence[EngineItem]) -> list[Finding]:
    """Findings in order: same ingredient by key, then same group by subgroup code."""
    # key -> item index -> (codes, form_confirmed, label)
    seen: dict[str, dict[int, tuple[frozenset[str], bool, str | None]]] = {}
    for item in items:
        for ing in item.ingredients:
            codes, confirmed, label = seen.setdefault(ing.key, {}).get(
                item.index, (frozenset[str](), True, None)
            )
            seen[ing.key][item.index] = (
                codes | ing.codes,
                confirmed and ing.form_confirmed,
                label or ing.label_en,
            )

    def member(key: str, group: str | None) -> Member | None:
        hits = {
            i: (codes if group is None else {c for c in codes if group_of(c) == group}, conf, label)
            for i, (codes, conf, label) in seen[key].items()
        }
        if group is not None:
            hits = {i: h for i, h in hits.items() if h[0]}
        if not hits:
            return None
        return Member(
            key=key,
            label_en=next((h[2] for _, h in sorted(hits.items()) if h[2]), None),
            items=tuple(sorted(hits)),
            codes=tuple(sorted({c for h in hits.values() for c in h[0]})),
            form_confirmed=all(h[1] for h in hits.values()),
        )

    out: list[Finding] = []
    for key in sorted(seen):
        m = member(key, None)
        if m is not None and len(m.items) >= 2:
            out.append(Finding("same_ingredient", None, (m,)))
    groups = sorted(
        {
            g
            for by_item in seen.values()
            for codes, _, _ in by_item.values()
            for g in (group_of(c) for c in codes)
            if g is not None
        }
    )
    for group in groups:
        members = tuple(m for m in (member(k, group) for k in sorted(seen)) if m is not None)
        # Two different keys standing in two different items.
        if any(
            a.key != b.key and any(i != j for i in a.items for j in b.items)
            for a in members
            for b in members
        ):
            out.append(Finding("same_group", group, members))
    return out
