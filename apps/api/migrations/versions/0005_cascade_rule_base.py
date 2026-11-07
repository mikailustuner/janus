"""Cascade rule base: one validated document per version and a current pointer.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-07

Cascade-engine design §3.7 (DP15). No user data: the rule base is built from the curated public
files under `data/`. Versions are never deleted, so a note made with an older version can still
name it. Written only by `janus/cascades/load.py`.
"""

from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE cascade_rule_base (
          version    text PRIMARY KEY CHECK (version ~ '^[0-9a-f]{64}$'),
          content    jsonb NOT NULL,
          inputs     jsonb NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE cascade_rule_base_current (
          one     boolean PRIMARY KEY CHECK (one),
          version text NOT NULL REFERENCES cascade_rule_base
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE cascade_rule_base_current")
    op.execute("DROP TABLE cascade_rule_base")
