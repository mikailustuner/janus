#!/usr/bin/env bash
# Load the reference data into the stack's database (evidence → cascades → resolution), in the
# order the specs require (cascade-engine design §5). Run on the server after sync-data.sh and the
# TİTCK job, then whenever a data run changes. Loaders are idempotent.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
tag="${JANUS_TAG:-$(current_tag)}"
[ -n "$tag" ] || die "no release yet: run deploy.sh first"
# The database URL is a mounted secret file (never an argument or environment value).
url_file="$STACK_DIR/secrets/database_url"
[ -r "$url_file" ] || die "$url_file is missing or unreadable (run secrets-setup.sh)"
run() {
  # The resolution loader writes its coverage report under the data directory, so the loaders get
  # a writable mount; the running API keeps its read-only one.
  # They run as the deploy user, who owns STACK_DIR/data and reads the secret file through its group.
  docker run --rm --network "${JANUS_STACK}-internal" --user "$(id -u):$(id -g)" --read-only --tmpfs /tmp \
    --cap-drop ALL --security-opt no-new-privileges:true \
    -e DATABASE_URL_FILE=/run/secrets/database_url -e JANUS_DATA_DIR=/data -e HOME=/tmp \
    -v "$url_file:/run/secrets/database_url:ro" -v "$STACK_DIR/data:/data" "janus-api:$tag" "$@"
}
mkdir -p "$STACK_DIR/data/resolution"
log "evidence";   run python -m janus.integrity.load --data-dir /data
log "cascades";   run python -m janus.cascades.load
log "resolution"; run python -m janus.resolution.load --data-dir /data
log "loaded"
