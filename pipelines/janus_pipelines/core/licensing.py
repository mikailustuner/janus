"""Licence guard for output paths (design §4.4, Req 3.1)."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from janus_pipelines.core.registry import Storage


class LicenceViolationError(Exception):
    """A write would break the source's storage rule."""


def is_within(path: Path, root: Path) -> bool:
    """True if `path` is `root` or inside it. Both must already be resolved."""
    return path == root or root in path.parents


def git_ignored(path: Path, repo_root: Path) -> bool:
    """True if git ignores `path` (which need not exist yet)."""
    git = shutil.which("git")
    if git is None:
        raise LicenceViolationError("git not found; cannot check whether the path is ignored")
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [git, "-C", str(repo_root), "check-ignore", "-q", "--no-index", str(path)],
        check=False,
        capture_output=True,
    )
    if result.returncode not in (0, 1):
        raise LicenceViolationError(f"git check-ignore failed: {result.stderr.decode().strip()}")
    return result.returncode == 0


def check_output_path(
    path: Path,
    storage: Storage,
    repo_root: Path,
    is_ignored: Callable[[Path], bool] | None = None,
) -> Path:
    """Return the resolved path, or raise if the source may not be written there.

    `runtime_only` sources may not be written inside `<repo>/data/`, nor anywhere in the
    repository that git does not ignore. `cited_only` sources are never written.
    """
    resolved = path.resolve()
    root = repo_root.resolve()
    if storage is Storage.CITED_ONLY:
        raise LicenceViolationError("cited-only sources are never stored")
    if storage is not Storage.RUNTIME_ONLY:
        return resolved
    if is_within(resolved, (root / "data").resolve()):
        raise LicenceViolationError(
            f"runtime-only source may not be written under data/: {resolved}"
        )
    if is_within(resolved, root):
        ignored = is_ignored(resolved) if is_ignored is not None else git_ignored(resolved, root)
        if not ignored:
            raise LicenceViolationError(
                f"runtime-only source may not be written to a path git tracks: {resolved}"
            )
    return resolved
