# Implementation Plan: Cascade Engine, Phase 1

> Scope: `apps/api/janus/cascades/`, migration `0005`, the curated class mapping and companion
> files under `data/`, the rule-base loader, `POST /cascades/evaluate`, the PIPC coverage report,
> two read-only helpers in `janus/resolution/`, two `cited_only` registry entries. Criteria tagged
> **[Later phase: OnSIDES]**, **[Phase 2: collective-memory]** and **[Client: …]** have no tasks
> here. Property numbers refer to design.md §9, decisions to §10.
> **Task 5 is a stop:** after the curated mapping is drafted, work pauses until the owner has
> reviewed it. No engine task that depends on the mapping starts before that.
> No health data in logs, fixtures or test output: tests use synthetic items and sentinel values.
> No TİTCK data in the repository. No new runtime dependency.

- [x] 1. Groundwork and fact checks
  - Confirm and record in design §11: recomputing the content hash of `data/pipc.csv` with the
    canonical algorithm gives `pipc.meta.json`'s `content_sha256` (else verify against the
    pipeline manifest and say so); the signatures of `register_records`, `rule_gate`, `cite`,
    `keep_output`, `build_item` and `load_snapshot`; how `resolve_products` builds
    `ResolvedIngredient`s, so `engine_items` (design §6.2) can reuse that builder.
  - Add `LogEvent.cascade_load` (counts only); extend the `write_tx` import-boundary test to allow
    `cascades/load.py` (DP19).
  - `tests/cascades_strategies.py`: classes and patterns at every ATC level, codes that hit or
    miss, items with duplicates and several ingredients, months (unknown, same month, window
    boundaries), snapshots built on `integrity_strategies.py`; brute-force references for class
    matching, timing and chains.
  - _Requirements: 1.1, 1.3, 9.5, 10.3_

- [x] 2. Papers and registry entries (Req 2.2, 6.1–6.3)
  - Add four rows to `data/evidence_papers.csv` (design §3.5): BMJ 2026 (`bmj_2026`, `e100499`),
    ThinkCascades (`thinkcascades`, `drugs_aging_2022`), Hendrix 2024 (`hendrix_2024`) and
    Vander Zanden 2001 (`vander_zanden_2001`), each with `verified_on` from a Crossref lookup
    done in this task.
  - Add `hendrix_2024` and `vander_zanden_2001` to `pipelines/sources.toml` (`cited_only`,
    section `cited`, licence as published); regenerate `NOTICE` with `janus-pipelines notice`;
    `notice --check` green. Describe the new papers in `data/README.md`.
  - Locally: `janus-pipelines run retractions`, then `python -m janus.integrity.load`; record the
    status of each new DOI in design §11.
  - _Requirements: 2.2, 6.1, 6.2, 6.3_

- [x] 3. Rule-base model, file parsers and validator (`model.py`, `patterns.py`, `rulebase.py`, pure)
  - Built before the draft, so the pharmacologist's files are checked mechanically.
  - `is_prefix_pattern`, `class_match` (design §4.1); parsers for the five curated files and
    `pipc.csv`; `validate` with every code of design §5.1; `build_rule_base`; `version()` with
    `ENGINE_RULES_VERSION`.
  - [x] 3.1 Property test P8: class matching equals the longest-prefix reference; pattern order does not matter; an inactive extension acts as absent. _Requirements: 1.2, 7.4_
  - [x] 3.2 Property test P17: valid file sets accepted; each single defect gives its code; the version ignores row order and changes with any content change. _Requirements: 1.1, 1.4, 5.2, 5.5_

- [x] 4. Draft the curated mapping with the pharmacologist agent
  - The pharmacologist agent drafts `data/cascade_classes.csv`, `data/pipc_rules.csv`,
    `data/cascade_priority.csv` and `data/abrupt_stop_classes.csv` (design §3.1–3.3) for all 65
    PIPC rows: one class per PIPC class and role, systemic forms for index classes, treatment
    forms for marker classes, notes with the clinical judgement, codes only (no WHO index text).
  - Rows that need confirmation are checked by hand on the WHOCC ATC/DDD Index pages
    (`basis = whocc_lookup`, URL and lookup date in the note).
  - Form extensions (DP8): `S01ED` for row 3 with `paper:vander_zanden_2001:aph_18464`; row 4
    only if a source naming erectile dysfunction for ophthalmic beta-blockers is found,
    Crossref-checked and added to `data/evidence_papers.csv` (and `sources.toml`); otherwise
    row 4 gets no extension. The not-extended forms of DP8 are written into the class notes.
  - BMJ data for rows 9, 25, 26, 47, 60, 65 exactly as in the abstract (design §1).
  - ThinkCascades overlap (rows 5, 8, 18, 23, 53, 56) confirmed against the paper (PMC9477172);
    confirmed rows get the supporting id.
  - Row 49 interpretation and every not-matchable role written with a reason.
  - The validator of task 3 passes on the drafted files (`build_rule_base` succeeds; no error code).
  - Write `.kiro/specs/cascade-engine/mapping-review.md`: one line per rule (row, PIPC text,
    index class, marker class, extension, BMJ data, supporting id), then one section per class
    (patterns, basis, notes), the abrupt-stop list with any group beyond the six named in
    `medical-safety.md`, and the questions for the owner.
  - Describe the new files in `data/README.md` (curated by Janus, Apache-2.0, re-review with each
    WHOCC ATC version).
  - _Requirements: 4.1, 5.1–5.6, 6.1, 6.2, 7.4_

