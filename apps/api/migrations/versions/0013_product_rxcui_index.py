"""GIN index on product RxCUIs for the CDS Hooks service (cds-hooks design §5).

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-09

`POST /cds-services/janus-cascade` looks US products up by an RxNorm code from an EHR order.
`res_product.product_rxcuis` had no index, so a lookup was a sequential scan of every product of
the dataset (about 14 s on the full dataset). Reference data only; no user data; no column change,
so no dataset reload.
"""

from __future__ import annotations

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX res_product_rxcuis ON res_product USING gin (product_rxcuis)")


def downgrade() -> None:
    op.execute("DROP INDEX res_product_rxcuis")
