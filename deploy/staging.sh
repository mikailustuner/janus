#!/usr/bin/env bash
# Ephemeral staging check of a release before the production swap (deploy README "Staging").
# Usage: staging.sh <tag>      (deploy.sh runs it after the build, before it touches production)
# Runs the new release's images as the stack `janus-staging` (own networks, own volume, own
# secrets, no tunnel) on a fresh copy of the production database: restore, migrations, simulator
# role, start, isolation check, smoke test. The staging stack and its volume are removed afterwards
# in every case. Exit status is non-zero on any failure. Nothing here prints a secret.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

tag="${1:-}"
[[ "$tag" =~ ^[0-9a-f]{12}$ ]] || die "usage: staging.sh <12-character release tag>"
sdir="$STAGING_DIR"
prod_stack="$JANUS_STACK"
[ -d "$sdir" ] || die "staging directory $sdir is missing (run staging-setup.sh)"
[ -f "$sdir/.env" ] || die "$sdir/.env is missing (run staging-setup.sh)"
[ "$(stat -c %a "$sdir/.env")" = "600" ] || die "$sdir/.env must have mode 600"
[ -e "$sdir/data" ] || die "$sdir/data is missing (run staging-setup.sh)"
"$DEPLOY_DIR/secrets-setup.sh" --check --staging >/dev/null || die "staging secrets are not in order (run secrets-setup.sh --staging)"
sstack="$(env_file_value "$sdir/.env" JANUS_STACK)"
if [ -z "$sstack" ] || [ "$sstack" = "$prod_stack" ]; then
  die "staging .env must set JANUS_STACK to a name other than production's ($prod_stack)"
fi
for k in JANUS_NET_INTERNAL JANUS_NET_EDGE JANUS_UID JANUS_GID; do
  [ -n "$(env_file_value "$sdir/.env" "$k")" ] || die "$k is not set in $sdir/.env"
done

# Compose for the staging stack. Production's `compose` (lib.sh) stays pointed at STACK_DIR.
scompose() {
  env JANUS_STACK="$sstack" JANUS_TAG="$tag" \
    docker compose --project-directory "$sdir" -f "$sdir/compose.yml" "$@"
}
cleanup() {
  log "removing the staging stack and its volume"
  scompose --profile migrate down --volumes --remove-orphans >/dev/null 2>&1 \
    || log "warning: staging stack removal reported an error"
}
trap cleanup EXIT

install -m 644 "$DEPLOY_DIR/compose.yml" "$sdir/compose.yml"
log "staging $tag: clearing any previous staging stack"
scompose --profile migrate down --volumes --remove-orphans >/dev/null 2>&1 || true

log "staging: starting postgres"
scompose up -d --wait postgres >/dev/null
log "staging: restoring a fresh dump of production"
compose exec -T postgres pg_dump -U janus -d janus --format=custom --compress=6 \
  | scompose exec -T postgres pg_restore -U janus -d janus --no-owner --no-privileges --exit-on-error
# Cluster-wide objects are not in the dump, and --no-privileges drops the grants: give the worker
# role back what migration 0014 gives it (the migrations below create the role when 0014 is new).
scompose exec -T postgres psql -U janus -d janus -v ON_ERROR_STOP=1 -q >/dev/null <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'janus_simulator') THEN
        CREATE ROLE janus_simulator NOLOGIN;
    END IF;
END
$$;
SQL
log "staging: migrating"
scompose --profile migrate run --rm migrate >/dev/null
scompose exec -T postgres psql -U janus -d janus -v ON_ERROR_STOP=1 -q >/dev/null <<'SQL'
GRANT USAGE ON SCHEMA public TO janus_simulator;
GRANT SELECT, UPDATE, DELETE ON simulation_jobs TO janus_simulator;
SQL
scompose --profile migrate run --rm migrate python -m janus.simulation.dbrole >/dev/null

log "staging: starting the release"
scompose up -d --wait postgres api simulator web >/dev/null

log "staging: checks"
export JANUS_STACK_DIR="$sdir" JANUS_TAG="$tag"
"$DEPLOY_DIR/verify-isolation.sh"
"$DEPLOY_DIR/smoke.sh" internal "$tag"
log "staging: ok ($tag)"
