#!/usr/bin/env bash
# One-time setup of the staging stack directory (deploy README "Staging"). Run as the deploy user.
# Creates STAGING_DIR (default: STACK_DIR/../janus-staging) with its own .env, a `data` link to the
# production data directory (the staging api mounts it read-only) and a secrets/ folder. The
# secrets themselves need root for their ownership: the last step is one sudo command, printed here.
# Idempotent. Staging uses new random secrets, never the production ones.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

[ "$(id -u)" != 0 ] || die "run as the deploy user, not root (the staging files belong to that user)"
[ -f "$STACK_DIR/.env" ] || die "$STACK_DIR/.env is missing"
uid_val="$(env_file_value "$STACK_DIR/.env" JANUS_UID)"
gid_val="$(env_file_value "$STACK_DIR/.env" JANUS_GID)"
if [ -z "$uid_val" ] || [ -z "$gid_val" ]; then die "JANUS_UID and JANUS_GID must be set in $STACK_DIR/.env"; fi
[ "$STAGING_DIR" != "$STACK_DIR" ] || die "STAGING_DIR must not be the production directory"

mkdir -p "$STAGING_DIR"
STAGING_DIR="$(cd "$STAGING_DIR" && pwd)"
if [ ! -f "$STAGING_DIR/.env" ]; then
  (umask 077; cat > "$STAGING_DIR/.env" <<EOF
# Staging stack (deploy/staging.sh). Settings only; its secrets are files under secrets/.
JANUS_STACK=janus-staging
JANUS_NET_INTERNAL=172.31.254.0/24
JANUS_NET_EDGE=172.31.253.0/24
JANUS_UID=$uid_val
JANUS_GID=$gid_val
# Set by staging.sh; do not edit.
JANUS_TAG=
EOF
  )
  log "wrote $STAGING_DIR/.env"
fi
chmod 600 "$STAGING_DIR/.env"
if [ ! -e "$STAGING_DIR/data" ]; then
  ln -s "$STACK_DIR/data" "$STAGING_DIR/data"
  log "linked $STAGING_DIR/data to the production data directory"
fi
mkdir -p "$STAGING_DIR/secrets"

if "$DEPLOY_DIR/secrets-setup.sh" --check --staging >/dev/null 2>&1; then
  log "staging secrets are in place; setup complete"
else
  log "next, as root (creates the staging secrets with the container users' ownership):"
  log "  sudo $DEPLOY_DIR/secrets-setup.sh --staging"
fi
