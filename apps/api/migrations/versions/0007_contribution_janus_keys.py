"""Donations accept Janus ingredient keys `J<n>` next to Wikidata items.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-08

Owner decision 2026-11-08 (collective-memory DP17): the resolver already knows curated Janus keys
(`data/janus_ingredients.csv`, migration 0006), so a donor must be able to report them. The check on
`contributions.ingredients` accepts both key forms; nothing else changes. No user data.

Forward-only in practice: an applied revision is never edited. The downgrade restores the old check;
donations that name a Janus key cannot satisfy it and are deleted (anonymous rows, so nothing
is lost that identifies anyone).
"""

from __future__ import annotations

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

NEW = (
    "cardinality(ingredients) BETWEEN 1 AND 20 "
    "AND array_position(ingredients, NULL) IS NULL "
    "AND array_to_string(ingredients, ',') "
    "~ '^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})(,(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5}))*$'"
)
OLD = (
    "cardinality(ingredients) BETWEEN 1 AND 20 "
    "AND array_position(ingredients, NULL) IS NULL "
    "AND array_to_string(ingredients, ',') ~ '^Q[1-9][0-9]{0,9}(,Q[1-9][0-9]{0,9})*$'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE contributions DROP CONSTRAINT contributions_ingredients_qids")
    op.execute(
        f"ALTER TABLE contributions ADD CONSTRAINT contributions_ingredients_qids CHECK ({NEW})"
    )


def downgrade() -> None:
    op.execute("DELETE FROM contributions WHERE array_to_string(ingredients, ',') ~ 'J'")
    op.execute("ALTER TABLE contributions DROP CONSTRAINT contributions_ingredients_qids")
    op.execute(
        f"ALTER TABLE contributions ADD CONSTRAINT contributions_ingredients_qids CHECK ({OLD})"
    )
