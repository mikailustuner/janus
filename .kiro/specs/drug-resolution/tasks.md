# Implementation Plan: Drug Resolution, Phase 1 (Türkiye and United States)

> Scope: `apps/api` resolution core, `tr` and `us` adapters, loader, routes; the `titck-2` and
> `us_ndc-2` pipeline changes (design §5.1). EU criteria (**[Phase 2: …]**) and **[Client: experience spec]**
> criteria have no tasks here. Property numbers refer to design.md §8. Owner decisions of
> 2026-11-07 applied (design §9). Execution stops after task 7 so the owner can review the
> combination-code rule file (DP3).
> No TİTCK data in the repository, fixtures, test output or logs; tests use synthetic data and
> sentinel values.

- [x] 1. Groundwork and fact checks
  - Add `duckdb` to `apps/api` (DP15); `uv lock`; confirm arm64 and amd64 wheels.
  - `Settings`: `JANUS_DATA_DIR` (loader only); add to `.env.example` if missing.
  - Confirm and record in design §10: GS1 AI table and predefined lengths; NDC GTIN indicator
    digits (GS1 US guideline); `pg_trgm` available in `postgres:16`.
  - `tests/resolution_strategies.py`: GTIN, element-string, NDC and synthetic-source strategies.
  - _Requirements: 1.1, 3.1, 9.1_

- [x] 2. GS1 parser (`janus/resolution/gs1.py`, pure)
  - FNC1 and parenthesised forms, symbology identifiers, AI table, duplicate-AI check, bare
    GTIN-8/12/13/14, mod-10 check digit, expiry with GS1 century rule; serial and lot dropped
    (design §4.5).
  - [x] 2.1 Property test P1: FNC1 and parenthesised forms parse identically. _Requirements: 1.1_
  - [x] 2.2 Property test P2: any corrupted check digit is rejected; padded short GTINs accepted. _Requirements: 1.2_
  - [x] 2.3 Property test P3: build → parse returns the same GTIN and expiry. _Requirements: 1.1, 1.3_
  - [x] 2.4 Property test P9: expiry `DD = 00`, impossible dates, century rule. _Requirements: 1.3_

- [x] 3. NDC handling (`janus/resolution/ndc.py`, pure)
  - Input forms and prefixes, layouts of plain 10 digits, canonical 11-digit and 9-digit
    product forms, `ndc_from_gtin` (design §4.4).
  - [x] 3.1 Property test P4: all forms of one NDC give the same canonical key. _Requirements: 3.2_
  - [x] 3.2 Property test P11: NDC GTIN round trip for indicator digits 0–8. _Requirements: 3.1_
  - [x] 3.3 Property test P12: accepted iff a listed form; plain 10 digits give 1–3 keys. _Requirements: 3.2_

- [x] 4. Checkpoint: parsers
  - All lint, format, type-check and test steps green (`apps/api`: ruff, ruff format, pyright
    strict, pytest with `HYPOTHESIS_PROFILE=ci`). Commit, push, confirm CI passes.

- [ ] 5. Pipeline changes `titck-2` and `us_ndc-2` (`pipelines/janus_pipelines/jobs/titck.py`, `us_ndc.py`)
  - Invalid-barcode rows output as name-only rows (`barcode = null`, `name_only = true`), metric
    `name_only_rows`; parenthesis-aware `split_ingredients`; schema version `titck-2`.
  - `us_ndc-2`: add `route` (list, as published) and `dosage_form` (as published) (DP20).
  - Update `data-pipelines` requirements (Req 6.4, 6.6, 8.3), design §5.2/§5.4 and its tests.
  - Re-run `titck` (`--input <local list>`) and `us_ndc` locally; record counts.
  - [ ] 5.1 Property tests (data-pipelines) P4, P6 and P12 updated and green: row accounting with name-only rows; metrics recount; characters kept, no split inside parentheses. _Requirements: 2.3 (drug-resolution); data-pipelines 6.4, 6.6_
  - [ ] 5.2 Example test (data-pipelines): `us_ndc` rows carry `route` and `dosage_form` as published; records without them get an empty list / null. _Requirements: data-pipelines 8.3_

