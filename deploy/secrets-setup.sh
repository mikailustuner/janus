#!/usr/bin/env bash
# Secrets as files (deploy README "Secrets"). Run with sudo, once; idempotent. Prints what it did,
# never a value.
#   sudo deploy/secrets-setup.sh              production: move the secrets of STACK_DIR/.env into
#                                             STACK_DIR/secrets/, then remove them from .env
#   sudo deploy/secrets-setup.sh --staging    staging stack (STAGING_DIR): new random secrets
#   deploy/secrets-setup.sh --check [--staging]   verify only (no sudo needed to read: group access)
#
# Each file is owned by the uid of the container user that reads it, group = the group of the
# stack's .env (the deploy user), mode 0440: plain compose bind-mounts the file with these host
# permissions, and the deploy user's scripts (load-data.sh, staging.sh) read it through the group.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

check_only=0 staging=0
for arg in "$@"; do
  case "$arg" in
    --check) check_only=1 ;;
    --staging) staging=1 ;;
    *) die "usage: secrets-setup.sh [--staging] [--check]" ;;
  esac
done
if [ "$staging" = 1 ]; then dir="$STAGING_DIR"; else dir="$STACK_DIR"; fi
env_file="$dir/.env"
sec="$dir/secrets"
[ -f "$env_file" ] || die "$env_file is missing"
[ "$check_only" = 1 ] || [ "$(id -u)" = 0 ] || die "run with sudo"

declare -A OWNER=(
  [postgres_password]=999            # postgres
  [database_url]=10001               # api, migrate
  [noise_key]=10001                  # api
  [simulator_db_password]=10001      # migrate (python -m janus.simulation.dbrole)
  [simulator_database_url]=10002     # simulator
)
NAMES=(postgres_password database_url noise_key simulator_db_password simulator_database_url)
ENV_KEYS=(POSTGRES_PASSWORD JANUS_NOISE_KEY SIMULATOR_DB_PASSWORD DATABASE_URL)
gid="$(stat -c %g "$env_file")"
uid="$(stat -c %u "$env_file")"

read_secret() { tr -d '\n' < "$sec/$1"; }  # only for comparisons; never printed
url_for() {  # url_for <role> <password>
  printf 'postgresql://%s:%s@postgres:5432/janus' "$1" "$2"
}

check_files() {  # check_files: returns 1 when a file is missing, mis-owned, or inconsistent
  local bad=0 n mode
  for n in "${NAMES[@]}"; do
    if [ ! -f "$sec/$n" ]; then log "missing: secrets/$n"; bad=1; continue; fi
    mode="$(stat -c %a "$sec/$n")"
    [ "$mode" = 440 ] || { log "secrets/$n: mode is $mode, want 440"; bad=1; }
    [ "$(stat -c %u "$sec/$n")" = "${OWNER[$n]}" ] || { log "secrets/$n: owner is not uid ${OWNER[$n]}"; bad=1; }
    [ "$(stat -c %g "$sec/$n")" = "$gid" ] || { log "secrets/$n: group is not the stack's group"; bad=1; }
    [ -s "$sec/$n" ] || { log "secrets/$n is empty"; bad=1; }
  done
  [ "$bad" = 0 ] || return 1
  [ "$(read_secret database_url)" = "$(url_for janus "$(read_secret postgres_password)")" ] \
    || { log "secrets/database_url does not match postgres_password"; bad=1; }
  [ "$(read_secret simulator_database_url)" = "$(url_for janus_simulator "$(read_secret simulator_db_password)")" ] \
    || { log "secrets/simulator_database_url does not match simulator_db_password"; bad=1; }
  return "$bad"
}

env_clean() {  # env_clean: no secret lines left in .env
  local k bad=0
  for k in "${ENV_KEYS[@]}"; do
    if grep -q "^$k=" "$env_file"; then log "$env_file still has a $k line"; bad=1; fi
  done
  return "$bad"
}

if [ "$check_only" = 1 ]; then
  rc=0
  check_files || rc=1
  env_clean || rc=1
  if [ "$rc" = 0 ]; then log "secrets: ok ($sec)"; else log "secrets: PROBLEMS in $sec"; fi
  exit "$rc"
fi

rand_password() { openssl rand -base64 32 | tr -d '/+=\n'; }
rand_key() { openssl rand 32 | basenc --base64url | tr -d '=\n'; }

if [ "$staging" = 1 ]; then
  # Keep what exists (so a re-run changes nothing), generate the rest.
  keep_or() {  # keep_or <name> <generator>
    if [ -f "$sec/$1" ]; then read_secret "$1"; else "$2"; fi
  }
  pw="$(keep_or postgres_password rand_password)"
  spw="$(keep_or simulator_db_password rand_password)"
  key="$(keep_or noise_key rand_key)"
else
  pw="$(env_file_value "$env_file" POSTGRES_PASSWORD)"
  spw="$(env_file_value "$env_file" SIMULATOR_DB_PASSWORD)"
  key="$(env_file_value "$env_file" JANUS_NOISE_KEY)"
  if [ -z "$pw$spw$key" ]; then
    # Already moved: only verify.
    if check_files && env_clean; then log "secrets already set up and verified ($sec)"; exit 0; fi
    die "no secrets in $env_file and the files in $sec are not in order"
  fi
  [ -n "$pw" ] || die "POSTGRES_PASSWORD is not set in $env_file"
  [ -n "$spw" ] || die "SIMULATOR_DB_PASSWORD is not set in $env_file"
  [ -n "$key" ] || die "JANUS_NOISE_KEY is not set in $env_file"
fi
# The passwords go into URLs unescaped: only URL-safe characters (the documented generators).
for v in "$pw" "$spw"; do
  [[ "$v" =~ ^[A-Za-z0-9._~-]{16,}$ ]] || die "a database password has characters that are not URL-safe or is too short"
done
[ "${#spw}" -ge 24 ] || die "the simulator password must have at least 24 characters"

install -d -m 750 -o "$uid" -g "$gid" "$sec"
put() {  # put <name> <value>: write atomically with the final ownership and mode
  local name="$1" tmp
  tmp="$(mktemp "$sec/.tmp.XXXXXX")"
  printf '%s' "$2" > "$tmp"
  chown "${OWNER[$name]}:$gid" "$tmp"
  chmod 440 "$tmp"
  mv -f "$tmp" "$sec/$name"
  log "wrote secrets/$name (uid ${OWNER[$name]}, mode 440)"
}
put postgres_password "$pw"
put database_url "$(url_for janus "$pw")"
put noise_key "$key"
put simulator_db_password "$spw"
put simulator_database_url "$(url_for janus_simulator "$spw")"
check_files || die "the new files did not verify; $env_file left untouched"

if [ "$staging" = 0 ]; then
  # Remove the secret lines in place (same file, so owner and mode stay as they are).
  tmp="$(mktemp)"
  grep -vE "^($(IFS='|'; echo "${ENV_KEYS[*]}"))=" "$env_file" > "$tmp" || true
  cat "$tmp" > "$env_file"
  rm -f "$tmp"
  env_clean || die "secret lines remain in $env_file"
  log "removed the secret lines from $env_file"
fi
log "secrets: ok ($sec)"