- [x] 5. **STOP — owner review of the curated mapping**
  - Run ruff, ruff format, pyright strict and pytest (`HYPOTHESIS_PROFILE=ci`) for the tasks
    so far; commit the curated files, `mapping-review.md` and tasks 1–4; push; confirm CI passes.
  - Report to the owner and stop. Do not start task 6 until the owner has answered.
  - Record the owner's decisions in design §10–11 and, where they change a criterion, in
    `requirements.md`; apply the requested changes to the curated files and re-run the validator.
  - _Requirements: 5.1_

- [ ] 6. Engine core (`timing.py`, `exposure.py`, `chains.py`, `engine.py`, pure)
  - `parse_month`, `classify` (design §4.2); `exposures` with the merge rule (DP10);
    `evaluate` with the input guard, pair rules, `same_product` (DP11), abrupt-stop flags,
    statements and sorting (§4.4, §4.6); `chains` with the bounds (§4.5). Integrity is passed in
    as a snapshot; task 7 adds its use.
  - [ ] 6.1 Property test P1: order independence. _Requirements: 2.1, 9.6_
  - [ ] 6.2 Property test P2: monotonicity (unmatched items change nothing; a new key never changes existing findings). _Requirements: 2.1_
  - [ ] 6.3 Property test P3: temporal soundness. _Requirements: 2.4_
  - [ ] 6.4 Property test P4: date refinement. _Requirements: 2.2–2.5_
  - [ ] 6.5 Property test P5: duplicate invariance. _Requirements: 2.1_
  - [ ] 6.6 Property test P6 (pure part): region invariance over TR-, US- and EU-shaped inputs. _Requirements: 7.1_
  - [ ] 6.7 Property test P9: malformed and combination codes are refused. _Requirements: 1.3_
  - [ ] 6.8 Property test P10: no self-pairs; `same_product` pairs give no finding; matched codes match the classes. _Requirements: 2.1_
  - [ ] 6.9 Property test P11: timing table and boundaries. _Requirements: 2.2–2.5_
  - [ ] 6.10 Property test P12: chains equal the reference; weakest-link status; bounds give `chains_truncated`. _Requirements: 2.6_
  - [ ] 6.11 Property test P14: abrupt-stop flags on findings and on every item. _Requirements: 4.1_
  - [ ] 6.12 Property test P15: statements; disclaimer; `matches_published_pattern`; no forbidden phrase or reassurance word in any language. _Requirements: 4.2, 4.3_
  - [ ] 6.13 Property test P16: not-checked ingredients reported and inert; form labels and sort order. _Requirements: 2.10, 7.2, 7.3_
  - [ ] 6.14 Example tests: amlodipine + hydrochlorothiazide in one product gives `same_product` for row 5; a 15-item list evaluates in under one second. _Requirements: 2.1, 9.7_

- [ ] 7. Evidence in the engine (`engine.py`)
  - Rule gate per rule, disabled-rule report, `cite` of finding ids, priority gated by the BMJ
    paper, extensions gated by their papers, `probable` gated by the window paper,
    `integrity_codes` from `build_item` (design §4.4, DP5, DP16).
  - [ ] 7.1 Property test P7: evidence completeness. _Requirements: 1.5, 2.7_
  - [ ] 7.2 Property test P13: disabled rules yield nothing; retraction only removes findings, priority, extensions and `probable`; restoring restores. _Requirements: 1.5, 2.2, 6.1, 7.4_
  - [ ] 7.3 Example tests: the PIPC correction gives `corrected_notice` on every finding; BMJ data on rows 9, 25, 26, 47, 60, 65 only; timolol eye drops (`S01ED01`) plus a later antidepressant give row 3 with `via_form_extension` and the Vander Zanden id, and never act as the row 17 marker; prednisolone eye drops (`S01BA04`) never trigger rows 59–61. _Requirements: 1.5, 6.1, 7.4_

- [ ] 8. Every rule against the real curated files (`test_cascades_rules_properties.py`)
  - [ ] 8.1 Property test P18: each matchable rule fires on codes inside its classes within the window and not outside them; not-matchable rules never fire and are listed. _Requirements: 5.2, 10.4_
  - [ ] 8.2 Example test: a table over all 65 rules with one positive and one negative example each (generated deterministically from the class patterns). _Requirements: 10.4_

- [ ] 9. Checkpoint: pure core
  - All lint, format, type-check and test steps green (`apps/api`: ruff, ruff format, pyright
    strict, pytest with `HYPOTHESIS_PROFILE=ci`); the medical-language and log guards pass on
    the new files. Commit, push, confirm CI passes.

