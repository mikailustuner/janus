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

| File                                                             | Purpose                                                                                                                                                                                                                                                                         |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `compose.yml`                                                    | The stack (copied to `STACK_DIR`)                                                                                                                                                                                                                                               |
| `env.example`                                                    | Template of `STACK_DIR/.env` (mode 600, settings only; secrets are files, see "Secrets")                                                                                                                                                                                                        |
| `cloudflared.config.yml.example`                                 | Tunnel ingress: `janusmeds.org → web:3000`, everything else 404                                                                                                                                                                                                                 |
| `secrets-setup.sh`                                               | Secrets as files under `STACK_DIR/secrets/` (owner, sudo); `--check`, `--staging`  |
| `staging.sh <tag>` / `staging-setup.sh`                          | Ephemeral staging check before every production swap; its one-time setup  |
| `check_compose.py`                                               | CI check of the hardening rules on the resolved compose file                                                                                                                                                                                                                    |
| `deploy.sh <commit>` / `rollback.sh [tag]`                       | Build on the server, migrate, swap, check; roll back on failure                                                                                                                                                                                                                 |
| `verify-isolation.sh`                                            | Probes from each Janus network: server ports, other networks, metadata must be closed                                                                                                                                                                                           |
| `smoke.sh internal\|<url> [tag]`                                 | Pages in two languages, public API routes, security headers, deployed commit                                                                                                                                                                                                    |
| `firewall.sh` + `janus-firewall.service`                         | Host rules (owner, sudo), re-applied at boot                                                                                                                                                                                                                                    |
| `sync-data.sh`                                                   | Developer machine → server copy of the built data runs (never TİTCK)                                                                                                                                                                                                            |
| `titck-refresh.sh` + `janus-titck.{service,timer}`               | Weekly TİTCK fetch on the server, the open Canadian and Italian product lists (`ca_dpd`, `eu_it_aifa`), then `load-data.sh`; then the FDA recall records (`us_recalls`), the model kit evidence (`modelkit_evidence`, seed files mounted read-only) and the data-quality report |
| `load-data.sh`                                                   | Evidence, cascade and resolution loaders into the database                                                                                                                                                                                                                      |
| `pipelines.Dockerfile`                                           | Image for pipeline jobs that must run on the server                                                                                                                                                                                                                             |
| `backup-serve.sh` / `backup-pull.sh` / `backup-restore-check.sh` | Backups pulled by a separate machine; see "Backups"                                                                                                                                                                                                                             |
| `janus-backup@.service` + `janus-backup-{db,data}.timer`         | Backup machine's user units: daily dump, weekly data snapshot                                                                                                                                                                                                                   |

## Secrets

No secret is an environment value (`docker inspect` would show it). Compose mounts files from
`STACK_DIR/secrets/` at `/run/secrets/<name>`, and each service gets only what it needs:

| File                     | Mounted into | Read as                                  |
| ------------------------ | ------------ | ---------------------------------------- |
| `postgres_password`      | postgres     | `POSTGRES_PASSWORD_FILE`                 |
| `database_url`           | api, migrate | `DATABASE_URL_FILE`                      |
| `noise_key`              | api          | `JANUS_NOISE_KEY_FILE`                   |
| `simulator_db_password`  | migrate      | `SIMULATOR_DB_PASSWORD_FILE` (role step) |
| `simulator_database_url` | simulator    | `DATABASE_URL_FILE`                      |

The API accepts `NAME_FILE` (path of a file; one trailing newline is removed) for `DATABASE_URL`,
`JANUS_NOISE_KEY`, `JANUS_NOTE_KEYS` and `SIMULATOR_DB_PASSWORD`; setting both forms, or naming a missing or
unreadable file, stops the process with the variable's name and never the value.

