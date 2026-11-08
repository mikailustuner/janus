# Implementation Plan: Experience, Phase 3 (client)

> Scope: `apps/web` (plus `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`, `NOTICE`). Requirement
> numbers refer to requirements.md; properties P1–P30, checks C1–C7 and decisions DP1–DP32 to design.md. Owner
> decisions of 2026-11-08 are applied (DP1–DP14). Task 22 is a hard stop for the owner's wording review.
> No health data in fixtures beyond the recorded synthetic patients; product names in fixtures and tests are invented
> (never TİTCK strings); no request value in any log or test output.
> **Checkpoints** run: `pnpm lint`, `pnpm typecheck`, `FC_PROFILE=ci pnpm test` (vitest + fast-check, including the
> i18n and source-scan tests), `pnpm --filter @janus/web e2e` (Playwright: axe, 375 px / 1280 px, network, demo flow),
> `pnpm build` + `node apps/web/scripts/bundle-budget.mjs`; the API suite only if a task changed `apps/api` (none is
> planned); then commit, push and confirm GitHub CI passes.
> The demo flow (demo patient → findings → Collective Memory → doctor note PDF) works end to end at checkpoint 1
> (task 12); scanning, the live API flow and the outcome loop follow.

- [ ] 1. Tooling, dependencies and transport (`apps/web/package.json`, `vitest.config.ts`, `playwright.config.ts`,
  `e2e/helpers.ts`, `next.config.ts`, `src/proxy.ts`, `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`,
  `NOTICE`; design §2.1, §5.5, DP13, DP15, DP31)
  - Add exactly: `zxing-wasm` 3.1.6, `tesseract.js` 7.0.0, `@react-pdf/renderer` 4.9.0, `qrcode` 1.5.4; dev
    `@types/qrcode` 1.5.6, `fast-check` 4.10.2, `@playwright/test` 1.64.0, `@axe-core/playwright` 4.14.0; lockfile.
  - vitest include `src/**/*.test.{ts,tsx}`; `src/test/fc.ts` with `FC_PROFILE` (dev 100 / ci 300 runs, seed printed);
    `src/test/arbitraries.ts` skeleton.
  - Playwright: production build web server, Chromium, 375 × 812 and 1280 × 800 projects, `page.route("**/api/**")`
    stub helper, `expectNoAxeViolations()` (WCAG 2.2 A/AA tags), `expectNoHorizontalScroll()`.
  - `rewrites()` `/api/:path*` → `JANUS_API_ORIGIN`; `headers()` CSP, `Referrer-Policy`, `Permissions-Policy`;
    `proxy.ts` matcher skips `/o`; compose build arg `JANUS_API_ORIGIN=http://api:8000`; `.env.example` documents the two
    consent versions the client uses (`JANUS_CONSENT_VERSIONS`, `JANUS_OUTCOME_CONSENT_VERSIONS`); CI job `web-e2e`;
    `NOTICE` lists the four fonts (OFL) and the runtime libraries.
  - [ ] 1.1 Smoke: one fast-check property and one Playwright page (home) pass locally and in CI. _Requirements: 3.1, 22.1_
  - [ ] 1.2 Example test: the response headers of `/` and `/o` carry the CSP with `connect-src 'self'` and
    `Referrer-Policy: no-referrer`; `/o` is not locale-redirected. _Requirements: 19.1, 23.4_

- [ ] 2. API contracts, decoders, builders and error map (`src/api/contracts.ts`, `decode.ts`, `builders.ts`,
  `errors.ts`, `client.ts`; design §5.1–§5.3, DP16)
  - Types and decoders for every response of §5.1; request builders as the only body constructors; `HttpClient` with
    timeouts (10 s reads, 20 s notes), `credentials: "omit"`, `cache: "no-store"`, no write retries; the `JanusClient`
    interface that `DemoClient` will implement.
  - [ ] 2.1 Property test P2 (builders part): exact keys, patterns, no box name, no ATC-shaped value, no `demo` key, no
    query string, token only in loop bodies. _Requirements: 23.1, 23.2, 4.3_
  - [ ] 2.2 Property test P20: every (route, status, code, body) maps to a typed error with an existing message key;
    no field value in messages; client-defect and `resolution_unavailable` rules; no exception escapes. _Requirements: 22.4, 10.4, 12.6, 16.11, 19.4, 20.7_
  - [ ] 2.3 Property test P19 (hand-made samples; re-run on recorded fixtures in task 7). _Requirements: 22.2_

