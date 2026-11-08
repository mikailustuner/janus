"""Outcome-store purge (doctor-loop design §7.7).

Usage: `python -m janus.notes.purge` (needs DATABASE_URL). Deletes used-token rows whose token has
expired and outcomes whose report week is on or before the date 24 months before today (UTC).
Safe to run repeatedly; the schedule joins the donation purge in Phase 5. Logs the count only.
"""

from __future__ import annotations

import datetime as dt
import sys

from janus.db.pool import Database
from janus.notes.repository import purge
from janus.observability.logging import LogEvent, configure_logging, log_event
from janus.settings import Settings


def main() -> int:
    configure_logging()
    settings = Settings.from_env()
    if not settings.database_url:
        sys.stderr.write("DATABASE_URL is required\n")
        return 2
    db = Database(settings.database_url, max_size=1)
    db.open()
    try:
        tokens, outcomes = purge(db, dt.datetime.now(dt.UTC).date())
    finally:
        db.close()
    log_event(LogEvent.note_purge, count=tokens + outcomes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
