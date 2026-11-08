"""The current light build, read-only (design §9, Req 6.4, DP11).

`LightHolder` follows `$JANUS_DATA_DIR/light/current` and reloads when the link moves; a missing,
unreadable or other-schema file fails closed with `LightUnavailableError` (503 `light_unavailable`).
It holds the parsed file, not results of requests.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from pydantic import ValidationError

from janus.light.build import LIGHT_DIR, LIGHT_FILE
from janus.light.schemas import LightFile


class LightUnavailableError(RuntimeError):
    """No usable light build. Never carries a medicine or condition."""


class LightHolder:
    def __init__(self, data_dir: Path | None) -> None:
        self._root = None if data_dir is None else data_dir / LIGHT_DIR
        self._file: LightFile | None = None
        self._lock = threading.Lock()

    def current(self) -> LightFile:
        if self._root is None:
            raise LightUnavailableError("no data directory is configured")
        link = self._root / "current"
        try:
            build = Path(os.readlink(link)).name
        except OSError as exc:
            raise LightUnavailableError("there is no current light build") from exc
        cached = self._file
        if cached is not None and cached.build_id == build:
            return cached
        with self._lock:
            cached = self._file
            if cached is not None and cached.build_id == build:
                return cached
            try:
                light = LightFile.model_validate_json((link / LIGHT_FILE).read_bytes())
            except (OSError, ValidationError) as exc:
                raise LightUnavailableError("the light build cannot be read") from exc
            if light.build_id != build:
                raise LightUnavailableError("the light build does not match its directory")
            self._file = light
            return light
