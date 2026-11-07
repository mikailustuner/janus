# Implementation Plan: Evidence Integrity, Phase 1

> Scope: `apps/api/janus/integrity/`, migration `0003`, the loader, the two routes, the freshness
> rule and the rule gate; one small `pipelines/` change (the paper list as a second DOI input).
> Criteria tagged **[Client: …]** and **[Phase 5: …]** have no tasks here. Property numbers refer
> to design.md §8. Owner decisions of 2026-11-07 applied: DP4 and DP14 confirmed; DP17 decided as "replace the
> constant" (task 5).
> No health data in logs, fixtures or test output: tests use synthetic evidence and sentinel
> values. No new runtime dependency.

- [x] 1. Groundwork and fact checks
  - Confirm how `pipc` locates the repository's `data/` directory (design §5.3) and record it in
    design §10; confirm `Database`, `medical_router`, `LogEvent` and `resolution.load` helpers
    (`read_rows`, `LoadError`) are importable as described.
  - Create `data/evidence_papers.csv` with the header `key,doi,source_id,title,verified_on,note`
    and no rows; describe it in `data/README.md` (curated by Janus, Apache-2.0).
  - Add `LogEvent.integrity_load` (counts only).
  - `tests/integrity_strategies.py`: record graphs (DAG, `rule` always with basis), states with
    notices, registry TOML text, id sets with unregistered ids; reference implementations of
    citability (path enumeration) and the line recount.
  - _Requirements: 4.1, 4.3, 8.5_

- [x] 2. Status, freshness and registry (`model.py`, `status.py`, `freshness.py`, `registry.py`, pure)
  - Types and closed vocabularies; `validate_incoming`, `merge_status` (sticky retraction, notices
    kept); `parse_snapshot_date`, `age_days`, `freshness`, `check_is_stale`;
    `parse_sources(toml_text)` reading `id, name, storage, cadence_days` (design §4.1, §4.3).
  - [x] 2.1 Property test P5: a retracted record changes only on a completed check with another status; failed and missing rows never change it; notices kept; `unknown` never becomes `ok`. _Requirements: 1.5_
  - [x] 2.2 Property test P6: malformed incoming rows are refused. _Requirements: 1.1, 8.1_
  - [x] 2.3 Property test P7: stale iff age > 2 × cadence; future dates give age 0; monotone; no cadence → `not_applicable`; date parser agrees for date and date-time forms. _Requirements: 2.2_
  - [x] 2.4 Property test P8: `parse_sources` returns exactly the declared cadences; example test on the real `pipelines/sources.toml` (titck 7, openfda_ndc 7, crossref 7, pipc 365). _Requirements: 2.1_
  - [x] 2.5 Property test P4 (pure part): `merge_status` applied twice with the same row equals once. _Requirements: 1.1, 8.2_

- [x] 3. Evidence records (`records.py`, pure)
  - `make_id`, `record_from_evidence_source`, `records_from_papers`, `validate_records` with the
    error codes of design §4.5 (cycle search, `no_cadence`, `rule_without_basis`).
  - [x] 3.1 Property test P13 (pure part): valid sets accepted; each single defect gives its code. _Requirements: 4.1, 4.4, 4.5, 2.1_
  - [x] 3.2 Property test P14 (pure part): ids independent of file order, run id and dates; distinct triples give distinct ids. _Requirements: 4.2, 4.3_

