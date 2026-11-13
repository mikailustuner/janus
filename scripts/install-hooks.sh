#!/usr/bin/env bash
# Point git at the repository's hooks (.githooks/). Git worktrees of this clone share the setting.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
git config core.hooksPath .githooks
echo "hooks: $(git config core.hooksPath)"
