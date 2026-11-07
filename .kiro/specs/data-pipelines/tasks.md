# Implementation Plan: Data Pipelines (ETL), Phase 1

> Scope: core (Req 1–4) and `pipc`, `titck`, `wikidata_ingredients`, `us_ndc`, `retractions`
> (Req 5–9). Property numbers refer to design.md §7. Tests use no network and no TİTCK data.

- [x] 1. Scaffold the `pipelines/` project
  - Create `pipelines/pyproject.toml` (`janus-pipelines`, Python 3.12; Polars, openpyxl,
    defusedxml, `httpx2`, Pydantic v2; dev: pytest, Hypothesis, ruff, pyright strict), matching
    `apps/api` tool settings; `uv lock`.
  - Package `janus_pipelines/` with `core/`, `jobs/`, `cli.py` (`run`, `promote`, `notice`).
  - Hypothesis profiles `dev` and `ci` in `tests/conftest.py`.
  - Add `.data/` to `.gitignore`; add `JANUS_DATA_DIR` and `JANUS_CONTACT` to `.env.example`.
  - Add a `pipelines` CI job (uv sync, ruff check, ruff format --check, pyright, pytest `ci`).
  - Confirm the `httpx2` client and mock-transport API used in later tasks.
  - _Requirements: 4.1, 3.1_

- [x] 2. Canonical rows and content hash (`core/canonical.py`)
  - Implement canonical serialisation and `content_hash` as in design §3.3.
  - [x] 2.1 Property test P2: permuting rows does not change the hash. _Requirements: 1.3_
  - [x] 2.2 Property test P1 (pure part): serialising the same rows twice gives the same hash. _Requirements: 1.1, 1.3_

- [x] 3. Validation (`core/validation.py`)
  - Expected-schema check (missing, renamed, retyped, extra columns), row accounting, review flag.
  - [x] 3.1 Property test P5: review flag iff `abs(c − p) > t·p`; never without a previous artifact. _Requirements: 2.2_
  - [x] 3.2 Property test P4 (generic): `input == output + Σ excluded`, every exclusion has a reason. _Requirements: 1.5_

- [x] 4. Source registry and licence guard (`sources.toml`, `core/registry.py`, `core/licensing.py`)
  - Write `sources.toml` with every source in the current `NOTICE` (ingested and cited only).
  - Registry loader rejects duplicate ids, missing licence, unknown storage values.
  - Licence guard per design §4.4; runner refuses sources missing from the registry.
  - [x] 4.1 Property test P7: a `runtime_only` path that resolves into `<repo>/data/` is refused and nothing is written. _Requirements: 3.1_
  - [x] 4.2 Example test: a `runtime_only` path inside the repo but not git-ignored is refused. _Requirements: 3.1_

- [x] 5. Store, manifest and runner (`core/store.py`, `core/manifest.py`, `core/runner.py`)
  - Staging → runs → atomic `current` symlink; manifest model; failed-run manifests;
    `promote` with `promoted_by`/`promoted_at`; evidence source record (design §3.5).
  - Logs carry run id, pipeline, step, outcome and counts only.
  - [x] 5.1 Property test P1 (runner): same input into two fresh data dirs gives the same rows and hash. _Requirements: 1.1, 1.2, 1.3_
  - [x] 5.2 Property test P3: schema-mismatched input fails, names the column, leaves `current` byte-identical. _Requirements: 2.1_
  - [x] 5.3 Property test P10: stateful test with fault injection; `current` is always absent or complete and last promoted. _Requirements: 4.2_
  - [x] 5.4 Example tests: `needs_review` run is not promoted; manual `promote` records who and when; no promoted artifact → source reported unavailable. _Requirements: 2.2, 4.2_

- [x] 6. HTTP client and retry policy (`core/http.py`, `core/retry.py`)
  - Timeouts, pure `should_retry`, `Retry-After`, per-host token bucket, User-Agent with
    `JANUS_CONTACT` (URL or email; Wikidata refuses to start without it; Crossref `mailto`
    only for an email contact, else the public pool).
  - [x] 6.1 Property test P9: retries only GET/HEAD on connection error / timeout / 429 / 5xx, at most 3, bounded delay. _Requirements: 4.1_
  - [x] 6.2 Example test with the mock transport: a 503 then 200 succeeds; a 404 is not retried. _Requirements: 4.1_

