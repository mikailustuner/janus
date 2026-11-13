"""Check C1 of the deploy spec on the resolved compose file (stdlib only).

Usage: docker compose -f deploy/compose.yml config --format json | python3 deploy/check_compose.py
Fails when a service publishes a port, uses the host network, runs privileged, adds capabilities,
mounts the Docker socket or a writable host path, lacks the hardening of design DP4, or exceeds
the resource caps of Req 7.4 (owner decision 2026-11-09): long-running services together at most
4.5 CPUs and 6 GB, the simulator at most 2.0 CPUs and 1.5 GB. Secrets are files, never environment
values: no environment entry looks like a password, key or credentialed URL, every service mounts
exactly the secrets it needs, and each is declared with a file under `secrets:`.
The project is `janus-public` (production) or `janus-staging` (staging.sh), never `janus`.
"""

from __future__ import annotations

import json
import re
import sys

NETWORKS = {
    "postgres": {"internal"},
    "migrate": {"internal"},
    "api": {"internal"},
    "simulator": {"internal"},
    "web": {"internal", "edge"},
    "cloudflared": {"edge"},
}
PROJECTS = {"janus-public", "janus-staging"}
SECRETS = {
    "postgres": {"postgres_password"},
    "migrate": {"database_url", "simulator_db_password"},
    "api": {"database_url", "noise_key"},
    "simulator": {"simulator_database_url"},
}
_SECRET_KEY = re.compile(r"PASSWORD|SECRET|TOKEN|KEY", re.IGNORECASE)
_URL_CREDENTIALS = re.compile(r"://[^/\s:@]+:[^/\s@]+@")
READ_ONLY_MOUNTS = {"api": {"/data"}, "cloudflared": {"/etc/cloudflared"}}
GIB = 1024**3
TOTAL_CPUS = 4.5
TOTAL_MEMORY = 6 * GIB
SIMULATOR_CPUS = 2.0
SIMULATOR_MEMORY = 1.5 * GIB
_UNITS = {"b": 1, "k": 1024, "m": 1024**2, "g": GIB}


def memory_bytes(value: object) -> int:
    """`mem_limit` as compose resolves it (bytes, as a number or a string) or with a unit."""
    text = str(value).strip().lower()
    if text.isdigit():
        return int(text)
    unit = text[-1]
    if unit in _UNITS and text[:-1].replace(".", "", 1).isdigit():
        return int(float(text[:-1]) * _UNITS[unit])
    raise ValueError(f"unreadable mem_limit {value!r}")


def resource_problems(services: dict[str, dict[str, object]]) -> list[str]:
    """Req 7.4: caps are ceilings, not reservations; one-shot services (profiles) not counted."""
    out: list[str] = []
    running = {n: s for n, s in services.items() if not s.get("profiles")}
    try:
        cpus = sum(float(str(s.get("cpus") or 0)) for s in running.values())
        mem = sum(memory_bytes(s.get("mem_limit") or 0) for s in running.values())
    except ValueError as exc:
        return [str(exc)]
    if cpus > TOTAL_CPUS:
        out.append(f"services together cap {cpus:g} CPUs, more than {TOTAL_CPUS:g}")
    if mem > TOTAL_MEMORY:
        out.append(f"services together cap {mem / GIB:.2f} GB, more than {TOTAL_MEMORY / GIB:g}")
    sim = services.get("simulator")
    if sim is not None:
        if int(str(sim.get("pids_limit") or 0)) not in range(1, 129):
            out.append("simulator: pids_limit must be set and at most 128")
        tmpfs = [str(t) for t in sim.get("tmpfs") or []]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        if not tmpfs or not all(
            "size=" in t and "noexec" in t and "nosuid" in t and "nodev" in t for t in tmpfs
        ):
            out.append("simulator: tmpfs must be sized and noexec, nosuid, nodev")
        if float(str(sim.get("cpus") or 0)) > SIMULATOR_CPUS:
            out.append(f"simulator: more than {SIMULATOR_CPUS:g} CPUs")
        if memory_bytes(sim.get("mem_limit") or 0) > SIMULATOR_MEMORY:
            out.append("simulator: more than 1.5 GB")
    return out


def secret_problems(config: dict[str, object]) -> list[str]:
    """Secrets only as mounted files: nothing secret-looking in `environment:`, exact mounts."""
    out: list[str] = []
    declared = config.get("secrets") or {}
    assert isinstance(declared, dict)
    for sname, spec in declared.items():  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(spec, dict) or not spec.get("file"):  # pyright: ignore[reportUnknownMemberType]
            out.append(f"secret {sname} must be a file")
    services = config.get("services")
    assert isinstance(services, dict)
    for name, svc in services.items():
        assert isinstance(svc, dict)
        for key, value in (svc.get("environment") or {}).items():
            text = str(value or "")
            if key.endswith("_FILE") or not text:
                continue  # a path to a mounted secret, or an explicitly empty setting
            if _SECRET_KEY.search(key):
                out.append(f"{name}: environment {key} has a value (secrets must be files)")
            elif _URL_CREDENTIALS.search(text):
                out.append(f"{name}: environment {key} holds a URL with credentials")
        used: set[str] = set()
        for ref in svc.get("secrets") or []:
            source = ref.get("source") if isinstance(ref, dict) else ref
            used.add(str(source))
            if source not in declared:
                out.append(f"{name}: secret {source} is not declared under secrets:")
        if used != SECRETS.get(name, set()):
            out.append(
                f"{name}: secrets must be {sorted(SECRETS.get(name, set()))}, got {sorted(used)}"
            )
    return out


def problems(config: dict[str, object]) -> list[str]:
    out: list[str] = []
    project = config.get("name")
    if project not in PROJECTS:
        out.append(
            "project name must be janus-public or janus-staging (not the development project `janus`)"
        )
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
    out.extend(secret_problems(config))
    out.extend(resource_problems(services))  # pyright: ignore[reportUnknownArgumentType]
    nets_cfg = config.get("networks")
    assert isinstance(nets_cfg, dict)
    internal = nets_cfg.get("internal")
    if not isinstance(internal, dict) or internal.get("internal") is not True:
        out.append("network internal must have internal: true")
    for net in ("internal", "edge"):
        spec = nets_cfg.get(net)
        if isinstance(spec, dict) and spec.get("name") != f"{project}-{net}":
            out.append(f"network {net} must be named {project}-{net}")
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
