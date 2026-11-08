# Implementation Plan: Drug Resolution, Phase 1 (Türkiye and United States) and Phase 2 (EU adapters and name rules)

> **Phase 2 tasks 15–28 are at the end of this file** (planned 2026-11-08, not started).
> Phase 1 tasks 1–14 are done.
>
> Scope (Phase 1): `apps/api` resolution core, `tr` and `us` adapters, loader, routes; the `titck-2` and
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

- [x] 5. Pipeline changes `titck-2` and `us_ndc-2` (`pipelines/janus_pipelines/jobs/titck.py`, `us_ndc.py`)
  - Invalid-barcode rows output as name-only rows (`barcode = null`, `name_only = true`), metric
    `name_only_rows`; parenthesis-aware `split_ingredients`; schema version `titck-2`.
  - `us_ndc-2`: add `route` (list, as published) and `dosage_form` (as published) (DP20).
  - Update `data-pipelines` requirements (Req 6.4, 6.6, 8.3), design §5.2/§5.4 and its tests.
  - Re-run `titck` (`--input <local list>`) and `us_ndc` locally; record counts.
  - [x] 5.1 Property tests (data-pipelines) P4, P6 and P12 updated and green: row accounting with name-only rows; metrics recount; characters kept, no split inside parentheses. _Requirements: 2.3 (drug-resolution); data-pipelines 6.4, 6.6_
  - [x] 5.2 Example test (data-pipelines): `us_ndc` rows carry `route` and `dosage_form` as published; records without them get an empty list / null. _Requirements: data-pipelines 8.3_

- [x] 6. Name normalisation (`janus/resolution/names.py`, pure)
  - `fold`, `strip_salts` (Turkish and English word lists, extended with the measured gaps:
    medoxomil, acetonide, bitartrate, oxalate, …), `spelling_key`, `RULES_VERSION` (design §5.2).
  - Pharmacologist agent reviews the word lists and rewrite rules.
  - [x] 6.1 Property test P6: `fold`, `strip_salts∘fold`, `spelling_key∘fold` are idempotent; never empty. _Requirements: 5.3, 5.7_

- [x] 7. ATC codes, combination check and route map (`janus/resolution/atc.py`, `data/atc_combination_rules.csv`, `data/route_atc_groups.csv`)
  - `is_ingredient_level`, `CombinationRules`, `is_combination` (exception → rule file → numbering
    rule → TİTCK observation), `ingredient_codes`, `select_codes` (design §5.4, §5.5).
  - First rule file drafted by the pharmacologist agent from the observed TİTCK multi-ingredient
    codes and the WHO conventions; first route map drafted by the pharmacologist agent from the
    openFDA route values (DP20). **Stop after this task** and show the owner the rule file with
    a short summary of how it was derived; continue only after the review.
  - [x] 7.1 Property test P17: every selected code is well formed and in the ingredient's own `ingredient_codes`; malformed published codes never selected. _Requirements: 5.1_
  - [x] 7.2 Property test P7 (pure part): no selected code is a combination code; a forced leak raises `CombinationCodeLeakError`. _Requirements: 5.2_
  - [x] 7.3 Property test P24: route-based selection keeps only allowed codes, never falls back, `all_codes` without a mapped route. _Requirements: 5.1, 5.4_
  - [x] 7.4 Example tests: a US topical betamethasone product keeps `D07…` codes and not `H02AB01`; AMLIPIN fields → amlodipine `C08CA01`, lisinopril `C09AA03`; `C09BB03` only as published code. _Requirements: 5.1, 5.2_

- [x] 8. Matching and dataset preparation (`matching.py`, `prepare.py`, `canonical.py`, `data/ingredient_synonyms.csv`)
  - `NameIndex.build`, ladder steps 0–6, ambiguity, `detect_unsplit`; `prepare_dataset` producing
    products, codes, ingredients, name index, combination audit and coverage report; final
    leak guard; canonical hash with the golden vector shared with `pipelines/`.
  - [x] 8.1 Property test P16: first matching step wins; ambiguity keeps all keys; order independent; unsplit names flagged. _Requirements: 5.3_
  - [x] 8.2 Property test P5: decomposition invariance for synthetic A + B, A, B. _Requirements: 5.1_
  - [x] 8.3 Property test P7 (prepare part): no combination code in any prepared ingredient, incl. unsplit names on single-ingredient rows. _Requirements: 5.2_
  - [x] 8.4 Property test P18: one entry per published ingredient, in order; non-mapped entries have a reason and no `rule_input`. _Requirements: 5.4_
  - [x] 8.5 Example test: golden canonical-hash vector equals the `pipelines/` value. _Requirements: 9.1_

