# Implementation Plan: Open data

- [x] 1. Outcome dataset: `janus/open/outcomes.py` (candidates, release through `release_cells`, version, CSV) and
  `router.py` (`/open/outcomes`, `/open/outcomes.csv`, 503). P1, P2, P4, P5. _Requirements: 1, 2_
- [x] 2. Cascade data package: `janus/open/package.py`, `titck_name_hashes.txt`, `data/open/cascade-package/`,
  `--check` in tests. P3, P6. _Requirements: 4_
- [x] 3. API document: `janus/open/openapi.py`, `docs/openapi-public.json`, `docs/open-api.md`. P6. _Requirements: 5_
- [x] 4. Docs: `docs/open-data.md` (dataset, dictionary, package), `docs/contributing-corrections.md`.
  _Requirements: 2.3, 6_
- [x] 5. Web: `src/open/*`, recorder, `OpenData` page, Research and footer links, `OpenData` namespace in five
  languages. _Requirements: 3_
- [x] 6. Reviews and e2e: safety-auditor and localization-reviewer passes on `OpenData` and the docs; Playwright
  `e2e/open-data.spec.ts` (five locales × two themes, axe, 375 / 1280, empty state, demo without requests, downloads).
  _Requirements: 7_
- [x] 7. Checkpoint: ruff, pyright, pytest (janus_test), web lint, typecheck, vitest, build, e2e; pre-launch items;
  commit. _Requirements: all_
