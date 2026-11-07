"""Region adapter interface (drug-resolution design §4.1, Req 10).

An adapter knows how a region's codes look and which product keys they give; the lookup itself
goes through the shared repository, and every adapter's products have the same shape. A new
region adds an adapter and a registration line; the service, the result model and
`rule_input` stay unchanged (Req 4.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

Region = Literal["TR", "US"]


@dataclass(frozen=True, order=True)
class ProductKey:
    kind: Literal["tr_barcode", "ndc_product9", "ndc_package11"]
    code: str


class RegionAdapter(Protocol):
    region: Region
    source_id: str
    matched_by: Literal["barcode", "ndc_gtin"]

    def accepts_gtin(self, gtin14: str) -> bool: ...

    def keys_from_gtin(self, gtin14: str) -> list[ProductKey]: ...

    def structural_hint(self, gtin14: str) -> bool: ...


def gs1_prefix_region(gtin14: str) -> Literal["TR", "US", "FR", "ES", "DE", "other"]:
    """Region suggested by the GS1 company prefix (a hint only, never a filter)."""
    if gtin14[1:3] == "03" and gtin14[0] in "012345678":
        return "US"
    prefix = int(gtin14[1:4])
    if prefix in (868, 869):
        return "TR"
    if 300 <= prefix <= 379:
        return "FR"
    if 840 <= prefix <= 849:
        return "ES"
    if 400 <= prefix <= 440:
        return "DE"
    return "other"
