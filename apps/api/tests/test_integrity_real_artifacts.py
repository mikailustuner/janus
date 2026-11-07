"""Real artifacts, local only (evidence-integrity design §7). Skipped in CI and when `.data` has
no current `pipc` and `retractions` artifacts. Uses the repository's `pipelines/sources.toml`."""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from janus.db.pool import Database
from janus.integrity import service
from janus.integrity.load import gather, load
from janus.integrity.model import Status
from tests.integrity_db import REGISTRY, reset

DATA = Path(os.environ.get("JANUS_DATA_DIR") or Path(__file__).resolve().parents[3] / ".data")
HAVE = (
    os.environ.get("CI") != "true"
    and (DATA / "artifacts" / "pipc" / "current").exists()
    and (DATA / "artifacts" / "retractions" / "current").exists()
)

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not HAVE, reason="no local pipc and retractions artifacts"),
]


@pytest.fixture
def database(db_url: str) -> Iterator[Database]:
    db = Database(db_url)
    db.open()
    yield db
    db.close()


def test_pipc_evidence_from_the_real_artifacts(
    database: Database, db_conn: psycopg.Connection
) -> None:
    reset(db_conn)
    day = dt.datetime.now(dt.UTC).date()
    load(database, gather(DATA, REGISTRY), day)
    with database.read_only_tx() as conn:
        res = service.resolve_evidence(conn, ["dataset:pipc"], day)
    (item,) = res.items
    assert item.citable
    assert item.doi == "10.1007/s41999-025-01215-x"
    assert item.integrity is not None
    assert item.integrity.status == Status.CORRECTED.value
    (notice,) = item.integrity.notices
    assert notice.notice_doi == "10.1007/s41999-025-01378-7"
    assert notice.type == "correction"
    assert notice.date == dt.date(2025, 12, 18)
    assert item.freshness is not None and item.freshness.state == "current"
    assert res.line.no_retracted_used and res.line.by_status.corrected == 1
