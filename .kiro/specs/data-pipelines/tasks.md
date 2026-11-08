# Implementation Plan: Data Pipelines (ETL), Phase 1 and Phase 2

> Scope of tasks 1–14 (Phase 1, done): core (Req 1–4) and `pipc`, `titck`, `wikidata_ingredients`,
> `us_ndc`, `retractions` (Req 5–9). Property numbers P1–P16 refer to design.md §7. Tests use no
> network and no TİTCK data.
> Scope of tasks 15–26 (Phase 2, planned 2026-11-08, **not started**): core changes (Req 14),
> `eu_fr_bdpm` (Req 11), `eu_es_cima` (Req 12), `faers` (Req 13) and the FAERS count builder
> (Req 15). Properties P17–P40 refer to design.md §16. Tests use no network and no committed
> source data. Every checkpoint runs ruff, ruff format, pyright, the full pytest suites with the
> `ci` Hypothesis profile (`pipelines/` and `apps/api/`, with the database tests against PostgreSQL
> 16), `janus-pipelines notice --check`, then commits, pushes and confirms GitHub CI is green.

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

---

## Phase 2 (planned 2026-11-08)

- [x] 15. Streamed content hash (`core/canonical.py`, `apps/api/janus/resolution/canonical.py`)
  - Add `content_hash_stream` (design §12.1): canonical lines in sorted chunks on disk, k-way
    merge into the digest, temp files removed in `finally`. Same function in the API copy; extend
    the shared golden-vector test of `drug-resolution` DP15 with a streamed case in both suites.
  - [x] 15.1 Property test P17 (hash part): for any rows and chunk sizes 1–10 the streamed hash
    equals `content_hash`; empty input too. _Requirements: 14.1, 1.3_

- [x] 16. File-backed output and side tables (`core/runner.py`, `core/store.py`, `core/manifest.py`)
  - `ParseResult.rows_file`, `output_rows`, `side_tables`; the runner hashes the file in batches,
    moves it to `rows.parquet`, stages side tables with SHA-256 and row counts in the manifest
    (`side_tables`, optional field). Phase 1 jobs and manifests unchanged.
  - [x] 16.1 Property test P17 (round-trip part): rows → Parquet → batches → stream hash equals the
    in-memory hash for nested lists, `None` and Unicode. _Requirements: 14.2, 1.3_
  - [x] 16.2 Property test P18: side tables never change the content hash; manifest SHA-256 equals
    the file's; staged files are unchanged after the run. _Requirements: 14.3, 1.2_
  - [x] 16.3 Extend the P10 state machine with file-backed runs and faults at the new steps (write
    spill, move rows file, stage side table); P1 and P3 still pass for Phase 1 jobs.
    _Requirements: 4.2, 14.2_

- [x] 17. Registry and NOTICE (`sources.toml`, `NOTICE`)
  - `faers`: name "openFDA / FDA Adverse Event Monitoring System (AEMS, formerly FAERS)", URLs of
    the quarterly page; keep CC0 and the "not deduplicated, reports not people" note.
  - `bdpm`: URL of the download page, attribution lines (source, update date, data not altered, no
    endorsement). `cima`: URLs of the Nomenclátor and the REST API, attribution line with source and
    update date (AEMPS legal notice, Ley 37/2007). Keep `cadence_days` 91, 30, 7.
  - Regenerate `NOTICE`; check it keeps every existing entry; `notice --check` green.
  - [x] 17.1 Existing P8 still passes with the new registry; add the three sources to a manifest
    set in the example test. _Requirements: 3.2_

- [x] 18. Checkpoint: core ready
  - Full checks (see header). Re-run the Phase 1 pipelines' tests unchanged. Ask the owner to
    confirm DP16 (region basis) and DP21 (scopes and denominators) before the FAERS tasks.

- [x] 19. `eu_fr_bdpm` job (`jobs/eu_fr_bdpm.py`)
  - Fetch the page and dates, download the three files (confirm the page's own links match the
    URL pattern), `--input DIR`; strict per-file decoding; line-based tab split; join; rows,
    name-only convention, metrics (design §13.1). `JANUS_CONTACT` optional.
  - [x] 19.1 Property test P19: cells are never altered (leading space, accents, quotes). _Requirements: 11.4_
  - [x] 19.2 Property test P20: strict per-file decoding, invalid bytes fail naming the file. _Requirements: 11.2_
  - [x] 19.3 Property test P21: CIP13 accepted exactly when 13 digits, `3400`, valid check digit; else name-only. _Requirements: 11.5_
  - [x] 19.4 Property test P22: join, orphans, empty composition, malformed lines, row accounting. _Requirements: 11.3, 11.6, 1.5_
  - [x] 19.5 Property test P23: update dates read per file; snapshot is the oldest; missing label fails. _Requirements: 11.1_
  - [x] 19.6 Example tests: metformin/vildagliptin composition keeps `FT` and `SA` lines with link numbers in file order; a presentation whose CIS is missing is kept with `specialty_missing`. _Requirements: 11.3, 11.6, 11.7_

