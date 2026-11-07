"""Janus ingredient keys next to Wikidata QIDs in `res_ingredient`.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-07

Owner decision of 2026-11-07 (cascade-engine review of the synonym proposals): substances that no
Wikidata item in the extract covers with an ATC code get a curated Janus key `J<n>` from
`data/janus_ingredients.csv` (first: dimenhydrinate, R06AA11). The key check accepts both forms.
No user data.
"""

from __future__ import annotations

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE res_ingredient DROP CONSTRAINT res_ingredient_qid")
    op.execute(
        "ALTER TABLE res_ingredient ADD CONSTRAINT res_ingredient_qid "
        "CHECK (qid ~ '^(Q[1-9][0-9]*|J[1-9][0-9]{0,5})$')"
    )


def downgrade() -> None:
    # Datasets that hold Janus keys cannot satisfy the old check; they are removed (reference
    # data only, reloadable with python -m janus.resolution.load).
    held = "SELECT dataset_id FROM res_ingredient WHERE qid LIKE 'J%'"
    op.execute(f"DELETE FROM res_current WHERE dataset_id IN ({held})")  # noqa: S608
    op.execute(f"DELETE FROM res_dataset WHERE id IN ({held})")  # noqa: S608
    op.execute("ALTER TABLE res_ingredient DROP CONSTRAINT res_ingredient_qid")
    op.execute(
        "ALTER TABLE res_ingredient ADD CONSTRAINT res_ingredient_qid "
        "CHECK (qid ~ '^Q[1-9][0-9]*$')"
    )
