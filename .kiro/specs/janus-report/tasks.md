# Implementation Plan: Janus report

> Scope: design.md §2. Property numbers refer to design §6, decisions to §7. No API change, no new dependency.

- [x] 1. Spec (`requirements.md`, `design.md`, `tasks.md`)
  - **Checkpoint:** commit the spec.

- [x] 2. View models (`src/flow/summary.ts`, `src/flow/share-card.ts`, `src/flow/findings.ts` `orderGroup`)
  - `summaryView`, `integritySummary` (DP3–DP7); `shareCard`, `shareCardText` (DP11).
  - 2.1 Properties P1, P3, P5 (`src/flow/summary.test.ts`); P6, P7 (`src/flow/share-card.test.ts`).
  - _Requirements: 2.1–2.7, 4.4, 5.2–5.4_
  - **Checkpoint:** lint, typecheck, vitest green; commit.

- [ ] 3. Summary screen (`src/components/report/{rings,Summary}.tsx`, route, `Report` namespace in five languages,
  results link, `Shell.tsx` wide route)
  - Rings and bars (DP8), tiles linking into the detail, zero state (DP9), emergency first, states.
  - 3.1 Render tests P2, P4, P8 (`src/components/report/summary.test.tsx`).
  - _Requirements: 1.1–1.4, 2.1–2.7, 3.1–3.4, 4.1–4.3, 6.1_
  - **Checkpoint:** lint, typecheck, vitest green; commit.

- [ ] 4. Share image (`src/components/report/{ShareImage.tsx,draw.ts}`)
  - Options, canvas drawing (DP10), confirmation dialog with the exact preview (DP12), Web Share with file, else
    download.
  - _Requirements: 5.1–5.7_
  - **Checkpoint:** lint, typecheck, vitest green; commit.

- [ ] 5. Browser checks (`e2e/report.spec.ts`, `e2e/routes.spec.ts`)
  - Summary from the demo, tiles navigate, share flow with confirmation, PNG 1080 × 1350 downloaded (P9), no request,
    axe, touch targets and no horizontal scroll at 375 / 1280, both themes, five locales (`E2E_LOCALES`).
  - Screenshots of the Summary and the confirmation at 375 and 1440 in both themes and of the image; reviewed.
  - _Requirements: 6.2–6.4, 5.5–5.7_
  - **Checkpoint:** build and e2e green; commit.

- [ ] 6. Reviews and final checkpoint
  - localization-reviewer and safety-auditor passes on the `Report` namespace, the Summary and the share image
    (`report-localization-reviewer-review.md`, `report-safety-auditor-review.md`); fixes applied. No statistician
    pass (DP13). Pre-launch checklist line.
  - **Checkpoint:** lint, typecheck, vitest, e2e green; commit.