Plain compose bind-mounts each file with its host permissions, so `secrets-setup.sh` makes each file owned by the
uid of the container user that reads it (postgres 999, api and migrate 10001, simulator 10002), group = the deploy
user's group, mode 0440: the container user reads it, and the deploy user's scripts (`load-data.sh`, `staging.sh`)
read it through the group. `load-data.sh` mounts `database_url` into its throw-away container and passes
`DATABASE_URL_FILE`; no secret is ever on a command line.

## Setup order on a server

1. `.env` of the stack directory with `JANUS_UID`, `JANUS_GID` (and, once, the three secret lines of an older
   install or of a new one, generated as in `env.example`).
2. `sudo deploy/secrets-setup.sh`: writes `secrets/*` with the ownership above, builds the two database URLs,
   removes the secret lines from `.env` only after the files verify. Idempotent; `deploy/secrets-setup.sh --check`
   verifies without changing anything.
3. `sudo deploy/firewall.sh`: now also covers the staging networks.
4. `deploy/staging-setup.sh` (deploy user), then `sudo deploy/secrets-setup.sh --staging` (the staging secrets are
   new random values, never the production ones).
5. `deploy/deploy.sh <commit>`.

## Staging (before every production swap)

`deploy.sh` runs `staging.sh <tag>` after building the images and before it touches production (before the
migrations), when the staging directory exists (`STAGING_DIR`, default `STACK_DIR/../janus-staging`). If it
fails, `deploy.sh` stops with "staging failed; production unchanged".

The staging stack is `compose.yml` again, with `JANUS_STACK=janus-staging` and its own subnets from the staging
directory's `.env` (172.31.253.0/24 edge, 172.31.254.0/24 internal; `firewall.sh` covers both). That directory
holds its own `.env`, its own `secrets/` and a `data` link to the production data directory (mounted read-only by
the api). `staging.sh`: removes any earlier staging containers and volume; starts staging postgres; restores a
fresh `pg_dump -Fc` of the production database into it (`--no-owner --no-privileges`; the simulator role and its
queue grants are recreated as migration 0014 defines them); runs the new release's migrations and the simulator
role step; starts `postgres api simulator web` (no cloudflared: no tunnel); runs `verify-isolation.sh` and
`smoke.sh internal` against it; then removes the stack and its volume, whatever the outcome. It needs disk for a
copy of the database and, for a few minutes, memory and CPU for a second stack.

The compose project name and network names come from `JANUS_STACK` (default `janus-public`), the subnets from
`JANUS_NET_INTERNAL` and `JANUS_NET_EDGE`; with none of them set, the resolved production config is identical to
the one before they existed (`apps/api/tests/test_deploy_compose.py` checks this). `lib.sh` reads `JANUS_STACK`
from the stack's `.env`; the checks use `${JANUS_STACK}-edge` and `${JANUS_STACK}-internal`.

## Check locally

