"""Ingredient lists of the French and Spanish sources (drug-resolution design §14.2, §14.3). Pure.

BDPM: the composition lines of a presentation are grouped by link number; per link the `FT` names
(therapeutic fraction) stand for the ingredient, and only a link without an `FT` line uses its `SA`
names (substance as formulated). Nomenclátor: the ingredients in `orden_colacion` order.
Both keep names and strengths exactly as published (licence: data are not altered).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from janus.resolution.names import fold

UNNAMED = "(unnamed ingredient)"
HOMEOPATHIC_MARKER = "pour preparations homeopathiques"


@dataclass(frozen=True)
class SourceIngredient:
    """One ingredient of a presentation: the published name and the dosage it was named from."""

    name: str
    strength: str | None


@dataclass(frozen=True)
class LinkStats:
    """Composition lines that did not become an ingredient of their own (coverage report)."""

    links: int = 0
    superseded_sa_lines: int = 0  # SA lines of a link that has an FT line
    multi_ft_links: int = 0  # links with two or more FT lines (each is an ingredient)


def _opt(value: Any) -> str | None:
    return None if value is None else str(value)


def bdpm_ingredients(
    composition: Sequence[Mapping[str, Any]],
) -> tuple[tuple[SourceIngredient, ...], LinkStats]:
    """Ingredients of a BDPM presentation from its composition lines (Req 5.8).

    Links are taken in the order of their first line; a line without a link number is a link of
    its own. Per link: every `FT` line is an ingredient; if there is none, every `SA` line is.
    """
    order: list[str] = []
    ft: dict[str, list[Mapping[str, Any]]] = {}
    sa: dict[str, list[Mapping[str, Any]]] = {}
    for i, line in enumerate(composition):
        link = _opt(line.get("link")) or f"\x00{i}"
        if link not in ft:
            order.append(link)
            ft[link], sa[link] = [], []
        (ft if line.get("nature") == "FT" else sa)[link].append(line)
    out: list[SourceIngredient] = []
    superseded = multi_ft = 0
    for link in order:
        chosen = ft[link] or sa[link]
        if ft[link]:
            superseded += len(sa[link])
            multi_ft += len(ft[link]) > 1
        out.extend(
            SourceIngredient(str(c.get("substance_name") or UNNAMED), _opt(c.get("dosage")))
            for c in chosen
        )
    return tuple(out), LinkStats(len(order), superseded, multi_ft)


def cima_ingredients(ingredients: Sequence[Mapping[str, Any]]) -> tuple[SourceIngredient, ...]:
    """Ingredients of a Nomenclátor presentation in `orden_colacion` order (file order breaks ties
    and puts a missing order last)."""
    indexed = list(enumerate(ingredients))
    indexed.sort(key=lambda p: (p[1].get("order") is None, p[1].get("order") or 0, p[0]))
    out: list[SourceIngredient] = []
    for _, ing in indexed:
        dose = _opt(ing.get("dose"))
        unit = _opt(ing.get("dose_unit"))
        strength = " ".join(x for x in (dose, unit) if x) or None
        out.append(SourceIngredient(str(ing.get("name") or UNNAMED), strength))
    return tuple(out)


def is_homeopathic_name(name: str) -> bool:
    """A BDPM substance name that carries the homeopathic marker (Req 12.10)."""
    return HOMEOPATHIC_MARKER in fold(name)
