"""France adapter: GTIN-14 = "0" + CIP13 → BDPM presentation (drug-resolution Req 4.1).

A French pack carries its CIP13 (13 digits, starting `3400`) as an EAN-13, so the GTIN-14 is a zero
followed by the CIP13. No other layout is accepted and nothing is derived from another one.
"""

from __future__ import annotations

import re

from janus.regions.base import Country, KeyGroup, ProductKey, Region, gs1_prefix_region
from janus.resolution.gs1 import Gs1Data, is_valid_gtin

CIP13_GTIN = re.compile(r"^0(3400[0-9]{9})$")


class FrCip13Adapter:
    region: Region = "EU"
    country: Country | None = "FR"
    source_id = "eu_fr_bdpm"

    def accepts_gtin(self, gtin14: str) -> bool:
        return CIP13_GTIN.match(gtin14) is not None and is_valid_gtin(gtin14)

    def structural_hint(self, gtin14: str) -> bool:
        return gs1_prefix_region(gtin14) == "FR"

    def key_groups(self, data: Gs1Data) -> list[KeyGroup]:
        m = CIP13_GTIN.match(data.gtin14)
        if m is None or not is_valid_gtin(data.gtin14):
            return []
        return [KeyGroup("cip13", (ProductKey("fr_cip13", m.group(1)),))]
