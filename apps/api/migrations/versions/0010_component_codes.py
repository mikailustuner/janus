"""Reviewed (key, combination code) pairs in the resolution dataset (drug-resolution Req 14).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-08

`res_component_code` holds the rows of `data/component_codes.csv` of a dataset: one curated Janus
key and the one combination code that may reach `rule_input` for that key only (owner decision
2026-11-08, option b: imipenem and `J01DH51`). Reference data only; no user data.
"""

from __future__ import annotations

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE res_component_code (
            dataset_id text NOT NULL REFERENCES res_dataset(id) ON DELETE CASCADE,
            key        text NOT NULL,
            code       text NOT NULL,
            evidence   text NOT NULL,
            whocc_url  text NOT NULL,
            whocc_date text NOT NULL,
            note       text NOT NULL,
            PRIMARY KEY (dataset_id, key, code),
            CONSTRAINT res_component_code_key CHECK (key ~ '^J[1-9][0-9]{0,5}$'),
            CONSTRAINT res_component_code_code CHECK (code ~ '^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$')
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE res_component_code")
