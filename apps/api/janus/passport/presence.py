"""Presence evaluation (medication-passport design §5.3, DP2, DP8, DP9, DP11). Pure.

`signature()` turns one grouped row of the presence statement into a `Signature` (strength codes,
dose-form group, homeopathic decision with the same functions as `/resolve/products`).
`evaluate()` answers every item for every source from the signatures alone, so item order, key
order and repeated items change nothing (P10). Only `mapped` ingredients count; a product with an
`unmapped` or `ambiguous` ingredient is never an exact match (DP11); homeopathic products count
towards nothing and are reported as `homeopathic_left_out` (DP9).
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass

from janus.passport.forms import NOT_COMPARED_GROUPS, FormTable
from janus.passport.schemas import Answer, Cmp, Comparison, ItemIn, ItemOut
from janus.passport.strength import StrengthCode, strength_code
from janus.resolution.model import is_homeopathic_product
from janus.resolution.prepare_eu import is_homeopathic_name

# (source id, region, country) in the fixed answer order TR, EU-FR, EU-ES, EU-DE, US (Req 2.1).
SOURCE_ORDER: tuple[tuple[str | None, str, str | None], ...] = (
    ("titck", "TR", None),
    ("eu_fr_bdpm", "EU", "FR"),
    ("eu_es_cima", "EU", "ES"),
    (None, "EU", "DE"),
    ("openfda_ndc", "US", None),
)


@dataclass(frozen=True)
class PresenceRow:
    """One row of the grouped statement of §4.2 (`products` products share it)."""

    source_id: str
    keys: Sequence[str]  # mapped keys, ordered by key then position (may repeat)
    strengths: Sequence[str | None]  # aligned with `keys`
    complete: bool  # every ingredient row is mapped
    hp_strength: bool  # some ingredient strength is in homeopathic units
    hp_names: Sequence[str]  # names that may carry the BDPM homeopathic marker (pre-filter)
    region: str
    dosage_form: str | None
    routes: Sequence[str]
    products: int


@dataclass(frozen=True)
class Signature:
    source_id: str
    keys: tuple[str, ...]
    strengths: tuple[StrengthCode | None, ...]
    complete: bool
    homeopathic: bool
    form_group: str | None
    products: int


@dataclass(frozen=True)
class ItemQuery:
    keys: frozenset[str]
    strengths: Mapping[str, StrengthCode | None]
    form_group: str | None

    @classmethod
    def of(cls, item: ItemIn) -> ItemQuery:
        return cls(
            frozenset(i.key for i in item.ingredients),
            {
                i.key: None
                if i.strength is None
                else StrengthCode(i.strength.amount, i.strength.unit, i.strength.basis)
                for i in item.ingredients
            },
            item.dose_form,
        )


def signature(row: PresenceRow, forms: FormTable) -> Signature:
    """Same homeopathic rule as `/resolve/products` (P8): homeopathic units in any strength, or
    for EU products the BDPM name marker (decided exactly by `is_homeopathic_name`)."""
    homeopathic = row.hp_strength or (
        row.region == "EU" and any(is_homeopathic_name(n) for n in row.hp_names)
    )
    group = forms.group(row.source_id, row.dosage_form, row.routes)
    return Signature(
        row.source_id,
        tuple(row.keys),
        tuple(strength_code(row.source_id, s, group) for s in row.strengths),
        row.complete,
        homeopathic,
        group,
        row.products,
    )


def is_homeopathic(strengths: Iterable[str | None], names: Iterable[str], region: str) -> bool:
    """The resolution rule itself (for tests): `ProductCandidate.homeopathic`."""
    return is_homeopathic_product(strengths) or (
        region == "EU" and any(is_homeopathic_name(n) for n in names)
    )


def comparable_form(group: str | None) -> bool:
    return group is not None and group not in NOT_COMPARED_GROUPS


def cmp(products: int, comparable: int, equal: int, item_known: bool) -> Cmp:
    """The result function of §5.3 (P9)."""
    if not item_known:
        return Cmp(result="could_not_compare", reason="not_known_for_item", comparable=0, equal=0)
    if equal > 0:
        return Cmp(result="matched", reason=None, comparable=comparable, equal=equal)
    if comparable == products:
        return Cmp(result="differs", reason=None, comparable=comparable, equal=0)
    reason = "not_known_in_source" if comparable == 0 else "not_all_comparable"
    return Cmp(result="could_not_compare", reason=reason, comparable=comparable, equal=0)


def compare(item: ItemQuery, exact: Sequence[Signature]) -> Comparison:
    """Strength, dose form and both, over the counted products (signature x count)."""
    products = sum(s.products for s in exact)
    strength_known = all(item.strengths.get(k) is not None for k in item.keys)
    form_known = comparable_form(item.form_group)
    totals = [0, 0, 0, 0, 0, 0]  # comparable and equal: strength, form, both
    for s in exact:
        s_cmp = (
            strength_known
            and len(set(s.keys)) == len(s.keys)
            and all(c is not None for c in s.strengths)
        )
        s_eq = s_cmp and all(
            item.strengths[k] == c for k, c in zip(s.keys, s.strengths, strict=True)
        )
        f_cmp = form_known and comparable_form(s.form_group)
        f_eq = f_cmp and s.form_group == item.form_group
        flags = (s_cmp, s_eq, f_cmp, f_eq, s_cmp and f_cmp, s_eq and f_eq)
        totals = [t + (s.products if f else 0) for t, f in zip(totals, flags, strict=True)]
    return Comparison(
        strength=cmp(products, totals[0], totals[1], strength_known),
        dose_form=cmp(products, totals[2], totals[3], form_known),
        strength_and_dose_form=cmp(products, totals[4], totals[5], strength_known and form_known),
    )


def _unavailable(index: int) -> Answer:
    return Answer(
        source=index,
        status="source_unavailable",
        products=0,
        with_other_ingredients=0,
        keys_found=[],
        homeopathic_left_out=0,
        comparison=None,
    )


def answer(index: int, item: ItemQuery, sigs: Sequence[Signature]) -> Answer:
    """One item against the signatures of one loaded source."""
    plain = [s for s in sigs if not s.homeopathic]
    exact = [s for s in plain if s.complete and frozenset(s.keys) == item.keys]
    products = sum(s.products for s in exact)
    with_other = sum(
        s.products
        for s in plain
        if not (s.complete and frozenset(s.keys) == item.keys) and item.keys <= set(s.keys)
    )
    found = sorted(item.keys & {k for s in plain for k in s.keys})
    left_out = sum(s.products for s in sigs if s.homeopathic and item.keys & set(s.keys))
    status = "present" if products else ("not_present" if found else "not_in_source")
    return Answer(
        source=index,
        status=status,
        products=products,
        with_other_ingredients=with_other,
        keys_found=found,
        homeopathic_left_out=left_out,
        comparison=compare(item, exact) if products else None,
    )


def evaluate(
    items: Sequence[ItemIn],
    signatures: Iterable[Signature],
    loaded: Collection[str],
    known_keys: Collection[str],
) -> list[ItemOut]:
    """Answers in request order, one per source in `SOURCE_ORDER` (Req 2.4, 2.6, 2.7, 6.2)."""
    by_source: dict[str, list[Signature]] = {}
    for s in signatures:
        by_source.setdefault(s.source_id, []).append(s)
    out: list[ItemOut] = []
    for n, item in enumerate(items):
        q = ItemQuery.of(item)
        answers = [
            answer(i, q, by_source.get(sid, []))
            if sid is not None and sid in loaded
            else _unavailable(i)
            for i, (sid, _, _) in enumerate(SOURCE_ORDER)
        ]
        out.append(
            ItemOut(
                item=n,
                keys=sorted(q.keys),
                unknown_keys=sorted(q.keys - set(known_keys)),
                answers=answers,
            )
        )
    return out
