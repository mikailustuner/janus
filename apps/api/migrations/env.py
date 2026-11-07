"""Alembic environment: URL from DATABASE_URL or `-x url=...`; logs via the allowlist formatter."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

from janus.observability.logging import configure_logging

configure_logging()


def _url() -> str:
    url = context.get_x_argument(as_dictionary=True).get("url") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL (or -x url=...) is required for migrations")
    # SQLAlchemy needs the psycopg 3 driver named explicitly.
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=None, transaction_per_migration=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
