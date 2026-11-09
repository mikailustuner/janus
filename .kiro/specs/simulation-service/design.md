# Design: Simulation service

## 1. Overview
```
browser ─ /research/model-explorer ─ in-browser model (src/simulation/pk.ts), no request
browser ─ /research/simulate ─ POST /api/simulate ─▶ web ─▶ api ──(simulation_jobs, Postgres)──▶ simulator
                                 GET /api/simulate/jobs/{id} (poll)        [internal network, no route out]
```
- `apps/api/janus/simulation/`: `allowlist.py` (the allow-list), `schemas.py` (validation, canonical form,
  disclaimer), `compartmental.py` (population Monte Carlo), `execute.py` (child processes, timeout),
  `httk_job.R` (HTTK-Pop run), `queue.py` (Postgres queue), `ratelimit.py`, `router.py`, `worker.py`,
  `parity.py` (fixtures for the browser port).
- Migration `0014_simulation_jobs`. Image `apps/api/simulator.Dockerfile`.
- Web: `src/simulation/` (port, PRNG, explorer model, client), `components/simulation/`.

## 2. Routes
| Route | Answer |
|---|---|
| `GET /simulate/compounds` | allow-list: compounds, virtual populations, dose bounds, scenarios, validation, limits, `server_runs` |
| `POST /simulate` | 202 job (queued or running), 200 job (finished, `cached: true`); 422 `invalid_request` + field names; 429 `queue_full` / `rate_limited` + `Retry-After`; 503 `simulation_unavailable`; 413/415 body policy |
| `GET /simulate/jobs/{id}` | job: state, queue position, result, validation, disclaimer, expiry; 404 `unknown_job`; 422 `invalid_request` (`job_id`); 429 `rate_limited` |
All medical routes (`no-store`, access line only). Every answer of these routes carries `disclaimer`.

Request kinds (strict pydantic, `extra="forbid"`):
- `compartmental`: `compound` (amlodipine, rhein), `population`, `dose_mg`, `interval_h` (null for one dose, else
  one of the compound's intervals: amlodipine 24 h; rhein 12 or 24 h), `doses` (1-14; the schedule plus 48 h must
  fit the 360 h horizon), `samples` (100-2000).