- [ ] 6. Name normalisation (`janus/resolution/names.py`, pure)
  - `fold`, `strip_salts` (Turkish and English word lists, extended with the measured gaps:
    medoxomil, acetonide, bitartrate, oxalate, …), `spelling_key`, `RULES_VERSION` (design §5.2).
  - Pharmacologist agent reviews the word lists and rewrite rules.
  - [ ] 6.1 Property test P6: `fold`, `strip_salts∘fold`, `spelling_key∘fold` are idempotent; never empty. _Requirements: 5.3, 5.7_

- [ ] 7. ATC codes, combination check and route map (`janus/resolution/atc.py`, `data/atc_combination_rules.csv`, `data/route_atc_groups.csv`)
  - `is_ingredient_level`, `CombinationRules`, `is_combination` (exception → rule file → numbering
    rule → TİTCK observation), `ingredient_codes`, `select_codes` (design §5.4, §5.5).
  - First rule file drafted by the pharmacologist agent from the observed TİTCK multi-ingredient
    codes and the WHO conventions; first route map drafted by the pharmacologist agent from the
    openFDA route values (DP20). **Stop after this task** and show the owner the rule file with
    a short summary of how it was derived; continue only after the review.
  - [ ] 7.1 Property test P17: every selected code is well formed and in the ingredient's own `ingredient_codes`; malformed published codes never selected. _Requirements: 5.1_
  - [ ] 7.2 Property test P7 (pure part): no selected code is a combination code; a forced leak raises `CombinationCodeLeak`. _Requirements: 5.2_
  - [ ] 7.3 Property test P24: route-based selection keeps only allowed codes, never falls back, `all_codes` without a mapped route. _Requirements: 5.1, 5.4_
  - [ ] 7.4 Example tests: a US topical betamethasone product keeps `D07…` codes and not `H02AB01`; AMLIPIN fields → amlodipine `C08CA01`, lisinopril `C09AA03`; `C09BB03` only as published code. _Requirements: 5.1, 5.2_

- [ ] 8. Matching and dataset preparation (`matching.py`, `prepare.py`, `canonical.py`, `data/ingredient_synonyms.csv`)
  - `NameIndex.build`, ladder steps 0–6, ambiguity, `detect_unsplit`; `prepare_dataset` producing
    products, codes, ingredients, name index, combination audit and coverage report; final
    leak guard; canonical hash with the golden vector shared with `pipelines/`.
  - [ ] 8.1 Property test P16: first matching step wins; ambiguity keeps all keys; order independent; unsplit names flagged. _Requirements: 5.3_
  - [ ] 8.2 Property test P5: decomposition invariance for synthetic A + B, A, B. _Requirements: 5.1_
  - [ ] 8.3 Property test P7 (prepare part): no combination code in any prepared ingredient, incl. unsplit names on single-ingredient rows. _Requirements: 5.2_
  - [ ] 8.4 Property test P18: one entry per published ingredient, in order; non-mapped entries have a reason and no `rule_input`. _Requirements: 5.4_
  - [ ] 8.5 Example test: golden canonical-hash vector equals the `pipelines/` value. _Requirements: 9.1_

- [ ] 9. Checkpoint: preparation and measured coverage
  - All lint, format, type-check and test steps green; commit, push, confirm CI passes.
  - Run `prepare_dataset` on the local artifacts (no database needed); write the coverage report
    to `$JANUS_DATA_DIR/resolution/`; copy the summary numbers (no TİTCK names) into design §1
    and compare with the DP22 targets. Tune salt words / synonyms only through reviewed data
    changes; report what changed.
  - _Requirements: 2.5, 5.6_