- [x] 9. Checkpoint: preparation and measured coverage
  - All lint, format, type-check and test steps green; commit, push, confirm CI passes.
  - Run `prepare_dataset` on the local artifacts (no database needed); write the coverage report
    to `$JANUS_DATA_DIR/resolution/`; copy the summary numbers (no TİTCK names) into design §1
    and compare with the DP22 targets. Tune salt words / synonyms only through reviewed data
    changes; report what changed.
  - _Requirements: 2.5, 5.6_

- [x] 10. Migration and loader (`migrations/versions/0002_resolution.py`, `janus/resolution/load.py`)
  - Tables and indexes of design §3.3 (`pg_trgm`), downgrade drops them; loader steps of design
    §6.1 (DuckDB read, manifest and hash check, dataset version, one transaction, retire old,
    `--activate`); `read_only_tx` with `REPEATABLE READ, READ ONLY`; import-boundary test allows
    `resolution/load.py` (DP16).
  - [x] 10.1 Property test P23: any sequence of good, refused and failing loads leaves exactly one complete dataset current. _Requirements: 9.1, 9.2_
  - [x] 10.2 Property test P8 (load part): the same artifacts give the same dataset version and product ids. _Requirements: 9.4, 7.3_
  - [x] 10.3 Example tests: upgrade → downgrade → upgrade gives identical schema; source versions recorded from `evidence_source.json`; a hash mismatch is refused. _Requirements: 9.1, 9.3_

- [x] 11. Adapters, repository and service (`janus/regions/base.py`, `tr/adapter.py`, `us/adapter.py`, `resolution/repository.py`, `service.py`, `model.py`)
  - `RegionAdapter`, TİTCK and openFDA adapters, dispatch and hints, region-not-available notice,
    candidate order, name search with pure `rank`, not-found vs unavailable, staleness notice,
    provenance, `rule_input` (design §3.2, §4).
  - [x] 11.1 Property test P21: adapter dispatch with and without override. _Requirements: 1.5_
  - [x] 11.2 Property test P13: all rows for a duplicated key, in stable order, for every input form. _Requirements: 2.1, 3.1, 6.2_
  - [x] 11.3 Property test P14: name-only rows never by barcode, always by exact name. _Requirements: 2.3_
  - [x] 11.4 Property test P15: search invariant to case, Turkish i's and diacritics; `rank` order independent; at most `limit`. _Requirements: 2.4, 3.3_
  - [x] 11.5 Property test P19: 503 when not loaded, empty 200 only when loaded. _Requirements: 6.2, 7.1_
  - [x] 11.6 Property test P20: every `SourceRef` belongs to the current dataset. _Requirements: 7.2_
  - [x] 11.7 Property test P8 (request part): identical JSON for repeated requests. _Requirements: 7.3_

- [x] 12. Routes and error handling (`janus/resolution/router.py`, wiring in `main.py`)
  - `POST /resolve/scan`, `/resolve/ndc`, `/resolve/search`, `/resolve/products` on
    `medical_router()`; fixed error codes; 422 without `input`/`ctx` on medical routes.
  - [x] 12.1 Property test P10: sentinel serial and lot never in response, logs or database, for valid and invalid scans. _Requirements: 1.4, 8.3, 8.4_
  - [x] 12.2 Property test P22: the four routes are stateless, send `no-store`, and log no input value (privacy harness). _Requirements: 8.1–8.3_
  - [x] 12.3 Example tests: `classify(app)` passes with the new routes; codes in a query string or path are not accepted (405/404, no lookup). _Requirements: 8.2_

- [x] 13. Checkpoint: API end to end
  - All lint, format, type-check and test steps green, incl. property tests and database tests
    against PostgreSQL 16; commit, push, confirm CI passes.
  - Locally: `janus-pipelines run` for the three sources, `python -m janus.resolution.load`,
    `docker compose up`; `POST /resolve/scan` with the AMLIPIN GTIN `08680199094206` returns
    amlodipine `C08CA01` and lisinopril `C09AA03`; a duplicated barcode returns every row; a
    name-only product is found by name; an NDC from a label resolves. API and Postgres logs show
    no codes or names.
  - `test_real_artifacts.py` green locally (skipped in CI).
  - _Requirements: 2.1, 2.3, 3.2, 5.2, 8.3_

