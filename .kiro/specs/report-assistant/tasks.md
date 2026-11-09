# Implementation Plan: Report Assistant

> Scope: design.md §2. Properties refer to design §5, decisions to §6. Web and data only; no API
> change; nothing is sent.

- [x] 1. Spec: requirements (EARS), design (DP1–DP12, P1–P10), this plan
  - _Requirements: all_

- [x] 2. Channel data: `data/report_channels.csv`, `data/report_channels.meta.json`, `data/README.md`
      entry, `pipelines/sources.toml` (`report_channels`, `hazell_2006`), regenerated `NOTICE`
      (`janus-pipelines notice --check` green), license guard green
  - _Requirements: 1.1–1.3, 1.5_

- [x] 3. Pure modules `src/report/{csv.mjs,types,channels,mapping,draft,fragment}.ts`, generator
      `scripts/gen-report-channels.mjs`, `src/report/channels.json`
  - _Requirements: 1.4, 2.4, 2.5, 4.1–4.3, 5.1–5.5, 8.1, 8.3, 9.2_

- [x] 4. Tests `src/report/*.test.ts`: CSV checks (source_url, checked_on, https/mailto/tel, JSON equals
      CSV, no `/media/76299`, no legacy French domain), properties P1–P10
  - _Requirements: 1.2–1.5, 4.2, 4.3, 5.1–5.5, 6.1, 8.1, 8.3, 9.2_

- [x] 5. Checkpoint 1: `pnpm lint`, `pnpm typecheck`, `pnpm test` green; commit

- [ ] 6. Screen `src/components/report/ReportAssistant.tsx`, route `app/[locale]/report/page.tsx`,
      print rules in `globals.css`, `MonthPicker` legend
  - _Requirements: 3, 4, 5, 6.2, 7.1, 7.5, 8.2, 8.3, 9, 10.2_

- [ ] 7. Entry links: `FindingDetail`, `FindingCard`, `Medicines`, `DoctorForm` (doctor page and demo)
  - _Requirements: 2.1–2.3, 8.1_

- [ ] 8. Texts: `ReportAssistant` namespace in the five message files; doctor link text in
      `src/doctor/messages.json`
  - _Requirements: 6.2, 7.2–7.4, 10.1_

- [ ] 9. Reviews: safety-auditor, pharmacologist, statistician, localization-reviewer →
      `report-assistant-*-review.md`; apply the fixes
  - _Requirements: 7, 10.3_

- [ ] 10. Playwright `e2e/report-assistant.spec.ts`: finding → draft → copy → official link href;
      doctor demo page → draft; region switch; print media; no request to `/api` or another origin;
      axe, scroll, targets at 375 and 1280, both themes, five locales (E2E_LOCALES); the route in
      `e2e/routes.spec.ts`
  - _Requirements: 2, 3, 5.4, 5.6, 5.7, 6.1, 9, 10.2_

- [ ] 11. Pre-launch checklist lines (legal review per region, re-verification cadence and dates,
      UNVERIFIED items, MedDRA decision)
  - _Requirements: 10.4_

- [ ] 12. Checkpoint 2: lint, typecheck, vitest, build, e2e green; screenshots (draft TR and US,
      doctor entry; 375 and 1440; both themes) looked at; commit
