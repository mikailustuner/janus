# Implementation Plan: Privacy and Consent, Phase 1 (server side)

> Scope: `apps/api` only (Req 1.4, 2, 3.1 server part, 3.2–3.6, 4, 5.2 server part).
> Owner decisions of 2026-11-07 applied (design §9: DP1–DP21 confirmed or set).
> Criteria tagged **[Client: experience spec]** have no tasks here. Property numbers refer to
> design.md §8. No health data in logs, fixtures or test output; tests use sentinel values.

- [x] 1. Groundwork: dependencies, settings, test setup
  - Add `psycopg[binary]`, `psycopg-pool`, `alembic`, `sqlalchemy` to `apps/api` (DP18); `uv lock`.
  - Update `.kiro/steering/structure.md` with the new API packages and `migrations/` (DP1).
  - `janus/settings.py`: `Settings` from the environment (design §3); invalid values stop
    startup and name the variable, never a secret's value.
  - `tests/conftest.py`: Hypothesis profiles `dev` / `ci`; `db` marker; Postgres fixtures using
    `JANUS_TEST_DATABASE_URL` (skip locally when unset, fail when `CI=true`).
  - Add the new variables to `.env.example` without values.
  - Confirm `scope["route"]` for mounted apps and 404/405 in FastAPI 0.162.1, and the current
    Alembic / psycopg versions.
  - [x] 1.1 Property test P14: `Settings` accepts k iff k ≥ 20 and ε iff 0 < ε ≤ 10. _Requirements: 4.1, 4.2_

- [x] 2. Allowlist logging (`janus/observability/logging.py`)
  - `AllowlistFormatter`, `LogEvent`, `log_event()`, `configure_logging()` replacing handlers on
    root, uvicorn, fastapi, httpx2, alembic and psycopg loggers (design §4.2).
  - [x] 2.1 Property test P2: any `LogRecord` gives one JSON object with allowlisted keys and validated values, and no sentinel. _Requirements: 2.2_

- [x] 3. Access-log middleware and error handler (`observability/middleware.py`, `errors.py`)
  - Pure ASGI middleware, outermost: server-generated request id, `X-Request-ID` header, route
    template or `<unmatched>`, status, latency (design §4.1); exception handler logging the
    class name only (design §4.4). Wire into `create_app()` in `main.py`.
  - `tests/harness.py`: test app with stub medical router, `capture_logs()`, sentinel strategies.
  - [x] 3.1 Property test P3: exactly one access line per request; template route; request id equals the header and ignores the caller's. _Requirements: 2.2_
  - [x] 3.2 Property test P1: no medical value from path, query, body or headers appears in any log output, for 2xx, 4xx and raised errors. _Requirements: 2.2_

- [x] 4. Route kinds, body policy, read-only database (`http_policy/`, `db/pool.py`)
  - `RouteKind`, `medical_router()`, `donation_router()`, operational allowlist and
    `classify(app)` startup check; `no-store` on medical and donation responses;
    `BodyPolicyMiddleware` (JSON only, 64 KiB); `read_only_tx()` / `write_tx()` (design §4.3).
  - `assert_stateless()` in `tests/harness.py` (reused by later specs).
  - [x] 4.1 Property test P4: non-donation medical requests leave the database and temp directory unchanged, send `no-store`, and cannot write in `read_only_tx()`. _Requirements: 2.1_
  - [x] 4.2 Property test P5: non-JSON or oversized bodies get 415/413, the endpoint is not called and nothing is written. _Requirements: 1.4, 2.1_
  - [x] 4.3 Example tests: `classify(app)` fails on an unclassified route; `write_tx` is imported only by `contributions/repository.py`. _Requirements: 2.1_

- [x] 5. Checkpoint: logging and stateless endpoints
  - All lint, format, type-check and test steps green (incl. property tests and database
    tests against PostgreSQL 16); the `log-guard` hook reports no findings under `apps/api`.
    Commit, push, and confirm CI passes.

- [ ] 6. Pure disclosure module (`janus/memory/noise.py`, `janus/memory/disclosure.py`)
  - Exact discrete Laplace sampler (CKS20, `int` / `Fraction` only), keyed HMAC-SHA256 generator
    with unbiased `randbelow`, `noisy_count`, `release_table` (design §6). No I/O.
  - [ ] 6.1 Property test P11: released cells all have count ≥ k; output unchanged when suppressed cells change below k. _Requirements: 4.1_
  - [ ] 6.2 Property test P12: noisy counts are non-negative integers. _Requirements: 4.2_
  - [ ] 6.3 Property test P13: same key, cell and data version give the same value; cell order does not matter. _Requirements: 4.2_
  - [ ] 6.4 Statistical test S1: chi-square fit of 200,000 seeded draws per ε against the discrete Laplace pmf; mean near 0. _Requirements: 4.2_
  - [ ] 6.5 Property test P14 (module part): `release_table` raises for k < 20. _Requirements: 4.1_

