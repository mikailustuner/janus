"""Outcome store (doctor-loop design §7). Parameterised SQL only.

The second module allowed to use `Database.write_tx()` for user data (after the donation
repository; the `write_tx` allowlist test lists it). It holds only the hashes of used or withdrawn
note ids until the token expires, and the doctor's outcomes.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Sequence
from enum import StrEnum

import psycopg

from janus.contributions.retention import retention_cutoff
from janus.db.pool import Database
from janus.notes.outcomes import OutcomeRow

# Test hook: called with a step name before each write statement (fault injection, P7).
FaultHook = Callable[[str], None]


def _no_fault(_step: str) -> None:
    return None


class SubmitResult(StrEnum):
    stored = "stored"
    used = "used"
    withdrawn = "withdrawn"


_MARK = (
    "INSERT INTO used_note_tokens (note_hash, expires_on, state) VALUES (%s, %s, 'used') "
    "ON CONFLICT (note_hash) DO NOTHING RETURNING 1"
)
_STATE = "SELECT state FROM used_note_tokens WHERE note_hash = %s"
_INSERT = """
INSERT INTO outcomes
  (report_week, region, rule_id, index_key, marker_key, ingredients, event, direction, assessment,
   action, action_on, form_confirmed, consent_version, deletion_hash)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
_DELETE = "DELETE FROM outcomes WHERE deletion_hash = ANY(%s)"
_WITHDRAW = (
    "INSERT INTO used_note_tokens (note_hash, expires_on, state) VALUES (%s, %s, 'withdrawn') "
    "ON CONFLICT (note_hash) DO UPDATE SET state = 'withdrawn'"
)
_PURGE_TOKENS = "DELETE FROM used_note_tokens WHERE expires_on <= %s"
_PURGE_OUTCOMES = "DELETE FROM outcomes WHERE report_week <= %s"


def token_state(conn: psycopg.Connection, note_hash: bytes) -> str | None:
    """`used`, `withdrawn` or None; inside the caller's (read-only) transaction."""
    row = conn.execute(_STATE, (note_hash,)).fetchone()
    return None if row is None else str(row[0])


def submit(
    db: Database,
    note_hash: bytes,
    expires_on: dt.date,
    rows: Sequence[OutcomeRow],
    hook: FaultHook = _no_fault,
) -> SubmitResult:
    """Mark the token used and store the outcomes in one transaction (design §7.4)."""
    with db.write_tx() as conn:
        hook("mark")
        if conn.execute(_MARK, (note_hash, expires_on)).fetchone() is None:
            state = token_state(conn, note_hash)
            return SubmitResult.withdrawn if state == "withdrawn" else SubmitResult.used
        for r in rows:
            hook("insert")
            conn.execute(
                _INSERT,
                (
                    r.report_week,
                    r.region,
                    r.rule_id,
                    r.index_key,
                    r.marker_key,
                    list(r.ingredients),
                    r.event,
                    r.direction,
                    r.assessment,
                    r.action,
                    r.action_on,
                    r.form_confirmed,
                    r.consent_version,
                    r.deletion_hash,
                ),
            )
        hook("commit")
    return SubmitResult.stored


def withdraw(
    db: Database,
    note_hash: bytes,
    expires_on: dt.date | None,
    deletion_hashes: Sequence[bytes],
    hook: FaultHook = _no_fault,
) -> None:
    """Delete the note's outcomes; block an unexpired token (`expires_on` None when expired)."""
    with db.write_tx() as conn:
        hook("delete")
        conn.execute(_DELETE, (list(deletion_hashes),))
        if expires_on is not None:
            hook("block")
            conn.execute(_WITHDRAW, (note_hash, expires_on))
        hook("commit")


def purge(db: Database, today: dt.date) -> tuple[int, int]:
    """Delete expired used-token rows and outcomes older than 24 months (design §7.7)."""
    with db.write_tx() as conn:
        tokens = conn.execute(_PURGE_TOKENS, (today,)).rowcount
        outcomes = conn.execute(_PURGE_OUTCOMES, (retention_cutoff(today),)).rowcount
    return tokens, outcomes
