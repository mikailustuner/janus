"""The current `us_label_interactions` run in memory (safety-check design §6).

Read from `<data_dir>/artifacts/us_label_interactions/current` on first use and again whenever
`current` points to another run, like the recall records (`janus.recalls.store`). No database:
about 1,500 public label sections, a few megabytes of text.
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
from janus.safety.interactions import Label

PIPELINE = "us_label_interactions"
SOURCE_ID = "openfda_label_interactions"
SCHEMA_VERSION = "us_label_interactions-1"
COLUMNS = ("substance_name", "set_id", "version", "effective_date", "product_type", "text")


@dataclass(frozen=True)
class Loaded:
    labels: dict[str, Label]  # by case-folded substance name
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
        raise ValueError("not a us_label_interactions-1 run")
    con = duckdb.connect()
    try:
        cur = con.execute(
            f"SELECT {', '.join(COLUMNS)} FROM read_parquet(?)",  # noqa: S608 - constant columns
            [str(run / "rows.parquet")],
        )
        rows = cur.fetchall()
    except duckdb.Error as exc:
        raise ValueError("rows cannot be read") from exc
    finally:
        con.close()
    return Loaded(
        labels={str(r[0]).casefold(): Label(*r) for r in rows},
        run_id=str(manifest["run_id"]),
        snapshot_date=parse_snapshot_date(str(manifest["snapshot_date"])),
        license=str(manifest["license"]),
    )


class LabelsHolder:
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
                except (OSError, ValueError, KeyError, TypeError):
                    self._value = None
                self._target = target
            return self._value