- [ ] 3. Themes, tokens and fonts (`src/theme/tokens.css`, `prepaint.ts`, `words.ts`, `src/app/globals.css`,
  `src/fonts/`, `src/app/[locale]/layout.tsx`; design §7, DP1, DP2, DP18, DP21)
  - Steering tokens exactly, both themes, Glass light/dark, reduce transparency (setting, media query, `@supports`);
    `@theme inline` mapping; fonts via `next/font/local` from committed OFL files; pre-paint inline script; face from
    the route; 400 ms mask transition, instant under reduced motion; ghost drift; a test that `src/components` and
    `src/app` hold no raw hex colour.
  - [ ] 3.1 Property test P18: contrast of every text and boundary pair, both themes, both schemes, Glass surfaces
    composited over each background field. _Requirements: 3.1_
  - [ ] 3.2 Property test P17: pre-paint script with any stored value and pathname. _Requirements: 6.7, 9.2_
  - [ ] 3.3 Example test: every letter of the five catalogues has a glyph in each embedded TTF (fontkit). _Requirements: 6.6, 17.8_

- [ ] 4. Message namespaces and the generated vocabulary (`messages/*.json`, `src/i18n/reassurance.ts`,
  `src/i18n/*.test.ts`, `scripts/gen-vocabulary.mjs`, `src/vocabulary/`; design §8, DP17, DP27)
  - Draft every namespace of §8.1 in five languages (English first, four drafts marked for review in task 22); paired
    `twoFaces` / `glass` keys; versioned consent texts with `src/consent/versions.ts`; TS mirror of `REASSURANCE`;
    vocabulary generator over the accepted glossary rows, active event rows and `data/pipc.csv`; `ingredientName()`.
  - [ ] 4.1 Property test P12: catalogue completeness, ICU placeholders, forbidden phrases, `Memory` word lists and the
    screening exception, reassurance and compliance words, Glass without theme-device words. _Requirements: 2.1, 2.4, 6.5, 16.4, 21.5_
  - [ ] 4.2 Property test P13: committed vocabulary equals the generator output; `ingredientName` follows doctor-loop
    DP16. _Requirements: 2.5_
  - [ ] 4.3 Parity test: `reassurance.ts` equals `REASSURANCE` of `apps/api/janus/notes/phrases.py`. _Requirements: 1.3_

- [ ] 5. Browser store (`src/store/storage.ts`, `settings.ts`, `list.ts`, `tokens.ts`, `reminders.ts`; design §4, DP5,
  DP29)
  - Versioned documents, safe wrapper with in-memory fallback and one notice, `useSyncExternalStore` hooks, item
    actions (add, edit start / box name / choices, remove), "delete everything" (storage + caches).
  - [ ] 5.1 Property test P16: any failure schedule; round trip; version mismatch refused without sending. _Requirements: 9.4, 9.5_

- [ ] 6. Shell, home, start and settings (`src/components/Shell.tsx`, `Header.tsx`, `MaskSwitch.tsx`, `Nav.tsx`,
  `Disclaimer.tsx`, `EmergencyNotice.tsx`, `DemoLabel.tsx`, `StateView.tsx`, `LanguageSwitcher.tsx`, primitives;
  `src/app/[locale]/page.tsx`, `start/`, `settings/`, `[...rest]/`; design §3, §7, §9, DP26)
  - Two Faces header + bottom nav and Glass pill tab bar from one component set; emergency notice first on home with the
    user region's number; disclaimer footer; settings incl. Appearance, read aloud, regions, note language, delete
    everything; localized not-found; Passport slots as empty components (§15).
  - [ ] 6.1 Playwright C1–C3 on home, start, settings, not-found (5 locales × 2 themes). _Requirements: 1.2, 3.1, 8.1–8.6, 9.1_

