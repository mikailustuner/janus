"""Source registry loaded from sources.toml (design §3.4, Req 3)."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast


class Storage(StrEnum):
    RUNTIME_ONLY = "runtime_only"
    CACHE = "cache"
    COMMIT = "commit"
    SEPARATE_PACKAGE = "separate_package"
    CITED_ONLY = "cited_only"


REGIONS = frozenset({"TR", "EU", "US"})


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    banner: bool = False


@dataclass(frozen=True)
class Source:
    id: str
    section: str
    name: str
    license: str
    storage: Storage
    publisher: str | None = None
    notes: tuple[str, ...] = ()
    region: str | None = None
    cadence_days: int | None = None
    urls: tuple[str, ...] = ()


class RegistryError(Exception):
    """sources.toml is invalid."""


class UnknownSourceError(Exception):
    """A pipeline or manifest names a source that is not in the registry (Req 3.1, 3.2)."""


@dataclass(frozen=True)
class Registry:
    header: str
    sections: tuple[Section, ...]
    sources: tuple[Source, ...]

    def get(self, source_id: str) -> Source:
        for s in self.sources:
            if s.id == source_id:
                return s
        raise UnknownSourceError(f"source {source_id!r} is not in the source registry")

    def __post_init__(self) -> None:
        validate(self)


def validate(reg: Registry) -> None:
    ids = [s.id for s in reg.sources]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise RegistryError(f"duplicate source ids: {', '.join(dupes)}")
    section_ids = [s.id for s in reg.sections]
    if len(set(section_ids)) != len(section_ids):
        raise RegistryError("duplicate section ids")
    for s in reg.sources:
        if not s.id or not s.name:
            raise RegistryError("every source needs an id and a name")
        if not s.license.strip():
            raise RegistryError(f"source {s.id!r} has no license")
        if s.section not in section_ids:
            raise RegistryError(f"source {s.id!r} names unknown section {s.section!r}")
        if s.region is not None and s.region not in REGIONS:
            raise RegistryError(f"source {s.id!r} has region {s.region!r}; use TR, EU or US")


def _str_tuple(value: object, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    items = cast(list[object], value) if isinstance(value, list) else None
    if items is None or not all(isinstance(v, str) for v in items):
        raise RegistryError(f"{where} must be a list of strings")
    return tuple(cast(list[str], value))


def _opt_str(table: Mapping[str, object], key: str) -> str | None:
    v = table.get(key)
    if v is not None and not isinstance(v, str):
        raise RegistryError(f"{key} must be a string")
    return v


def _req_str(table: Mapping[str, object], key: str, where: str) -> str:
    v = table.get(key)
    if not isinstance(v, str):
        raise RegistryError(f"{where}: {key} is required and must be a string")
    return v


def parse_registry(data: Mapping[str, object]) -> Registry:
    notice = data.get("notice", {})
    if not isinstance(notice, Mapping):
        raise RegistryError("[notice] must be a table")
    header = _opt_str(cast(Mapping[str, object], notice), "header") or ""

    raw_sections = cast(Sequence[Mapping[str, object]], data.get("sections", []))
    sections = tuple(
        Section(
            id=_req_str(s, "id", "section"),
            title=_req_str(s, "title", "section"),
            banner=bool(s.get("banner", False)),
        )
        for s in raw_sections
    )
    sources: list[Source] = []
    for raw in cast(Sequence[Mapping[str, object]], data.get("sources", [])):
        where = f"source {raw.get('id')!r}"
        storage_value = _req_str(raw, "storage", where)
        try:
            storage = Storage(storage_value)
        except ValueError:
            raise RegistryError(f"{where}: unknown storage {storage_value!r}") from None
        cadence = raw.get("cadence_days")
        if cadence is not None and (not isinstance(cadence, int) or cadence <= 0):
            raise RegistryError(f"{where}: cadence_days must be a positive integer")
        sources.append(
            Source(
                id=_req_str(raw, "id", where),
                section=_req_str(raw, "section", where),
                name=_req_str(raw, "name", where),
                license=_req_str(raw, "license", where),
                storage=storage,
                publisher=_opt_str(raw, "publisher"),
                notes=_str_tuple(raw.get("notes"), f"{where}.notes"),
                region=_opt_str(raw, "region"),
                cadence_days=cadence,
                urls=_str_tuple(raw.get("urls"), f"{where}.urls"),
            )
        )
    return Registry(header=header, sections=sections, sources=tuple(sources))


def load_registry(path: Path) -> Registry:
    with path.open("rb") as f:
        return parse_registry(tomllib.load(f))
