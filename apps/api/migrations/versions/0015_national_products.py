"""Canadian and Italian products in the resolution tables (national-products design 5, Req 4.4).

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-10

`res_product_code.kind` accepts the Canadian Drug Identification Number (`ca_din`) and the Italian
AIC pack code (`it_aic`); `res_product.region` accepts `CA` (Health Canada DPD products; Italian
products are region `EU`). `res_source_version.region` is unchanged: the DPD source has no
statistics region. Reference data only; no user data.
"""

from __future__ import annotations

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

OLD_KINDS = (
    "'tr_barcode', 'ndc_product9', 'ndc_package11', 'fr_cip13', 'es_cn', 'es_ntin', 'es_gtin'"
)
NEW_KINDS = f"{OLD_KINDS}, 'ca_din', 'it_aic'"
OLD_REGIONS = "'TR', 'EU', 'US'"
NEW_REGIONS = f"{OLD_REGIONS}, 'CA'"


def _checks(kinds: str, regions: str) -> None:
    op.execute("ALTER TABLE res_product_code DROP CONSTRAINT res_product_code_kind")
    op.execute(
        "ALTER TABLE res_product_code ADD CONSTRAINT res_product_code_kind "
        f"CHECK (kind IN ({kinds}))"
    )
    op.execute("ALTER TABLE res_product DROP CONSTRAINT res_product_region")
    op.execute(
        f"ALTER TABLE res_product ADD CONSTRAINT res_product_region CHECK (region IN ({regions}))"
    )


def upgrade() -> None:
    _checks(NEW_KINDS, NEW_REGIONS)


def downgrade() -> None:
    # Datasets that hold Canadian products or the new code kinds cannot satisfy the old checks;
    # they are removed (reference data, reloadable with python -m janus.resolution.load).
    held = (
        "SELECT dataset_id FROM res_product WHERE region = 'CA' "
        "UNION SELECT dataset_id FROM res_product_code WHERE kind IN ('ca_din', 'it_aic')"
    )
    op.execute(f"DELETE FROM res_current WHERE dataset_id IN ({held})")  # noqa: S608
    op.execute(f"DELETE FROM res_dataset WHERE id IN ({held})")  # noqa: S608
    _checks(OLD_KINDS, OLD_REGIONS)