- [ ] 7. Demo fixtures, demo codes and the demo client (`scripts/record-demo.ts`, `src/demo/fixtures/*.json`,
  `src/demo/codes.ts`, `client.ts`, `sheet.tsx`, `src/app/[locale]/demo/`; design §13, DP11, DP32)
  - Run the recorder against the local API (real dataset, note keys set locally): Istanbul = the gate-1 list; Cologne
    and Ohio as proposed; record the versions; scrub product text to invented names; record what each case returns in
    design §13.1 (rows, statuses, months, warnings). Demo patient picker, printable code sheet, demo label, exit demo.
  - [ ] 7.1 Example test: Istanbul fixture has `pipc:5` `probable`, `months_between` 5, index matched code `C08CA01`
    from the combination item, `corrected_notice`, rows 6, 9, 12, two `item_warnings`; the combination item resolves to
    `C08CA01` and `C09AA03` with `C09BB03` only as `published_atc`. _Requirements: 4.2_
  - [ ] 7.2 Example test: no product text field in any fixture is outside the invented-name table; no token or `qr_url`
    stored. _Requirements: 4.6_
  - [ ] 7.3 Property test P15: demo code range and detection before any request. _Requirements: 4.2, 4.5_
  - [ ] 7.4 Property test P19 on every recorded fixture with mutations. _Requirements: 22.2_

- [ ] 8. Medicine list, "since when" and timeline (`src/flow/evaluate.ts`, `timeline.ts`,
  `src/components/MonthPicker.tsx`, `src/app/[locale]/medicines/`, `timeline/`; design §4, §9)
  - List rows (box name, ingredients via the vocabulary, region, source, start, abrupt-stop line after evaluation),
    edit and remove, > 50 warning, out-of-date marking, timeline lanes and finding links; works on the demo session.
  - [ ] 8.1 Property test P3: evaluation input, index map, months, 50-item bound. _Requirements: 14.1, 13.1, 1.6_
  - [ ] 8.2 Property test P23: timeline model. _Requirements: 13.3_

- [ ] 9. Results: findings, chains, scope, safety lines, read aloud (`src/flow/findings.ts`, `locator.ts`,
  `src/components/Ghost.tsx`, `SafetyLine.tsx`, `AbruptStopLine.tsx`, `ReadAloud.tsx`, `src/app/[locale]/results/`;
  design §9, Req 14, Req 7)
  - [ ] 9.1 Property test P7: findings view model. _Requirements: 1.3, 14.4–14.9_
  - [ ] 9.2 Property test P6: locator parse and event key. _Requirements: 7.5, 16.1_
  - [ ] 9.3 Property test P9: safety lines, emergency first, crisis line with abrupt-stop lines, no PT outside detail. _Requirements: 7.1–7.8_
  - [ ] 9.4 Property test P8 (results and finding cards): disclaimer once, no forbidden or reassurance phrase, Glass
    without theme words, both themes, five locales. _Requirements: 1.3, 6.5, 8.1_

- [ ] 10. Finding detail, evidence and Collective Memory (`src/flow/integrity.ts`, `memory.ts`,
  `src/components/CiBar.tsx`, `ZombieStamp.tsx`, `SourceAttribution.tsx`, `src/app/[locale]/results/[finding]/`,
  `memory/`; design §9, Req 15, Req 16)
  - Evidence view and integrity line; FAERS pair panel (detail-only assessment, screening sentence, limits, window,
    attribution, MedDRA notice); list-level panels: combination, regions, donated reports, doctor-confirmed outcomes;
    `GET /memory/snapshot` notices; > 20 keys chooser.
  - [ ] 10.1 Property test P30: evidence view model. _Requirements: 15.2, 15.3_
  - [ ] 10.2 Property test P10: memory display rules. _Requirements: 16.5–16.8_
  - [ ] 10.3 Property test P11: CI bar geometry and locale formatting. _Requirements: 16.6, 2.3, 3.6_
  - [ ] 10.4 Property test P8 (memory panels and evidence view). _Requirements: 16.3, 8.1_

