"""The current `modelkit_evidence` run with every drug's set and validation computed once
(design DP-M9). Read from `<data_dir>/artifacts/modelkit_evidence/current` on first use and again
whenever `current` points to another run, so a new release needs no restart. No database.
Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from janus.modelkit.builder import NoSet, ParameterSet, build_set
from janus.modelkit.evidence import PIPELINE, Ev, read_run
from janus.modelkit.validate import SystemReport, Validation, system_report, validate


@dataclass(frozen=True)
class DrugEntry:
    key: str
    rows: tuple[Ev, ...]
    built: ParameterSet | NoSet
    validation: Validation


@dataclass(frozen=True)
class Release:
    run_id: str
    snapshot_date: str
    license: str
    pipeline_version: str
    drugs: dict[str, DrugEntry]
    system: SystemReport
    manifest_metrics: dict[str, Any]

    def info(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "snapshot_date": self.snapshot_date,
            "pipeline_version": self.pipeline_version,
        }


def build_release(run: Path) -> Release:
    manifest, rows = read_run(run)
    by_drug: dict[str, list[Ev]] = {}
    for r in rows:
        by_drug.setdefault(r.drug_key, []).append(r)
    drugs: dict[str, DrugEntry] = {}
    for key in sorted(by_drug):
        built = build_set(key, by_drug[key])
        drugs[key] = DrugEntry(key, tuple(by_drug[key]), built, validate(key, by_drug[key], built))
    return Release(
        run_id=str(manifest["run_id"]),
        snapshot_date=str(manifest["snapshot_date"]),
        license=str(manifest["license"]),
        pipeline_version="modelkit-evidence-1.0",
        drugs=drugs,
        system=system_report([d.validation for d in drugs.values()]),
        manifest_metrics=dict(manifest.get("metrics") or {}),
    )


class ModelkitHolder:
    """`value` is the current release, or None when none is installed or it cannot be read."""

    def __init__(self, data_dir: Path | None) -> None:
        self._link = None if data_dir is None else data_dir / "artifacts" / PIPELINE / "current"
        self._lock = threading.Lock()
        self._target: str | None = None
        self._value: Release | None = None

    @property
    def value(self) -> Release | None:
        if self._link is None:
            return None
        try:
            target = os.path.realpath(self._link, strict=True)
        except OSError:
            return None
        with self._lock:
            if target != self._target:
                try:
                    self._value = build_release(Path(target))
                except (OSError, ValueError, KeyError):
                    self._value = None
                self._target = target
            return self._value
