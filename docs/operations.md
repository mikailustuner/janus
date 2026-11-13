# Operations

Service level objectives, alerts and what to do when one fires. Host-specific details (names, addresses, paths)
are not in this repository. Deployment and backups: [deploy/README.md](../deploy/README.md); metrics:
[metrics.md](metrics.md); security: [security.md](security.md).

## Service level objectives

| Objective    | Indicator                                                                                                                                                | Target (30 days)  |
| ------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| Availability | Share of API requests that do not end in a 5xx answer                                                                                                    | ≥ 99.5 %          |
| Latency      | Share of API requests that finish within 500 ms (p95 ≤ 500 ms)                                                                                           | ≥ 95 %            |
| Reachability | External check of the home page, `/api/health` and the model kit API every 15 minutes from outside the server's network (`.github/workflows/uptime.yml`) | every check green |

The error budget is what the targets leave: 0.5 % of requests may fail and 5 % may be slow in 30 days. The
"Janus SLO" dashboard shows both objectives, the budget left and the burn rate (1 = the budget is used up exactly
in 30 days). Rules: `deploy/monitoring/slo.rules.yml`; dashboard: `deploy/monitoring/janus-slo.dashboard.json`.

## Performance budgets

`.github/workflows/perf.yml` runs Lighthouse (simulated slow phone) on the production build: performance,
accessibility and SEO at least 0.90 on `/en/about` and `/en/privacy`. The home page is at 0.87 today (largest paint
3.9 s, the hero image painted about 2.6 s after it has loaded, behind the page's script work); its target of 0.90 is
a warning and 0.85 is the hard floor until that is fixed. Measured on 2026-11-13 on a desktop machine, the same
build scores 0.93 (three runs; largest paint 3.0 s, the emergency line), so the CI figure depends on the runner. Two
causes were ruled out: loading the hero eagerly did not help, and rendering the shell without its Suspense boundary
made it worse (0.86, largest paint 4.0 s on the hero image), so the boundary stays. A small k6 load check of the public API runs weekly
(`deploy/load/smoke.js`; p95 of reads below 500 ms).

## Alerts

Alerts go to a private push channel. A failed GitHub workflow (external uptime, nightly tests, security scans,
weekly reproduction) sends GitHub's failed-workflow notification.

| Alert                                                  | Meaning                                                   | Runbook                                   |
| ------------------------------------------------------ | --------------------------------------------------------- | ----------------------------------------- |
| `JanusAvailabilityBudgetFastBurn`                      | More than 7.2 % of requests fail (1 h and 5 min)          | [5xx](#many-5xx-answers)                  |
| `JanusAvailabilityBudgetSlowBurn`                      | More than 3 % fail (6 h and 30 min)                       | [5xx](#many-5xx-answers)                  |
| `JanusLatencyBudgetFastBurn`, `…SlowBurn`              | Many requests take longer than 500 ms                     | [slow](#slow-answers)                     |
| `JanusApi5xx`                                          | More than 5 % 5xx over 10 min                             | [5xx](#many-5xx-answers)                  |
| `JanusPushMissing`                                     | No metrics from the server for 10 min                     | [server unreachable](#server-unreachable) |
| `JanusDiskHigh`                                        | Server disk above 85 %                                    | [disk](#disk-full)                        |
| `JanusMemoryHigh`                                      | Server memory above 90 %                                  | [slow](#slow-answers)                     |
| `JanusSimulationQueueStuck`                            | A simulation job has waited more than 5 min               | [queue](#simulation-queue-stuck)          |
| `JanusDatabaseBackupOverdue`, `JanusDataBackupOverdue` | No successful backup for 30 h (database) or 8 days (data) | [backup](#backup-overdue)                 |
| `JanusBackupMachineUnreachable`                        | The backup machine has not answered for 36 h              | [backup](#backup-overdue)                 |

## Runbook

Every step that changes the server is followed by `deploy/smoke.sh` against the public address.

### Server unreachable

1. Check the external uptime workflow and the CDN status page: is only the monitoring push missing, or the site too?
2. If SSH times out from everywhere after a reboot, suspect the host firewall: a rule set loaded at boot may drop
   SSH. Reach the machine through the cloud provider's serial console, add an accept rule for SSH after the
   `established,related` rule, reload, and keep a dated copy of the old file. Never create paid rescue resources.
3. If the machine answers but the site does not: `docker compose ps` in the stack directory, then
   `docker compose up -d --wait`; check the tunnel container's log for authentication errors.

### Many 5xx answers

1. Grafana "Janus app" → requests by status class and by route: one route or all?
2. API container log (structured, no request bodies): look for the error code.
3. If it started with a release: roll back with `deploy/rollback.sh` (previous tag), then investigate on a branch.
4. If the database is the cause (pool waiting, connection errors): `docker compose restart postgres`, then the API.

### Release flow

1. Merge to the release branch; CI is green.
2. On the server: `deploy/deploy.sh <commit>`. It builds the images, then runs `deploy/staging.sh <tag>`: the new
   release on a throw-away `janus-staging` stack (own networks, own volume, own secrets, no tunnel) with a fresh
   restore of the production database, the migrations, the isolation check and the smoke test. The staging stack
   and its volume are removed afterwards in every case.
3. If staging fails, `deploy.sh` stops with "staging failed; production unchanged": nothing of production was
   touched. Read the log, fix on a branch, release again.
4. Otherwise it migrates the production database, swaps the containers, checks them, and rolls back by itself when a
   check fails. Then run `deploy/smoke.sh https://janusmeds.org`.

Staging needs free disk for a copy of the database and memory for a second stack for a few minutes.

### Slow answers

1. "Janus app" → p95 by route; "System overview" → CPU, memory, disk I/O.
2. A burst of simulations is expected to queue, not to slow other routes; if it does, lower the queue limit.
3. Memory pressure: check which container grows; restart it and open an issue with the graph.

### Disk full

1. `df -h`, then `docker system df`: old images are the usual cause. `deploy.sh` keeps the last three releases;
   remove older images and build cache with `docker image prune` and `docker builder prune` (never volumes).
2. Old pipeline runs under the data directory: keep each dataset's `current` run and the previous one.

### Simulation queue stuck

1. `docker compose logs simulator` for model errors; `docker compose restart simulator`.
2. If jobs keep failing, set `JANUS_SIMULATION: "off"` in the compose file and release; the in-browser explorer
   keeps working.

### Roll back a release

`deploy/rollback.sh [tag]` restarts the previous images (tags in `releases.log`). A release that added a migration
has a downgrade; read it before rolling back across it. Releases that changed the compose file need the old file
first (`deploy/README.md`).

### Restore from backup

1. On the backup machine pick a dump (`db/janus-<time>.dump`) and check it with `backup-restore-check.sh`.
2. Stop `api`, `web` and `simulator`; restore with
   `pg_restore -U janus -d janus --clean --if-exists` inside the Postgres container; copy a data snapshot back with
   rsync if the data directory was lost.
3. Start the stack and run `deploy/smoke.sh`. A test restore took about 3 minutes for the 1.2 GB database.

### Backup overdue

1. On the backup machine: `systemctl --user list-timers 'janus-backup*'` and
   `journalctl --user -u 'janus-backup@*' -n 50`.
2. A missed run catches up at the next start (`Persistent=true`); start it by hand with
   `systemctl --user start janus-backup@db.service`.
3. If the pull is refused: the restricted key on the server must still name `backup-serve.sh` and the backup
   machine's private address.