- [ ] 11. Doctor note preview, side-by-side and PDF (`src/note/layout.ts`, `pdf.tsx`, `src/app/[locale]/note/`;
  design §10.1–§10.2, DP6)
  - `POST /notes/document` with pins and one or two languages; 409 handling (re-evaluate, show, then print); preview in a
    light-face paper card; side-by-side; lazy PDF with embedded fonts, A4/Letter, footer on every page, demo label.
  - [ ] 11.1 Property test P4: product-name slots and no box name in later requests. _Requirements: 17.4, 23.1_
  - [ ] 11.2 Property test P24: section order, verbatim text, empty headings, page footer, side-by-side pairing. _Requirements: 17.3, 17.6, 17.7, 17.9, 17.10_

- [ ] 12. Checkpoint 1: end-to-end demo flow
  - Playwright C6 (Istanbul → results with row 5 → finding detail → memory → note in two languages → PDF file starting
    `%PDF` containing the disclaimer), C1–C3 on every route built so far, C4 for the demo flow (no request at all).
  - All checkpoint steps green; commit, push, CI passes.

- [ ] 13. Scanning (`src/scan/gs1.ts`, `zxing.ts`, `camera.ts`, `src/app/[locale]/scan/`, `scripts/vendor-assets.mjs`;
  design §6.1–§6.3, DP9)
  - Lazy zxing reader with the wasm from `/vendor/`; camera with permission handling; photo picker; typed input rules;
    demo detection on every path; 422 code messages; scan region from settings.
  - [ ] 13.1 Property test P1: outbound filter. _Requirements: 10.2, 10.3, 23.1_
  - [ ] 13.2 Example test (node): zxing-wasm decodes the demo sheet's DataMatrix images, and the filtered content has no
    `(21)`. _Requirements: 10.1, 10.2_

- [ ] 14. Label text recognition, NDC and name search (`src/scan/ocr.ts`, `ocr-extract.ts`, scan tab "Photo of label";
  design §6.4, DP10)
  - Lazy tesseract worker with self-hosted core and `tessdata_fast` (pinned hashes); tappable words; NDC chips;
    no-open-database path from Confirm leads here.
  - [ ] 14.1 Property test P22: nothing sent without a choice; only the NDC or the selected words; national codes not
    sent as codes. _Requirements: 11.2, 11.4_

- [ ] 15. Confirm screen, live flow and version changes (`src/flow/confirm.ts`, `reresolve.ts`,
  `src/app/[locale]/confirm/`, list re-resolution prompts; design §5.4, §9, DP20)
  - Candidate cards with attribution, notices, `matched_by` notes, status strings, homeopathic, component code,
    ambiguous choices, box name, since when; `/resolve/products` refresh within one dataset version; 409 re-resolution.
  - [ ] 15.1 Property test P21: confirm view model. _Requirements: 12.1–12.11_
  - [ ] 15.2 Property test P5: re-resolution (model-based with fake resolver and engine). _Requirements: 22.3, 14.2_
  - [ ] 15.3 Playwright: stubbed live flow (scan TR code → confirm → since when → results) and the 409 path. _Requirements: 1.1, 22.3_

- [ ] 16. Outcome loop: QR opt-in, reminder, withdrawal (`src/note/qr.ts`, `src/app/[locale]/note/` opt-in card,
  `note/withdraw/`, `src/store/reminders.ts`; design §10.3–§10.4, DP7, DP23)
  - Consent text, `POST /notes/token`, QR at 50 mm in the PDF with the coverage line, `qr_url` or own-origin address,
    `no_findings` and 503 paths, reminder card after 28 days leading to the donation flow, withdrawal screen.
  - [ ] 16.1 Property test P25: QR version ≤ 25, level M, byte mode, decodes back (zxing-wasm in node). _Requirements: 18.2, 18.3_
  - [ ] 16.2 Property test P29: reminder due date and token lifecycle. _Requirements: 18.4, 18.5_

