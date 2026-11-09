"""Queue of the simulation service (simulation-service design §6).

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-09

One row per model run: the validated, canonical input (allow-listed ids and bounded numbers
only, at most 1 KiB), its hash for the cache, the state, the result and its expiry. No address,
no request metadata, no personal data: nothing identifies who asked.

The worker gets its own role, `janus_simulator`, created without login: it may read, update and
delete queue rows and nothing else (safety review F1). The deploy gives it a password and login
with `python -m janus.simulation.dbrole` (deploy/README.md).
"""

from __future__ import annotations

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE simulation_jobs (
            id uuid PRIMARY KEY,
            input_hash char(64) NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
            kind text NOT NULL CHECK (kind IN ('compartmental', 'httk_population')),
            input jsonb NOT NULL CHECK (octet_length(input::text) <= 1024),
            state text NOT NULL CHECK (state IN ('queued', 'running', 'done', 'failed')),
            created_at timestamptz NOT NULL DEFAULT now(),
            started_at timestamptz,
            finished_at timestamptz,
            expires_at timestamptz NOT NULL,
            attempts smallint NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
            result jsonb CHECK (result IS NULL OR octet_length(result::text) <= 262144),
            error text CHECK (error IS NULL OR error IN
                ('timeout', 'model_failed', 'expired', 'worker_lost')),
            CHECK ((state = 'done') = (result IS NOT NULL)),
            CHECK ((state = 'failed') = (error IS NOT NULL))
        )
        """
    )
    op.execute("CREATE INDEX simulation_jobs_state ON simulation_jobs (state, created_at)")
    op.execute("CREATE INDEX simulation_jobs_hash ON simulation_jobs (input_hash)")
    op.execute("CREATE INDEX simulation_jobs_expiry ON simulation_jobs (expires_at)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'janus_simulator') THEN
                CREATE ROLE janus_simulator NOLOGIN;
            END IF;
        END
        $$
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO janus_simulator")
    op.execute("GRANT SELECT, UPDATE, DELETE ON simulation_jobs TO janus_simulator")


def downgrade() -> None:
    op.execute("DROP TABLE simulation_jobs")
    op.execute("REVOKE USAGE ON SCHEMA public FROM janus_simulator")
    op.execute("DROP ROLE IF EXISTS janus_simulator")