```bash
stack="$(mktemp -d)"; mkdir "$stack/secrets"; cp deploy/compose.yml "$stack/"
for n in postgres_password database_url noise_key simulator_db_password simulator_database_url; do
  echo x > "$stack/secrets/$n"
done
JANUS_UID=1000 JANUS_GID=1000 JANUS_TAG=test \
  docker compose --project-directory "$stack" -f "$stack/compose.yml" --profile migrate config --format json \
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
6. `deploy.sh` gives the worker's own database role (`janus_simulator`: read, update and delete
   on the queue table only) its login after the migrations, with `python -m janus.simulation.dbrole`; its
   password is the secret file `simulator_db_password` (see "Secrets").
7. The api has `JANUS_BEHIND_CLOUDFLARE: "on"`: rate limits count Cloudflare's `CF-Connecting-IP` (IPv6 per /64).
8. Rolling back across this release: the older release has no simulator, so restore its compose file first
   (`git -C src show <old-commit>:deploy/compose.yml > compose.yml`), then run `rollback.sh <old-tag>`; it
   refuses while an image of the tag is missing.
9. `JANUS_SIMULATION: "on"` of the api in `compose.yml` switches server runs on; `off` stops accepting
   them (the in-browser explorer keeps working).

## Metrics (private monitoring)

The api serves Prometheus text format on its own port (9464, `JANUS_METRICS_PORT`), inside the container and
on the internal network only:

- It is a second listener of the api process, not a route of the public app: `/api/metrics` and every
  variant answer 404, and the web app's `/api/*` rewrite always targets the api's public port, so the
  proxy cannot reach it. `smoke.sh` and `verify-isolation.sh` check both; no `ports:` entry exists.
- A collector running on the host with the host network scrapes the api container directly at its address
  on the internal network, then forwards the samples to a private monitoring service. Nothing else
  connects to the port. The host firewall (`firewall.sh`) only blocks new connections that containers open
  towards the host; a connection the host opens towards a container is not affected, so no firewall change
  is needed.
- Labels come from fixed sets only (route templates, HTTP methods, status classes, job states, dataset
  names); no query string, path value, name, code, address or user agent is ever recorded.
- The api runs a single process, so the series are process-wide; do not raise the worker count without
  switching `prometheus_client` to its multi-process mode.

Reference: `docs/metrics.md` (every series, its labels and meaning).

## Backups

A separate machine pulls the backups; the server holds no credential for it, so a compromised server cannot
reach or delete them.

- **Access.** The backup machine has its own key. On the server, `authorized_keys` binds it to
  `command="STACK_DIR/backup-serve.sh",restrict,from="<backup machine>"`. `backup-serve.sh` (installed as a
  copy in `STACK_DIR`, so a release checkout never changes it) answers three requests only: `pg_dump`,
  `releases.log`, and a read-only `rrsync` of `STACK_DIR/data`. Shell, other commands, writes, paths
  outside `data/` and port forwarding are refused. `.env` is never readable.
- **Database.** `backup-pull.sh db` daily: a custom-format `pg_dump`, accepted only if it starts with `PGDMP`
  and `pg_restore --list` reads it; the newest 14 dumps and `releases.log` copies are kept.
- **Data.** `backup-pull.sh data` weekly: a snapshot of `STACK_DIR/data` (build artifacts, `current` links);
  unchanged files are hard links to the previous snapshot; the newest 4 are kept.
- **Restore check.** `backup-restore-check.sh <dump>` restores into a throwaway Postgres 16 container (own
  name, no network, removed afterwards) and prints time, table count, migration and the largest tables.
- **Monitoring.** After each success the pull writes `metrics/janus_backup.prom` (last success per kind);
  `janus-backup-metrics.service` serves that folder read-only on the private network, and the monitoring
  server alerts when a pull is overdue or the machine has not answered for 36 h
  (`deploy/monitoring/backup.rules.yml`).
- **Failure.** A failed pull posts to the private notification service when `NTFY_URL` and `NTFY_TOKEN` are
  set. Timers use `Persistent=true`, so a run missed while the machine was off happens at the next start.
- **External check.** `.github/workflows/uptime.yml` requests the home page, `/api/health` and the model kit
  API every 15 minutes from outside the server's network; a failed run sends GitHub's failed-workflow
  notification.
- **Restore.** Stop `api`, `web` and `simulator`, then
  `docker compose ... exec -T postgres pg_restore -U janus -d janus --clean --if-exists < janus-<time>.dump`;
  copy a data snapshot back with rsync; start the stack and run `smoke.sh`.

## Releases that change the deploy scripts

`deploy.sh` runs from the `src/` checkout and checks out the new commit while it runs, so a release that
changes `deploy.sh` itself is executed by the **old** script. Run `deploy.sh <commit>` a second time for such
a release (the second run uses the new script; builds are cached). The release that introduces `staging.sh` and the
secret files is such a release: set up the secrets first (`sudo deploy/secrets-setup.sh`, then `staging-setup.sh`),
because the old script already installs the new `compose.yml` before it migrates; the staging check runs from the
second run on. `rollback.sh` uses the installed `compose.yml`, so it keeps working. Rolling back to a release whose
compose file still reads secrets from `.env` needs that old file and the old `.env` lines, written back from
`secrets/` by hand.