- [x] 4. Citability, rule gate, line and item view (`citability.py`, `gate.py`, `line.py`, `view.py`, `IntegritySnapshot.version`)
  - Verdicts, `roots`, `cite`, `keep_output` (design §4.2); `rule_gate` (§4.4); `build_line`,
    `build_item` with the closed code set (§4.6); snapshot version over canonical JSON lines (§4.7).
  - [x] 4.1 Property test P1: no retracted-only backing, against the path-enumeration reference. _Requirements: 1.3, 5.2, 5.4_
  - [x] 4.2 Property test P2: unknown, unchecked and DOI-less records are never shown as `ok`. _Requirements: 1.5, 3.2, 5.3_
  - [x] 4.3 Property test P3: setting one record to `retracted` only shrinks citable ids, kept outputs and enabled rules. _Requirements: 1.3, 5.5, 6.2_
  - [x] 4.4 Property test P9: verdicts equal the reference for any order; terminates on cyclic graphs. _Requirements: 5.2_
  - [x] 4.5 Property test P10: rule gate (enabled iff a citable source; reasons; monotonicity; order and repetition independence). _Requirements: 6.1–6.5_
  - [x] 4.6 Property test P11: the integrity line equals an independent recount; `no_retracted_used` exactly when no used root is retracted. _Requirements: 3.1_
  - [x] 4.7 Property test P12: all notices listed, newest first, with `notice_url`; roots carry the notices of what a record rests on. _Requirements: 1.4, 3.2_
  - [x] 4.8 Property test P18 (version part): equal snapshots give equal versions; any one-field change gives a different version. _Requirements: 8.4_
  - [x] 4.9 Example test: PIPC case from the stored Crossref values (`corrected`, notice `10.1007/s41999-025-01378-7`, `correction`, `publisher`, 2025-12-18) is citable and its notice shows on the dataset and on a synthetic `rule:pipc:12`; adding a retraction notice excludes it and disables the rule. _Requirements: 1.4, 3.2, 6.2_

- [x] 5. Drug-resolution uses the shared freshness rule (DP17)
  - Migration `0003_source_cadence`: `res_source_version.cadence_days integer NULL`. The
    resolution loader reads `pipelines/sources.toml` with `integrity.registry.parse_sources`,
    stores each source's cadence in `res_source_version`, and adds the cadences to the dataset
    version. `service._notices` calls `integrity.freshness.freshness()` instead of the constant
    `STALE_AFTER`; a missing cadence on `titck` or `openfda_ndc` gives the notice (cannot be
    judged, so it is shown). Update drug-resolution requirements (Req 7.2), design §4.7 and DP18.
  - [x] 5.1 Update the existing drug-resolution tests (cadence in `resolution_db.inputs`; stale at 15 days, fresh at 14, for the two weekly sources). _Requirements: 2.1, 2.2 (drug-resolution 7.2)_
  - [x] 5.2 Example test: no `STALE_AFTER` constant remains in `janus/resolution/`; the notice follows a changed cadence. _Requirements: 2.1_

- [x] 6. Checkpoint: pure core
  - All lint, format, type-check and test steps green (`apps/api`: ruff, ruff format, pyright
    strict, pytest with `HYPOTHESIS_PROFILE=ci`). The medical-language and log guards pass on
    the new files. Commit, push, confirm CI passes.

- [x] 7. Pipeline change: paper list as a DOI input (`pipelines/janus_pipelines/jobs/retractions.py`)
  - `collect_dois` also reads `data/evidence_papers.csv`; DOIs normalised and de-duplicated; a
    missing file is an empty list; a malformed row fails the run. Schema `retractions-1` and
    output rows unchanged.
  - Update `data-pipelines` Req 9.1 and design §5.5 (second DOI input).
  - [x] 7.1 Property test (pipelines): the collected DOIs are the normalised union of artifact DOIs and paper-list DOIs, without repeats, whatever the order. _Requirements: 1.2 (data-pipelines 9.1)_
  - [x] 7.2 Example tests (pipelines): empty file, missing file, bad DOI fails the run. _Requirements: 1.2_

