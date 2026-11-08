"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

from janus.contributions.vocabulary import load_vocabulary
from janus.db.pool import Database
from janus.http_policy.body_limits import BodyPolicyMiddleware
from janus.http_policy.routes import classify, operational_router
from janus.light.store import LightHolder
from janus.memory.reader import CountsHolder
from janus.memory.shared import ContributionsSource
from janus.memory.vocabulary import load_events
from janus.notes.glossary import load as load_glossary
from janus.notes.glossary import vocabulary_digest
from janus.notes.source import OutcomesSource
from janus.notes.token import Keyring
from janus.observability.logging import (
    LogEvent,
    configure_logging,
    log_event,
    register_route_templates,
)
from janus.observability.middleware import AccessLogMiddleware
from janus.passport.forms import load as load_dose_forms
from janus.settings import EVENT_VOCABULARY, Settings


class Health(BaseModel):
    status: Literal["ok"]


health_router = operational_router()


@health_router.get("/health")
def health() -> Health:
    return Health(status="ok")


def create_app(
    settings: Settings | None = None,
    *,
    database: Database | None = None,
    extra_routers: Iterable[APIRouter] = (),
    configure_logs: bool = True,
) -> FastAPI:
    """Build the API. A `database` passed in is opened and closed by the caller (tests);
    one built from `DATABASE_URL` is owned by the app's lifespan."""
    if configure_logs:
        configure_logging()
    settings = settings or Settings.from_env()
    owns_database = database is None and settings.database_url is not None
    if database is None and settings.database_url:
        database = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        if owns_database and database is not None:
            database.open()
        log_event(LogEvent.startup)
        try:
            yield
        finally:
            if owns_database and database is not None:
                database.close()
            log_event(LogEvent.shutdown)

    app = FastAPI(title="Janus API", version="0.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.database = database
    app.state.events = load_vocabulary(settings.event_vocabulary_path)
    path = settings.event_vocabulary_path
    app.state.event_vocabulary = load_events(path if path.suffix == ".csv" else EVENT_VOCABULARY)
    app.state.counts = CountsHolder(settings.data_dir)
    app.state.light = LightHolder(settings.data_dir)
    vocab = app.state.event_vocabulary
    app.state.glossary = load_glossary(
        extra=vocabulary_digest(
            {k.key: dict(k.labels) for k in vocab.keys},
            {k.key: k.safety_line for k in vocab.keys if k.safety_line},
        )
    )
    app.state.user_layer_sources = {
        "contributions": ContributionsSource(),
        "outcomes": OutcomesSource(),
    }
    # Dose-form table (medication-passport §5.2): a defect stops startup; a missing file makes
    # `/passport/presence` answer 503 and leaves the resolution fields null (Req 5.3, 6.6).
    try:
        app.state.dose_forms = load_dose_forms()
    except FileNotFoundError:
        app.state.dose_forms = None
    app.state.note_keyring = (
        Keyring(settings.note_keys, settings.note_signing_key_id)
        if settings.note_keys and settings.note_signing_key_id
        else None
    )
    # Imported here to avoid an import cycle (the routers read settings from app.state).
    from janus.cascades.router import router as cascades_router
    from janus.contributions.router import router as contributions_router
    from janus.integrity.router import router as integrity_router
    from janus.light.router import router as light_router
    from janus.memory.router import router as memory_router
    from janus.memory.router import snapshot_router as memory_snapshot_router
    from janus.notes.router import donation as notes_donation_router
    from janus.notes.router import router as notes_router
    from janus.passport.router import router as passport_router
    from janus.privacy.router import router as privacy_router
    from janus.resolution.router import router as resolution_router

    routers = [
        health_router,
        privacy_router,
        contributions_router,
        resolution_router,
        integrity_router,
        cascades_router,
        memory_router,
        memory_snapshot_router,
        notes_router,
        notes_donation_router,
        passport_router,
        light_router,
        *extra_routers,
    ]
    for router in routers:
        app.include_router(router)
    kinds = classify(app, routers)  # fails on an unclassified route (DP2)
    register_route_templates(kinds)
    # Added last = outermost: the access log also sees body-policy rejections.
    app.add_middleware(BodyPolicyMiddleware)
    app.add_middleware(AccessLogMiddleware)
    return app


app = create_app()
