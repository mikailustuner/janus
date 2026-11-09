"""Check C1 of the deploy spec on the resolved compose file (stdlib only).

Usage: docker compose -f deploy/compose.yml config --format json | python3 deploy/check_compose.py
Fails when a service publishes a port, uses the host network, runs privileged, adds capabilities,
mounts the Docker socket or a writable host path, or lacks the hardening of design DP4.
"""

from __future__ import annotations

import json
import sys

NETWORKS = {
    "postgres": {"internal"},
    "migrate": {"internal"},
    "api": {"internal"},
    "web": {"internal", "edge"},
    "cloudflared": {"edge"},
}
READ_ONLY_MOUNTS = {"api": {"/data"}, "cloudflared": {"/etc/cloudflared"}}


def problems(config: dict[str, object]) -> list[str]:
    out: list[str] = []
    if config.get("name") != "janus-public":
        out.append("project name must be janus-public (never the development project `janus`)")
    services = config.get("services")
    assert isinstance(services, dict)
    if set(services) != set(NETWORKS):
        out.append(f"services must be exactly {sorted(NETWORKS)}, got {sorted(services)}")
    for name, svc in services.items():
        assert isinstance(svc, dict)

        def bad(msg: str, name: str = name) -> None:
            out.append(f"{name}: {msg}")

        if svc.get("ports"):
            bad("publishes ports")
        if svc.get("network_mode"):
            bad("sets network_mode")
        if svc.get("privileged"):
            bad("is privileged")
        if svc.get("cap_add"):
            bad("adds capabilities")
        if svc.get("cap_drop") != ["ALL"]:
            bad("must drop ALL capabilities")
        if svc.get("read_only") is not True:
            bad("root file system must be read-only")
        if "no-new-privileges:true" not in (svc.get("security_opt") or []):
            bad("needs no-new-privileges")
        user = str(svc.get("user") or "")
        if not user or user.split(":")[0] in {"0", "root"}:
            bad("must run as a non-root user")
        if not svc.get("mem_limit") or not svc.get("cpus"):
            bad("needs mem_limit and cpus")
        nets = set((svc.get("networks") or {}).keys())
        if name in NETWORKS and nets != NETWORKS[name]:
            bad(f"networks must be {sorted(NETWORKS[name])}, got {sorted(nets)}")
        for vol in svc.get("volumes") or []:
            assert isinstance(vol, dict)
            if vol.get("type") == "volume":
                continue
            target = vol.get("target")
            if "docker.sock" in str(vol.get("source")):
                bad("mounts the Docker socket")
            if target not in READ_ONLY_MOUNTS.get(name, set()):
                bad(f"unexpected host mount {target}")
            elif not vol.get("read_only"):
                bad(f"host mount {target} must be read-only")
    nets_cfg = config.get("networks")
    assert isinstance(nets_cfg, dict)
    internal = nets_cfg.get("internal")
    if not isinstance(internal, dict) or internal.get("internal") is not True:
        out.append("network internal must have internal: true")
    return out


def main() -> int:
    found = problems(json.load(sys.stdin))
    for p in found:
        print(f"compose check: {p}", file=sys.stderr)
    if not found:
        print("compose check: ok")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
