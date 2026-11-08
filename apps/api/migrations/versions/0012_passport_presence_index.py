"""Partial index on mapped ingredient keys for the Passport presence query (medication-passport
design §4.1, DP12).

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-08

`POST /passport/presence` looks products up by ingredient key. `res_product_ingredient` had only
its primary key `(dataset_id, source_id, product_id, position)`, so a key lookup was a parallel
sequential scan of about 317,000 rows. Only `mapped` rows can match a key, so the index is partial.
Reference data only; no user data; no column change, so no dataset reload.
"""

from __future__ import annotations

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX res_product_ingredient_key ON res_product_ingredient "
        "(dataset_id, qid, source_id, product_id) WHERE status = 'mapped'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX res_product_ingredient_key")
