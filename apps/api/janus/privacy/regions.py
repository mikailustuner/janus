"""Donation storage region (privacy design §5.5, Req 3.4, DP12).

OCI region ids located in EU member states (checked 2026-11-07 against Oracle's "Regions and
Availability Domains" page). Exact match only: `eu-zurich-1` (Switzerland) and
`eu-jovanovac-1` (Serbia) start with `eu-` but are outside the EU.
"""

from __future__ import annotations

from typing import Final

LOCAL: Final = "local"
EU_STORAGE_REGIONS: Final = frozenset(
    {
        "eu-frankfurt-1",
        "eu-paris-1",
        "eu-marseille-1",
        "eu-milan-1",
        "eu-turin-1",
        "eu-amsterdam-1",
        "eu-madrid-1",
        "eu-madrid-3",
        "eu-stockholm-1",
    }
)


def in_eu(region: str | None) -> bool:
    return region in EU_STORAGE_REGIONS


def region_allows_donations(region: str | None) -> bool:
    return region == LOCAL or in_eu(region)
