"""Reader for the precomputed time-machine artifact (design §8.3). No computation on a
request: the file is read once at startup and held in memory. A missing or malformed file
leaves the holder empty and `/timemachine/*` answers 503."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ArtifactError(ValueError):
    """The artifact is missing required keys."""


REQUIRED = (
    "built_at",
    "validation",
    "substances",
    "exposure",
    "cascades",
    "sources",
    "references",
    "onset_subset_caveat",
)


@dataclass(frozen=True)
class TimeMachine:
    built_at: str
    payload: dict[str, Any]

    @property
    def cascade_ids(self) -> list[str]:
        return [str(c["cascade_id"]) for c in self.payload["cascades"]]

    @property
    def substance_ids(self) -> list[str]:
        return [str(s["substance_id"]) for s in self.payload["substances"]]

    def cascade(self, cascade_id: str) -> dict[str, Any] | None:
        for c in self.payload["cascades"]:
            if c["cascade_id"] == cascade_id:
                return dict(c)
        return None

    def substance(self, substance_id: str) -> dict[str, Any] | None:
        for s in self.payload["substances"]:
            if s["substance_id"] == substance_id:
                return dict(s)
        return None

    def exposure_for(self, substance_id: str) -> list[dict[str, Any]]:
        return [dict(e) for e in self.payload["exposure"] if e["substance_id"] == substance_id]


def load(path: Path) -> TimeMachine:
    payload = json.loads(path.read_text())
    missing = [k for k in REQUIRED if k not in payload]
    if missing:
        raise ArtifactError(f"time machine artifact is missing {', '.join(missing)}")
    return TimeMachine(str(payload["built_at"]), payload)


class Holder:
    """Loads the artifact once; `value` is None when it is absent or malformed."""

    def __init__(self, data_dir: Path | None) -> None:
        self._path = (
            None if data_dir is None else data_dir / "timemachine" / "current" / "time_machine.json"
        )
        self._value: TimeMachine | None = None
        self._loaded = False

    @property
    def value(self) -> TimeMachine | None:
        if not self._loaded:
            self._loaded = True
            if self._path is not None:
                try:
                    self._value = load(self._path)
                except (OSError, ValueError):
                    self._value = None
        return self._value
