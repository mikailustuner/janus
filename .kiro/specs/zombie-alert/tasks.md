# Implementation Plan: Zombie Alert

> Scope: design.md §2. Properties refer to design §5, decisions to §6. Web only; no API change.
> No health data in fixtures beyond the recorded demo patient; the simulated change is labelled.

- [x] 1. Spec: requirements (EARS), design (DP1–DP10, P1–P9), this plan
  - _Requirements: all_

- [x] 2. Pure logic `src/flow/zombie.ts` + properties `src/flow/zombie.test.ts`
  - Cited ids and kept sentences from a note; check body; `matchChanges`; fallback from a
    resolution; `diffNote`; `withoutEvidence`; `isDue`; bounds.
  - Properties P1–P5, P7–P9.
  - _Requirements: 1.1, 1.5, 2.3–2.5, 3.1, 3.2, 5.2, 6.4_

- [x] 3. Document `src/store/zombie.ts` (validation, memory doc for the demo) + P6
  - Reset in `deleteEverything` (`src/store/hooks.ts`).
  - _Requirements: 1.2–1.4, 6.1_

- [x] 4. API client: `evidenceChanges` in `src/api/client.ts`, decoder `changesResult` in
      `src/api/decode.ts`, route `evidence/changes` in `src/api/errors.ts`; decoder tests
  - _Requirements: 2.3, 2.6_

- [x] 5. Checkpoint 1: `pnpm lint`, `pnpm typecheck`, `pnpm test` green; commit

- [x] 6. Demo fixture `src/demo/fixtures/zombie.json`
  - _Requirements: 6.2, 6.3_

- [x] 7. Watcher and actions `src/flow/useZombie.ts`
  - Open / 24 h / visibility, single flight, notification via the SW registration; record, update,
    dismiss, simulate.
  - `public/sw.js`: `notificationclick` opens the note.
  - _Requirements: 2.1, 2.2, 2.6, 2.7, 4.3, 4.4, 5.1, 5.3–5.5, 6.2, 6.5_

- [x] 8. Components `src/components/zombie/` and the additive lines in Shell, Home, Results,
      NotePage, Settings
  - _Requirements: 3.3–3.6, 4.1, 4.2, 4.5, 5.2, 6.2, 6.3_

- [x] 9. Texts: `ZombieAlert` namespace in the five message files
  - _Requirements: 3.5, 3.6, 4.3, 7.1_

- [x] 10. Reviews: localization-reviewer and safety-auditor → `zombie-alert-*-review.md`; apply
  - _Requirements: 7.1_

- [x] 11. Playwright `e2e/zombie-alert.spec.ts`
  - Demo: simulate → alert → update → what changed, no request; live: stubbed changes →
    alert on home → note update → what changed, request body has no id; notification permission
    with a mocked `Notification`; axe, scroll, targets at both projects, both themes, all locales
    (E2E_LOCALES).
  - _Requirements: 2–7_

- [x] 12. Checkpoint 2: lint, typecheck, vitest, build, e2e green; screenshots at 375 and 1440 in
      both themes looked at; checklist line; commit
