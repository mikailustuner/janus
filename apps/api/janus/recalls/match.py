"""Recall matching (recall-check design §5, Req 3). Pure: no I/O, no clock.

A record is reported only when the query's NDC key is one of the NDC keys read from the record's
own text. The lot never decides whether a record is reported; it only adds `listed` or
`not_listed`, by equality of normalised codes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from janus.recalls.codes import lot_codes, ndc_keys, normalise_lot
from janus.resolution.ndc import NdcError, parse_ndc_input

NdcMatch = Literal["package", "product"]
LotMatch = Literal["listed", "not_listed", "not_given"]
TERMINATED = "Terminated"


@dataclass(frozen=True)
class Recall:
    recall_number: str
    event_id: str | None
    status: str | None
    classification: str | None
    product_description: str | None
    code_info: str | None
    more_code_info: str | None
    reason_for_recall: str | None
    recalling_firm: str | None
    recall_initiation_date: str | None
    center_classification_date: str | None
    report_date: str | None
    termination_date: str | None
    package_keys: frozenset[str]
    product_keys: frozenset[str]
    lot_codes: frozenset[str]

    @property
    def terminated(self) -> bool:
        return self.status == TERMINATED


def recall_from_row(row: Mapping[str, Any]) -> Recall:
    """A row of the `us_recalls` artifact with the keys and lot codes read from its text."""

    def text(name: str) -> str | None:
        value = row.get(name)
        return value if isinstance(value, str) and value else None

    description, code_info, more = (
        text("product_description"),
        text("code_info"),
        text("more_code_info"),
    )
    packages, products = ndc_keys(description, code_info, more)
    return Recall(
        recall_number=str(row["recall_number"]),
        event_id=text("event_id"),
        status=text("status"),
        classification=text("classification"),
        product_description=description,
        code_info=code_info,
        more_code_info=more,
        reason_for_recall=text("reason_for_recall"),
        recalling_firm=text("recalling_firm"),
        recall_initiation_date=text("recall_initiation_date"),
        center_classification_date=text("center_classification_date"),
        report_date=text("report_date"),
        termination_date=text("termination_date"),
        package_keys=packages,
        product_keys=products,
        lot_codes=lot_codes(code_info, more),
    )


@dataclass(frozen=True)
class Query:
    """`package` is the 11-digit key when the caller named a package; `product` its 9 digits.
    `lot` is the normalised lot, or None when no lot was given."""

    product: str
    package: str | None = None
    lot: str | None = None


def query_from_input(ndc: str, lot: str | None = None) -> Query:
    """NDC as written (hyphenated package or product, or 11 digits) → query.

    Raises `NdcError` for anything else, including ten plain digits: their three possible
    layouts would name up to three different products.
    """
    keys = parse_ndc_input(ndc)
    if len(keys) != 1:
        raise NdcError()
    (key,) = keys
    normalised = None if lot is None else normalise_lot(lot)
    if key.kind == "ndc_package11":
        return Query(product=key.code[:9], package=key.code, lot=normalised)
    return Query(product=key.code, lot=normalised)


@dataclass(frozen=True)
class Match:
    recall: Recall
    ndc_match: NdcMatch
    lot_match: LotMatch


@dataclass(frozen=True)
class Index:
    """Records by product key. Every record with a package key is under that package's product
    key too (`codes.ndc_keys`), so one lookup finds both kinds of match."""

    by_product: Mapping[str, tuple[Recall, ...]]
    records: int
    records_with_ndc: int


def build_index(recalls: Iterable[Recall]) -> Index:
    by_product: dict[str, list[Recall]] = {}
    total = with_ndc = 0
    for recall in recalls:
        total += 1
        with_ndc += bool(recall.product_keys)
        for key in recall.product_keys:
            by_product.setdefault(key, []).append(recall)
    return Index({k: tuple(v) for k, v in by_product.items()}, total, with_ndc)


def _lot_match(recall: Recall, lot: str | None) -> LotMatch:
    if lot is None:
        return "not_given"
    return "listed" if lot in recall.lot_codes else "not_listed"


def _order(m: Match) -> tuple[int, int, int, str]:
    # Lot listed first, package before product, newer report first, then the recall number.
    report = m.recall.report_date
    return (
        0 if m.lot_match == "listed" else 1,
        0 if m.ndc_match == "package" else 1,
        -int(report.replace("-", "")) if report else 0,
        m.recall.recall_number,
    )


def find(index: Index, query: Query) -> list[Match]:
    """Every record that names the query's package or product code, in the documented order."""
    out = [
        Match(
            recall,
            "package"
            if query.package is not None and query.package in recall.package_keys
            else "product",
            _lot_match(recall, query.lot),
        )
        for recall in index.by_product.get(query.product, ())
    ]
    return sorted(out, key=_order)
