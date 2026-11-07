"""Shared test setup: Hypothesis profiles and PostgreSQL fixtures (privacy design §7)."""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from hypothesis import HealthCheck, settings

settings.register_profile(
    "dev",
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
settings.register_profile(
    "ci",
    max_examples=300,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))

# Database-backed properties run fewer examples (design §7).
DB_EXAMPLES = 100 if os.environ.get("HYPOTHESIS_PROFILE") == "ci" else 50

TEST_DB_ENV = "JANUS_TEST_DATABASE_URL"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "db: needs PostgreSQL 16 at JANUS_TEST_DATABASE_URL")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get(TEST_DB_ENV):
        return
    if os.environ.get("CI") == "true":
        # In CI the database tests must run; an unset URL is a configuration error (DP19).
        raise pytest.UsageError(f"{TEST_DB_ENV} must be set in CI; database tests cannot skip")
    skip = pytest.mark.skip(reason=f"{TEST_DB_ENV} not set")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


API_ROOT = Path(__file__).resolve().parents[1]


def alembic_config(url: str) -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.cmd_opts = argparse.Namespace(x=[f"url={url}"])
    return cfg


@pytest.fixture(scope="session")
def db_url() -> str:
    url = os.environ.get(TEST_DB_ENV)
    if not url:
        pytest.skip(f"{TEST_DB_ENV} not set")
    command.upgrade(alembic_config(url), "head")
    return url


@pytest.fixture
def db_conn(db_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(db_url, autocommit=True) as conn:
        yield conn