- [x] 14. Final checkpoint
  - All steps green locally and in CI; commit, push, confirm CI passes.
  - Record final coverage numbers and remaining open items in design §1/§10 and append a dated
    entry to `docs/kiro-usage.md` (spec refinement, counterexamples found by property tests and
    their fixes).
  - Note for `cascade-engine`: read codes only through `rule_input`; `all_codes` is less specific.
  - _Requirements: 5.6, 7.2, 10.1_

---

# Phase 2: EU adapters (`eu_fr`, `eu_es`, `eu_name`) and name rules

> Planned 2026-11-08. Requirements 4, 5.8–5.11, 9.7–9.9, 12, 13, 14; design §11–§19; properties
> P27–P49. Execution rules as in Phase 1: run tasks in order; at each checkpoint run ruff, ruff
> format, pyright strict and pytest with `HYPOTHESIS_PROFILE=ci` (database tests against real
> PostgreSQL 16, `alembic upgrade head` on `janus_test` first), then commit, push and confirm CI.
> **One stop:** task 20 (rule review, owner); the imipenem choice (task 27) was made on
> 2026-11-08 (option (b)). Execution started 2026-11-08 with tasks 15–20. Rule data
> (word lists, anion-acid table, French route rows, synonyms) stays at the Phase 1 content until
> task 21. No TİTCK file, no `.data` content and no source name list is committed; coverage files
> and the per-name sidecar stay in `$JANUS_DATA_DIR/resolution/`. Counts in every report; ε and k
> unchanged. Append a dated entry to `docs/kiro-usage.md` in task 28.
> Owner answers received 2026-11-08: O1 option (b), O2 approved (design §19).

- [x] 15. Baseline and groundwork
  - Copy the Phase 1 `fold`, `strip_salts`, `spelling_key`, `map_name` and word lists verbatim into
    `tests/frozen_names.py` (the regression oracle of P34); extend `resolution_strategies.py` with
    BDPM-like presentations (links with `FT`/`SA`, homeopathic names, French routes, name-only),
    Nomenclátor-like presentations (NTIN/GTIN lists, shared and mismatched values, published ATC,
    no ingredient) and word strategies per language.
  - Write the **baseline coverage** (Req 13.1) with the unchanged Phase 1 code: TR and US from
    `prepare_dataset`, FR and ES from throw-away builders that produce the same `_Raw` shape as
    design §14.2–§14.3 (they become `prepare_eu` in task 22 and the baseline is re-created from the
    same functions then), FAERS from the current counts build. Files go to
    `$JANUS_DATA_DIR/resolution/coverage-baseline-<dataset 8>.json` with a per-name sidecar.
    Record the summary counts (no names) in design §11 beside the prototype figures and report any
    difference.
  - _Requirements: 13.1_
  - **Done 2026-11-08.** Frozen oracle: `tests/frozen_names.py` and `tests/frozen_matching.py`. The
    BDPM-like and Nomenclátor-like synthetic sources are created by the tasks that use them (22, 23);
    the pure ingredient builders `prepare_eu.bdpm_ingredients` / `cima_ingredients` (with P29, tests
    in `test_eu_prepare_properties.py`, ticked as 22.1) were written here because the baseline needs
    them. The baseline tool is `janus/resolution/coverage_snapshot.py` (`snapshot` and `compare`;
    tests `test_coverage_snapshot_properties.py`); it replaces the throw-away builders, so the
    baseline and the "after" use one code path (DP40). Baseline `coverage-baseline-f55a79cf.json`
    in `.data/resolution/` (counts in design §11).

