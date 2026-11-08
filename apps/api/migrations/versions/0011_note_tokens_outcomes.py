"""Used note tokens and doctor-reported outcomes (doctor-loop design §7.1).

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-08

Owner decision 2026-11-08: the token carries the note's finding codes, so the server keeps no
record of a note. It stores only the SHA-256 of each used or withdrawn note id until the token
expires (single use) and the outcomes. No timestamp column, no clock default; the only dates are
Mondays (expiry, report week). CHECK constraints repeat the API's validation.
"""

from __future__ import annotations

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

KEY = r"^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE used_note_tokens (
          note_hash  bytea PRIMARY KEY
                     CONSTRAINT used_note_tokens_hash_len CHECK (octet_length(note_hash) = 32),
          expires_on date NOT NULL
                     CONSTRAINT used_note_tokens_expires_monday
                     CHECK (extract(isodow FROM expires_on) = 1),
          state      text NOT NULL
                     CONSTRAINT used_note_tokens_state CHECK (state IN ('used', 'withdrawn'))
        )
        """
    )
    op.execute("CREATE INDEX used_note_tokens_expires_on_idx ON used_note_tokens (expires_on)")
    op.execute(
        f"""
        CREATE TABLE outcomes (
          id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          report_week     date NOT NULL
                          CONSTRAINT outcomes_report_week_monday
                          CHECK (extract(isodow FROM report_week) = 1),
          region          text NOT NULL
                          CONSTRAINT outcomes_region CHECK (region IN ('TR', 'EU', 'US')),
          rule_id         text NOT NULL
                          CONSTRAINT outcomes_rule_id
                          CHECK (rule_id ~ '^pipc:([1-9]|[1-5][0-9]|6[0-5])$'),
          index_key       text NOT NULL CONSTRAINT outcomes_index_key CHECK (index_key ~ '{KEY}'),
          marker_key      text NOT NULL CONSTRAINT outcomes_marker_key CHECK (marker_key ~ '{KEY}'),
          ingredients     text[] NOT NULL
                          CONSTRAINT outcomes_ingredients_pair
                          CHECK (
                            cardinality(ingredients) = 2
                            AND ingredients[1] < ingredients[2]
                            AND index_key <> marker_key
                            AND ingredients @> ARRAY[index_key, marker_key]
                          ),
          event           text NOT NULL
                          CONSTRAINT outcomes_event CHECK (event ~ '^[a-z0-9][a-z0-9_.-]{{0,39}}$'),
          direction       text NOT NULL
                          CONSTRAINT outcomes_direction CHECK (direction IN ('adverse', 'benefit')),
          assessment      text NOT NULL
                          CONSTRAINT outcomes_assessment
                          CHECK (assessment IN ('confirmed', 'not_a_cascade')),
          action          text NULL
                          CONSTRAINT outcomes_action
                          CHECK (
                            action IN ('dose_changed', 'medicine_changed', 'stopped', 'no_change')
                          ),
          action_on       text NULL
                          CONSTRAINT outcomes_action_on CHECK (action_on IN ('index', 'marker')),
          form_confirmed  boolean NOT NULL,
          consent_version text NOT NULL
                          CONSTRAINT outcomes_consent_version
                          CHECK (consent_version ~ '^[a-z0-9][a-z0-9.-]{{0,31}}$'),
          deletion_hash   bytea NOT NULL
                          CONSTRAINT outcomes_deletion_hash_key UNIQUE
                          CONSTRAINT outcomes_deletion_hash_len
                          CHECK (octet_length(deletion_hash) = 32),
          CONSTRAINT outcomes_action_medicine
          CHECK (
            coalesce(action IN ('dose_changed', 'medicine_changed', 'stopped'), false)
            = (action_on IS NOT NULL)
          )
        )
        """
    )
    op.execute("CREATE INDEX outcomes_report_week_idx ON outcomes (report_week)")


def downgrade() -> None:
    op.execute("DROP TABLE outcomes")
    op.execute("DROP TABLE used_note_tokens")
