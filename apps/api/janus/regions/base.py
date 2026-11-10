"""Region adapter interface (drug-resolution design §4.1, §13.1, Req 10).

An adapter knows how a region's codes look and which product keys they give; the lookup itself
goes through the shared repository, and every adapter's products have the same shape. A new
region or country adds an adapter and a registration line; the service, the result model and
`rule_input` stay unchanged (Req 4.5).

Phase 2: region `EU` has one adapter per country (`FR`, `ES`) and one adapter that only knows
countries without an open product-code database. An adapter returns **key groups in order of
trust**: the service uses the first group that finds a product and never merges groups.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from janus.resolution.gs1 import Gs1Data

Region = Literal["TR", "US", "EU"]
Country = Literal["FR", "ES", "IT"]
KeyKind = Literal[
    "tr_barcode", "ndc_product9", "ndc_package11", "fr_cip13", "es_cn", "es_ntin", "es_gtin"
]  # `ca_din` and `it_aic` are stored as identifiers; no adapter looks a scan up by them
MatchedBy = Literal["barcode", "ndc_gtin", "cip13", "ntin", "gtin", "ai_712", "ntin_digits"]


@dataclass(frozen=True, order=True)
class ProductKey:
    kind: KeyKind
    code: str


@dataclass(frozen=True)
class KeyGroup:
    """Keys that one kind of evidence gives, and the label the result carries for it."""

    matched_by: MatchedBy
    keys: tuple[ProductKey, ...]


class RegionAdapter(Protocol):
    # Read-only members, so an adapter may declare narrower types (e.g. a fixed `source_id`).
    @property
    def region(self) -> Region: ...

    @property
    def country(self) -> Country | None: ...

    @property
    def source_id(self) -> str | None:
        """None: the adapter searches no source (eu_name)."""
        ...

    def accepts_gtin(self, gtin14: str) -> bool: ...

    def structural_hint(self, gtin14: str) -> bool: ...

    def key_groups(self, data: Gs1Data) -> list[KeyGroup]: ...


# --- GS1 company-prefix table ------------------------------------------------------------------


@dataclass(frozen=True)
class PrefixRow:
    """A GS1 prefix range (three digits after the indicator digit) and what is known of it."""

    low: int
    high: int
    country: Literal["FR", "ES", "DE"]
    no_open_database: bool
    source: str
    checked: str


# Checked 2026-11-08 against Wikipedia "List of GS1 country codes" (a secondary copy of the GS1
# prefix list; gs1.org is not readable from the research environment). Other EU countries are
# deliberately absent until they are verified (drug-resolution Req 4.3).
_SOURCE = "Wikipedia: List of GS1 country codes (secondary copy of the GS1 prefix list)"
GS1_PREFIXES: tuple[PrefixRow, ...] = (
    PrefixRow(300, 379, "FR", False, _SOURCE, "2026-11-08"),
    PrefixRow(400, 440, "DE", True, _SOURCE, "2026-11-08"),
    PrefixRow(840, 849, "ES", False, _SOURCE, "2026-11-08"),
)


def _prefix_row(gtin14: str) -> PrefixRow | None:
    if len(gtin14) != 14 or not gtin14[1:4].isdigit():
        return None
    prefix = int(gtin14[1:4])
    return next((r for r in GS1_PREFIXES if r.low <= prefix <= r.high), None)


def gs1_prefix_region(gtin14: str) -> Literal["TR", "US", "FR", "ES", "DE", "other"]:
    """Region suggested by the GS1 company prefix (a hint only, never a filter)."""
    if gtin14[1:3] == "03" and gtin14[0] in "012345678":
        return "US"
    if int(gtin14[1:4]) in (868, 869):
        return "TR"
    row = _prefix_row(gtin14)
    return row.country if row is not None else "other"


def no_open_database_country(gtin14: str) -> Literal["DE"] | None:
    """The country of a GTIN whose products cannot be looked up in an open database."""
    row = _prefix_row(gtin14)
    return "DE" if row is not None and row.no_open_database and row.country == "DE" else None