- [x] 16. Parser, model and adapter interface
  - `gs1.py`: `Gs1Data.national_code` from AI 712 (7 digits or dropped); serial and lot unchanged.
    `regions/base.py`: `Region` adds `EU`, `Country`, `KeyGroup`, `RegionAdapter.key_groups`,
    new `ProductKey` kinds, the reviewed GS1 prefix table (FR, ES, DE; verify the three ranges
    against the GS1 prefix list, and if gs1.org is not readable record "not verified" in the
    pre-launch checklist). `resolution/model.py`: `Region`, candidate-id pattern, `country`,
    `status_published`, `matched_by` and `Notice` additions (`no_open_product_database`,
    `Notice.country`). `cascades/schemas.py`: candidate pattern. TR and US adapters return one key
    group; `service` uses `key_groups`.
  - [x] 16.1 Extend P1 and P3: AI 712 is kept as `national_code` in both element-string forms and never leaks into `ScanInfo`; a bad AI 712 is dropped and the GTIN still resolves; lot stays dropped. _Requirements: 1.1, 1.4_
  - [x] 16.1a Property test P50 (owner decision 2026-11-08): AI (21) in any element string is rejected by the parser and by `/resolve/scan` with 422 `gs1_serial_not_accepted`, no lookup, no echo; P10 and the earlier serial/lot tests are updated (a valid scan with a serial is now a 422; lot is still dropped). _Requirements: 1.4, 8.3_
  - [x] 16.2 Re-run P21 (adapter dispatch) with `key_groups` stubs and the `EU` override. _Requirements: 1.5_
  - [x] 16.3 Example test: TR and US JSON for fixed inputs differs from the Phase 1 golden only by the additive fields. _Requirements: 4.5_
  - _Requirements: 1.1, 1.4, 1.5, 4.5_

- [x] 17. Migration `0008_eu_resolution`
  - Widen `res_product_code_kind`; add `res_product.status_published text[]`; downgrade deletes the
    datasets that hold EU kinds or products and restores the check (design §14.5).
  - [x] 17.1 Example test: upgrade → downgrade → upgrade gives an identical schema; a dataset with EU rows is removed by the downgrade and the old check holds again. _Requirements: 9.2_

- [x] 18. Language-aware name functions, mechanism only (no new rule data enabled)
  - `name_lists.py` holds the Phase 1 lists as the `base` set plus empty per-language sets and
    connector sets; `names.py`: `strip_salts(·, lang)`, `spelling_key(·, lang)` with the Spanish
    final-vowel and acid-word-order rules written but driven by the lists, connector removal,
    `RULES_VERSION`; `anion_acid.py` (table class, CSV loader with the checks of Req 12.7, empty
    table committed); `matching.py`: `lang` replaces `turkish`, steps `anion_acid` and
    `biologic_suffix`, unsplit guard. The suffix step is gated by a switch in `name_lists.py`
    (`BIOLOGIC_SUFFIX_ENABLED = False`, part of `RULES_VERSION`) that task 21 turns on after the
    review; tests switch it on explicitly. The unsplit guard does not change a Phase 1 result
    (it only ignores spans of salt and connector words, which are the Phase 1 lists for `tr`/`en`
    and empty for `fr`/`es`). Update the call sites (`prepare`, `faers_build.map_names`, tests) to
    pass `lang`.
  - [x] 18.1 Property test P34: idempotence and non-empty for every language; equality with `frozen_names.py` for `tr`/`en` on names without Phase 2 words; `RULES_VERSION` changes with any list. _Requirements: 12.1, 12.2, 5.7_
  - [x] 18.2 Property test P35: salt, hydrate and connector invariance, in the word order of each language, using test-only lists. _Requirements: 12.2, 12.3_
  - [x] 18.3 Property test P36: counter-ion substances and prodrug esters stay apart. _Requirements: 12.4_
  - [x] 18.4 Property test P37: anion-acid step lands only on existing keys, never changes an earlier hit; the table loader refuses bad rows. _Requirements: 12.6, 12.7_
  - [x] 18.5 Property test P38: biologic suffix, exact conditions and near misses. _Requirements: 12.8, 12.6_
  - [x] 18.6 Property test P39: unsplit guard; P16 still passes unchanged. _Requirements: 12.12, 5.3_
  - [x] 18.7 Property test P40: parts of combination strings are not guessed. _Requirements: 12.9_
  - [x] 18.8 Regression: the whole Phase 1 suite (P1–P26) passes unchanged, and the dataset built from the real TİTCK and openFDA artifacts maps every name as before (local, counts only; no allowed difference: all Phase 2 rule data is still off, so the dataset
    differs from the Phase 1 one only in its version). _Requirements: 12.1, 12.11_

