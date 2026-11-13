#!/usr/bin/env bash
# Host firewall rules that keep every Janus container away from the server itself, private address
# ranges and the cloud metadata service (deploy Req 2.3, design §4). Run by the owner with sudo;
# idempotent (rules carry the comment "janus-isolation" and are replaced on each run).
#   sudo deploy/firewall.sh          apply
#   sudo deploy/firewall.sh --remove remove
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo" >&2; exit 1; }
TAG="janus-isolation"
# edge, internal, jobs (compose.yml); then the ephemeral staging stack's edge and internal networks
# (staging.sh, `janus-staging`): staging containers get the same isolation as production.
NETS=(172.31.250.0/24 172.31.251.0/24 172.31.252.0/24 172.31.253.0/24 172.31.254.0/24)
BLOCK=(10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 169.254.0.0/16)

remove() {
  for chain in INPUT DOCKER-USER; do
    while read -r rule; do
      # shellcheck disable=SC2086  # the rule's own words, from `iptables -S` (no spaces inside)
      [ -n "$rule" ] && iptables ${rule/-A/-D}
    done < <(iptables -S "$chain" 2>/dev/null | grep -- "--comment $TAG" || true)
  done
}
remove
[ "${1:-}" = --remove ] && { echo "janus isolation rules removed"; exit 0; }

iptables -L DOCKER-USER >/dev/null 2>&1 || { echo "DOCKER-USER chain missing: is Docker running?" >&2; exit 1; }
for net in "${NETS[@]}"; do
  # No new connection from a Janus container to the server itself (any of its addresses).
  iptables -I INPUT 1 -s "$net" -m conntrack --ctstate NEW -m comment --comment "$TAG" -j DROP
  # Forwarded traffic: drop private, shared-address and metadata destinations...
  for dst in "${BLOCK[@]}"; do
    iptables -I DOCKER-USER 1 -s "$net" -d "$dst" -m comment --comment "$TAG" -j DROP
  done
  # ...except traffic inside the container's own network (inserted last, so it is checked first).
  iptables -I DOCKER-USER 1 -s "$net" -d "$net" -m comment --comment "$TAG" -j RETURN
done
if docker info --format '{{.IPv6}}' 2>/dev/null | grep -qi true; then
  echo "warning: Docker IPv6 is on; these rules cover IPv4 only (design §4)" >&2
fi
echo "janus isolation rules applied"
