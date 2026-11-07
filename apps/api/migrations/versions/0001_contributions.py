"""Donations table with allowed fields only (privacy spec Req 3.2, 3.5; design §5.2).

Revision ID: 0001
Revises:
Create Date: 2026-11-07

No timestamps, no clock defaults, no sequence: ids are random UUIDs and the only date is the
report week (a Monday). CHECK constraints repeat the API's validation.
"""

from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE contributions (
          id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          report_week         date NOT NULL
                              CONSTRAINT contributions_report_week_monday
                              CHECK (extract(isodow FROM report_week) = 1),
          age_band            smallint NOT NULL
                              CONSTRAINT contributions_age_band_adult_5y
                              CHECK (age_band BETWEEN 20 AND 90 AND age_band % 5 = 0),
          sex                 text NULL
                              CONSTRAINT contributions_sex_values
                              CHECK (sex IN ('female', 'male')),
          region              text NOT NULL
                              CONSTRAINT contributions_region_values
                              CHECK (region IN ('TR', 'EU', 'US')),
          ingredients         text[] NOT NULL
                              CONSTRAINT contributions_ingredients_qids
                              CHECK (
                                cardinality(ingredients) BETWEEN 1 AND 20
                                AND array_position(ingredients, NULL) IS NULL
                                AND array_to_string(ingredients, ',')
                                    ~ '^Q[1-9][0-9]{0,9}(,Q[1-9][0-9]{0,9})*$'
                              ),
          event               text NOT NULL
                              CONSTRAINT contributions_event_key
                              CHECK (event ~ '^[a-z0-9][a-z0-9_.-]{0,63}$'),
          direction           text NOT NULL
                              CONSTRAINT contributions_direction_values
                              CHECK (direction IN ('adverse', 'benefit')),
          consent_version     text NOT NULL
                              CONSTRAINT contributions_consent_version_id
                              CHECK (consent_version ~ '^[a-z0-9][a-z0-9.-]{0,31}$'),
          deletion_token_hash bytea NOT NULL
                              CONSTRAINT contributions_deletion_token_hash_key UNIQUE
                              CONSTRAINT contributions_deletion_token_hash_len
                              CHECK (octet_length(deletion_token_hash) = 32)
        )
        """
    )
    op.execute("CREATE INDEX contributions_report_week_idx ON contributions (report_week)")


def downgrade() -> None:
    op.execute("DROP TABLE contributions")
