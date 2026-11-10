# Deploy

How the public Janus at <https://janusmeds.org> runs. Specification: `.kiro/specs/deploy/`.
Host-specific values (server, addresses, paths, private network) are deliberately not in this
repository; the scripts read them on the server.

## Shape
```
browser ─HTTPS─▶ Cloudflare ─tunnel (outbound only)─▶ cloudflared ─▶ web ─/api/*─▶ api ─▶ postgres ◀─ simulator
                                                      [edge]          [edge+internal]  [internal, no route out]
```
- No port is published on the server; the tunnel connects outwards.
- `api`, `postgres` and `simulator` sit on a Docker network with `internal: true`.
- `simulator` (`.kiro/specs/simulation-service/`) runs queued model runs: its own image with pinned
  R 4.6.1 + httk 2.7.4 (`apps/api/simulator.Dockerfile`), two worker slots, 30 s per job, no route out;
  it reads and writes only the `simulation_jobs` queue in Postgres.
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
| `titck-refresh.sh` + `janus-titck.{service,timer}` | Weekly TİTCK fetch on the server, the open Canadian and Italian product lists (`ca_dpd`, `eu_it_aifa`), then `load-data.sh`; then the FDA recall records (`us_recalls`) and the data-quality report |
| `load-data.sh` | Evidence, cascade and resolution loaders into the database |
| `pipelines.Dockerfile` | Image for pipeline jobs that must run on the server |

## Check locally
```bash
POSTGRES_PASSWORD=x JANUS_NOISE_KEY=x SIMULATOR_DB_PASSWORD=x JANUS_UID=1000 JANUS_GID=1000 JANUS_TAG=test \
  docker compose -f deploy/compose.yml --profile migrate config --format json \
  | python3 deploy/check_compose.py
```

## Simulation service (the release that adds it)
Owner decision 2026-11-09: resource caps raised (deploy Req 7.4): long-running services at most 4.5 CPU and
6 GB in total, the simulator at most 2.0 CPU and 1.5 GB; `check_compose.py` enforces both.

1. `deploy.sh <commit>` also builds `janus-simulator:<tag>` natively on the server. The first build installs
   the R packages from the dated CRAN snapshot (compiled from source where no arm64 binary exists; allow
   10-30 minutes); later builds are cached. Nothing is installed on the host itself.
2. The `migrate` step applies Alembic revision `0014_simulation_jobs` (forward-only; its downgrade drops the
   table).
3. No firewall or subnet change: the simulator joins the existing internal network, which `firewall.sh`
   already covers. `verify-isolation.sh` also probes from inside the running simulator (internet, R package
   mirrors, metadata service and host ports closed; only postgres open).
4. `smoke.sh` runs one small compartmental job and checks that the repeat is answered from the cache.
5. Cloudflare (owner, dashboard → Security → WAF → Rate limiting rules): expression
   `(http.request.uri.path wildcard "/api/simulate*" and http.request.method eq "POST")`, counted per IP,
   5 requests per 10 seconds, action Block for 10 seconds. The Free plan has one rule: keep the `/api/*` rule
   and rely on the in-app limits, or replace it with this one; with more rules, add both.
8. Before the first deploy of this release, add `SIMULATOR_DB_PASSWORD` to `STACK_DIR/.env` (see
   `env.example`). `deploy.sh` gives the worker's own database role (`janus_simulator`: read, update and delete
   on the queue table only) its login after the migrations, with `python -m janus.simulation.dbrole`.
9. The api has `JANUS_BEHIND_CLOUDFLARE: "on"`: rate limits count Cloudflare's `CF-Connecting-IP` (IPv6 per /64).
6. Rolling back across this release: the older release has no simulator, so restore its compose file first
   (`git -C src show <old-commit>:deploy/compose.yml > compose.yml`), then run `rollback.sh <old-tag>`; it
   refuses while an image of the tag is missing.
7. `JANUS_SIMULATION: "on"` of the api in `compose.yml` switches server runs on; `off` stops accepting
   them (the in-browser explorer keeps working).

## Releases that change the deploy scripts
`deploy.sh` runs from the `src/` checkout and checks out the new commit while it runs, so a release that
changes `deploy.sh` itself is executed by the **old** script. Run `deploy.sh <commit>` a second time for such
a release (the second run uses the new script; builds are cached).
