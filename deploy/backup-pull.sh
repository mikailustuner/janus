#!/usr/bin/env bash
# Pull one backup of the public Janus from its server (deploy/README.md, "Backups").
# Runs on the backup machine, never on the server. Usage: backup-pull.sh db|data
#   db    database dump (custom format, checked before it is kept) + releases.log; keeps the newest 14
#   data  snapshot of the server's data directory, unchanged files hard-linked to the previous one; keeps 4
# Config: BACKUP_DIR/backup.env (mode 600) sets BACKUP_SOURCE (ssh destination whose key is restricted by
# backup-serve.sh), BACKUP_KEY (that key) and optionally NTFY_URL and NTFY_TOKEN (a message is posted there
# on failure).
set -euo pipefail
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/janus}"
# shellcheck source=/dev/null
source "$BACKUP_DIR/backup.env"
: "${BACKUP_SOURCE:?set in backup.env}" "${BACKUP_KEY:?set in backup.env}"
mode="${1:-}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
ssh_cmd="ssh -i $BACKUP_KEY -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30"

notify() {
  [ -n "${NTFY_URL:-}" ] || return 0
  # The token goes through stdin, so it never appears in the process list.
  printf 'header = "Authorization: Bearer %s"\n' "${NTFY_TOKEN:-}" \
    | curl -fsS -m 20 -K - -H "Title: Janus backup failed" -H "Priority: high" -H "Tags: warning" \
      -d "$1" "$NTFY_URL" >/dev/null || true
}
trap 'notify "backup-pull $mode failed ($stamp, line $LINENO)"' ERR

prune() {  # prune <dir> <glob> <keep>: remove all but the newest <keep> entries (names sort by time)
  local dir="$1" glob="$2" keep="$3"
  find "$dir" -maxdepth 1 -name "$glob" -printf '%f\n' | sort | head -n "-$keep" \
    | while read -r name; do rm -rf -- "${dir:?}/$name"; done
}

case "$mode" in
  db)
    dir="$BACKUP_DIR/db"
    mkdir -p "$dir"
    part="$dir/.janus-$stamp.dump.part"
    trap 'rm -f "$part"' EXIT
    $ssh_cmd "$BACKUP_SOURCE" pg_dump > "$part"
    # A complete custom-format dump starts with PGDMP and its table of contents can be listed.
    [ "$(head -c 5 "$part")" = "PGDMP" ]
    docker run --rm -i --network none postgres:16.15-bookworm pg_restore --list < "$part" > /dev/null
    $ssh_cmd "$BACKUP_SOURCE" releases.log > "$dir/releases-$stamp.log"
    mv "$part" "$dir/janus-$stamp.dump"
    prune "$dir" 'janus-*.dump' 14
    prune "$dir" 'releases-*.log' 14
    ;;
  data)
    dir="$BACKUP_DIR/data"
    mkdir -p "$dir"
    part="$dir/.$stamp.part"
    link=()
    [ -d "$dir/latest/" ] && link=(--link-dest="$dir/latest/")
    rsync -a --delete "${link[@]}" -e "$ssh_cmd" "$BACKUP_SOURCE:./" "$part/"
    mv "$part" "$dir/$stamp"
    ln -sfn "$stamp" "$dir/latest"
    prune "$dir" '20*' 4
    ;;
  *)
    echo "usage: backup-pull.sh db|data" >&2
    exit 2
    ;;
esac
date -u +%Y-%m-%dT%H:%M:%SZ > "$BACKUP_DIR/$mode.last-ok"
# Prometheus text file of the last successes, served to the monitoring server (README, "Backups").
mkdir -p "$BACKUP_DIR/metrics"
{
  echo "# HELP janus_backup_last_success_timestamp_seconds Unix time of the last successful pull."
  echo "# TYPE janus_backup_last_success_timestamp_seconds gauge"
  for kind in db data; do
    [ -f "$BACKUP_DIR/$kind.last-ok" ] || continue
    printf 'janus_backup_last_success_timestamp_seconds{kind="%s"} %s\n' \
      "$kind" "$(date -u -d "$(cat "$BACKUP_DIR/$kind.last-ok")" +%s)"
  done
} > "$BACKUP_DIR/metrics/.janus_backup.prom.tmp"
mv "$BACKUP_DIR/metrics/.janus_backup.prom.tmp" "$BACKUP_DIR/metrics/janus_backup.prom"
