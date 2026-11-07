"""Donation storage (privacy design §5, Req 3.2, 3.3, 3.6). Parameterised SQL only.

This is the only module allowed to use `Database.write_tx()` (enforced by a test).
"""

from __future__ import annotations

import datetime as dt

from janus.contributions.models import ContributionStored
from janus.contributions.retention import retention_cutoff
from janus.db.pool import Database

_INSERT = """
INSERT INTO contributions
  (report_week, age_band, sex, region, ingredients, event, direction, consent_version,
   deletion_token_hash)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
_DELETE_BY_TOKEN = "DELETE FROM contributions WHERE deletion_token_hash = %s RETURNING 1"  # noqa: S105
_PURGE = "DELETE FROM contributions WHERE report_week <= %s"


def insert(db: Database, stored: ContributionStored, deletion_token_hash: bytes) -> None:
    with db.write_tx() as conn:
        conn.execute(
            _INSERT,
            (
                stored.report_week,
                stored.age_band,
                stored.sex,
                stored.region,
                list(stored.ingredients),
                stored.event,
                stored.direction,
                stored.consent_version,
                deletion_token_hash,
            ),
        )


def delete_by_token_hash(db: Database, deletion_token_hash: bytes) -> bool:
    with db.write_tx() as conn:
        rows = conn.execute(_DELETE_BY_TOKEN, (deletion_token_hash,)).fetchall()
    return len(rows) > 0


def purge_expired(db: Database, today: dt.date) -> int:
    """Delete every donation whose report week is on or before the 24-month cutoff."""
    with db.write_tx() as conn:
        cur = conn.execute(_PURGE, (retention_cutoff(today),))
        return cur.rowcount
