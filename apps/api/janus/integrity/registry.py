"""Read the source registry for cadence, storage and licence (evidence-integrity design §4.5).

`pipelines/sources.toml` is the only place a cadence is declared (Req 2.1). This module reads the
fields the API needs; the pipelines project validates the whole file. Pure: takes text.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from janus.integrity.model import STORAGE_VALUES, SourceInfo


class RegistryError(ValueError):
    """The registry text cannot be used. The message names the source, never a value."""


def parse_sources(toml_text: str) -> dict[str, SourceInfo]:
    try:
        data = tomllib.loads(toml_text)
    except tomllib.TOMLDecodeError as exc:
        raise RegistryError("sources.toml is not valid TOML") from exc
    out: dict[str, SourceInfo] = {}
    for raw in cast(list[Mapping[str, Any]], data.get("sources", [])):
        sid = raw.get("id")
        if not isinstance(sid, str) or not sid:
            raise RegistryError("a source has no id")
        if sid in out:
            raise RegistryError(f"{sid}: duplicate source id")
        storage = raw.get("storage")
        if storage not in STORAGE_VALUES:
            raise RegistryError(f"{sid}: unknown storage rule")
        cadence = raw.get("cadence_days")
        if cadence is not None and (
            isinstance(cadence, bool) or not isinstance(cadence, int) or cadence < 1
        ):
            raise RegistryError(f"{sid}: cadence_days must be a positive integer")
        name = raw.get("name")
        lic = raw.get("license")
        region = raw.get("region")
        urls = raw.get("urls")
        first = urls[0] if isinstance(urls, list) and urls and isinstance(urls[0], str) else None
        out[sid] = SourceInfo(
            source_id=sid,
            name=name if isinstance(name, str) else sid,
            storage=cast(str, storage),
            cadence_days=cadence,
            license=lic if isinstance(lic, str) else None,
            region=region if isinstance(region, str) else None,
            url=first,
        )
    return out


def read_sources(path: Path) -> dict[str, SourceInfo]:
    return parse_sources(path.read_text(encoding="utf-8"))
