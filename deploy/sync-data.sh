#!/usr/bin/env bash
# Copy the current runs of the built data from the developer's machine to the server (deploy
# Req 5.3–5.4, design §5) and switch each `current` link atomically there. Never TİTCK (Req 5.2).
# Usage (on the developer's machine, from the repository root):
#   JANUS_DEPLOY_SSH=<ssh destination> JANUS_DEPLOY_STACK=<STACK_DIR on the server> deploy/sync-data.sh
set -euo pipefail
dest="${JANUS_DEPLOY_SSH:?set JANUS_DEPLOY_SSH (ssh destination of the server)}"
stack="${JANUS_DEPLOY_STACK:?set JANUS_DEPLOY_STACK (STACK_DIR on the server)}"
local_data="${JANUS_DATA_DIR:-.data}"
roots=(memory/faers_counts light timemachine)
for job in "$local_data"/artifacts/*/; do
  name="$(basename "$job")"
  [ "$name" = titck ] && continue   # fetched on the server (data-sources.md)
  roots+=("artifacts/$name")
done
for root in "${roots[@]}"; do
  link="$local_data/$root/current"
  [ -L "$link" ] || { echo "skip $root (no current run)"; continue; }
  target="$(readlink "$link")"
  [[ "$target" == runs/* ]] || { echo "error: $link is not a relative runs/ link" >&2; exit 1; }
  run="${target#runs/}"
  rsync -a --mkpath --delete "$local_data/$root/runs/$run/" "$dest:$stack/data/$root/runs/$run/"
  # shellcheck disable=SC2029  # expanded here on purpose: paths of this machine's run ids
  ssh "$dest" "cd '$stack/data/$root' && ln -sfn 'runs/$run' current.tmp && mv -T current.tmp current"
  echo "synced $root -> $run"
done
