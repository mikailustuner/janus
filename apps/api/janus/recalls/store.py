"""The current `us_recalls` run as an in-memory index (recall-check design §6).

Read from `<data_dir>/artifacts/us_recalls/current` on first use and again whenever `current`
points to another run, so a weekly refresh needs no restart (Req 4.9). No database: the rows are
public records and the index is rebuilt in well under a second.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from janus.integrity.freshness import parse_snapshot_date
from janus.recalls.match import Index, build_index, recall_from_row

PIPELINE = "us_recalls"
SOURCE_ID = "openfda_enforcement"
SCHEMA_VERSION = "us_recalls-1"
COLUMNS = (
    "recall_number",
    "event_id",
    "status",
    "classification",
    "product_description",
    "code_info",
    "more_code_info",
    "reason_for_recall",
    "recalling_firm",
    "recall_initiation_date",
    "center_classification_date",
    "report_date",
    "termination_date",
)


@dataclass(frozen=True)
class Loaded:
    index: Index
    run_id: str
    snapshot_date: dt.date
    license: str


def read_run(run: Path) -> Loaded:
    """Read one run directory. Raises `OSError` or `ValueError` when it cannot be used."""
    manifest: dict[str, Any] = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    outcome = manifest.get("outcome")
    if outcome == "needs_review" and not (run / "promotion.json").exists():
        raise ValueError("needs_review run was not promoted")
    if outcome not in ("succeeded", "needs_review"):
        raise ValueError("run did not succeed")
    if manifest.get("source_id") != SOURCE_ID or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("not a us_recalls-1 run")
    con = duckdb.connect()
    try:
        cur = con.execute(
            f"SELECT {', '.join(COLUMNS)} FROM read_parquet(?)",  # noqa: S608 - constant columns
            [str(run / "rows.parquet")],
        )
        rows: list[dict[str, Any]] = [dict(zip(COLUMNS, r, strict=True)) for r in cur.fetchall()]
    except duckdb.Error as exc:
        raise ValueError("rows cannot be read") from exc
    finally:
        con.close()
    return Loaded(
        index=build_index(recall_from_row(r) for r in rows),
        run_id=str(manifest["run_id"]),
        snapshot_date=parse_snapshot_date(str(manifest["snapshot_date"])),
        license=str(manifest["license"]),
    )


class RecallsHolder:
    """`value` is the current run, or None when none is installed or it cannot be read."""

    def __init__(self, data_dir: Path | None) -> None:
        self._link = None if data_dir is None else data_dir / "artifacts" / PIPELINE / "current"
        self._lock = threading.Lock()
        self._target: str | None = None
        self._value: Loaded | None = None

    @property
    def value(self) -> Loaded | None:
        if self._link is None:
            return None
        try:
            target = os.path.realpath(self._link, strict=True)
        except OSError:
            return None
        with self._lock:
            if target != self._target:
                try:
                    self._value = read_run(Path(target))
                except (OSError, ValueError, KeyError):
                    self._value = None
                self._target = target
            return self._value