- [x] 7. NOTICE generator (`core/notice.py`, `janus-pipelines notice [--check]`)
  - Render from the registry (design §4.5); regenerate `NOTICE` and check it keeps every entry
    of the current hand-written file; add `notice --check` to the CI job.
  - [x] 7.1 Property test P8: every manifest source has an entry; an unknown source fails generation. _Requirements: 3.2_

- [x] 8. Checkpoint: core complete
  - All tests green (`uv run pytest`, ruff, pyright). Ask the owner to confirm decision DP4
    (needs_review runs are not promoted) before the jobs rely on it.

- [x] 9. `pipc` job (`jobs/pipc.py`)
  - Fetch Europe PMC XML; parse Table 1 with the row state machine (design §5.1); exactly 65
    cascades; on promotion write `data/pipc.csv` and `data/pipc.meta.json`; evidence source
    record with the DOI.
  - [x] 9.1 Property test P11: generated Table-1-like XML parses to exactly the generated cascades, split rows merged. _Requirements: 5.2, 5.3, 5.4_
  - [x] 9.2 Example test: the statin cascade split over two `<tr>` merges into one row; 64 + 1 = 65. _Requirements: 5.4, 5.3_
  - [x] 9.3 Run the job once, review `data/pipc.csv` against the paper, commit it with its metadata file. _Requirements: 5.5, 5.6_

- [x] 10. `titck` job (`jobs/titck.py`)
  - Fetch the newest list from the TİTCK page or `--input PATH`; header row by name; barcode
    validation; duplicates kept; `split_ingredients`; metrics; artifacts only in the data dir.
  - Confirm the live page's link and date format.
  - [x] 10.1 Property test P12: splitting returns the joined names and keeps every non-separator character. _Requirements: 6.6_
  - [x] 10.2 Property test P6: metrics equal a direct recount. _Requirements: 2.3, 6.4, 6.5_
  - [x] 10.3 Property test P4 (titck): row accounting on generated workbooks with invalid and blank rows. _Requirements: 1.5, 6.4_
  - [x] 10.4 Example test: `amlodipin besilat/lisinopril dihidrat` splits into two names; ATC `C09BB03` kept as published. _Requirements: 6.3, 6.6, 6.8_
  - [x] 10.5 Optional integration test against `JANUS_TITCK_LIST` (skipped when unset and in CI). _Requirements: 6.1, 6.2_

- [x] 11. `wikidata_ingredients` job (`jobs/wikidata_ingredients.py`)
  - Code query + one label query per language; split by ATC first letter on timeout; pure merge;
    record query hashes; snapshot = retrieval time.
  - [x] 11.1 Property test P13: merge is independent of order and partitioning; each QID once with ≥ 1 ATC. _Requirements: 7.3, 7.4_

- [x] 12. `us_ndc` job (`jobs/us_ndc.py`)
  - Read `download.json`; download partitions into `raw/`; stream records; fields as published.
  - [x] 12.1 Example test: record count different from the index fails the run. _Requirements: 8.2_
  - [x] 12.2 Example test: one sample record maps to the output row with all fields as published. _Requirements: 8.3, 8.4_

- [x] 13. `retractions` job (`jobs/retractions.py`)
  - Collect DOIs from current evidence source records; `normalise_doi`; Crossref per DOI;
    `status_from_notices`; `effective`; raw responses in `raw/`; `changes[]`; change away from
    `retracted` → `needs_review`. Confirm Crossref rate limits and notice type names.
  - [x] 13.1 Property test P14: status is the most severe notice, whatever the order. _Requirements: 9.2, 9.3_
  - [x] 13.2 Property test P15: a failed check never turns `retracted` into anything else; `unknown` is never `ok`. _Requirements: 9.4, 9.5_
  - [x] 13.3 Property test P16: DOI normalisation is idempotent and ignores case and prefixes. _Requirements: 9.1_
  - [x] 13.4 Example test: a recorded Crossref response with a `retraction-watch` retraction notice gives `retracted` with source and notice DOI. _Requirements: 9.2, 9.7_

- [x] 14. Final checkpoint
  - Done 2026-11-07: all five pipelines ran locally (titck as a live download) and were checked;
    `wikidata_ingredients` and `retractions` ran with `JANUS_CONTACT` set to a URL (DP13).
  - Run all five pipelines locally (TİTCK with `--input`); check every manifest (counts, hashes,
    snapshot dates, licences) and the TİTCK metrics; all tests and `notice --check` green.
  - Update `pipelines/README.md` (commands, env vars, data dir) and `docs/kiro-usage.md`.
  - _Requirements: 1.1, 1.4, 2.3, 3.2_
