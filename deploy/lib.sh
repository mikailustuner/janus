# shellcheck shell=bash
# Shared helpers for the deploy scripts (sourced, not run). No host-specific values live here:
# STACK_DIR is the parent of the `src/` checkout that holds these scripts.
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(dirname "$DEPLOY_DIR")"
STACK_DIR="$(dirname "$SRC_DIR")"
compose() { docker compose --project-directory "$STACK_DIR" -f "$STACK_DIR/compose.yml" "$@"; }
log() { printf '[janus-deploy] %s\n' "$*" >&2; }
die() { log "error: $*"; exit 1; }
current_tag() { tail -n 1 "$STACK_DIR/releases.log" 2>/dev/null || true; }
previous_tag() {  # the last release that differs from the current one (empty when none)
  local cur; cur="$(current_tag)"
  grep -vx "$cur" "$STACK_DIR/releases.log" 2>/dev/null | tail -n 1 || true
}
set_tag() {
  # Record the running tag in .env so `docker compose` works by hand and after a reboot.
  local tag="$1" env="$STACK_DIR/.env"
  if grep -q '^JANUS_TAG=' "$env"; then sed -i "s/^JANUS_TAG=.*/JANUS_TAG=$tag/" "$env"
  else printf 'JANUS_TAG=%s\n' "$tag" >> "$env"; fi
}
