"""Property and example tests for the licence guard and the registry."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from janus_pipelines.core.licensing import LicenceViolationError, check_output_path
from janus_pipelines.core.registry import (
    Registry,
    RegistryError,
    Storage,
    UnknownSourceError,
    load_registry,
    parse_registry,
)

SOURCES_TOML = Path(__file__).resolve().parents[1] / "sources.toml"

SEGMENTS = st.lists(
    st.sampled_from([".", "..", "data", "x", "out", "link_to_data", "link_to_out", "DATA"]),
    min_size=1,
    max_size=6,
)


def _write_attempt(target: Path, storage: Storage, repo: Path) -> bool:
    """Write through the guard; True if written."""
    try:
        resolved = check_output_path(target, storage, repo, is_ignored=lambda _p: True)
    except LicenceViolationError:
        return False
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text("row")
    return True


@given(SEGMENTS, st.booleans())
def test_runtime_only_never_lands_in_data(segments: list[str], from_inside: bool) -> None:
    """Feature: data-pipelines, Property P7 — Validates: Req 3.1.

    For any path built from `.`, `..`, names and symlinks, a runtime_only write that resolves
    inside <repo>/data/ is refused and data/ stays empty. Paths elsewhere are judged exactly
    like a reference resolve() containment check.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp).resolve()
        # Deep enough that up to 6 `..` segments stay inside the temporary directory.
        repo = base.joinpath(*[f"l{i}" for i in range(8)], "repo")
        data = repo / "data"
        (repo / "x" / "out").mkdir(parents=True)
        data.mkdir()
        os.symlink(data, repo / "x" / "link_to_data")
        os.symlink(repo / "x" / "out", repo / "link_to_out")
        start = repo / "x" if from_inside else repo
        target = start.joinpath(*segments, "rows.parquet")

        reference_in_data = data in target.resolve().parents
        assert base in target.resolve().parents  # the test never writes outside its sandbox
        written = _write_attempt(target, Storage.RUNTIME_ONLY, repo)

        assert written is not reference_in_data
        assert list(data.rglob("*")) == []


def test_runtime_only_tracked_path_is_refused(tmp_path: Path) -> None:
    """Validates: Req 3.1 — inside the repo but not git-ignored is refused."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)  # noqa: S603, S607
    (repo / ".gitignore").write_text(".data/\n")
    with pytest.raises(LicenceViolationError, match="git tracks"):
        check_output_path(repo / "pipelines" / "copy.parquet", Storage.RUNTIME_ONLY, repo)
    allowed = check_output_path(repo / ".data" / "a" / "rows.parquet", Storage.RUNTIME_ONLY, repo)
    assert allowed.name == "rows.parquet"
    outside = check_output_path(tmp_path / "elsewhere" / "r", Storage.RUNTIME_ONLY, repo)
    assert outside.parent.name == "elsewhere"


def test_cache_and_commit_allowed_in_data(tmp_path: Path) -> None:
    for storage in (Storage.CACHE, Storage.COMMIT):
        check_output_path(tmp_path / "data" / "pipc.csv", storage, tmp_path)
    with pytest.raises(LicenceViolationError):
        check_output_path(tmp_path / "x", Storage.CITED_ONLY, tmp_path)


def test_real_registry_loads() -> None:
    reg = load_registry(SOURCES_TOML)
    assert reg.get("titck").storage is Storage.RUNTIME_ONLY
    assert reg.get("pipc").storage is Storage.COMMIT
    with pytest.raises(UnknownSourceError):
        reg.get("nope")


def _minimal(**overrides: object) -> dict[str, object]:
    source: dict[str, object] = {
        "id": "a",
        "section": "s",
        "name": "A",
        "license": "CC0",
        "storage": "cache",
    }
    source.update(overrides)
    return {"sections": [{"id": "s", "title": "S"}], "sources": [source]}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"storage": "sometimes"}, "unknown storage"),
        ({"license": "  "}, "no license"),
        ({"region": "DE"}, "region"),
        ({"section": "zzz"}, "unknown section"),
    ],
)
def test_registry_rejects_invalid(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(RegistryError, match=message):
        parse_registry(_minimal(**overrides))


def test_registry_rejects_duplicate_ids() -> None:
    data = _minimal()
    sources = data["sources"]
    assert isinstance(sources, list)
    data["sources"] = [*sources, *sources]
    with pytest.raises(RegistryError, match="duplicate"):
        parse_registry(data)


def test_registry_type() -> None:
    assert isinstance(parse_registry(_minimal()), Registry)
