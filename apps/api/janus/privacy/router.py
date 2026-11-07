"""GET /privacy/storage (privacy design §5.1, §5.5; Req 3.4, 5.2). Facts only, no claims."""

from __future__ import annotations

from fastapi import Request
from pydantic import BaseModel

from janus.contributions.service import donations_enabled
from janus.http_policy.routes import operational_router
from janus.privacy.regions import in_eu
from janus.settings import Settings

router = operational_router()


class StorageInfo(BaseModel):
    donation_storage_region: str | None
    in_eu: bool
    donations_enabled: bool


@router.get("/privacy/storage")
def storage(request: Request) -> StorageInfo:
    settings: Settings = request.app.state.settings
    return StorageInfo(
        donation_storage_region=settings.donation_region,
        in_eu=in_eu(settings.donation_region),
        donations_enabled=donations_enabled(request.app),
    )
