"""Evidence records, integrity status, notices and the status-change log.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-07

Evidence-integrity design §3.2. Public data only: no user data in any table. Foreign keys have no
ON DELETE CASCADE because the loader never deletes evidence; a delete that would orphan a row
fails loudly. CHECK constraints repeat the loader's validation.
"""

# ruff: noqa: E501
from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

TABLES = (
    "evidence_status_change",
    "evidence_notice",
    "evidence_integrity",
    "evidence_basis",
    "evidence",
    "evidence_source",
)

STATUSES = "('ok','corrected','expression_of_concern','retracted','unknown')"
DOI_PATTERN = r"^10\.[0-9]{4,9}/[^[:space:]]+$"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE evidence_source (
          source_id    text PRIMARY KEY
                       CONSTRAINT evidence_source_id_format CHECK (source_id ~ '^[a-z0-9_]{1,40}$'),
          name         text NOT NULL,
          storage      text NOT NULL
                       CONSTRAINT evidence_source_storage CHECK (storage IN
                         ('runtime_only','cache','commit','separate_package','cited_only')),
          cadence_days integer NULL
                       CONSTRAINT evidence_source_cadence CHECK (cadence_days BETWEEN 1 AND 3660)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE evidence (
          id            text PRIMARY KEY
                        CONSTRAINT evidence_id_format CHECK (
                          id ~ '^[a-z_]+:[a-z0-9_]+(:[A-Za-z0-9_.-]{{1,64}})?$'
                          AND length(id) <= 100),
          kind          text NOT NULL
                        CONSTRAINT evidence_kind CHECK (kind IN
                          ('dataset','rule','faers_stat','paper','label','ancient','chembl','outcome')),
          source_id     text NOT NULL REFERENCES evidence_source (source_id),
          source_url    text NOT NULL
                        CONSTRAINT evidence_source_url CHECK (source_url ~ '^https?://[^[:space:]]+$'),
          license       text NOT NULL
                        CONSTRAINT evidence_license CHECK (length(btrim(license)) > 0),
          region        text NULL
                        CONSTRAINT evidence_region CHECK (region IN ('TR','EU','US')),
          snapshot_date date NOT NULL,
          snapshot_is_retrieval_time boolean NOT NULL,
          doi           text NULL
                        CONSTRAINT evidence_doi CHECK (doi ~ '{DOI_PATTERN}' AND doi = lower(doi)),
          locator       text NULL CONSTRAINT evidence_locator CHECK (length(locator) <= 200),
          title         text NULL CONSTRAINT evidence_title CHECK (length(title) <= 300)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE evidence_basis (
          evidence_id text NOT NULL REFERENCES evidence (id),
          basis_id    text NOT NULL REFERENCES evidence (id),
          PRIMARY KEY (evidence_id, basis_id),
          CONSTRAINT evidence_basis_not_self CHECK (evidence_id <> basis_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE evidence_integrity (
          evidence_id  text PRIMARY KEY REFERENCES evidence (id),
          status       text NOT NULL CONSTRAINT evidence_integrity_status CHECK (status IN {STATUSES}),
          check_status text NOT NULL
                       CONSTRAINT evidence_integrity_check_status CHECK (check_status IN {STATUSES}),
          reason       text NULL
                       CONSTRAINT evidence_integrity_reason CHECK (
                         reason ~ '^(check_failed|not_found|unreadable_response|not_yet_checked|http_[0-9]{{3}})$'),
          checked_at   date NULL,
          check_run_id text NULL CONSTRAINT evidence_integrity_run CHECK (length(check_run_id) <= 80)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE evidence_notice (
          evidence_id text NOT NULL REFERENCES evidence (id),
          position    smallint NOT NULL,
          type        text NOT NULL CONSTRAINT evidence_notice_type CHECK (type ~ '^[a-z_]{{1,40}}$'),
          source      text NULL CONSTRAINT evidence_notice_source CHECK (length(source) <= 40),
          notice_doi  text NULL CONSTRAINT evidence_notice_doi CHECK (notice_doi ~ '{DOI_PATTERN}'),
          notice_date date NULL,
          PRIMARY KEY (evidence_id, position)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE evidence_status_change (
          id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          evidence_id text NOT NULL REFERENCES evidence (id),
          from_status text NULL CONSTRAINT evidence_change_from CHECK (from_status IN {STATUSES}),
          to_status   text NOT NULL CONSTRAINT evidence_change_to CHECK (to_status IN {STATUSES}),
          observed_on date NOT NULL,
          run_id      text NULL CONSTRAINT evidence_change_run CHECK (length(run_id) <= 80)
        )
        """
    )
    op.execute(
        "CREATE INDEX evidence_status_change_observed "
        "ON evidence_status_change (observed_on DESC, evidence_id)"
    )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TABLE {table}")
