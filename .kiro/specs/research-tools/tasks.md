# Implementation Plan: Research tools (Phase 1)

- [x] 1. Spec (requirements, design, properties R1-R6)
- [x] 2. Models and recorded answers: `src/research/dataQuality.ts`, `src/research/onset.ts`,
  `scripts/record-research.mjs` (recorded from the real local API, 220 findings, 65 rows)
  - _Requirements: 1, 2, 4.3_
- [x] 3. Screens: data quality, onset table, onset row, developers; Research index entries; wide layout
  - _Requirements: 1-4_
- [x] 4. Messages in five languages; error map (503, 404)
  - _Requirements: 4.2_
- [x] 5. Property tests (`src/research/research.test.ts`) and rendered checks (`e2e/research-tools.spec.ts`)
- [x] 6. Reviews: safety auditor, statistician, localization reviewer (`reviews.md`); fixes applied
- [x] 7. Checkpoint: lint, typecheck, unit tests, e2e (five locales, two themes, 375/1280 px, axe)

## Open items
- Onset-table build: truncated row note `nonspecific_gi_terms` (rows 26, 27); shares still published on
  `cluster_dominated` rows in the CSV/JSON (statistician).
- Native-speaker pharmacovigilance review of the onset texts in TR, DE, FR, ES.
