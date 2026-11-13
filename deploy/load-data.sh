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
# The API builds the new name index on the first lookup after a dataset change; until then the web
# proxy can drop visitors' searches. One lookup here builds it before anyone else asks.
code="$(docker run --rm --network "${JANUS_STACK}-internal" --read-only --cap-drop ALL curlimages/curl:8.17.0 \
  -s -o /dev/null -w '%{http_code}' -m 300 -X POST -H 'content-type: application/json' \
  -d '{"query":"amlodipine"}' http://api:8000/resolve/search || true)"
if [ "$code" = 200 ]; then log "name index warm"; else log "warning: warm-up lookup answered ${code:-nothing}"; fi
log "loaded"
