# Implementation Plan: Cascade Map

> Scope: design.md §2. Property numbers refer to design §8, decisions to §9. Client only; no API
> change, no new dependency. No health data in logs; demo mode makes no request.

- [x] 1. Spec
  - `requirements.md` (EARS), `design.md` (DP1–DP10, P1–P8), this plan.
  - _Requirements: all_

- [x] 2. Generator and graph (`apps/web/scripts/gen-cascade-map.mjs`, `src/cascade-map/graph.json`)
  - Node ids (DP3), one edge per row with its event key, deterministic layout (DP2), sha256 of the
    inputs; `.prettierignore` entry for the generated file.
  - Tests: P1, P4, P5 (`src/cascade-map/graph.test.ts`).
  - _Requirements: 1.1, 1.2, 1.4, 2.1, 2.2_

- [x] 3. View model (`src/cascade-map/model.ts`)
  - Labels, search folding, `filterEdges`, `touchedNodes`, `matchedRows`/`matchedEdges`,
    `cannotCheck`, `move`, `byLabel`, `edgeGeometry`, `starField`.
  - Tests: P2, P3, P6, P7, P8 (`src/cascade-map/model.test.ts`).
  - _Requirements: 1.3, 3.1, 3.2, 4.2, 5.1, 6.2_

- [x] **Checkpoint A** — `pnpm typecheck`, `pnpm test` green; commit.

- [ ] 4. Screen (`src/components/cascade-map/*`, `src/theme/cascade-map.css`, `src/app/[locale]/cascades/page.tsx`)
  - Map (pan/zoom engine DP4, roving tabindex, legend), List (DP9), panel (DP8), filters, count,
    matches line states; `/cascades` in `WIDE`.
  - _Requirements: 2.3, 3, 4, 5.2, 5.3, 6, 7.1, 8.1, 8.2_

- [ ] 5. Messages and entries
  - `CascadeMap` namespace in EN, TR, DE, FR, ES; links from the results scope card, Research and
    the footer (DP1).
  - `pnpm exec vitest --run src/i18n` (forbidden phrases, parity, no empty strings).
  - _Requirements: 8.2, 8.3, 8.4_

- [ ] **Checkpoint B** — lint, typecheck, vitest; build; look at the screen; commit.

- [ ] 6. Playwright (`e2e/cascade-map.spec.ts`; `/cascades` added to `e2e/routes.spec.ts`)
  - Map and list (65 edges / 65 rows), filters, keyboard flow (Tab to a star, arrows, Enter, Escape
    returns focus), panel content (row, source, evidence ids, cannot-check for row 27, the demo's
    matched rows 5, 6, 9, 12 with the finding link), axe, no horizontal scroll, touch targets, both
    themes, five locales (E2E_LOCALES), no network in demo, reduced motion.
  - _Requirements: 1.2, 3, 4, 5.4, 6, 8_

- [ ] 7. Performance measurement (design §7.1)
  - 375 px, CPU 4×, drag, zoom buttons, Ctrl + wheel, filters; assert no long task > 50 ms; record
    the numbers in design §7.1.
  - _Requirements: 7.2_

- [ ] 8. Review passes (labelled, separate)
  - pharmacologist (class merge, labels, edges vs PIPC), localization-reviewer and safety-auditor
    over the `CascadeMap` texts; files `cascade-map-<role>-review.md`; apply fixes; checklist line
    in `docs/pre-launch-checklist.md` for anything that needs an expert.
  - _Requirements: 8.4_

- [ ] **Checkpoint C** — all tests, screenshots at 375 and 1440 in both themes (map, panel, list),
  looked at and fixed; commit.