- [x] 19. Rule-impact report tool (`janus/resolution/name_rules_report.py`)
  - For each candidate word, table row and rule of design §15.2 and §15.4–§15.6: names and
    occurrences touched per source (TİTCK, openFDA, BDPM, Nomenclátor, FAERS), the mapped
    ingredient, the ATC agreement of §15.2 (five-character group against the published code of
    single-ingredient TİTCK and Nomenclátor products, with and without the word), names that would
    become ambiguous or change key. Writes `$JANUS_DATA_DIR/resolution/name-rules-<ruleset>.json`;
    prints counts only; refuses an output path inside the repository unless git-ignored.
  - [x] 19.1 Property test: the report's counts equal an independent recount on synthetic sources; a word that changes a mapped name's key is reported. _Requirements: 12.11, 13.3_
  - Run it on the real artifacts with the candidate lists of design §15.2; keep the file local.
  - _Requirements: 12.2, 12.11_

- [x] 20. **Review stop: name rules** (pharmacologist agent, then owner)
  - Run the pharmacologist agent (`agent://pharmacologist`, one self-contained prompt with the
    report path and the rules of Req 12). It writes
    `.kiro/specs/drug-resolution/name-rules-review.md` in the layout of
    `cascade-engine/mapping-review.md`: how the lists were derived; one table per language of
    words with names touched, ATC agreement, decision (accept / reject / needs owner) and reason;
    the anion-acid rows with the WHOCC lookup (URL and date, one page at a time, no index text
    copied); the French route rows (the 30 most frequent strings, 99.2 % of presentations) with
    allowed ATC prefixes; synonym proposals (pancrelipase parts and others); the names left
    unmapped on purpose (prodrugs with own INN, bare elements, vitamins and similar class words);
    the measured before/after counts per source. Check the sheet for forbidden phrases and for
    source names (none beyond public INNs).
  - **Stop.** Show the owner the sheet with a short summary of the numbers. Continue only after the
    owner's answers; record them in the sheet and in design §19.
  - _Requirements: 12.11_
  - **Status 2026-11-08: sheet written, waiting for the owner.** `name-rules-review.md` (734 lines,
    pharmacologist agent). Accepted set measured with the what-if tool: BDPM 67.6 → 81.9 %, Nomenclátor
    48.1 → 86.1 %, FAERS 84.0 → 86.6 %, TİTCK 84.6 % unchanged, openFDA Rx 91.7 → 92.4 % of
    occurrences; no mapped name changes to another key. Ten owner decisions in its Section 10. No rule
    data is enabled (checked: `name_lists.py`, `anion_acid_forms.csv`, the route map and the synonym
    file are unchanged). Task 21 starts only after the owner's answers.

- [x] 21. Enable the reviewed rule data
  - Turn on `BIOLOGIC_SUFFIX_ENABLED` if the owner accepted the rule. Put the accepted words into
    `name_lists.py`, the accepted rows into `data/anion_acid_forms.csv`,
    the French rows into `data/route_atc_groups.csv`, the accepted synonyms into
    `data/ingredient_synonyms.csv`; update `data/README.md` (derivation, date, re-review note).
  - [x] 21.1 Re-run P34–P40 with the real lists as the generators' source; the frozen-function regression (P34) is the guard for TR and US. _Requirements: 12.1–12.12_
  - [x] 21.2 Example tests from the review sheet: `CHLORHYDRATE DE TRAMADOL`, `AMLODIPINO BESILATO`, `MYCOPHENOLATE MOFETIL`, `INFLIXIMAB-DYYB`, `INSULIN GLARGINE-YFGN` map to their bases; `MAGNESIUM SALICYLATE` does not map to salicylic acid; `ARIPIPRAZOLE LAUROXIL` stays unmapped; `MALÉATE D'ÉNALAPRIL` is not `unsplit`. _Requirements: 12.4, 12.7, 12.8, 12.12_
  - Re-run the comparison of task 18.8 on TİTCK and openFDA; list changed names by kind (counts).
  - _Requirements: 12.1, 13.3_

