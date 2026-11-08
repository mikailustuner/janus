"""Countries without an open product-code database (drug-resolution Req 4.3, 6.2).

Germany (and any country added to the GS1 prefix table with `no_open_database`) has no open
database that maps a pack code to a product. This adapter searches no source: it only says that a
scan belongs to such a country, so the service can answer with a notice and no candidate, and the
client can offer name search and on-device text recognition instead.
"""

from __future__ import annotations

from janus.regions.base import Country, KeyGroup, Region, no_open_database_country
from janus.resolution.gs1 import Gs1Data


class EuNameAdapter:
    region: Region = "EU"
    country: Country | None = None
    source_id = None

    def accepts_gtin(self, gtin14: str) -> bool:
        return no_open_database_country(gtin14) is not None

    def structural_hint(self, gtin14: str) -> bool:
        return self.accepts_gtin(gtin14)

    def key_groups(self, data: Gs1Data) -> list[KeyGroup]:
        del data
        return []