- [x] 20. `eu_es_cima` job (`jobs/eu_es_cima.py`)
  - Fetch the archive with the pipelines' User-Agent (403 → clear message); streaming parse with
    defusedxml; dictionary join; GS1 validity; rows and metrics; advice elements never read
    (design §13.2). `--input FILE`.
  - [x] 20.1 Property test P24: `is_valid_gs1` and NTIN construction. _Requirements: 12.3_
  - [x] 20.2 Property test P25: generated Nomenclátor parses to the generated presentations in any order; ingredients in `orden_colacion` order; extra and advice elements ignored; missing header date fails. _Requirements: 12.1, 12.2, 12.5_
  - [x] 20.3 Property test P26: 6-digit `cod_nacion` kept, else name-only; shared NTIN/GTIN kept on all presentations. _Requirements: 12.3, 12.4_
  - [x] 20.4 Example tests: a presentation with NTIN and GTIN; HTTP 403 gives the User-Agent message; an ingredient code absent from the dictionary keeps the code with a null name. _Requirements: 12.2, 12.7_

- [x] 21. Checkpoint: both EU pipelines run locally
  - Run `eu_fr_bdpm` and `eu_es_cima` against the live sources; compare every manifest figure with
    design §10 (20,918 presentations, 30,900 presentations, NTIN and GTIN counts; differences
    are explained by newer data, not by parser faults); record the figures in this spec.
  - Update `pipelines/README.md` (commands, sources, raw files) and run all checks. Commit, push, CI.

- [x] 22. `faers` job (`jobs/faers.py`)
  - Page parsing and `select_quarters`; archive download; line-based `$` split with strict
    UTF-8; `choose_kept`; `derive_region`; `split_ai`; per-quarter column-wise joins; spill file
    and `removed` side table; metrics (design §13.3). Job threshold 15 %. `--quarters` option.
  - [x] 22.1 Property test P27: case deduplication with deletions, any order. _Requirements: 13.3, 1.5_
  - [x] 22.2 Property test P28: row accounting with malformed, orphan and blank lines. _Requirements: 13.2, 13.5, 1.5_
  - [x] 22.3 Property test P29: region rule. _Requirements: 13.6_
  - [x] 22.4 Property test P30: quarter window. _Requirements: 13.1_
  - [x] 22.5 Property test P31: LF, CRLF and mixed line ends; quote characters kept. _Requirements: 13.2_
  - [x] 22.6 Property test P32: no field outside `faers-1`. _Requirements: 13.4_
  - [x] 22.7 Example tests: a `SULFAMETHOXAZOLE\TRIMETHOPRIM` drug line splits into two names; role `DN` kept in the artifact (the builder excludes it); `COUNTRY NOT SPECIFIED` falls back to UNKNOWN; a follow-up version replaces the initial one from an earlier quarter. _Requirements: 13.3, 13.4, 13.6_

- [x] 23. Checkpoint: FAERS artifact on real data
  - Run `faers` on the four latest quarters. Compare with design §10 (if the window is still
    2025 Q4 – 2026 Q3: 1,626,375 reports read, 111,604 superseded, 3,967 deleted, 1,510,804 kept;
    region counts of DP16). Report wall time, peak memory (target ≤ 4 GiB, Req 14.4) and the size
    of the artifact and the raw files. If the target is missed, apply the levers of §12.4 first.
  - Confirm with the owner the region result and DP21; update the spec with the measured figures.
  - All checks, commit, push, CI.

- [ ] 24. Name index extraction in `drug-resolution` (`apps/api/janus/resolution/prepare.py`)
  - Extract `build_name_index(...)` from `prepare_dataset` without changing behaviour.
  - [ ] 24.1 Regression: the drug-resolution suite (including P16 and the database tests) passes
    unchanged and the dataset version computed from the real artifacts is identical before and
    after. _Requirements: 15.2_

- [ ] 25. FAERS count builder (`apps/api/janus/memory/faers_build.py`)
  - `read_artifact` with streamed hash check; `map_names`; DuckDB facts and count tables; metadata
    with table hashes; staging and atomic `current` swap under `artifacts/faers_counts/`;
    coverage report to `$JANUS_DATA_DIR/memory/coverage-<build>.json` (never into the repository);
    `LogEvent.faers_build` with counts only; CLI (design §14).
  - [ ] 25.1 Property test P33: SQL tables equal the Python reference; 2×2 identities. _Requirements: 15.5_
  - [ ] 25.2 Property test P34: regions add up; `suspect` ≤ `any`; DN and unknown roles counted nowhere. _Requirements: 15.3, 15.5_
  - [ ] 25.3 Property test P35: duplicate lines and repeated events change nothing. _Requirements: 15.4_
  - [ ] 25.4 Property test P36: only `mapped` names are counted; unmapped occurrences add up. _Requirements: 15.2_
  - [ ] 25.5 Property test P37: report order does not change tables or hashes; two builds agree. _Requirements: 15.7_
  - [ ] 25.6 Property test P38: any changed artifact row or manifest hash is refused. _Requirements: 15.1_
  - [ ] 25.7 Property test P39: stateful fault injection around the `current` swap. _Requirements: 15.8_
  - [ ] 25.8 Property test P40: sentinel names never reach a log record; the privacy log-guard hook passes for the new module. _Requirements: 15.9_

- [ ] 26. Final checkpoint: Phase 2 data ready for Collective Memory
  - Run `faers` then the builder end to end on real data. Compare the coverage report with
    design §10 (84.0 % of occurrences, 80.5 % in suspect roles); report table row counts and file
    size (`faers_pair_counts`, open item 7), the share of reports with a mapped ingredient, and
    the run times.
  - Record owner decisions in this spec, the measured results in design §10, and the open items
    for `collective-memory` (denominator, region basis) in its requirements.
  - Update `pipelines/README.md`, `docs/kiro-usage.md` (dated entry for Phase 2), `data/README.md`
    if a data file was added. All checks, commit, push, CI.
