#!/usr/bin/env bash
# Forced command of the backup key on the Janus server (deploy/README.md, "Backups").
# Installed as STACK_DIR/backup-serve.sh (a copy, so a release checkout never changes it) and named in
# authorized_keys as: command="STACK_DIR/backup-serve.sh",restrict,from="<backup machine>" ssh-ed25519 ...
# It answers three read-only requests and refuses everything else.
set -euo pipefail
STACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${SSH_ORIGINAL_COMMAND:-}" in
  pg_dump)
    exec docker compose --project-directory "$STACK_DIR" -f "$STACK_DIR/compose.yml" \
      exec -T postgres pg_dump -U janus -d janus --format=custom --compress=6
    ;;
  releases.log)
    exec cat "$STACK_DIR/releases.log"
    ;;
  "rsync --server --sender "*)
    # rrsync checks the rsync arguments itself and confines them, read-only, to the data directory.
    exec rrsync -ro "$STACK_DIR/data"
    ;;
  *)
    echo "backup-serve: request refused" >&2
    exit 1
    ;;
esac
