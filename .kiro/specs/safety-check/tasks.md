# Implementation Plan: Safety check of the medicine list

> Requirements in `requirements.md`, design and decisions in `design.md`. Three parts, each committed before the
> next is started. No database change. Nothing pushed, merged or deployed in this work.

- [x] 1. Spec: requirements (EARS) for the three parts; design with decisions and properties for part A
  - _Requirements: all_
- [x] 2. Part A, API: `engine_items` extracted from the cascade service (no change of behaviour);
  `janus/safety/duplication.py` (pure), `schemas.py`, `service.py`, `router.py`; `POST /safety/check`
  - Properties S1-S7; the contract fixture for the web app.
  - _Requirements: 1, 2_
- [x] 3. Part A, web: `safety/model.ts`, `client.ts`, `useSafety.ts`, `components/safety/SafetyChecks.tsx`, the
  `more` slot of the results screen, texts in five languages (namespace `SafetyCheck`, keys added only)
  - Properties W1-W4; Playwright with axe (`e2e/safety.spec.ts`): five languages × two themes × 375 px and
    1280 px.
  - _Requirements: 7, 8.1_
- [x] 4. Part B, pipeline: `us_label_interactions` job, source `openfda_label_interactions` in `sources.toml`
  (NOTICE regenerated), name exclusions file, tests
  - _Requirements: 3_
- [x] 5. Part B, API and web: `safety/interactions.py`, `store.py`, `repository.py`, `interactions` block of
  `POST /safety/check`; card "Label text that names another medicine" in five languages; tests and Playwright
  - _Requirements: 4, 7_
