# Implementation Plan: Collective Memory, Phase 2

> Scope: `apps/api` (`janus/memory/`, one migration) and the message files in `apps/web`.
> Requirement numbers refer to requirements.md; property numbers (P1–P31) and decisions (DP1–DP23)
> refer to design.md. Tasks 1–13 executed 2026-11-08 (checkpoint 1 is `338d7ce`; task 14 is the
> final checkpoint). No health data in logs, fixtures or test output; tests use sentinel values.
> Checkpoints run every lint, format, type-check and test step (ruff, ruff format, pyright strict,
> pytest with `HYPOTHESIS_PROFILE=ci` including database tests against PostgreSQL 16, vitest and
> web lint), then commit, push and confirm GitHub CI passes. The full API suite takes 10 minutes or
> more: run it with `nohup` and read the log; only one suite at a time.

- [x] 1. Groundwork
  - The statistics review (verdict: approved with changes) is already applied in requirements.md
    and design.md §3, §8; re-read §8 before coding and keep `PARAMS` equal to design §3.2.
  - Done 2026-11-08: Evans, Waller and Davis 2001 (DOI 10.1002/pds.677) verified in Crossref (journal article,
    no notice); added to `data/evidence_papers.csv` (`pds_677`) and `sources.toml` (`evans_2001`, cited only);
    NOTICE regenerated. Evidence integrity check: the new row passes `records_from_papers` (tests below).
  - Confirm `JANUS_DATA_DIR` is the only new setting needed (counts path is derived); update
    `.env.example` if not.
  - _Requirements: 1.2, 1.6, 1.8, 5_

- [x] 2. Count file changes (`janus/memory/faers_build.py`, Req 11, DP13)
  - Result 2026-11-08: build `20261108T020842Z-7445632a-f55a79cf-4714`, 421 s, peak 2.7 GiB; file 120 MB → 80 MB; hashes of all unchanged tables identical to the first build (only `faers_report` changed, new `mapped` column); one-statement pair lookup p50 4.8 ms, p95 5.9 ms (one region), p95 6.9 ms (six regions).
  - Physically sorted tables, `faers_report.mapped`, new table `faers_region_basis`, schema
    `faers_counts-2`; extend `TABLES` and the table hashes; update the module docstring and
    `data-pipelines` design §14.3 with a pointer.
  - [x] 2.1 Property test P28 (extend `test_faers_build_properties.py`): sorted layout gives the same table hashes; `mapped` equals "has a mapped ingredient"; region-basis sums; schema version. _Requirements: 11.1–11.4_
  - [x] 2.2 Rebuild the real counts file in the background (about 7 minutes, 2.9 GiB peak); record file size, build id and the new row counts; confirm that every old table hash is unchanged. _Requirements: 11.2_

- [x] 3. Pure statistics (`janus/memory/stats.py`, `model.py`)
  - `Table`, `Cells`, `Estimates`, `Stats`, `PARAMS`, `evaluate()`, `assess()`, `sensitivity()`;
    exact integer arithmetic, one float conversion (design §3).
  - [x] 3.1 Property test P1: estimates positive, finite, interval around ROR. _Requirements: 1.2, 1.6_
  - [x] 3.2 Property test P2: role swap inverts ROR and the interval. _Requirements: 1.6_
  - [x] 3.3 Property test P3: scaling leaves PRR and ROR unchanged and narrows the interval. _Requirements: 1.6_
  - [x] 3.4 Property test P4: PRR, ROR, interval and χ² against a `Fraction`/`Decimal` reference for cells up to 2,000,000. _Requirements: 1.1, 1.9_
  - [x] 3.5 Property test P5: Haldane flag, χ² from the raw table, `no_reports`, `insufficient_data` exactly. _Requirements: 1.2, 1.3_
  - [x] 3.6 Property test P6: assessment equals the reference rule; boundary values. _Requirements: 1.6_
  - [x] 3.7a Property test P29: monotone in a (ROR lower bound and class). _Requirements: 1.6_
  - [x] 3.7 Property test P9 (pure part): sensitivity formulas and the flag. _Requirements: 1.7_
  - [x] 3.8 Example tests (Yates form, integer decision at PRR = 2 and χ² = 4 boundaries): the worked table (a=20, b=180, c=100, d=9,700); c = 0 with Haldane; a negative cell raises `StatsError`. _Requirements: 1.1, 1.2_

