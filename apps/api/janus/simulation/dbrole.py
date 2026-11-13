"""Give the worker's database role its password and login (simulation-service design §8; safety
review F1). Run by `deploy.sh` in the one-off `migrate` container after the migrations:

    python -m janus.simulation.dbrole

Reads `DATABASE_URL` (the owner role) and `SIMULATOR_DB_PASSWORD` (at least 24 characters) from
the environment or, as `DATABASE_URL_FILE` and `SIMULATOR_DB_PASSWORD_FILE`, from mounted secret
files; the password never appears on a command line or in a log. Idempotent.
"""

from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql

from janus.settings import SettingsError, secret_value

ROLE = "janus_simulator"
MIN_LENGTH = 24


def set_password(conn: psycopg.Connection, password: str) -> None:
    if len(password) < MIN_LENGTH:
        raise ValueError(f"SIMULATOR_DB_PASSWORD must have at least {MIN_LENGTH} characters")
    conn.execute(
        sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
            sql.Identifier(ROLE), sql.Literal(password)
        )
    )


def main() -> int:
    try:
        url = secret_value(os.environ, "DATABASE_URL").strip()
        password = secret_value(os.environ, "SIMULATOR_DB_PASSWORD")
    except SettingsError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not url or not password:
        print("DATABASE_URL and SIMULATOR_DB_PASSWORD are required", file=sys.stderr)
        return 2
    try:
        with psycopg.connect(url, autocommit=True, connect_timeout=10) as conn:
            set_password(conn, password)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"{ROLE}: login set")
    return 0


if __name__ == "__main__":
    sys.exit(main())
