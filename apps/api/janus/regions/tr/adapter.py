"""Türkiye adapter: İTS DataMatrix GTIN-14 = "0" + 13-digit TİTCK barcode (Req 2.1).

Every GTIN-14 that starts with "0" is looked up, whatever its GS1 prefix: the TİTCK list also
holds imported products with foreign prefixes. Name-only rows have no barcode key, so a barcode
lookup never returns them (Req 2.3).
"""

from __future__ import annotations

from janus.regions.base import Country, KeyGroup, ProductKey, Region, gs1_prefix_region
from janus.resolution.gs1 import Gs1Data


class TitckAdapter:
    region: Region = "TR"
    country: Country | None = None
    source_id = "titck"

    def accepts_gtin(self, gtin14: str) -> bool:
        return len(gtin14) == 14 and gtin14.startswith("0")

    def keys_from_gtin(self, gtin14: str) -> list[ProductKey]:
        return [ProductKey("tr_barcode", gtin14[1:])] if self.accepts_gtin(gtin14) else []

    def structural_hint(self, gtin14: str) -> bool:
        return gs1_prefix_region(gtin14) == "TR"

    def key_groups(self, data: Gs1Data) -> list[KeyGroup]:
        keys = self.keys_from_gtin(data.gtin14)
        return [KeyGroup("barcode", tuple(keys))] if keys else []
