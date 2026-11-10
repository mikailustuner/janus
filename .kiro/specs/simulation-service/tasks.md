# Implementation Plan: Simulation service

- [x] 1. Spec (requirements in EARS, design with decisions DP-S1-DP-S10, properties S1-S8, Q1-Q4, R1-R2);
  deploy Req 7.4 amended (owner decision 2026-11-09); owner decision on virtual populations recorded
- [x] 2. Allow-list `data/simulation/compounds.json` (compounds, virtual populations, dose bounds, scenarios,
  validation verdicts, limits)
  - _Requirements: 1.2, 2.1, 2.3_
- [x] 3. Browser port: CPython's Mersenne Twister and `gauss` (`src/simulation/random.ts`), the model and the
  population Monte Carlo (`pk.ts`), the explorer (`explorer.ts`, `explorer.json`); parity fixtures
  (`python -m janus.simulation.parity`)
  - _Requirements: 1_
- [x] 4. API: validation and canonical form, queue (migration 0014), rate limits, routes, body limit 1 KiB
  - _Requirements: 2, 3_
- [x] 5. Worker: child process per job with a 30 s process-group kill, httk HTTK-Pop script, reaper,
  heartbeat; image `apps/api/simulator.Dockerfile` (R 4.6.1, httk 2.7.4 pinned)
  - _Requirements: 2.5-2.8, 4.1_
- [x] 6. Deploy: compose service (internal only, hardened, 2.0 CPU / 1.5 GB), `check_compose.py` (service,
  networks, caps), `verify-isolation.sh` (probes from inside the simulator), `smoke.sh` (one cached job),
  `deploy.sh` / `rollback.sh`, README, CI (amd64 build and hardened self-test), NOTICE
  - _Requirements: 4_
- [x] 7. Screens: model explorer, queued runs; Research entries; five languages; recorded demo answers
  (`scripts/record-simulation.mjs`, from the real local API and worker)
  - _Requirements: 1, 5_
- [x] 8. Property tests (API: S1-S7, Q1-Q4, R1-R2; web: S1, S2, S8) and e2e (five locales, two themes,
  375/1280 px, axe)
- [x] 9. Automated review passes: safety auditor, pharmacologist, localization reviewer (`reviews.md`); fixes
  applied (worker role, IPv6 /64, header trust switch, per-compound intervals, httk ratio, directions, scope)
- [x] 10. Checkpoint
- [x] 11. Label-reported half-life next to the model's half-life (Req 6.7) and "not drug-specific" next to every
  HTTK-Pop ratio (Req 6.8): data file, explorer export, `LabelHalfLife`, five languages, tests.

## Measured (development PC, 2026-11-09; worker in the hardened container: read-only, `noexec` tmpfs, no
## capabilities, internal network, own database role, 2.0 CPU / 1.5 GB; submit to result incl. 0.25 s polling)
| Run | Submit to result |
|---|---|
| compartmental, 1,000 virtual individuals, one dose | 1.0-2.1 s |
| compartmental, 2,000 individuals, 14 doses every 24 h (the largest allowed) | 8.4 s |
| httk, both HTTK-Pop age ranges, 100 or 1,000 individuals each | 8.9-10.4 s (R start-up and two Monte Carlo runs) |
| six different httk runs at once | finished at 9.4, 9.4, 17.5, 18.1, 27.2, 27.2 s (two at a time) |
| identical run again (cache) | 2-6 ms |
| burst of 12 distinct submissions | 10 accepted, then 429 `queue_full` with `Retry-After: 25` |
Worker memory with two R runs: 155-220 MB. Image: 1.85 GB (amd64), built in about 4 minutes. In the container:
internet (1.1.1.1:443, 8.8.8.8:53), R mirrors (name resolution fails), metadata service and host ports closed;
postgres open; root file system read-only; `/tmp` writable, not executable. Self-test in the CI configuration
(no network): compartmental 7.0 s (2,000 × 14 doses), httk 9.3-10.1 s.

## Open items
- The API itself still connects as the database owner (unchanged by this feature).
- A dedicated network for postgres and the simulator (safety review F7) would need a new firewall subnet.
- The arm64 image was not built here (no emulation on the development PC); `deploy.sh` builds it natively.
- An expert check of the virtual populations (amlodipine ≥ 65 clearance factor) and of the PK wording in
  TR, DE, FR, ES. Expert review has not yet been done.