- `httk_population`: `compound` (risperidone, metoclopramide, haloperidol), `samples` (100-1000). Both HTTK-Pop
  age ranges run in one job; the result is the older-to-younger ratio of medians with both bands. Daily dose
  fixed at 1 mg/kg/day (the time machine's relative comparison; no dose input).

## 3. Allow-list and virtual populations (DP-S1, owner decision 2026-11-09)
| Compound | Population | Definition | Source |
|---|---|---|---|
| amlodipine | adult ("young healthy adults") | cited parameters and spreads (the CL spread is a judgement that already covers the older-vs-younger difference) | Faulkner 1986, 12 young volunteers |
| amlodipine | adult_65plus ("older adults") | clearance × 19/25 = 0.76 on top of the same spreads, rest unchanged; 80+ not covered | Abernethy 1990: hypertensive patients, mean age 68, CL 19 vs 25 L/h, half-life 58 vs 42 h (volume about unchanged) |
| rhein | adult ("healthy adults") | cited apparent parameters and spreads, F fixed at 1 (already apparent) | Magnard 1993; no older-adult data verified → no ≥ 65 population |
| httk drugs | adult / adult_65plus | HTTK-Pop virtual individuals, NHANES 2013-2018, ages 20-50 / 65-79 | Ring 2017; HTTK-Pop has no record above 79 (time-machine DP-T10) |
Dose bounds (fixed bounds of the model, not dosing): amlodipine 2.5-10 mg; rhein 9.645-480 mg rhein equivalent
(from a quarter of the validation dose to the Canon scenario's midpoint, whose caveats are shown with it).
Intervals per compound: amlodipine every 24 h only (Faulkner's design); rhein every 12 or 24 h (twice-daily
diacerein). Validation fold errors carry their direction (model lower / higher) and the checked scope; a run
away from the validation dose or with repeated doses is labelled an extrapolation.

## 4. Validation and normalisation (DP-S2, DP-S5)
Strict types (no string numbers, no booleans, finite), id pattern `^[a-z][a-z0-9_]{0,31}$` plus allow-list
membership, bounds from the allow-list, unknown fields → `<unknown>`. A 422 names fields only. The canonical
form (floats at 6 significant digits) plus the allow-list version is hashed (SHA-256) for the cache key.

## 5. Models and execution (DP-S3, DP-S6)
- Compartmental: `simulate()` of `janus.timemachine.pk` over the population spec, repeated doses by
  superposition, horizon = 48 h after the last dose (≤ 360 h; a longer schedule is refused), 385 time points; outputs p5/p50/p95 curves, peak
  band, single-dose AUC band. The browser port reproduces CPython's Mersenne Twister and `gauss`, so it gives
  the same numbers (fixtures `apps/web/src/simulation/parity.fixture.json`).
- httk: `calc_mc_css` (HTTK-Pop, `pbtk`, package defaults) for both age ranges → p5/p50/p95 Css at
  1 mg/kg/day each and the older-to-younger ratio of medians (the result; absolute values failed validation).
- Each job runs in a child process (`python -m janus.simulation.execute` or `Rscript httk_job.R`) in its own
  process group; at 30 s the group is killed. argv is built from allow-list values and integers; no shell; the
  child's environment is reduced to PATH, HOME, TMPDIR, R_LIBS_USER, LANG; stderr is discarded (no free text
  reaches a log). The R script re-checks every argument.

## 6. Queue (DP-S4)
Table `simulation_jobs` (id uuid, input_hash, kind, canonical input ≤ 1 KiB, state, timestamps, expiry, attempts,
result ≤ 256 KiB, error code). No address or request metadata. `submit` and `claim` take one transaction-scoped
advisory lock: queue ≤ 10 queued + running, running ≤ 2 (so even two worker containers cannot exceed it).
`reap` (every 30 s): running past 30 s + 30 s grace → `worker_lost`; queued older than 10 min → `expired`;
rows past expiry deleted (results 24 h, failures 1 h). Postgres was chosen because it is already in the stack
(no Redis or broker to add, operate or secure).

## 7. Rate limits (DP-S7)
| Scope | Limit |
|---|---|
| submissions per client | 3 per 30 s and 5 per 10 min |
| submissions in total | 120 per 10 min |
| polls per client | 120 per minute |
| queue | 10 queued or running |
| running | 2 |
| per job | 30 s |
The client is Cloudflare's `CF-Connecting-IP` when `JANUS_BEHIND_CLOUDFLARE=on` (the deploy compose: the API is
reachable only through the tunnel and the web app's rewrite, and Cloudflare overwrites the header), else the
socket peer; an IPv6 address counts as its /64. It is reduced to HMAC-SHA256(secret, address)[:16]; the secret is
random per process and never stored; entries expire after the longest window (10 min); at most 10,000 keys.
The API runs one process, so the limits are global to it.

**Cloudflare rule (deployer, dashboard → Security → WAF → Rate limiting rules):**
expression `(http.request.uri.path wildcard "/api/simulate*" and http.request.method eq "POST")`, counting
characteristic IP, 5 requests per 10 seconds, action Block for 10 seconds. The Free plan allows one rate-limiting
rule: if the existing `/api/*` rule (deploy design §7) uses it, keep that rule and rely on the in-app limits
above, or replace it by this one; on a paid plan add both.

## 8. Worker and image (DP-S8)
`rocker/r-ver:4.6.1` (pinned by digest; CRAN pinned to the P3M snapshot of 2026-10-28), httk 2.7.4 checked at
build time, Python 3.12 from Ubuntu 24.04 with the API's locked dependencies (uv). User `simulator` (10002).
Compose: internal network only, `read_only`, tmpfs `/tmp` 256 MB `noexec,nosuid,nodev`, `cap_drop: [ALL]`,
`no-new-privileges`, `pids_limit: 128`, 2.0 CPU / 1.5 GB, health check on a heartbeat file. Database role
`janus_simulator` (migration 0014, created without login; `deploy.sh` gives it its password from `.env` with
`python -m janus.simulation.dbrole`): SELECT, UPDATE, DELETE on `simulation_jobs` only. The worker stays on the
shared internal network (it can reach `api:8000`, the same public surface the internet reaches); a separate
network would need a new firewall subnet and was not added (safety review F7, declined). The amd64 image is built in CI; the
arm64 image is built natively on the host by `deploy.sh`.

## 9. Properties and checks
| # | Property | Test |
|---|---|---|
| S1 | browser port = Python model on shared fixtures; fixtures current | `src/simulation/pk.test.ts`, `test_s1_*` |
| S2 | no person-specific field, no free text; results are distributions only; every answer carries the disclaimer | `test_s2_*`, `test_r2_*`, web tests |
| S3 | validation: bounds, strict types, unknown fields, errors name fields only | `test_s3_*` |
| S4 | cache key ignores order and noise, changes with input and allow-list version | `test_s4_*` |
| S5 | rate limits never exceeded; honest Retry-After; no address kept; bounded; expiring | `test_s5_*` |
| S6 | verdicts = time machine's (compartmental recomputed); populations cited | `test_s6_*` |
| S7 | httk output reader strict | `test_s7_*` |
| Q1-Q4 | queue ≤ 10, running ≤ 2 (two claimers), cache and reuse, expiry and reaper | `test_simulation_queue.py` (Postgres) |
| R1 | routes: 503, 413/415, 422, 202/200, 429 + Retry-After, 404 | `test_simulation_queue.py` |
| C | compose: simulator internal only, hardened, caps | `deploy/check_compose.py` |

## 10. Decisions
| # | Decision | Why |
|---|---|---|
| DP-S1 | Allow-list as committed data; only ids travel | Nothing typed by a user reaches a model; reviewable in one file |
| DP-S2 | Strict pydantic, 1 KiB body | Smallest attack surface; numbers only |
| DP-S3 | Port the model to TypeScript with CPython's PRNG | Exact parity is testable; the explorer needs no server |
| DP-S4 | Queue in Postgres with an advisory lock | Already in the stack; atomic limits; no broker |
| DP-S5 | Cache by canonical hash | Repeated runs cost nothing; abuse by repetition is free |
| DP-S6 | Child process per job, process-group kill at 30 s | A stuck R or Python run cannot hold a slot |
| DP-S7 | In-memory keyed-hash limiter + global window + Cloudflare rule | privacy.md: no stored addresses; rotation bounded globally |
| DP-S8 | Separate image, internal network only | R and its packages never sit in the API image; no egress |
| DP-S9 | Owner decision 2026-11-09: virtual populations only; free parameter sliders and the httk single-dose run (one reference individual) dropped | Individual dosing software is a medical device; one curve reads as one person |
| DP-S10 | Daily dose of the httk run fixed at 1 mg/kg/day | Same as the time machine; httk failed validation, so only the relative older-vs-younger comparison is meaningful |

## 11. Measured
See `tasks.md`.

## 12. Reviews
Automated review passes (safety auditor, pharmacologist, localization reviewer): `reviews.md`. Expert review
has not yet been done.
