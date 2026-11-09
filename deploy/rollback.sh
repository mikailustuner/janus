#!/usr/bin/env bash
# Re-start the stack with an earlier release's images (deploy Req 6.4).
# Usage: rollback.sh [tag]   (default: the release before the current one)
# Migrations are forward-only and backward-compatible within one release, so no downgrade runs.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
tag="${1:-$(previous_tag)}"
[[ "$tag" =~ ^[0-9a-f]{12}$ ]] || die "no earlier release to roll back to"
docker image inspect "janus-api:$tag" "janus-web:$tag" "janus-simulator:$tag" >/dev/null 2>&1 \
  || die "images of $tag are gone (a release before the simulator needs its own compose.yml, see README)"
export JANUS_TAG="$tag"
compose up -d --wait --remove-orphans
set_tag "$tag"
echo "$tag" >> "$STACK_DIR/releases.log"
log "rolled back to $tag"
