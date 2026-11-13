#!/usr/bin/env bash
# Tag a release (docs/releasing.md). Usage: scripts/release.sh X.Y.Z
# Needs a clean main that is pushed, and a "## [X.Y.Z] - YYYY-MM-DD" section in CHANGELOG.md. Sets the
# version and date in CITATION.cff, commits that, creates the annotated tag vX.Y.Z and pushes both.
# Deploying the tagged commit is a separate step on the server (deploy/deploy.sh <commit>).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
version="${1:-}"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "usage: release.sh X.Y.Z" >&2; exit 2; }
[ "$(git branch --show-current)" = main ] || { echo "release from main only" >&2; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "the working tree has changes" >&2; exit 1; }
git fetch --quiet origin main
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || { echo "main is not pushed" >&2; exit 1; }
git rev-parse -q --verify "refs/tags/v$version" >/dev/null && { echo "v$version exists" >&2; exit 1; }
date="$(sed -n "s/^## \[$version\] - \([0-9-]*\)$/\1/p" CHANGELOG.md)"
[ -n "$date" ] || { echo "CHANGELOG.md has no '## [$version] - YYYY-MM-DD' section" >&2; exit 1; }

sed -i "s/^version: .*/version: \"$version\"/; s/^date-released: .*/date-released: \"$date\"/" CITATION.cff
if [ -n "$(git status --porcelain CITATION.cff)" ]; then
  git commit --quiet -m "release: $version" CITATION.cff
fi
git tag -a "v$version" -m "Janus $version"
git push --quiet origin main "v$version"
echo "tagged v$version at $(git rev-parse --short=12 HEAD); deploy that commit on the server"
