"""United States adapter: NDC GTIN (indicator, 03, 10 NDC digits, check) → openFDA NDC (Req 3.1).

Ten digits do not say which layout (4-4-2, 5-3-2, 5-4-1) they use, so all three canonical
11-digit keys are looked up and every hit is returned.
"""

from __future__ import annotations

from janus.regions.base import Country, KeyGroup, ProductKey, Region
from janus.resolution.gs1 import Gs1Data
from janus.resolution.ndc import layouts_of_ndc10, ndc_from_gtin


class OpenFdaNdcAdapter:
    region: Region = "US"
    country: Country | None = None
    source_id = "openfda_ndc"

    def accepts_gtin(self, gtin14: str) -> bool:
        return ndc_from_gtin(gtin14) is not None

    def keys_from_gtin(self, gtin14: str) -> list[ProductKey]:
        digits = ndc_from_gtin(gtin14)
        if digits is None:
            return []
        return sorted({ProductKey("ndc_package11", k) for k in layouts_of_ndc10(digits).values()})

    def structural_hint(self, gtin14: str) -> bool:
        return self.accepts_gtin(gtin14)

    def key_groups(self, data: Gs1Data) -> list[KeyGroup]:
        keys = self.keys_from_gtin(data.gtin14)
        return [KeyGroup("ndc_gtin", tuple(keys))] if keys else []
