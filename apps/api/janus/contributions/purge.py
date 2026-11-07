"""Retention purge command (privacy design §5.7, Req 3.6).

Usage: `python -m janus.contributions.purge` (needs DATABASE_URL). Deletes every donation whose
report week is on or before the date 24 months before today (UTC). Safe to run repeatedly; the
daily schedule is added in Phase 5. Logs only the number of deleted rows.
"""

from __future__ import annotations

import datetime as dt
import sys

from janus.contributions.repository import purge_expired
from janus.db.pool import Database
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
        deleted = purge_expired(db, dt.datetime.now(dt.UTC).date())
    finally:
        db.close()
    log_event(LogEvent.purge, count=deleted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