- [x] 22. EU preparation and loader (`prepare_eu.py`, `prepare.py`, `load.py`)
  - `bdpm_products` (links, `FT` before `SA`, status, marketing end date, homeopathic marker) and
    `cima_products` (ingredient order, codes, published ATC, status); `prepare_dataset` takes the
    EU rows, uses `lang` per product, feeds the Nomenclátor's observed combination evidence only
    (DP34), builds EU name entries (region `EU`, de/fr/es labels) and the `eu_fr_bdpm` and
    `eu_es_cima` coverage sections. `load.py`: optional EU artifacts, schema and hash checks,
    `describe()` and the dataset version, `write_dataset` for the new kinds and `status_published`.
    Re-create the task 15 FR/ES baseline from `bdpm_products`/`cima_products` with the Phase 1
    ladder and confirm it equals the first baseline.
  - [x] 22.1 Property test P29: `FT` before `SA` per link, every line accounted for. _Requirements: 5.8_
  - [x] 22.2 Property test P41: French homeopathic products. _Requirements: 12.10, 5.11, 11.1_
  - [x] 22.3 Property test P42: French route selection. _Requirements: 5.9_
  - [x] 22.4 Property test P43: Nomenclátor published ATC selection. _Requirements: 5.10, 5.2_
  - [x] 22.5 Property test P45: coverage recount, homeopathic excluded, comparison lists changed names, a mapped name never changes key. _Requirements: 13.2, 13.3_
  - [x] 22.6 Property test P46: the dataset version follows every Phase 2 input. _Requirements: 9.8, 9.4_
  - [x] 22.7 Property test P47 (load part): any subset of sources loads; a present invalid EU artifact refuses the load and the previous dataset keeps serving. _Requirements: 9.7_
  - [x] 22.8 Re-run P5, P7, P17, P18 over French-like and Spanish-like sources (P44, pure part). _Requirements: 5.1, 5.2, 5.4_
  - _Requirements: 4.1, 4.2, 5.8–5.11, 9.7–9.9_

