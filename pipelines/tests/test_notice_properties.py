"""Property and example tests for NOTICE generation."""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.notice import render_notice
from janus_pipelines.core.registry import (
    Registry,
    Section,
    Source,
    Storage,
    UnknownSourceError,
    load_registry,
)

LINE = (
    st.text(
        alphabet=st.characters(categories=["L", "N", "P", "Zs"], exclude_characters="\n\r"),
        min_size=1,
        max_size=30,
    )
    .map(str.strip)
    .filter(bool)
)

SOURCES = st.lists(
    st.tuples(st.from_regex(r"[a-z][a-z0-9_]{0,10}", fullmatch=True), LINE, LINE),
    min_size=1,
    max_size=12,
    unique_by=lambda t: t[0],
)


@st.composite
def registries(draw: st.DrawFn) -> Registry:
    sections = (Section("a", "Section A"), Section("b", "SECTION B", banner=True))
    sources = tuple(
        Source(
            id=sid,
            section=draw(st.sampled_from(["a", "b"])),
            name=name,
            license=lic,
            storage=draw(st.sampled_from(list(Storage))),
            publisher=draw(st.one_of(st.none(), LINE)),
        )
        for sid, name, lic in draw(SOURCES)
    )
    return Registry(header="Header line", sections=sections, sources=sources)


@given(registries(), st.data())
def test_notice_has_entry_for_every_used_source(reg: Registry, data: st.DataObject) -> None:
    """Feature: data-pipelines, Property P8 — Validates: Req 3.2.

    For any registry and any set of artifact sources in it, the NOTICE has an entry (name
    line and licence line) for every used source; the output is the same on every call.
    """
    used = data.draw(st.lists(st.sampled_from([s.id for s in reg.sources]), unique=True))
    text = render_notice(reg, used)
    lines = text.splitlines()

    def squash(s: str) -> str:
        return "".join(s.split())

    for sid in used:
        source = reg.get(sid)
        blocks: list[str] = []
        for i, line in enumerate(lines):
            if line == source.name:
                end = next((j for j in range(i + 1, len(lines)) if not lines[j]), len(lines))
                blocks.append(squash(" ".join(lines[i + 1 : end])))
        assert any("License:" + squash(source.license) in b for b in blocks), sid
    assert render_notice(reg, used) == text


@given(registries(), st.from_regex(r"zz[a-z]{1,5}", fullmatch=True))
def test_unknown_source_fails(reg: Registry, unknown: str) -> None:
    """Feature: data-pipelines, Property P8 — Validates: Req 3.2 (unknown source)."""
    with pytest.raises(UnknownSourceError):
        render_notice(reg, [unknown])


REPO = Path(__file__).resolve().parents[2]


def test_committed_notice_matches_registry() -> None:
    """Validates: Req 3.2 — the committed NOTICE is the generated one (also run in CI)."""
    from janus_pipelines.cli import build_notice

    assert (REPO / "NOTICE").read_text(encoding="utf-8") == build_notice(REPO)


def test_real_registry_keeps_notice_entries() -> None:
    reg = load_registry(REPO / "pipelines" / "sources.toml")
    text = " ".join(render_notice(reg).split())
    for needle in [
        "TİTCK — Ruhsatlı Beşeri Tıbbi Ürünler Listesi",
        "openFDA NDC Directory",
        "RxNav / RxClass",
        "NLM is not responsible",
        "WHOCC",
        "counts are reports, not people",
        "CC BY-NC-SA 4.0",
        "CITED ONLY — NOT INGESTED OR REDISTRIBUTED",
        "Hamdard",
        "Research prototype".lower(),
    ]:
        assert needle.lower() in text.lower(), needle


def test_phase2_sources_have_notice_entries() -> None:
    """Validates: Req 3.2 — the Phase 2 sources are in the registry and in NOTICE."""
    registry = load_registry(Path(__file__).resolve().parents[1] / "sources.toml")
    text = render_notice(registry, ["faers", "bdpm", "cima"])
    for needle in (
        "Adverse Event Monitoring System (AEMS, formerly FAERS)",
        "MedDRA® trademark is registered by IFPMA on behalf of ICH.",
        "Licence Ouverte (Etalab)",
        "Reuse with attribution (Ley 37/2007)",
    ):
        assert " ".join(needle.split()) in " ".join(text.split())
