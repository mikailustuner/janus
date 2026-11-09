# Deploy

How the public Janus at <https://janusmeds.org> runs. Specification: `.kiro/specs/deploy/`.
Host-specific values (server, addresses, paths, private network) are deliberately not in this
repository; the scripts read them on the server.

## Shape
```
browser ─HTTPS─▶ Cloudflare ─tunnel (outbound only)─▶ cloudflared ─▶ web ─/api/*─▶ api ─▶ postgres
                                                      [edge]          [edge+internal]  [internal, no route out]
```
- No port is published on the server; the tunnel connects outwards.
- `api` and `postgres` sit on a Docker network with `internal: true`.
- Host firewall rules (`firewall.sh`, run by the owner) stop every Janus container from opening
  connections to the server itself, to private address ranges and to the cloud metadata service.
- Every container: non-root, read-only root file system, no capabilities, `no-new-privileges`,
  memory and CPU limits, automatic restart.
- Donations and the doctor outcome loop are **off**: no health data is stored on the server.

## Files
| File | Purpose |
|---|---|
| `compose.yml` | The stack (copied to `STACK_DIR`) |
| `env.example` | Template of `STACK_DIR/.env` (mode 600, secrets generated on the server) |
| `cloudflared.config.yml.example` | Tunnel ingress: `janusmeds.org → web:3000`, everything else 404 |
| `check_compose.py` | CI check of the hardening rules on the resolved compose file |
| `deploy.sh <commit>` / `rollback.sh [tag]` | Build on the server, migrate, swap, check; roll back on failure |
| `verify-isolation.sh` | Probes from each Janus network: server ports, other networks, metadata must be closed |
| `smoke.sh internal\|<url> [tag]` | Pages in two languages, public API routes, security headers, deployed commit |
| `firewall.sh` + `janus-firewall.service` | Host rules (owner, sudo), re-applied at boot |
| `sync-data.sh` | Developer machine → server copy of the built data runs (never TİTCK) |
| `titck-refresh.sh` + `janus-titck.{service,timer}` | Weekly TİTCK fetch on the server, then `load-data.sh` |
| `load-data.sh` | Evidence, cascade and resolution loaders into the database |
| `pipelines.Dockerfile` | Image for pipeline jobs that must run on the server |

## Check locally
```bash
POSTGRES_PASSWORD=x JANUS_NOISE_KEY=x JANUS_UID=1000 JANUS_GID=1000 JANUS_TAG=test \
  docker compose -f deploy/compose.yml --profile migrate config --format json \
  | python3 deploy/check_compose.py
```
