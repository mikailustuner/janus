"""Reference data for drug resolution (drug-resolution design §3.3, Req 9).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-07

Every table is keyed by the dataset version and written only by the loader
(`python -m janus.resolution.load`); the API reads it in read-only transactions. No user data.
`res_current` points at the dataset the API serves; switching it is one UPDATE.
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = (
    "res_coverage",
    "res_combination_atc",
    "res_name",
    "res_ingredient",
    "res_product_ingredient",
    "res_product_code",
    "res_product",
    "res_source_version",
    "res_current",
    "res_dataset",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE TABLE res_dataset (
          id          text PRIMARY KEY CONSTRAINT res_dataset_id_hex CHECK (id ~ '^[0-9a-f]{64}$'),
          status      text NOT NULL
                      CONSTRAINT res_dataset_status CHECK (status IN ('ready', 'retired')),
          inputs      jsonb NOT NULL,
          created_at  timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE res_current (
          one         boolean PRIMARY KEY DEFAULT true CONSTRAINT res_current_singleton CHECK (one),
          dataset_id  text NOT NULL REFERENCES res_dataset (id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE res_source_version (
          dataset_id      text NOT NULL REFERENCES res_dataset (id) ON DELETE CASCADE,
          source_id       text NOT NULL,
          run_id          text NOT NULL,
          region          text NULL
                          CONSTRAINT res_source_region CHECK (region IN ('TR', 'EU', 'US')),
          snapshot_date   text NOT NULL,
          snapshot_is_retrieval_time boolean NOT NULL,
          content_sha256  text NOT NULL,
          schema_version  text NOT NULL,
          license         text NOT NULL,
          source_url      text NOT NULL,
          PRIMARY KEY (dataset_id, source_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE res_product (
          dataset_id         text NOT NULL,
          source_id          text NOT NULL,
          product_id         integer NOT NULL,
          region             text NOT NULL
                             CONSTRAINT res_product_region CHECK (region IN ('TR', 'EU', 'US')),
          product_name       text NULL,
          brand_name         text NULL,
          generic_name       text NULL,
          ingredient_text    text NULL,
          published_atc      text NULL,
          product_type       text NULL,
          routes             text[] NOT NULL,
          dosage_form        text NULL,
          marketing_end_date text NULL,
          suspension_status  integer NULL,
          name_only          boolean NOT NULL,
          product_rxcuis     text[] NOT NULL,
          PRIMARY KEY (dataset_id, source_id, product_id),
          FOREIGN KEY (dataset_id, source_id)
            REFERENCES res_source_version (dataset_id, source_id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        """
        CREATE TABLE res_product_code (
          dataset_id     text NOT NULL,
          kind           text NOT NULL
                         CONSTRAINT res_product_code_kind
                         CHECK (kind IN ('tr_barcode', 'ndc_product9', 'ndc_package11')),
          code           text NOT NULL CONSTRAINT res_product_code_digits CHECK (code ~ '^[0-9]+$'),
          code_published text NOT NULL,
          source_id      text NOT NULL,
          product_id     integer NOT NULL,
          FOREIGN KEY (dataset_id, source_id, product_id)
            REFERENCES res_product (dataset_id, source_id, product_id) ON DELETE CASCADE
        )
        """
    )
    op.execute("CREATE INDEX res_product_code_lookup ON res_product_code (dataset_id, kind, code)")
    op.execute(
        """
        CREATE TABLE res_product_ingredient (
          dataset_id     text NOT NULL,
          source_id      text NOT NULL,
          product_id     integer NOT NULL,
          position       integer NOT NULL,
          published_name text NOT NULL,
          strength       text NULL,
          status         text NOT NULL
                         CONSTRAINT res_ingredient_status
                         CHECK (status IN ('mapped', 'ambiguous', 'unmapped')),
          reason         text NULL,
          qid            text NULL,
          key_candidates text[] NOT NULL,
          match_step     text NULL,
          atc            jsonb NOT NULL,
          atc_selection  text NULL,
          rxcuis         text[] NOT NULL,
          rxcui_status   text NULL,
          PRIMARY KEY (dataset_id, source_id, product_id, position),
          FOREIGN KEY (dataset_id, source_id, product_id)
            REFERENCES res_product (dataset_id, source_id, product_id) ON DELETE CASCADE,
          CONSTRAINT res_mapped_has_codes CHECK (status <> 'mapped' OR jsonb_array_length(atc) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE res_ingredient (
          dataset_id     text NOT NULL REFERENCES res_dataset (id) ON DELETE CASCADE,
          qid            text NOT NULL CONSTRAINT res_ingredient_qid CHECK (qid ~ '^Q[1-9][0-9]*$'),
          labels         jsonb NOT NULL,
          ingredient_atc jsonb NOT NULL,
          rxcuis         text[] NOT NULL,
          PRIMARY KEY (dataset_id, qid)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE res_name (
          dataset_id  text NOT NULL REFERENCES res_dataset (id) ON DELETE CASCADE,
          name_key    text NOT NULL,
          kind        text NOT NULL
                      CONSTRAINT res_name_kind CHECK (kind IN ('product', 'ingredient')),
          region      text NOT NULL,
          ref         text NOT NULL,
          display     text NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX res_name_key ON res_name (dataset_id, name_key)")
    op.execute("CREATE INDEX res_name_trgm ON res_name USING gin (name_key gin_trgm_ops)")
    op.execute(
        """
        CREATE TABLE res_combination_atc (
          dataset_id  text NOT NULL REFERENCES res_dataset (id) ON DELETE CASCADE,
          code        text NOT NULL,
          reason      text NOT NULL,
          PRIMARY KEY (dataset_id, code)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE res_coverage (
          dataset_id  text PRIMARY KEY REFERENCES res_dataset (id) ON DELETE CASCADE,
          report      jsonb NOT NULL
        )
        """
    )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TABLE {table}")
    # pg_trgm is left installed: other objects may use it, and it holds no data.
