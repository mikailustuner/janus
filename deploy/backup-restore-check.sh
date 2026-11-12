#!/usr/bin/env bash
# Restore a database dump into a throwaway Postgres 16 and report what came back and how long it took
# (deploy/README.md, "Backups"). Runs on the backup machine. Usage: backup-restore-check.sh <file.dump>
# The container has its own name, no published port and no network; it is removed afterwards.
set -euo pipefail
dump="${1:?usage: backup-restore-check.sh <file.dump>}"
[ -f "$dump" ] || { echo "no such file: $dump" >&2; exit 1; }
name="janus-restore-check-$$"
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT

docker run -d --name "$name" --network none -e POSTGRES_PASSWORD="$(head -c 18 /dev/urandom | base64)" \
  -e POSTGRES_DB=janus postgres:16.15-bookworm >/dev/null
for _ in $(seq 60); do
  docker exec "$name" pg_isready -U postgres -d janus -q 2>/dev/null && break
  sleep 1
done
# The init script restarts the server once; wait until it accepts queries.
until docker exec "$name" psql -U postgres -d janus -Atqc 'select 1' >/dev/null 2>&1; do sleep 1; done

start="$(date +%s)"
docker exec -i "$name" pg_restore -U postgres -d janus --no-owner --no-privileges --exit-on-error < "$dump"
seconds=$(( $(date +%s) - start ))

q() { docker exec "$name" psql -U postgres -d janus -Atqc "$1"; }
echo "dump:      $dump ($(du -h "$dump" | cut -f1))"
echo "restored:  ${seconds}s"
echo "tables:    $(q "select count(*) from information_schema.tables where table_schema = 'public'")"
echo "migration: $(q 'select version_num from alembic_version')"
echo "size:      $(q "select pg_size_pretty(pg_database_size('janus'))")"
echo "largest tables (rows):"
q "select relname || ' ' || n_live_tup from pg_stat_user_tables order by n_live_tup desc limit 5" \
  | sed 's/^/  /'
