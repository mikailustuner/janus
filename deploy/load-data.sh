#!/usr/bin/env bash
# Load the reference data into the stack's database (evidence → cascades → resolution), in the
# order the specs require (cascade-engine design §5). Run on the server after sync-data.sh and the
# TİTCK job, then whenever a data run changes. Loaders are idempotent.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
tag="${JANUS_TAG:-$(current_tag)}"
[ -n "$tag" ] || die "no release yet: run deploy.sh first"
pw="$(grep '^POSTGRES_PASSWORD=' "$STACK_DIR/.env" | cut -d= -f2-)"
[ -n "$pw" ] || die "POSTGRES_PASSWORD is not set in .env"
run() {
  # The resolution loader writes its coverage report under the data directory, so the loaders get
  # a writable mount; the running API keeps its read-only one.
  # They run as the deploy user, who owns STACK_DIR/data.
  docker run --rm --network janus-public-internal --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp \
    --cap-drop ALL --security-opt no-new-privileges:true \
    -e "DATABASE_URL=postgresql://janus:$pw@postgres:5432/janus" -e JANUS_DATA_DIR=/data -e HOME=/tmp \
    -v "$STACK_DIR/data:/data" "janus-api:$tag" "$@"
}
mkdir -p "$STACK_DIR/data/resolution"
log "evidence";   run python -m janus.integrity.load --data-dir /data
log "cascades";   run python -m janus.cascades.load
log "resolution"; run python -m janus.resolution.load --data-dir /data
log "loaded"
