# shellcheck shell=bash
# Shared helpers for the deploy scripts (sourced, not run). No host-specific values live here:
# STACK_DIR is the parent of the `src/` checkout that holds these scripts. JANUS_STACK_DIR points the
# scripts at another stack directory instead (staging.sh runs the checks against the staging stack).
set -euo pipefail
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(dirname "$DEPLOY_DIR")"
STACK_DIR="${JANUS_STACK_DIR:-$(dirname "$SRC_DIR")}"
STAGING_DIR="${STAGING_DIR:-$STACK_DIR/../janus-staging}"
env_file_value() {  # env_file_value <file> <KEY> [default]: a plain KEY=value line of an env file
  local v; v="$(grep -m1 "^$2=" "$1" 2>/dev/null | cut -d= -f2-)" || true
  printf '%s' "${v:-${3:-}}"
}
# Compose project name: the production default, or the staging stack's own (see staging.sh).
JANUS_STACK="$(env_file_value "$STACK_DIR/.env" JANUS_STACK janus-public)"
export JANUS_STACK
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
