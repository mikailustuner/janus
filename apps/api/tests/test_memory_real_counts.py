"""Local-only checks against the real counts file (skipped without counts, and in CI).

The precomputed tables and the report-level tables are two independent routes to the same cells;
the packaged Janus vocabulary must only name PTs that exist in the file (Req 6.5).
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pytest

from janus.memory.faers_build import COUNTS_DB, counts_root
from janus.memory.model import RESPONSE_REGIONS
from janus.memory.reader import CountsHolder
from janus.memory.vocabulary import load_events, missing_pts
from janus.settings import EVENT_VOCABULARY

DATA_DIR = os.environ.get("JANUS_DATA_DIR")
COUNTS = None if not DATA_DIR else counts_root(Path(DATA_DIR)) / "current" / COUNTS_DB

pytestmark = pytest.mark.skipif(
    COUNTS is None or not COUNTS.exists(), reason="no local counts file (JANUS_DATA_DIR)"
)


def test_precomputed_and_report_level_cells_agree_on_real_pairs() -> None:
    assert DATA_DIR is not None
    reader = CountsHolder(Path(DATA_DIR)).current()
    probe = duckdb.connect(str(reader.path), read_only=True)
    sample = probe.execute(
        "SELECT ingredient_key, pt, scope FROM (SELECT * FROM faers_pair_counts "
        "WHERE region = 'ALL') USING SAMPLE 150 ROWS (reservoir, 11)"
    ).fetchall()
    probe.close()
    assert len(sample) == 150
    with reader.session() as s:
        for key, pt, scope in sample:
            fast = s.cells([key], [pt], scope, RESPONSE_REGIONS)
            slow = s.cells([key], [pt], scope, RESPONSE_REGIONS, force_report_level=True)
            assert fast == slow, (key, pt, scope)
            c = fast["ALL"]
            assert c.a >= 1 and c.a <= min(c.exposure, c.event_mapped)
            assert sum(fast[r].a for r in RESPONSE_REGIONS if r != "ALL") == c.a


def test_the_packaged_vocabulary_names_only_pts_that_exist() -> None:
    assert COUNTS is not None
    con = duckdb.connect(str(COUNTS), read_only=True)
    known = {
        str(r[0]) for r in con.execute("SELECT DISTINCT pt FROM faers_event_counts").fetchall()
    }
    con.close()
    assert missing_pts(load_events(EVENT_VOCABULARY), known) == {}