- [x] 8. Migration, repository and loader (`migrations/versions/0004_evidence_integrity.py`, `repository.py`, `load.py`)
  - Tables of design §3.2 with CHECK constraints and downgrade; `load_snapshot`; the loader of
    design §5.1 (artifact checks, hash of the `retractions` rows, validation, `merge_status`
    against stored state, change log, one transaction, `LOCK TABLE`); `register_records`;
    CLI; `write_tx` boundary test allows `integrity/load.py`; `integrity_load` log line with
    counts only.
  - `tests/integrity_db.py`: synthetic artifact directories (Parquet via DuckDB, manifests with
    correct hashes, `evidence_source.json`).
  - [x] 8.1 Property test P4 (database part): loading the same artifacts twice leaves every table and the version identical and adds no change rows. _Requirements: 1.1, 8.2, 8.4_
  - [x] 8.2 Property test P13 (database part): a refused record set changes nothing. _Requirements: 4.1_
  - [x] 8.3 Property test P14 (database part): a new run of the same source keeps ids and updates the snapshot date; no record is deleted. _Requirements: 4.2_
  - [x] 8.4 Property test P15: the status-change log has one row per real change; `changes` ordering, `since` and `limit`. _Requirements: 3.3_
  - [x] 8.5 Property test P16: any sequence of good, refused and failing loads leaves the state of the last good load. _Requirements: 8.1_
  - [x] 8.6 Example tests: upgrade → downgrade → upgrade gives an identical schema (0003 and 0004); hash mismatch refused; `needs_review` artifact without promotion refused; DOI record not in the artifact is stored `unknown / not_yet_checked` and reported; PIPC load gives status `corrected` with its notice. _Requirements: 1.2, 8.1, 8.3_

- [x] 9. Service and routes (`service.py`, `router.py`, wiring in `main.py`)
  - `POST /evidence/resolve` and `POST /evidence/changes` on `medical_router()` with their own
    body validation (field names only); fixed error codes `invalid_request`,
    `integrity_unavailable`; `today()` hook for tests; disclaimer on every response.
  - [x] 9.1 Property test P17: nothing loaded → 503 and nothing citable; loaded → unregistered ids are `not_registered`, 200. _Requirements: 7.4_
  - [x] 9.2 Property test P18 (route part): identical bytes for repeated calls and any order or repetition of ids. _Requirements: 7.5_
  - [x] 9.3 Property test P19: routes are stateless, send `no-store`, log no id, DOI or notice DOI; 422 bodies echo nothing. _Requirements: 7.6, 8.5_
  - [x] 9.4 Property test P20: request validation near misses; closed vocabularies; no forbidden phrase in any response. _Requirements: 7.1–7.3, 7.6_
  - [x] 9.5 Example tests: `classify(app)` passes with the new routes; codes are not accepted in a path or query string (404/405); the shared freshness rule gives 14 days for `titck` and `openfda_ndc` (DP17). _Requirements: 2.2, 8.5_

- [x] 10. Checkpoint: API end to end
  - All lint, format, type-check and test steps green, including property tests and database
    tests against PostgreSQL 16; commit, push, confirm CI passes.
  - Locally: `janus-pipelines run retractions` (reads the PIPC DOI), `python -m
    janus.integrity.load`, `docker compose up`; `POST /evidence/resolve` with `dataset:pipc`
    returns status `corrected`, the correction notice with its link, `citable`, freshness
    `current`, and an integrity line with one source and `no_retracted_used`; `POST
    /evidence/changes` lists nothing before a second load and shows the first sighting only in
    the database; API and Postgres logs show no evidence id or DOI.
  - `test_integrity_real_artifacts.py` green locally (skipped in CI).
  - _Requirements: 1.4, 3.1, 3.2, 7.1, 8.5_

- [x] 11. Contract and documentation
  - Record the rule-gate contract (design §4.4, §10) in `cascade-engine/requirements.md` open
    items, as drug-resolution did for `rule_input`.
  - Note the new integrity data in `data/README.md`; update `docs/kiro-usage.md` after the final
    checkpoint (task 12).
  - _Requirements: 6.6_

- [x] 12. Final checkpoint
  - All steps green locally and in CI; commit, push, confirm CI passes.
  - Record final numbers (records, statuses, tests) and remaining open items in design §10 and
    append a dated entry to `docs/kiro-usage.md` (spec refinement, counterexamples found by the
    property tests and their fixes).
  - Note for `cascade-engine`: load the snapshot once per request, gate every rule, put only
    `gate.usable` into evidence ids, carry `integrity_version`.
  - _Requirements: 6.6, 8.4_
