"""The repository root for build-time tools (data packages, light face build, OpenAPI document).

Inside the API image the package lives at `/app/janus` and there is no repository above it; the
running API never reads these paths, but the modules that define them are imported at startup,
so the root falls back to the working directory instead of failing (deploy task 1).
"""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    parents = Path(__file__).resolve().parents  # janus, api, apps, <repo>
    return parents[3] if len(parents) > 3 else Path.cwd()
