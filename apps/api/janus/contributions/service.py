"""Whether donations are enabled (privacy design §3, §5.5; Req 3.4).

Donations need all of: an allowed storage region (`local` or an EU region), at least one
consent version, a database and an event vocabulary. Otherwise the donation routes return 503.
"""

from __future__ import annotations

from fastapi import FastAPI

from janus.db.pool import Database
from janus.privacy.regions import region_allows_donations
from janus.settings import Settings


def donations_enabled(app: FastAPI) -> bool:
    settings: Settings = app.state.settings
    events: frozenset[str] = getattr(app.state, "events", frozenset())
    return (
        region_allows_donations(settings.donation_region)
        and bool(settings.consent_versions)
        and isinstance(getattr(app.state, "database", None), Database)
        and bool(events)
    )
