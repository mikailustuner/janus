"""The outcome-store purge command (doctor-loop design §7.7): exit codes and one run."""

from __future__ import annotations

import pytest

from janus.notes import purge


def test_purge_needs_a_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert purge.main() == 2


@pytest.mark.db
def test_purge_runs_against_a_migrated_database(
    monkeypatch: pytest.MonkeyPatch, db_url: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", db_url)
    assert purge.main() == 0
    assert purge.main() == 0  # safe to repeat