- [x] 4. Janus event vocabulary (`vocabulary.py`, `apps/api/janus/memory/memory_events.csv`, DP11)
  - Done: loader, 34 adverse + 5 benefit keys proposed (all `status = proposed`), `event_proposals.py`, review sheet `event-mapping-review.md`, pharmacologist review `event-mapping-pharmacologist-review.md`.
  - Loader and validator (design §4.6). Script that lists, for each of the 41 PIPC phrasings,
    candidate PTs from the real counts file with their report counts, and writes
    `data/memory_events_review.md`. Proposed `apps/api/janus/memory/memory_events.csv` with the placeholder keys kept.
  - [x] 4.1 Property test P15: valid file accepted, each defect rejected, missing-PT report exact. _Requirements: 6.2, 6.5, 6.6_
  - [x] 4.2 Done 2026-11-08: owner review, all 39 keys active, setting switched, placeholder removed. **Review stop (owner).** The owner reviews every key, label (five languages) and PT list,
    with the pharmacologist agent's check of the clinical choices; decisions are recorded in the
    review file, the CSV and requirements.md. Status line kept: reviewed by the project owner with AI
    assistance, needs a pharmacist or physician before any public claim. Then switch
    `Settings.event_vocabulary_path` default from the placeholder file to the new vocabulary
    (`contributions` loader reads keys only) and remove the placeholder. _Requirements: 6.2, 6.3_

- [x] 5. Checkpoint 1: statistics, count file, vocabulary
  - All steps green, including P1–P6, P9 (pure part), P15, P28 and the extended builder tests;
    the `log-guard` and `medical-language-guard` hooks report nothing. Commit, push, CI passes.

- [x] 6. Counts reader (`janus/memory/reader.py`, DP14, DP15)
  - `CountsReader` with the DuckDB settings, `SnapshotMeta`, schema-version and table checks,
    follow-`current` swap, statement counter; freshness and version notices (pure functions).
  - [x] 6.1 Property test P22: missing, wrong-version, tampered, half-written files give `memory_unavailable`; a promoted build is picked up. _Requirements: 7.6, 11.4_
  - [x] 6.2 Property test P23: `stale` iff age > 182 days; version-mismatch notice iff versions differ. _Requirements: 7.7, 7.8_

- [x] 7. Pair, regional breakdown and snapshot (`service.py`, `schemas.py`, `router.py`, DP4–DP6)
  - Models (design §5), `POST /memory/pair`, `POST /memory/regions` (pair and key paths), `GET /memory/snapshot`
    (operational: add to `OPERATIONAL_ALLOWLIST` with a test); `messages.py` with the closed code set and English
    sentences; wire into `create_app()` (reader opened in the lifespan; routes answer 503 when no file).
  - [x] 7.1 Property test P7: cells equal a recount from the report facts (differential against `aggregate`); negative cell fails loudly. _Requirements: 1.1_
  - [x] 7.2 Property test P8: report order and request order do not change the response. _Requirements: 7.4_
  - [x] 7.3 Property test P9 (service part): sensitivity table and flag from real count tables. _Requirements: 1.7_
  - [x] 7.4 Property test P10: lists ordered by reports then PT, independent of assessments and `PARAMS`. _Requirements: 1.8, 2.1_
  - [x] 7.5 Property test P13: regions add up; filter equals breakdown row; shares; fallback counts. _Requirements: 3.1, 3.3, 3.5_
  - [x] 7.6 Property test P14: Janus key union equals recount; one-PT key equals PT path; unknown PT. _Requirements: 6.4_
  - [x] 7.7 Property test P20: invalid input gets 422, no statement, no echo. _Requirements: 7.3_
  - [x] 7.8 Property test P21: byte-identical repeats, `assert_stateless`, `no-store`, sentinel logging. _Requirements: 7.2, 7.4, 7.10_
  - [x] 7.9 Property test P24 (pair and regions): statement budget. _Requirements: 9.6_

- [x] 8. Combination view (`ladder.py`, `service.combination`, DP6, DP8)
  - Set count, top events, pairwise fallback and single level in the statements of design §4.4;
    `POST /memory/combination`.
  - [x] 8.1 Property test P11: combination count recount, monotonicity, duplicate lines, order, one-ingredient equals the precomputed pair. _Requirements: 2.1_
  - [x] 8.1a Property test P31: members alone, `exposure` and `comparison` fields. _Requirements: 2.3_
  - [x] 8.2 Property test P12: ladder levels, skipped reasons, `no_reports`. _Requirements: 2.2, 2.4_
  - [x] 8.3 Property test P24 (combination): statement budget for 2–20 ingredients. _Requirements: 9.6_

- [x] 9. Checkpoint 2: FAERS API on the real counts file
  - Local real-data test (skipped without a counts file): 200 random pairs equal a direct SQL recount;
    vocabulary PTs exist in the file; a sample response per route is read for wording.
  - `python -m janus.memory.bench`: print percentiles for pair, regions, key path, combination (2, 5,
    10, 20 ingredients) and 8 concurrent clients; compare with the Req 9 targets; record the numbers in
    `design.md` §1 and `docs/kiro-usage.md`. If the pairwise statement misses the target, apply the
    fallback of design §4.4 and note it.
  - All steps green; commit, push, CI passes. _Requirements: 9.1–9.8_

