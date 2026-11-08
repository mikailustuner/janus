"""Spain adapter: the AEMPS Nomenclátor loaded into PostgreSQL (drug-resolution Req 4.2, DP27).

The lookup order is the order of trust; the service keeps the first step that finds a presentation
and never combines steps, and nothing is guessed:

1. AI (01) in the NTIN list of the Nomenclátor (`ntin`);
2. AI (01), padded to 14 digits, in the GTIN list (`gtin`);
3. AI (712): its first six digits as the national code (`ai_712`; the control digit is not checked,
   no official algorithm was found);
4. AI (01) of the form `0847000` + CN + check digit: the CN is digits 8 to 13 (`ntin_digits`).
"""

from __future__ import annotations

import re

from janus.regions.base import Country, KeyGroup, ProductKey, Region, gs1_prefix_region
from janus.resolution.gs1 import Gs1Data, is_valid_gtin

NTIN_DIGITS = re.compile(r"^0847000([0-9]{6})[0-9]$")


class EsNomenclatorAdapter:
    region: Region = "EU"
    country: Country | None = "ES"
    source_id = "eu_es_cima"

    def accepts_gtin(self, gtin14: str) -> bool:
        # Any valid GTIN may be a company GTIN listed in the Nomenclátor; a miss costs one query.
        return is_valid_gtin(gtin14)

    def structural_hint(self, gtin14: str) -> bool:
        return gs1_prefix_region(gtin14) == "ES"

    def key_groups(self, data: Gs1Data) -> list[KeyGroup]:
        if not is_valid_gtin(data.gtin14):
            return []
        groups = [
            KeyGroup("ntin", (ProductKey("es_ntin", data.gtin14),)),
            KeyGroup("gtin", (ProductKey("es_gtin", data.gtin14),)),
        ]
        if data.national_code is not None and len(data.national_code) >= 6:
            groups.append(KeyGroup("ai_712", (ProductKey("es_cn", data.national_code[:6]),)))
        m = NTIN_DIGITS.match(data.gtin14)
        if m is not None:
            groups.append(KeyGroup("ntin_digits", (ProductKey("es_cn", m.group(1)),)))
        return groups
