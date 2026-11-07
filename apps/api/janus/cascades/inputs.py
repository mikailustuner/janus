"""Turn resolved list items into engine input (cascade-engine design §6.2, Req 7.1-7.3). Pure.

Codes are read only through `janus.resolution.model.rule_input`. Nothing region-specific passes
into the engine: an ingredient is its key, its rule-input codes and whether the codes are
form-confirmed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from janus.cascades.model import EngineIngredient, EngineItem, Month, NotChecked
from janus.resolution.model import IngredientCandidate, ResolvedIngredient, rule_input


class ChoiceError(ValueError):
    """A choice names a position that is not ambiguous, or a key outside its candidates."""


def _codes_of(atc: Sequence[str]) -> frozenset[str]:
    return frozenset(atc)


def product_item(
    index: int,
    start: Month | None,
    ingredients: Sequence[ResolvedIngredient],
    choices: Mapping[int, str],
    key_codes: Mapping[str, tuple[frozenset[str], str | None]],
) -> tuple[EngineItem, list[NotChecked]]:
    """A product's ingredients; `choices` maps an ambiguous position to the chosen key.

    `key_codes` gives, for a chosen key, all its ingredient-level codes and its English label
    (a chosen key is evaluated with all its codes, as form-unconfirmed: Req 7.2).
    """
    by_pos = {i.position: i for i in ingredients}
    for pos, qid in choices.items():
        ing = by_pos.get(pos)
        if ing is None or ing.status != "ambiguous" or qid not in ing.key_candidates:
            raise ChoiceError("choice does not match an ambiguous ingredient")
        if qid not in key_codes:
            raise ChoiceError("chosen key is not in the dataset")
    out: list[EngineIngredient] = []
    unchecked: list[NotChecked] = []
    for ing in sorted(ingredients, key=lambda i: i.position):
        if ing.status == "mapped" and ing.ingredient_key is not None:
            out.append(
                EngineIngredient(
                    key=ing.ingredient_key.qid,
                    codes=_codes_of(rule_input(ing)),
                    form_confirmed=ing.atc_selection != "all_codes",
                    label_en=ing.ingredient_key.label_en,
                )
            )
        elif ing.position in choices:
            qid = choices[ing.position]
            codes, label = key_codes[qid]
            out.append(EngineIngredient(qid, codes, False, label))
        elif ing.status == "ambiguous":
            unchecked.append(NotChecked(index, ing.position, "ambiguous"))
        else:
            unchecked.append(NotChecked(index, ing.position, ing.reason or "no_ingredient_key"))
    return EngineItem(index, start, tuple(out)), unchecked


def ingredient_item(
    index: int, start: Month | None, cand: IngredientCandidate
) -> tuple[EngineItem, list[NotChecked]]:
    """An ingredient found by name: all its ingredient-level codes, form-unconfirmed."""
    codes = frozenset(a.code for a in cand.atc_codes)
    if not codes:
        return EngineItem(index, start, ()), [NotChecked(index, 0, "no_ingredient_atc")]
    ing = EngineIngredient(cand.ingredient_key.qid, codes, False, cand.ingredient_key.label_en)
    return EngineItem(index, start, (ing,)), []
