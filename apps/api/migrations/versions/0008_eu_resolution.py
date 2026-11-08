"""EU products in the resolution tables (drug-resolution Phase 2, design §14.5).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-08

`res_product_code.kind` accepts the French CIP13 (`fr_cip13`) and the Spanish national code,
NTIN and GTIN (`es_cn`, `es_ntin`, `es_gtin`); `res_product.status_published` holds the EU
authorisation and marketing status as published (display only). The region check of
`res_product` and `res_source_version` already allows `EU`. Reference data only; no user data.
"""

from __future__ import annotations

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

OLD_KINDS = "'tr_barcode', 'ndc_product9', 'ndc_package11'"
NEW_KINDS = f"{OLD_KINDS}, 'fr_cip13', 'es_cn', 'es_ntin', 'es_gtin'"


def upgrade() -> None:
    op.execute("ALTER TABLE res_product_code DROP CONSTRAINT res_product_code_kind")
    op.execute(
        "ALTER TABLE res_product_code ADD CONSTRAINT res_product_code_kind "
        f"CHECK (kind IN ({NEW_KINDS}))"  # noqa: S608 (constants above)
    )
    op.execute("ALTER TABLE res_product ADD COLUMN status_published text[] NOT NULL DEFAULT '{}'")


def downgrade() -> None:
    # Datasets that hold EU products or EU code kinds cannot satisfy the old check; they are
    # removed (reference data, reloadable with python -m janus.resolution.load).
    held = (
        "SELECT dataset_id FROM res_product WHERE region = 'EU' "
        "UNION SELECT dataset_id FROM res_product_code "
        "WHERE kind IN ('fr_cip13', 'es_cn', 'es_ntin', 'es_gtin')"
    )
    op.execute(f"DELETE FROM res_current WHERE dataset_id IN ({held})")  # noqa: S608
    op.execute(f"DELETE FROM res_dataset WHERE id IN ({held})")  # noqa: S608
    op.execute("ALTER TABLE res_product DROP COLUMN status_published")
    op.execute("ALTER TABLE res_product_code DROP CONSTRAINT res_product_code_kind")
    op.execute(
        "ALTER TABLE res_product_code ADD CONSTRAINT res_product_code_kind "
        f"CHECK (kind IN ({OLD_KINDS}))"  # noqa: S608 (constants above)
    )