- [ ] 17. Doctor page (`src/app/o/layout.tsx`, `page.tsx`, `src/app/[locale]/demo/doctor/`; design §11, DP19)
  - Fragment read, pattern check, demo fragment, form with two questions per finding, error texts in the note's
    language, success state, `janus:form-ready` mark.
  - [ ] 17.1 Property test P26: token transport. _Requirements: 19.1, 19.7_
  - [ ] 17.2 Property test P27: outcome answers and the Send rule. _Requirements: 19.2, 19.5_
  - [ ] 17.3 Playwright C5: form ready < 3 s median of 5 cold loads on the 4G profile; JS budget of §16. _Requirements: 5.1, 19.6, 25.1_

- [ ] 18. Donation and deletion (`src/app/[locale]/donate/`, `donate/delete/`; design §12, DP24)
  - Emergency notice first, event picker with safety lines, fields of Req 20.2, stored summary, consent, deletion token
    screen, delete by token, error texts, demo replacement sentence.
  - [ ] 18.1 Property test P28: donation request. _Requirements: 20.2, 20.3, 20.8_
  - [ ] 18.2 Property test P14 (complete): model-based demo session over every screen incl. note, QR, doctor demo,
    donate and withdraw; no request, no store write, demo label everywhere. _Requirements: 4.3, 4.4, 4.7, 20.8_

- [ ] 19. Privacy page, researcher shell and error states (`src/app/[locale]/privacy/`, `research/**`; design §12, §14,
  Req 21, Req 24)
  - Privacy sections with `GET /privacy/storage`, limits, legal frame, sources; research layout in the light face with
    four Phase 4 empty states; every screen's loading, empty, error and long-content states per design §9 table.
  - [ ] 19.1 Playwright: each route's four states rendered from stubs (long German content at 375 px included). _Requirements: 3.3, 21, 24_

- [ ] 20. Offline demo, PWA and accessibility features (`public/sw.js`, `public/manifest.webmanifest`, large text,
  reduce transparency, read aloud; design §7, §13.4, DP22, DP14)
  - [ ] 20.1 Playwright: after one visit, the Istanbul flow works with the network offline; `/api` responses are never in
    the cache. _Requirements: 4.4, 22.5_
  - [ ] 20.2 Playwright C4 (all flows) and C7 (reduced motion, reduce transparency); large text at 375 px without
    horizontal scroll. _Requirements: 3.1, 3.2, 3.4, 23.4_

- [ ] 21. Checkpoint 2: everything built
  - C1–C7 on every route × 5 locales × 2 themes; `bundle-budget.mjs` values recorded in design §16 with the budget set
    to measured + 10 % (within the ceilings); rendering time of a 15-item result recorded. All checkpoint steps green;
    commit, push, CI passes. _Requirements: 25.2, 25.3_

- [ ] 22. Wording review and **review stop (owner)**
  - Localization review of every new namespace in four languages (forbidden and near-forbidden forms, register, meaning
    parity, Glass vocabulary), pharmacologist review of the clinical wording (findings, timing, not-checked reasons,
    consent texts), written to `wording-localization-review.md` and `wording-pharmacologist-review.md` with a summary
    `wording-review.md` (counts, flagged keys, the final demo cases of §13.1, the open items of design §20). Commit,
    push, CI green, then **stop and wait for the owner**. _Requirements: 2.4, 7.7, 21, DP27_

- [ ] 23. Apply the owner's decisions and final checkpoint
  - Apply the wording and open-item decisions (demo names, Spanish status codes, demo cases, shadcn/ui) in one commit;
    record them in requirements.md and design.md (DPs, §20); re-record fixtures if the demo cases changed; add the
    pre-launch items (native-speaker review of the new namespaces, print-and-scan test of the demo QR at 50 mm on
    several phones, re-check of the emergency and crisis numbers) to `docs/pre-launch-checklist.md`.
  - Every checkpoint step green (web, e2e, CI); report what was built, counterexamples the property tests found and how
    they were fixed, and the open items.
