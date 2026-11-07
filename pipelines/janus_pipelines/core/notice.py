"""NOTICE rendering from the source registry (design §4.5, Req 3.2). Pure."""

from __future__ import annotations

import textwrap
from collections.abc import Iterable, Mapping

from janus_pipelines.core.registry import Registry, Source, UnknownSourceError

WIDTH = 80
RULE = "-" * WIDTH


def _wrap(text: str) -> list[str]:
    return textwrap.wrap(
        text,
        width=WIDTH,
        initial_indent="  ",
        subsequent_indent="  ",
        break_long_words=False,
        break_on_hyphens=False,
    ) or ["  "]


def _entry(source: Source, snapshot: str | None) -> list[str]:
    lines = [source.name]
    if source.publisher:
        lines += _wrap(f"Publisher: {source.publisher}")
    lines += _wrap(f"License: {source.license}")
    for note in source.notes:
        lines += _wrap(note)
    if snapshot:
        lines += _wrap(f"Snapshot: {snapshot}")
    return lines


def render_notice(
    registry: Registry,
    used_source_ids: Iterable[str] = (),
    snapshots: Mapping[str, str] | None = None,
) -> str:
    """Render NOTICE. Fails if an artifact uses a source that is not in the registry."""
    known = {s.id for s in registry.sources}
    unknown = sorted(set(used_source_ids) - known)
    if unknown:
        raise UnknownSourceError(
            "artifacts use sources missing from sources.toml: " + ", ".join(unknown)
        )
    snapshots = snapshots or {}
    out: list[str] = [registry.header.strip("\n"), ""]
    for section in registry.sections:
        members = [s for s in registry.sources if s.section == section.id]
        if not members:
            continue
        if section.banner:
            out += [RULE, section.title, RULE, ""]
        else:
            out += [section.title, "-" * len(section.title), ""]
        for source in members:
            out += [*_entry(source, snapshots.get(source.id)), ""]
    return "\n".join(out).rstrip("\n") + "\n"
