"""Index for the foreign key from `res_product_code` to `res_product` (drug-resolution task 23).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-08

Deleting a product row (when the loader retires an old dataset) makes PostgreSQL look up its
`res_product_code` rows by `(dataset_id, source_id, product_id)`. Only the lookup index
`(dataset_id, kind, code)` existed, so every deleted product scanned the whole table: retiring one
dataset of about 160,000 products took more than 50 minutes. With this index it is a plain delete.
Reference data only; no user data.
"""

from __future__ import annotations

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX res_product_code_product ON res_product_code "
        "(dataset_id, source_id, product_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX res_product_code_product")
