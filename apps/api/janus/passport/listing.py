"""Products with the same active ingredients in one target source (medication-passport design
§15, Req 14-16, DP27-DP33). Pure.

`listing()` takes the grouped rows of one target source and one item query and returns the
products whose mapped ingredient keys are exactly the item's keys (complete, not homeopathic,
finished products only), each with a per-product comparison of strength and dose form:
`same`, `different` or `unknown`. `same` is given only when both sides have a code and the codes
are equal (P22, P23); nothing is converted and nothing is assumed. The answer never says that two
products are the same medicine; the client words it as "contains the same active ingredient".

Only sources whose licence allows showing product names are listable (`LISTABLE_SOURCES`): the
TİTCK list has unclear redistribution terms, so its products are counted (`/passport/presence`)
but never listed (DP28).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from janus.passport.forms import FormTable
from janus.passport.presence import (
    ItemQuery,
    PresenceRow,
    Signature,
    answer,
    comparable_form,
    signature,
)
from janus.passport.schemas import (
    Answer,
    Level,
    LevelCounts,
    LevelReason,
    ListedIngredient,
    ListedProduct,
    ListingCounts,
    Marketed,
)

# Open licences that allow showing the published product name with attribution and data date:
# BDPM (Licence Ouverte), AEMPS Nomenclátor (reuse with attribution), openFDA NDC (CC0), AIFA open
# data (CC BY 4.0), Health Canada DPD (Open Government Licence, Canada).
LISTABLE_SOURCES: tuple[str, ...] = (
    "eu_fr_bdpm",
    "eu_es_cima",
    "openfda_ndc",
    "eu_it_aifa",
    "ca_dpd",
)
# openFDA product types that are not finished medicines a person can be given (DP31).
NOT_FINISHED_TYPES: frozenset[str] = frozenset(
    {
        "BULK INGREDIENT",
        "DRUG FOR FURTHER PROCESSING",
        "ANIMAL DRUG FOR FURTHER PROCESSING",
        "LICENSED VACCINE BULK INTERMEDIATE",
    }
)
_LEVEL_RANK: dict[Level, int] = {"same": 0, "unknown": 1, "different": 2}
_MARKETED_RANK: dict[Marketed, int] = {
    "listed_as_marketed": 0,
    "not_stated": 1,
    "listed_as_not_marketed": 2,
}


@dataclass(frozen=True)
class ListingRow:
    """One grouped row of the listing statement: `row.products` listings share every field."""

    row: PresenceRow
    name: str | None
    product_type: str | None
    marketing_end_date: str | None  # openFDA, YYYYMMDD
    status_published: Sequence[str]


@dataclass(frozen=True)
class Listing:
    answer: Answer  # status and counts, as `/passport/presence` computes them
    products: list[ListedProduct]  # every exact product, sorted (the service pages it)
    counts: ListingCounts
    not_finished_left_out: int


def marketed(
    source_id: str, status_published: Sequence[str], end_date: str | None, today: dt.date
) -> Marketed:
    """What the source states about marketing; never a statement about a pharmacy's stock."""
    if source_id == "eu_fr_bdpm":
        if "Commercialisée" in status_published:
            return "listed_as_marketed"
        return (
            "listed_as_not_marketed" if "Non commercialisée" in status_published else "not_stated"
        )
    if source_id == "eu_es_cima":
        if "commercialised:true" in status_published:
            return "listed_as_marketed"
        return (
            "listed_as_not_marketed" if "commercialised:false" in status_published else "not_stated"
        )
    if source_id == "ca_dpd":
        # The DPD extract read is the marketed one; the status is the source's own word.
        return "listed_as_marketed" if "MARKETED" in status_published else "not_stated"
    if (
        source_id == "openfda_ndc"
        and end_date is not None
        and len(end_date) == 8
        and end_date.isascii()
        and end_date.isdigit()
        and end_date < today.strftime("%Y%m%d")
    ):
        return "listed_as_not_marketed"
    return "not_stated"


def compare_strength(item: ItemQuery, sig: Signature) -> tuple[Level, LevelReason | None]:
    """`same` only when every ingredient has a code on both sides and all are equal (P23)."""
    if any(item.strengths.get(k) is None for k in item.keys):
        return "unknown", "not_known_for_item"
    if len(set(sig.keys)) != len(sig.keys) or any(c is None for c in sig.strengths):
        return "unknown", "not_known_in_source"
    equal = all(item.strengths[k] == c for k, c in zip(sig.keys, sig.strengths, strict=True))
    return ("same" if equal else "different"), None


def compare_form(item: ItemQuery, sig: Signature) -> tuple[Level, LevelReason | None]:
    if not comparable_form(item.form_group):
        return "unknown", "not_known_for_item"
    if not comparable_form(sig.form_group):
        return "unknown", "not_known_in_source"
    return ("same" if sig.form_group == item.form_group else "different"), None


def _tally(levels: Sequence[tuple[Level, int]]) -> LevelCounts:
    total = {"same": 0, "different": 0, "unknown": 0}
    for level, n in levels:
        total[level] += n
    return LevelCounts(**total)


def listing(
    item: ItemQuery, rows: Sequence[ListingRow], forms: FormTable, today: dt.date
) -> Listing:
    """Rows of one source. Exact ingredient-set equality decides what is listed (P22)."""
    finished = [r for r in rows if r.product_type not in NOT_FINISHED_TYPES]
    sigs = [signature(r.row, forms) for r in finished]
    # Source entries that show the same name, strengths, form and marketing statement are one
    # listed row with their number (openFDA lists one entry per labeller).
    merged: dict[str, ListedProduct] = {}
    for r, s in zip(finished, sigs, strict=True):
        if s.homeopathic or not s.complete or frozenset(s.keys) != item.keys:
            continue
        strength, strength_reason = compare_strength(item, s)
        form, form_reason = compare_form(item, s)
        product = ListedProduct(
            name=r.name or "",
            ingredients=[
                ListedIngredient(key=k, strength_published=p)
                for k, p in zip(r.row.keys, r.row.strengths, strict=True)
            ],
            dose_form_published=r.row.dosage_form,
            dose_form_group=s.form_group,  # pyright: ignore[reportArgumentType]
            strength=strength,
            strength_reason=strength_reason,
            dose_form=form,
            dose_form_reason=form_reason,
            marketed=marketed(r.row.source_id, r.status_published, r.marketing_end_date, today),
            listings=0,
        )
        key = product.model_dump_json()
        seen = merged.get(key, product)
        merged[key] = seen.model_copy(update={"listings": seen.listings + r.row.products})
    products = sorted(
        merged.values(),
        key=lambda p: (
            _MARKETED_RANK[p.marketed],
            _LEVEL_RANK[p.strength],
            _LEVEL_RANK[p.dose_form],
            p.name.casefold(),
            p.model_dump_json(),
        ),
    )
    left_out = 0
    for r in rows:
        if r.product_type in NOT_FINISHED_TYPES:
            s = signature(r.row, forms)
            if not s.homeopathic and s.complete and frozenset(s.keys) == item.keys:
                left_out += r.row.products
    return Listing(
        answer=answer(0, item, sigs),
        products=products,
        counts=ListingCounts(
            strength=_tally([(p.strength, p.listings) for p in products]),
            dose_form=_tally([(p.dose_form, p.listings) for p in products]),
        ),
        not_finished_left_out=left_out,
    )