- [ ] 10. Migration, repository and loader (`0005_cascade_rule_base.py`, `repository.py`, `load.py`)
  - Tables of design §3.7 with downgrade; `current_rule_base_version`, rule-base read; the loader
    of design §5.2 (validate first, one transaction, `register_records` for 65 rule records with
    basis `dataset:pipc`, current pointer, `cascade_load` log line with counts only); CLI.
  - [ ] 10.1 Property test P19: atomic, idempotent load; 65 rule records with basis `dataset:pipc`; refused inputs change nothing. _Requirements: 1.1, 10.1–10.3_
  - [ ] 10.2 Example tests: upgrade → downgrade → upgrade gives an identical schema; a changed `pipc.csv` (hash mismatch) is refused; loading before the integrity loader has run is refused with a clear error; `/evidence/resolve` for `rule:pipc:12` returns the PIPC correction notice through its basis. _Requirements: 1.1, 1.4, 1.5, 10.1_

- [ ] 11. Request path (`resolution` helpers, `service.py`, `schemas.py`, `router.py`, wiring in `main.py`)
  - `engine_items` and `combination_codes` in `janus/resolution/` (read-only, design §6.2);
    `POST /cascades/evaluate` on `medical_router()` with its own body validation (field paths
    only), 409 `dataset_version_mismatch`, 503 `cascades_unavailable`, rule-base cache by
    version, `today()` hook for tests, disclaimer on every response.
  - [ ] 11.1 Property test P6 (database part): region invariance through `engine_items`. _Requirements: 7.1_
  - [ ] 11.2 Property test P20: stateless, `no-store`, nothing of the request in logs, 422 field paths only, 409 and 503 cases. _Requirements: 9.1–9.5_
  - [ ] 11.3 Property test P21: byte-identical repeated responses; permuted items give the same findings. _Requirements: 9.6_
  - [ ] 11.4 Example tests: `classify(app)` accepts the route; codes and ids are not accepted in a path or query string (404/405); a choice outside `key_candidates` is 422; an ambiguous ingredient without a choice is `not_checked`; synthetic Istanbul patient (TİTCK-shaped AMLIPIN `C09BB03` → amlodipine `C08CA01`, a diuretic started later) gives row 5 `probable`; 15 items in under one second through the API. _Requirements: 7.2, 9.1, 9.7, 9.8_

- [ ] 12. PIPC coverage report (`coverage.py`, `report.py`)
  - `trigram_similarity`, `build_coverage` (design §7); CLI with the output-path guard,
    counts-only output and log.
  - [ ] 12.1 Property test P22: counts equal a recount with `class_match`; hints never contain mapped names; ranking; similarity properties. _Requirements: 8.1–8.4_
  - [ ] 12.2 Example tests: the output path inside the repository is refused; published combination codes give `titck_product_code` hints but never findings. _Requirements: 8.2, 8.3, 8.5_
  - Locally on the real dataset: run the report, record counts (no names) in design §11: rules
    that cannot fire in TR or US, not-matchable rules, marker classes with high OTC share, the
    number of hints per rule. The pharmacologist proposes synonym rows for the hints with the
    most products into a review list in `mapping-review.md`; `data/ingredient_synonyms.csv` is
    not changed without owner review.
  - _Requirements: 8.1–8.6_

- [ ] 13. Checkpoint: API end to end
  - All lint, format, type-check and test steps green, including property tests and database
    tests against PostgreSQL 16; commit, push, confirm CI passes.
  - Locally: rebuild the migrate image before `docker compose up` (new migration), run
    `python -m janus.integrity.load` and `python -m janus.cascades.load`; Gate 1: the Istanbul
    synthetic patient (9 medicines, one AMLIPIN) resolved through `/resolve/scan` and evaluated
    through `POST /cascades/evaluate` finds the cascade from the amlodipine in AMLIPIN; API and
    Postgres logs contain no candidate id, QID, start month, code or rule id.
  - `test_cascades_real_artifacts.py` green locally (skipped in CI).
  - _Requirements: 9.5, 9.8_

- [ ] 14. Contracts and documentation
  - Record in the open items of `experience`, `doctor-loop` and `collective-memory`
    requirements the contracts of design §11 (re-resolve after 409, form-unconfirmed findings,
    `item_warnings`, codes to wording, `faers_stat:` ids); record the two resolution helpers in
    `drug-resolution` design §3.2.
  - `data/README.md` up to date for every new file.
  - _Requirements: 2.7, 4.1, 7.3, 9.2_

- [ ] 15. Final checkpoint
  - All steps green locally and in CI; commit, push, confirm CI passes.
  - Record final numbers (rules matchable, findings for the demo patients, tests, coverage
    summary) and remaining open items in design §11; append a dated entry to
    `docs/kiro-usage.md` (spec refinement, the review stop, counterexamples found by the property
    tests and their fixes).
  - Report to the owner, including the synonym proposals awaiting review and DP18.
