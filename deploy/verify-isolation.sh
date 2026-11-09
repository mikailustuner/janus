#!/usr/bin/env bash
# Prove deploy Req 2.3 from inside each Janus network (design §4, check C2).
# Probes run in throw-away containers of the API image (Python sockets), so the app images need no
# extra tools. Targets are read at run time, never committed:
#   - every TCP port the server listens on (`ss -tln`), at the server's own addresses and at each
#     Janus network's gateway;
#   - the gateway of every other Docker network;
#   - the cloud metadata service;
#   - optional extra addresses in STACK_DIR/isolation-probes ("host port" per line), e.g. a
#     machine of the owner's private network.
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
tag="${JANUS_TAG:-$(current_tag)}"
image="janus-api:$tag"

ports="$(ss -tlnH | awk '{print $4}' | sed -E 's/.*:([0-9]+)$/\1/' | sort -un | tr '\n' ' ')"
host_ips="$(hostname -I | tr ' ' '\n' | grep -E '^[0-9.]+$' | tr '\n' ' ')"
gw() { docker network inspect "$1" --format '{{range .IPAM.Config}}{{.Gateway}}{{end}}'; }
others=""
for n in $(docker network ls --format '{{.Name}}' | grep -vE '^(janus-public-|bridge$|host$|none$)'); do
  g="$(gw "$n")"; [ -n "$g" ] && others+="$g "
done
extra=""
[ -f "$STACK_DIR/isolation-probes" ] && extra="$(grep -vE '^\s*(#|$)' "$STACK_DIR/isolation-probes" | tr '\n' ';')"

probe() {  # probe <network> <expect: open|closed> <host:port>...
  local net="$1" expect="$2"; shift 2
  # -i is required: the probe program arrives on stdin (without it Python runs an empty script and
  # every probe "passes"; caught by the positive control in the task 2 rehearsal).
  docker run -i --rm --network "$net" --user 10001 --read-only --cap-drop ALL \
    --security-opt no-new-privileges:true --entrypoint python "$image" - "$expect" "$@" <<'PY'
import socket, sys
from concurrent.futures import ThreadPoolExecutor

expect, targets = sys.argv[1], sys.argv[2:]


def state(t: str) -> str:
    host, port = t.rsplit(":", 1)
    try:
        socket.create_connection((host, int(port)), timeout=2).close()
        return "open"
    except OSError:
        return "closed"


# Dropped packets time out, so probe in parallel (hundreds of targets in a few seconds).
with ThreadPoolExecutor(64) as pool:
    results = list(zip(targets, pool.map(state, targets)))
bad = [(t, got) for t, got in results if got != expect]
print(f"  probed {len(results)} targets, {len(bad)} unexpected", file=sys.stderr)
if not results:
    sys.exit(2)
for t, got in bad:
    print(f"  UNEXPECTED {got}: {t}")
sys.exit(1 if bad else 0)
PY
}

fail=0
for net in janus-public-edge janus-public-internal; do
  g="$(gw "$net")"
  closed=()
  for p in $ports; do
    for ip in $g $host_ips; do closed+=("$ip:$p"); done
  done
  for o in $others; do for p in $ports; do closed+=("$o:$p"); done; done
  closed+=("169.254.169.254:80")
  IFS=';' read -ra ex <<<"$extra"
  for e in "${ex[@]}"; do [ -n "$e" ] && closed+=("${e// /:}"); done
  log "$net: ${#closed[@]} targets that must be closed"
  probe "$net" closed "${closed[@]}" || fail=1
done
log "expected paths"
probe janus-public-internal open api:8000 postgres:5432 || fail=1
probe janus-public-edge open web:3000 region1.v2.argotunnel.com:7844 || fail=1
probe janus-public-internal closed 1.1.1.1:443 || fail=1
probe janus-public-edge closed api:8000 postgres:5432 || fail=1
if [ "$fail" = 0 ]; then log "isolation: ok"; else die "isolation: FAILED"; fi
