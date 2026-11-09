#!/usr/bin/env bash
# Build and release one commit of the public repository (deploy design §6).
# Usage (on the server): STACK_DIR/src/deploy/deploy.sh <commit>
# Build first, then swap: a failed build or check leaves the running version in place.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

commit="${1:-}"
[[ "$commit" =~ ^[0-9a-f]{7,40}$ ]] || die "usage: deploy.sh <git commit id>"
[ -f "$STACK_DIR/.env" ] || die "STACK_DIR/.env is missing (see deploy/env.example)"
[ "$(stat -c %a "$STACK_DIR/.env")" = "600" ] || die "STACK_DIR/.env must have mode 600"
[ -f "$STACK_DIR/cloudflared/config.yml" ] || die "cloudflared/config.yml is missing"

cd "$SRC_DIR"
[ -z "$(git status --porcelain)" ] || die "the src checkout has local changes"
git fetch --quiet origin
git checkout --quiet --detach "$commit"
full="$(git rev-parse HEAD)"
tag="${full:0:12}"
log "building $tag"
docker build --quiet -t "janus-api:$tag" --build-arg "JANUS_COMMIT=$full" -f apps/api/Dockerfile . >/dev/null
docker build --quiet -t "janus-web:$tag" --build-arg "JANUS_COMMIT=$full" -f apps/web/Dockerfile . >/dev/null
# Simulation worker: R + httk (the first build on the server compiles packages; later builds are cached).
docker build --quiet -t "janus-simulator:$tag" -f apps/api/simulator.Dockerfile . >/dev/null

prev="$(current_tag)"
install -m 644 deploy/compose.yml "$STACK_DIR/compose.yml"
export JANUS_TAG="$tag"
log "migrating"
compose --profile migrate run --rm migrate >/dev/null
# The simulation worker's database role gets its login (idempotent; password from .env, never argv).
compose --profile migrate run --rm migrate python -m janus.simulation.dbrole >/dev/null
log "starting"
if ! compose up -d --wait --remove-orphans; then
  log "start failed"; [ -n "$prev" ] && "$DEPLOY_DIR/rollback.sh" "$prev"; exit 1
fi
if ! "$DEPLOY_DIR/verify-isolation.sh" || ! "$DEPLOY_DIR/smoke.sh" internal "$tag"; then
  log "checks failed"; [ -n "$prev" ] && "$DEPLOY_DIR/rollback.sh" "$prev"; exit 1
fi
set_tag "$tag"
echo "$tag" >> "$STACK_DIR/releases.log"
# Keep the images of the last three releases.
keep="$(tail -n 3 "$STACK_DIR/releases.log")"
for repo in janus-api janus-web janus-simulator; do
  docker image ls "$repo" --format '{{.Tag}}' | while read -r t; do
    grep -qx "$t" <<<"$keep" || docker image rm --force "$repo:$t" >/dev/null 2>&1 || true
  done
done
log "released $tag"
