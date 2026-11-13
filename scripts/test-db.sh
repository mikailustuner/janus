#!/usr/bin/env bash
# Run a command against a throwaway PostgreSQL 16 so the database tests also run locally.
# Usage: scripts/test-db.sh [command ...]   (default: the API test suite)
# The server has its own container name, data in memory (tmpfs), a port Docker picks on 127.0.0.1,
# the same logging settings as production, and is removed afterwards. It never touches the
# development database container.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
name="janus-testdb-$$"
password="$(head -c 18 /dev/urandom | base64 | tr -d '/+=')"
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT

docker run -d --name "$name" -p 127.0.0.1::5432 --tmpfs /var/lib/postgresql/data \
  -e POSTGRES_DB=janus_test -e POSTGRES_USER=janus -e POSTGRES_PASSWORD="$password" \
  postgres:16.15-bookworm postgres -c log_error_verbosity=terse -c log_min_error_statement=panic \
  -c log_statement=none -c log_min_duration_statement=-1 -c fsync=off >/dev/null
port="$(docker port "$name" 5432/tcp | head -n 1 | sed 's/.*://')"
# The image's init script restarts the server once; wait until it answers queries.
for _ in $(seq 60); do
  docker exec "$name" psql -U janus -d janus_test -Atqc 'select 1' >/dev/null 2>&1 && break
  sleep 1
done
export JANUS_TEST_DATABASE_URL="postgresql://janus:$password@127.0.0.1:$port/janus_test"

if [ "$#" -eq 0 ]; then
  set -- bash -c 'cd apps/api && uv run pytest'
fi
"$@"