- [ ] 10. Migration and loader (`migrations/versions/0002_resolution.py`, `janus/resolution/load.py`)
  - Tables and indexes of design §3.3 (`pg_trgm`), downgrade drops them; loader steps of design
    §6.1 (DuckDB read, manifest and hash check, dataset version, one transaction, retire old,
    `--activate`); `read_only_tx` with `REPEATABLE READ, READ ONLY`; import-boundary test allows
    `resolution/load.py` (DP16).
  - [ ] 10.1 Property test P23: any sequence of good, refused and failing loads leaves exactly one complete dataset current. _Requirements: 9.1, 9.2_
  - [ ] 10.2 Property test P8 (load part): the same artifacts give the same dataset version and product ids. _Requirements: 9.4, 7.3_
  - [ ] 10.3 Example tests: upgrade → downgrade → upgrade gives identical schema; source versions recorded from `evidence_source.json`; a hash mismatch is refused. _Requirements: 9.1, 9.3_

- [ ] 11. Adapters, repository and service (`janus/regions/base.py`, `tr/adapter.py`, `us/adapter.py`, `resolution/repository.py`, `service.py`, `model.py`)
  - `RegionAdapter`, TİTCK and openFDA adapters, dispatch and hints, region-not-available notice,
    candidate order, name search with pure `rank`, not-found vs unavailable, staleness notice,
    provenance, `rule_input` (design §3.2, §4).
  - [ ] 11.1 Property test P21: adapter dispatch with and without override. _Requirements: 1.5_
  - [ ] 11.2 Property test P13: all rows for a duplicated key, in stable order, for every input form. _Requirements: 2.1, 3.1, 6.2_
  - [ ] 11.3 Property test P14: name-only rows never by barcode, always by exact name. _Requirements: 2.3_
  - [ ] 11.4 Property test P15: search invariant to case, Turkish i's and diacritics; `rank` order independent; at most `limit`. _Requirements: 2.4, 3.3_
  - [ ] 11.5 Property test P19: 503 when not loaded, empty 200 only when loaded. _Requirements: 6.2, 7.1_
  - [ ] 11.6 Property test P20: every `SourceRef` belongs to the current dataset. _Requirements: 7.2_
  - [ ] 11.7 Property test P8 (request part): identical JSON for repeated requests. _Requirements: 7.3_

- [ ] 12. Routes and error handling (`janus/resolution/router.py`, wiring in `main.py`)
  - `POST /resolve/scan`, `/resolve/ndc`, `/resolve/search`, `/resolve/products` on
    `medical_router()`; fixed error codes; 422 without `input`/`ctx` on medical routes.
  - [ ] 12.1 Property test P10: sentinel serial and lot never in response, logs or database, for valid and invalid scans. _Requirements: 1.4, 8.3, 8.4_
  - [ ] 12.2 Property test P22: the four routes are stateless, send `no-store`, and log no input value (privacy harness). _Requirements: 8.1–8.3_
  - [ ] 12.3 Example tests: `classify(app)` passes with the new routes; codes in a query string or path are not accepted (405/404, no lookup). _Requirements: 8.2_

- [ ] 13. Checkpoint: API end to end
  - All lint, format, type-check and test steps green, incl. property tests and database tests
    against PostgreSQL 16; commit, push, confirm CI passes.
  - Locally: `janus-pipelines run` for the three sources, `python -m janus.resolution.load`,
    `docker compose up`; `POST /resolve/scan` with the AMLIPIN GTIN `08680199094206` returns
    amlodipine `C08CA01` and lisinopril `C09AA03`; a duplicated barcode returns every row; a
    name-only product is found by name; an NDC from a label resolves. API and Postgres logs show
    no codes or names.
  - `test_real_artifacts.py` green locally (skipped in CI).
  - _Requirements: 2.1, 2.3, 3.2, 5.2, 8.3_

- [ ] 14. Final checkpoint
  - All steps green locally and in CI; commit, push, confirm CI passes.
  - Record final coverage numbers and remaining open items in design §1/§10 and append a dated
    entry to `docs/kiro-usage.md` (spec refinement, counterexamples found by property tests and
    their fixes).
  - Note for `cascade-engine`: read codes only through `rule_input`; `all_codes` is less specific.
  - _Requirements: 5.6, 7.2, 10.1_