- [ ] 23. Adapters, repository, service and routes
  - `regions/eu_fr/adapter.py`, `eu_es/adapter.py`, `eu_name/adapter.py`; service changes of design
    §13 (`REGION_SOURCES`, key groups in order, sources a scan needs, `rule_inputs`, notices,
    staleness, name search with region `EU`); repository reads `status_published`; routes accept
    region `EU`.
  - [ ] 23.1 Property test P27: French key. _Requirements: 4.1_
  - [ ] 23.2 Property test P28: French lookups are complete; name-only rows. _Requirements: 4.1, 2.3_
  - [ ] 23.3 Property test P30: Spanish order of trust. _Requirements: 4.2_
  - [ ] 23.4 Property test P31: no external call (sockets blocked; import-graph test; extend the privacy harness's `assert_stateless`). _Requirements: 4.2, 7.1_
  - [ ] 23.5 Property test P32: no open database. _Requirements: 4.3, 6.2_
  - [ ] 23.6 Property test P33: EU name search by language and region. _Requirements: 4.4_
  - [ ] 23.7 Property test P47 (request part): a request that needs a missing EU source answers 503; Turkish and US requests on a dataset without EU data behave as in Phase 1; `rule_inputs` needs only the regions present. _Requirements: 6.2, 9.7_
  - [ ] 23.8 Re-run P13, P14, P19, P20, P21, P22 with EU sources (P44, database part). _Requirements: 2.1, 2.3, 6.2, 7.2, 8_
  - [ ] 23.9 Example tests: the stale-source notices for BDPM (60 days) and the Nomenclátor (14 days); a presentation with an empty ingredient list; the BDPM text is returned exactly as published (leading and trailing spaces, accents). _Requirements: 4.1, 4.2_
  - _Requirements: 1.5, 4.1–4.7, 6.2, 7.1_

- [ ] 24. Checkpoint: EU resolution end to end and coverage after
  - All lint, format, type-check and test steps green; commit, push, confirm CI passes.
  - Locally: `janus-pipelines` artifacts are current for all five sources; `python -m
    janus.resolution.load` (background, `nohup`); `docker compose up`. `POST /resolve/scan`: a
    real CIP13 from the BDPM as `0` + CIP13 returns the presentation with its `FT` ingredients and
    the BDPM date; a real NTIN from the Nomenclátor returns the presentation; a GTIN from its
    GTIN list returns it; a CN as AI 712 returns it labelled `ai_712`; a German-prefix GTIN gives
    the notice and no German candidate; `POST /resolve/search` with `region: "EU"` finds
    `tramadol`, `Tramadol`, `ácido acetilsalicílico` and `paracétamol`. API and Postgres logs show
    no codes or names. `test_eu_real_artifacts.py` green locally (skipped in CI).
  - Write the **after** coverage files and the comparison with the baseline (Req 13.1, 13.3); copy
    the summary counts into design §11/§17 (before/after table for TİTCK, openFDA, BDPM,
    Nomenclátor); compare with the targets of Req 13.4 and explain any miss.
  - _Requirements: 4.1–4.4, 13.1–13.4_

- [ ] 25. FAERS builder and the `faers_mapping_gap` decision
  - `faers_build.map_names(..., lang="en")`; `_candidate_impact` reduced to the parts-of-combination
    count; rebuild the counts file (background); compare the coverage report with the baseline
    (84.0 % of 6,201,428 occurrences; 80.5 % in suspect roles): occurrences mapped, reports with a
    mapped ingredient (1,252,900 of 1,510,804), names changed by kind.
  - Record the decision DP36 in `data-pipelines` design (open item 3 closed; DP34; Req 15.2 now
    says "`en` mode of the ladder"), `collective-memory` design §8.2 and its requirements'
    resolved-items section (no table, no `mapping_gap_possible`; the denominator sentence carries the
    limit), with the numbers of design §11/§16.3 and the new measured residual (re-run the
    whole-word-part scan on the new build). If the owner rejected the suffix or acid-form rules in
    task 20, stop here and write the table instead (design §16.3).
  - [ ] 25.1 Run the `data-pipelines` builder properties P33–P40 and the `collective-memory` suite unchanged; add one property: names `base-XXXX` in a generated artifact count under the base's key, once per report. _Requirements: data-pipelines 15.2, 15.4; drug-resolution 12.8_
  - _Requirements: 12.7, 12.8, 13.2_

- [ ] 26. Coverage report: EU bucket and `member_name_part` hints (`cascades/coverage.py`)
  - `bucket()` and the `present` / `cannot_fire_in` loops handle `EU`; the hint kind of design
    §16.4 with its fixed rule; update `cascade-engine` requirements (Req 8, added bullet) and
    design §7/§11 (the follow-up is done; counts of hints before and after on the real dataset).
  - [ ] 26.1 Property test P49 and the re-run of cascade-engine P22 with the EU bucket. _Requirements: cascade-engine 8.1–8.3_
  - Run `python -m janus.cascades.report` locally (background); record counts: hints before 343,
    after; `lithium carbonate` and the atorvastatin solvate now hinted if still unmapped.
  - _Requirements: cascade-engine 8_

- [ ] 27. Imipenem: component-code exception (owner decision 2026-11-08: option (b), DP43)
  - `data/janus_ingredients.csv` row `J2` imipenem (labels in five languages, no WHO code of its own
    in `atc_codes`: the loader's rule "codes must be ingredient-level" gets a documented
    exception for a curated key whose only code comes from `component_codes.csv`);
    `data/component_codes.csv` (`key, code, evidence, whocc_url, whocc_date, note`); migration
    `0009` for `res_component_code`; `atc.py`/`prepare.py` carry the (key, code) pair as
    `atc_selection = component_code`; `cascades/inputs.py` and `repository.combination_codes`
    accept exactly the listed pairs; re-check the WHOCC `J01DH` page and put URL and date in the
    note. `cascade-engine` DP23 and requirements record the exception.
  - [ ] 27.1 Property test P48: the pair reaches `rule_input` only for its key; no other ingredient or combination code gets the treatment; loader refusals. _Requirements: 14_
  - [ ] 27.2 Re-run P7 and the cascade-engine input-guard properties; example: row 58 fires on imipenem, not on cilastatin. _Requirements: 14, 5.2_
  - _Requirements: 14_

- [ ] 28. Final checkpoint
  - All steps green locally and in CI (ruff, format, pyright, pytest `HYPOTHESIS_PROFILE=ci`, `db`
    tests on PostgreSQL 16); commit, push, confirm CI passes.
  - Update design §1/§11 with the final coverage numbers, §19 with the owner's answers;
    `docs/pre-launch-checklist.md` (name rules, anion-acid table and French route map reviewed by a
    pharmacist or physician; GS1 prefix table and AI 710–714 confirmation; a real French and
    Spanish box; BDPM and AEMPS attribution and date shown by the client); `data/README.md`;
    `NOTICE` check (`janus-pipelines notice --check`); `experience` requirements (open items from
    this spec: region `EU`, `country`, `status_published`, notices, AI 712, DE offer);
    `docs/kiro-usage.md` dated entry (what was built, counterexamples found by the property tests and
    how they were fixed, owner decisions, open items).
  - _Requirements: 4, 5.8–5.11, 9.7–9.9, 12, 13, 14_
