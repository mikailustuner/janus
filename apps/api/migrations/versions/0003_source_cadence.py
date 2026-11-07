"""Source cadence stored with the resolution dataset (evidence-integrity DP17).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-07

The staleness notice of drug resolution uses the shared freshness rule (twice the cadence in
`pipelines/sources.toml`). The loader stores the cadence with each source version so a request
stays inside one dataset. NULL (datasets loaded before this revision) means "cannot be judged".
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE res_source_version
          ADD COLUMN cadence_days integer NULL
          CONSTRAINT res_source_cadence_range CHECK (cadence_days BETWEEN 1 AND 3660)
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE res_source_version DROP COLUMN cadence_days")
