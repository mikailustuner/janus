# Implementation Plan: OCR first — a box from any country

> Requirements in `requirements.md`, design and decisions DP-O1–DP-O8 in `design.md`, numbers in `evaluation.md`.
> Web only. Nothing pushed, merged or deployed in this work.

- [x] 1. Spec: requirements (EARS), design with decisions and properties
  - _Requirements: all_
- [x] 2. Measure first: synthetic label images and recorded text
  - `scripts/ocr-eval-fixtures.mjs` (seeded case list; fonts, sizes, rotations, looks; five held languages,
    Italian, Portuguese, Dutch, Polish, Latin; combinations; labels without a held ingredient), images
    git-ignored. `src/scan/eval/ocr-run.test.ts` (on request) records the text of every reading the app could
    make into `ocr-text.json`. `measure.ts` and `hit-rate.test.ts` compute before and after; `results.json`.
  - _Requirements: 5_
- [x] 3. Device list
  - `gen-vocabulary.mjs` writes `src/vocabulary/ingredient-names.json` (key → held names, English first); the
    parity test covers it.
  - _Requirements: 3.1_
- [x] 4. Matcher (`src/scan/ingredient-match.ts`, pure)
  - Folding, skeleton, salt words, compounds, capped tolerance, combination labels, same-name keys. Properties
    P1–P4, P6.
  - _Requirements: 3_
- [x] 5. Reading (`src/scan/ocr-passes.ts`, `ocr.ts`, `camera.ts`)
  - Deskew, turned readings when the upright one is neither useful nor confident, photo size limit, camera frame
    capture. Property P8.
  - _Requirements: 4_
- [x] 6. Label session (`src/scan/label-session.ts`)
  - Reducer without a chosen state; `outboundOf` as the only way to a request; memory-only store. Property P5.
  - _Requirements: 2.3, 2.4, 2.7, 6_
- [x] 7. Screens (`components/scan/ScanPage.tsx`, `LabelPanel.tsx`, `components/confirm/ConfirmPage.tsx`,
  `flow/confirm.ts`, `flow/pending.ts`, icons) and texts in five languages
  - Three equal ways with the any-country line; lead sentences; "other ways" wherever a code cannot be used;
    candidates, similar-spelling note, already-in-list note, show all; words behind a disclosure; camera,
    refused / missing camera, progress, failed, nothing recognised, no ingredient recognised; chosen ingredient
    first on confirm (property P7). Home `how1` and Start `intro`.
  - _Requirements: 1, 2, 4, 7_
- [x] 8. Rendered checks (`e2e/ocr-first.spec.ts`; `e2e/live-flow.spec.ts` updated)
  - Five languages × two themes for the three ways; not found → label photo → candidates → confirm → second
    ingredient; no-database path; unusable code; camera refused; no camera; reading failed; nothing recognised;
    no ingredient; candidates in five languages. axe, no horizontal scroll, 44 px targets, request bodies.
  - _Requirements: 1, 2, 4, 6, 7_
- [x] 9. Review passes: `safety-auditor` and `localization-reviewer` (separate), findings fixed
  - `review-safety-auditor.md`, `review-localization.md`.
  - _Requirements: 7_
- [x] 10. Verification: lint, typecheck, unit tests, build, Playwright smoke + routes + ocr-first, bundle budget
  - _Requirements: all_