- [ ] 7. Migration and local database settings (`apps/api/migrations/`, `docker-compose.yml`)
  - Alembic setup; revision `0001_contributions` with the schema and CHECKs from design §5.2 and
    a downgrade that drops the table.
  - Postgres in compose with `log_error_verbosity=terse`, `log_min_error_statement=panic`,
    `log_statement=none`, `log_min_duration_statement=-1` (design §5.4).
  - [ ] 7.1 Example test: upgrade → downgrade → upgrade on an empty database gives identical columns and constraints. _Requirements: 3.5_
  - [ ] 7.2 Example test: the database rejects a row outside each field's domain (CHECKs hold without the API). _Requirements: 3.2_
  - [ ] 7.3 Example test: `SHOW log_error_verbosity` is `terse` on the compose database. _Requirements: 2.3_

- [ ] 8. Donation model, week, tokens, retention (`janus/contributions/models.py`, `week.py`, `tokens.py`, `vocabulary.py`, `retention.py`)
  - `ContributionIn` / `ContributionStored` / `DeletionIn` with `extra="forbid"` and the domains of
    design §5.1 (age bands 20–85 and 90; consent version); event vocabulary loader with the
    placeholder file (design §5.8); `report_week`; `new_token`, `token_hash`;
    `retention_cutoff`, `is_expired` (design §5.7).
  - [ ] 8.1 Property test P8: `report_week` returns the Monday of the UTC ISO week for any aware instant. _Requirements: 3.2_
  - [ ] 8.2 Property test P7 (model part): extra fields, missing fields, out-of-domain values (incl. age bands under 20), duplicate ingredients and missing or unknown consent fail validation. _Requirements: 3.1, 3.2_
  - [ ] 8.3 Property test P16 (pure part): `retention_cutoff` is 24 calendar months earlier, clamped, matching an independent reference. _Requirements: 3.6_

- [ ] 9. Donation storage, deletion and storage region (`contributions/repository.py`, `router.py`, `privacy/`)
  - Repository with parameterised SQL; `POST /contributions` (stores the consent version;
    rejects `"demo": true`), `POST /contributions/deletions`, `GET /privacy/storage`; region
    guard with the explicit EU list; 503 when donations are not fully configured (design §5).
  - `purge_expired` and `python -m janus.contributions.purge` (design §5.7).
  - [ ] 9.1 Property test P6: a stored donation has exactly the allowed columns and the normalised input values. _Requirements: 3.2_
  - [ ] 9.2 Property test P7 (endpoint part): every invalid payload, incl. `"demo": true`, gets 422 and the table is unchanged; stored week equals `report_week(server clock)` (P8 router part). _Requirements: 3.1, 3.2_
  - [ ] 9.3 Property test P9: after deletion no query returns the donation, others are unchanged, a recomputed aggregate excludes it. _Requirements: 3.3_
  - [ ] 9.4 Property test P10: the token is not in the database; other tokens delete nothing; second use returns 404. _Requirements: 3.3_
  - [ ] 9.5 Property test P16 (database part): the purge deletes exactly the expired donations and a second run deletes nothing. _Requirements: 3.6_
  - [ ] 9.6 Property test P15: donations enabled iff region is `local` or exactly an EU storage region id. _Requirements: 3.4_
  - [ ] 9.7 Example tests: `/privacy/storage` in `local` mode reports the region and `in_eu=false` with no compliance wording; donation routes return 503 when not configured; P1 rerun over the donation routes. _Requirements: 3.4, 5.2, 2.2_

- [ ] 10. CI
  - `api` job: `postgres:16` service, `JANUS_TEST_DATABASE_URL`, `HYPOTHESIS_PROFILE=ci`,
    `alembic upgrade head` before pytest; the `db` tests must run, not skip.
  - _Requirements: 3.5, 2.1_

- [ ] 11. Final checkpoint
  - All tests green locally and in CI; `docker compose up` starts the API with donations in
    `local` mode; a manual donation and deletion leave no trace in API or Postgres logs.
  - All lint, format, type-check and test steps green; commit, push, confirm CI passes.
  - Record the open items (Phase 5: purge schedule, Caddy rate limiting, hardening) in
    `docs/kiro-usage.md`.
  - _Requirements: 2.2, 2.3, 3.3, 3.4_