- [x] 10. User layers (`shared.py`, migration `0007`, DP9, DP10, DP17)
  - Migration `0007_contribution_janus_keys` (upgrade and downgrade; table CHECK and the model
    pattern accept `J<n>`); `UserLayerSource` protocol; `ContributionsSource` (read-only transaction,
    per-cell version from contributor ids, `ingredients @> …`); `OutcomesUnavailable`; `POST /memory/shared`
    through `release_table` with k, ε and the noise key from settings; layer answers `layer_unavailable`
    / `not_available`. The sibling rule of Req 5.8 runs before `release_table` (one extra grouped statement).
  - [x] 10.1 Property test P16: hidden is uniform for true counts 0–19; hidden cells never change released values or the total; integers ≥ 0; determinism; deletion changes the version. _Requirements: 4.5, 4.6, 5.1, 5.2, 5.4_
  - [x] 10.1a Property test P30: sibling rule (nested cells differ by 0 or at least 20; ineligible equals hidden). _Requirements: 5.8_
  - [x] 10.2 Property test P17: no cross-layer number in any response. _Requirements: 4.3, 4.4_
  - [x] 10.3 Property test P18: no key or no database gives `layer_unavailable`, never a count. _Requirements: 5.5_
  - [x] 10.4 Property test P19: outcomes interface and stub source. _Requirements: 4.7_
  - [x] 10.5 Property tests re-run for the new route: logging (P21), stateless, route kind. _Requirements: 5.7, 7.2_
  - [x] 10.6 Example tests: migration upgrade → downgrade → upgrade; a donation with `J1` is accepted and a malformed key is rejected by both model and CHECK. _Requirements: 4.1_

- [x] 11. Citation (`evidence.py`, DP12; owner decision 2026-11-08; locator and cascade hook, no loader)
  - Pure `faers_locator`, `parse_locator`, `FAERS_EVIDENCE_ID`; `citation` in the pair, combination and
    regions responses (design §6). Cascade-engine hook, minimal: optional `RuleBase.faers_event_keys`
    (filled from `active` vocabulary keys by the service), `Finding.faers_locator`, `dataset:faers` through
    the existing `_cite`, `FindingOut.faers_locator`. Evidence-integrity: no code change; confirm that
    `dataset:faers` is registered by the loader from the faers artifact (run the integrity loader on the dev DB).
  - Record the decision as a DP in `cascade-engine` (DP22) and `evidence-integrity` (DP22) designs and fix
    the `faers_stat` mentions in their requirements and open items.
  - [x] 11.1 Property test P27: locator round trip, no run id/date, malformed rejected; finding hook with and without the record. _Requirements: 10.3, 10.4_
  - [x] 11.2 Property test P26: statistic sentences carry the citation; a < 3 yields no number; `cite` drops them without the record. _Requirements: 8.8, 10.3_
  - [x] 11.3 Example test: the cascade engine test suite: a finding carries `dataset:faers` and the locator when the rule has a key and the record is registered, and neither when not. _Requirements: 10.4_

- [x] 12. Message catalogue and wording guard
  - `Memory` namespace in `apps/web/messages/{en,tr,de,fr,es}.json` for every code (design §7.1),
    sentences from the statistics review; `apps/web/src/i18n/memory-words.ts` with the lists of
    §7.2 and a vitest that applies them to the namespace; a pytest scan of `messages.py`.
  - Run the `localization-reviewer` and `safety-auditor` agents over the namespace, the English
    sentences and the word lists (read-only); apply their findings; record them.
  - [x] 12.1 Property test P25 (vitest `describe.each(locales)` and pytest scan): keys, no empty strings, forbidden phrases, people nouns, causal/risk/reassurance words. _Requirements: 8.1–8.4_
  - [x] 12.2 Example test: the required sentences (disclaimer, limits, window, attribution, MedDRA notice, nothing-found) are present in every language. _Requirements: 8.6, 8.7_

- [x] 13. Contracts, data docs and write-up
  - Optional `faers_mapping_gap` table in the builder (design §8.2): not built, the owner has not asked for it.
  - Record the contracts of design §5 in the open items of `experience` (rendering, five-language
    wording, separate panels, MedDRA notice, demo exclusion), `medication-passport` (pair and
    combination for the merged list), `doctor-loop` (numbers printed in the note, regional ids, outcomes
    layer interface) and `light-face` (shared `CountsReader`, PT search), and in `cascade-engine`
    (task 11 hook).
  - `data/README.md` for `memory_events.csv`; `NOTICE` check (`janus-pipelines notice --check`);
    `docs/pre-launch-checklist.md`: verify the EudraVigilance public address form (Req 3.2), MedDRA
    display terms (exists), Evans citation if used in copy; dated entry in `docs/kiro-usage.md`
    (what was built, counterexamples found by property tests and how fixed, the latency numbers,
    open items).

- [ ] 14. Final checkpoint
  - Every lint, format, type-check and test step for `apps/api` (full suite with `HYPOTHESIS_PROFILE=ci`
    and PostgreSQL 16, after `alembic upgrade head` on the test database) and `apps/web` (vitest, lint,
    build); the real-data test and benchmark rerun on the rebuilt counts file; hooks clean; commit, push,
    CI passes. Final report: what was built, counterexamples found and how fixed, the measured numbers
    against Req 9, open items.
