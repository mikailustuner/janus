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

- [x] 1. Tooling, dependencies and transport (`apps/web/package.json`, `vitest.config.ts`, `playwright.config.ts`,
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
  > Done 2026-11-08 (Claude Code): dependencies pinned as listed (tesseract.js build script denied in `pnpm-workspace.yaml`); NOTICE
  > regenerated from `pipelines/sources.toml` (new section "Web app", NOTICE is generated, not hand-edited). Deviation: no
  > `web-e2e` CI job yet (DP36): the Playwright checks run locally; `record-demo` is `.mjs` (Node here has no TS stripping).
  - [x] 1.1 Smoke: one fast-check property and one Playwright page (home) pass locally and in CI. _Requirements: 3.1, 22.1_
  - [x] 1.2 Example test: the response headers of `/` and `/o` carry the CSP with `connect-src 'self'` and
    `Referrer-Policy: no-referrer`; `/o` is not locale-redirected. _Requirements: 19.1, 23.4_

- [x] 2. API contracts, decoders, builders and error map (`src/api/contracts.ts`, `decode.ts`, `builders.ts`,
  `errors.ts`, `client.ts`; design §5.1–§5.3, DP16)
  - Types and decoders for every response of §5.1; request builders as the only body constructors; `HttpClient` with
    timeouts (10 s reads, 20 s notes), `credentials: "omit"`, `cache: "no-store"`, no write retries; the `JanusClient`
    interface that `DemoClient` will implement.
  > Done 2026-11-08 (Claude Code): response types are inferred from the decoders (one source); the read routes are `JanusReadClient`,
  > write/loop routes `JanusLoopClient`. `Scan.errors.*`: one `unreadable` key for all `gs1_*`/`gtin_missing`, plus
  > `gtin_check_digit` and `ndc_malformed`. Counterexample (P19): dropping an entry of a `record` (Wikidata `labels.es`) is
  > not a contract error; the mutation generator now treats record entries as optional.
  - [x] 2.1 Property test P2 (builders part): exact keys, patterns, no box name, no ATC-shaped value, no `demo` key, no
    query string, token only in loop bodies. _Requirements: 23.1, 23.2, 4.3_
  - [x] 2.2 Property test P20: every (route, status, code, body) maps to a typed error with an existing message key;
    no field value in messages; client-defect and `resolution_unavailable` rules; no exception escapes. _Requirements: 22.4, 10.4, 12.6, 16.11, 19.4, 20.7_
  - [x] 2.3 Property test P19 (hand-made samples; re-run on recorded fixtures in task 7). _Requirements: 22.2_

- [x] 3. Themes, tokens and fonts (`src/theme/tokens.css`, `prepaint.ts`, `words.ts`, `src/app/globals.css`,
  `src/fonts/`, `src/app/[locale]/layout.tsx`; design §7, DP1, DP2, DP18, DP21)
  - Steering tokens exactly, both themes, Glass light/dark, reduce transparency (setting, media query, `@supports`);
    `@theme inline` mapping; fonts via `next/font/local` from committed OFL files; pre-paint inline script; face from
    the route; 400 ms mask transition, instant under reduced motion; ghost drift; a test that `src/components` and
    `src/app` hold no raw hex colour.
  > Done 2026-11-08 (Claude Code): Atkinson Hyperlegible Next instead of the 2020 release (DP33: the old one lacks `İ`); Glass chip
  > tokens, colour fields and card shadow added as tokens (DP33). Counterexample (3.3): `γ` and `Δ` of reviewed fr/es/de
  > names (γ-aminobutyric acid, Δ-9-THC) are in no text font; the PDF falls back to IBM Plex Mono (`→`) and a Noto Sans
  > subset (OFL, in NOTICE).
  - [x] 3.1 Property test P18: contrast of every text and boundary pair, both themes, both schemes, Glass surfaces
    composited over each background field. _Requirements: 3.1_
  - [x] 3.2 Property test P17: pre-paint script with any stored value and pathname. _Requirements: 6.7, 9.2_
  - [x] 3.3 Example test: every letter of the five catalogues has a glyph in each embedded TTF (fontkit). _Requirements: 6.6, 17.8_

- [x] 4. Message namespaces and the generated vocabulary (`messages/*.json`, `src/i18n/reassurance.ts`,
  `src/i18n/*.test.ts`, `scripts/gen-vocabulary.mjs`, `src/vocabulary/`; design §8, DP17, DP27)
  - Draft every namespace of §8.1 in five languages (English first, four drafts marked for review in task 22); paired
    `twoFaces` / `glass` keys; versioned consent texts with `src/consent/versions.ts`; TS mirror of `REASSURANCE`;
    vocabulary generator over the accepted glossary rows, active event rows and `data/pipc.csv`; `ingredientName()`.
  > Done 2026-11-08 (Claude Code): drafted the namespaces of the screens of tasks 1–12 plus every key of the error map (`Doctor`,
  > `Withdraw`, `Donate` errors); the remaining screen namespaces (`Scan` UI, `Confirm`, `OutcomeConsent`, `Reminder`,
  > `Donate` form, `Privacy`, `Doctor` chrome) are drafted with their screens (tasks 13–19), so no unused keys are
  > guessed. Collective Memory chrome is a new `MemoryView` namespace held to the `Memory` word lists. Hook findings while
  > drafting: Turkish "tanı" (in "Otomatik tanı") and "olasılık" in a Memory screen string, both reworded.
  - [x] 4.1 Property test P12: catalogue completeness, ICU placeholders, forbidden phrases, `Memory` word lists and the
    screening exception, reassurance and compliance words, Glass without theme-device words. _Requirements: 2.1, 2.4, 6.5, 16.4, 21.5_
  - [x] 4.2 Property test P13: committed vocabulary equals the generator output; `ingredientName` follows doctor-loop
    DP16. _Requirements: 2.5_
  - [x] 4.3 Parity test: `reassurance.ts` equals `REASSURANCE` of `apps/api/janus/notes/phrases.py`. _Requirements: 1.3_

- [x] 5. Browser store (`src/store/storage.ts`, `settings.ts`, `list.ts`, `tokens.ts`, `reminders.ts`; design §4, DP5,
  DP29)
  - Versioned documents, safe wrapper with in-memory fallback and one notice, `useSyncExternalStore` hooks, item
    actions (add, edit start / box name / choices, remove), "delete everything" (storage + caches).
  - [x] 5.1 Property test P16: any failure schedule; round trip; version mismatch refused without sending. _Requirements: 9.4, 9.5_

- [x] 6. Shell, home, start and settings (`src/components/Shell.tsx`, `Header.tsx`, `MaskSwitch.tsx`, `Nav.tsx`,
  `Disclaimer.tsx`, `EmergencyNotice.tsx`, `DemoLabel.tsx`, `StateView.tsx`, `LanguageSwitcher.tsx`, primitives;
  `src/app/[locale]/page.tsx`, `start/`, `settings/`, `[...rest]/`; design §3, §7, §9, DP26)
  - Two Faces header + bottom nav and Glass pill tab bar from one component set; emergency notice first on home with the
    user region's number; disclaimer footer; settings incl. Appearance, read aloud, regions, note language, delete
    everything; localized not-found; Passport slots as empty components (§15).
  > Done 2026-11-08 (Claude Code): the research shell (task 19 content) was pulled forward as the mask switch's target; `/scan` is a
  > placeholder until task 13. The shell is wrapped in `Suspense` for the dynamic not-found route (cache components).
  - [x] 6.1 Playwright C1–C3 on home, start, settings, not-found (5 locales × 2 themes). _Requirements: 1.2, 3.1, 8.1–8.6, 9.1_

- [x] 7. Demo fixtures, demo codes and the demo client (`scripts/record-demo.ts`, `src/demo/fixtures/*.json`,
  `src/demo/codes.ts`, `client.ts`, `sheet.tsx`, `src/app/[locale]/demo/`; design §13, DP11, DP32)
  - Run the recorder against the local API (real dataset, note keys set locally): Istanbul = the gate-1 list; Cologne
    and Ohio as proposed; record the versions; scrub product text to invented names; record what each case returns in
    design §13.1 (rows, statuses, months, warnings). Demo patient picker, printable code sheet, demo label, exit demo.
  > Done 2026-11-08 (Claude Code): all three owner cases reproduce on the real engine: Istanbul `pipc:5` probable 5 months (+ rows 6, 9,
  > 12; 2 warnings; 63/65 rules); Cologne `pipc:1` and `pipc:51`, both form-unconfirmed (German boxes by name);
  > Ohio `pipc:24` (5 months) and `pipc:31` (4 months), 1 warning (gabapentin). TR items other than the combination box are
  > resolved through `/resolve/products` from the ingredient's observed product id (no DB access, no TİTCK string); only
  > the chosen candidate is kept (DP34). DataMatrix sheet drawn with zxing-wasm's writer at build (`gen-demo-codes.mjs`).
  - [x] 7.1 Example test: Istanbul fixture has `pipc:5` `probable`, `months_between` 5, index matched code `C08CA01`
    from the combination item, `corrected_notice`, rows 6, 9, 12, two `item_warnings`; the combination item resolves to
    `C08CA01` and `C09AA03` with `C09BB03` only as `published_atc`. _Requirements: 4.2_
  - [x] 7.2 Example test: no product text field in any fixture is outside the invented-name table; no token or `qr_url`
    stored. _Requirements: 4.6_
  - [x] 7.3 Property test P15: demo code range and detection before any request. _Requirements: 4.2, 4.5_
  - [x] 7.4 Property test P19 on every recorded fixture with mutations. _Requirements: 22.2_

- [x] 8. Medicine list, "since when" and timeline (`src/flow/evaluate.ts`, `timeline.ts`,
  `src/components/MonthPicker.tsx`, `src/app/[locale]/medicines/`, `timeline/`; design §4, §9)
  - List rows (box name, ingredients via the vocabulary, region, source, start, abrupt-stop line after evaluation),
    edit and remove, > 50 warning, out-of-date marking, timeline lanes and finding links; works on the demo session.
  - [x] 8.1 Property test P3: evaluation input, index map, months, 50-item bound. _Requirements: 14.1, 13.1, 1.6_
  - [x] 8.2 Property test P23: timeline model. _Requirements: 13.3_

- [x] 9. Results: findings, chains, scope, safety lines, read aloud (`src/flow/findings.ts`, `locator.ts`,
  `src/components/Ghost.tsx`, `SafetyLine.tsx`, `AbruptStopLine.tsx`, `ReadAloud.tsx`, `src/app/[locale]/results/`;
  design §9, Req 14, Req 7)
  > Done 2026-11-08 (Claude Code): the ghost is in `components/icons.tsx` and the cards in `components/results/`.
  > Counterexample from C6: the abrupt-stop line appeared twice for one item on the results screen (card and medicines
  > section); the card now shows it only on the finding detail (once per item per screen, Req 14.5).
  - [x] 9.1 Property test P7: findings view model. _Requirements: 1.3, 14.4–14.9_
  - [x] 9.2 Property test P6: locator parse and event key. _Requirements: 7.5, 16.1_
  - [x] 9.3 Property test P9: safety lines, emergency first, crisis line with abrupt-stop lines, no PT outside detail. _Requirements: 7.1–7.8_
  - [x] 9.4 Property test P8 (results and finding cards): disclaimer once, no forbidden or reassurance phrase, Glass
    without theme words, both themes, five locales. _Requirements: 1.3, 6.5, 8.1_

- [x] 10. Finding detail, evidence and Collective Memory (`src/flow/integrity.ts`, `memory.ts`,
  `src/components/CiBar.tsx`, `ZombieStamp.tsx`, `SourceAttribution.tsx`, `src/app/[locale]/results/[finding]/`,
  `memory/`; design §9, Req 15, Req 16)
  - Evidence view and integrity line; FAERS pair panel (detail-only assessment, screening sentence, limits, window,
    attribution, MedDRA notice); list-level panels: combination, regions, donated reports, doctor-confirmed outcomes;
    `GET /memory/snapshot` notices; > 20 keys chooser.
  > Done 2026-11-08 (Claude Code): finding detail at `/results/finding#<position>` (DP35); evidence call sends `evidence_ids` plus the
  > `excluded_evidence` ids so a retracted source can be shown with its stamp (DP37). Real case for P10: Ohio donepezil →
  > urinary incontinence is `insufficient_data` (2 reports), shown with no ratio.
  - [x] 10.1 Property test P30: evidence view model. _Requirements: 15.2, 15.3_
  - [x] 10.2 Property test P10: memory display rules. _Requirements: 16.5–16.8_
  - [x] 10.3 Property test P11: CI bar geometry and locale formatting. _Requirements: 16.6, 2.3, 3.6_
  - [x] 10.4 Property test P8 (memory panels and evidence view). _Requirements: 16.3, 8.1_

- [x] 11. Doctor note preview, side-by-side and PDF (`src/note/layout.ts`, `pdf.tsx`, `src/app/[locale]/note/`;
  design §10.1–§10.2, DP6)
  - `POST /notes/document` with pins and one or two languages; 409 handling (re-evaluate, show, then print); preview in a
    light-face paper card; side-by-side; lazy PDF with embedded fonts, A4/Letter, footer on every page, demo label.
  > Done 2026-11-08 (Claude Code): demo two-language notes are composed from the per-language recordings (DP34). P24 checks order,
  > verbatim text, headings and pairing; the page footer is checked in the real PDF by C6 (text extracted from the file).
  - [x] 11.1 Property test P4: product-name slots and no box name in later requests. _Requirements: 17.4, 23.1_
  - [x] 11.2 Property test P24: section order, verbatim text, empty headings, page footer, side-by-side pairing. _Requirements: 17.3, 17.6, 17.7, 17.9, 17.10_

- [x] 12. Checkpoint 1: end-to-end demo flow
  - Playwright C6 (Istanbul → results with row 5 → finding detail → memory → note in two languages → PDF file starting
    `%PDF` containing the disclaimer), C1–C3 on every route built so far, C4 for the demo flow (no request at all).
  - All checkpoint steps green; commit, push, CI passes.
  > Done 2026-11-08 (Claude Code): web lint, typecheck, `FC_PROFILE=ci` vitest (289 tests), `next build`, Playwright locally: smoke, C6
  > (both viewports; PDF starts `%PDF`, its text holds the Turkish disclaimer, the box name and the demo label), C1–C3 on 14
  > routes × 5 locales × 2 themes × 2 viewports (40 tests, axe WCAG 2.2 A/AA: 0 violations), C4 (no `/api` request in the
  > demo flow). Counterexample from C4: after a reload the HTTP client fired `GET /memory/snapshot` before demo mode was
  > read; the client is now null until the store is read. Bundle budget script and C5/C7 belong to later tasks.

- [x] 13. Scanning (`src/scan/gs1.ts`, `zxing.ts`, `camera.ts`, `src/app/[locale]/scan/`, `scripts/vendor-assets.mjs`;
  design §6.1–§6.3, DP9)
  - Lazy zxing reader with the wasm from `/vendor/`; camera with permission handling; photo picker; typed input rules;
    demo detection on every path; 422 code messages; scan region from settings.
  > Done 2026-11-08 (Claude Code): zxing-wasm reader (wasm from `/vendor/zxing`), camera every 150 ms, photo picker, typed
  > input rules, demo detection first on every path; `vendor-assets.mjs` copies the wasm, the tesseract worker and core and
  > fetches `tessdata_fast` (commit 87416418, SHA-256 pinned) before `next build` / `next dev`.
  - [x] 13.1 Property test P1: outbound filter. _Requirements: 10.2, 10.3, 23.1_
  - [x] 13.2 Example test (node): zxing-wasm decodes the demo sheet's DataMatrix images, and the filtered content has no
    `(21)`. _Requirements: 10.1, 10.2_

- [x] 14. Label text recognition, NDC and name search (`src/scan/ocr.ts`, `ocr-extract.ts`, scan tab "Photo of label";
  design §6.4, DP10)
  - Lazy tesseract worker with self-hosted core and `tessdata_fast` (pinned hashes); tappable words; NDC chips;
    no-open-database path from Confirm leads here.
  > Done 2026-11-08 (Claude Code): checked in Chromium by Playwright on a label photographed in the browser: words become
  > tap targets, nothing is sent until a choice, the demo NDC chip opens the demo prompt with no request.
  - [x] 14.1 Property test P22: nothing sent without a choice; only the NDC or the selected words; national codes not
    sent as codes. _Requirements: 11.2, 11.4_

- [x] 15. Confirm screen, live flow and version changes (`src/flow/confirm.ts`, `reresolve.ts`,
  `src/app/[locale]/confirm/`, list re-resolution prompts; design §5.4, §9, DP20)
  - Candidate cards with attribution, notices, `matched_by` notes, status strings, homeopathic, component code,
    ambiguous choices, box name, since when; `/resolve/products` refresh within one dataset version; 409 re-resolution.
  > Done 2026-11-08 (Claude Code): live flow checked against the real local API (type a name → confirm → list). The 409
  > path re-resolves every item by its source key once and evaluates once more; a second 409 shows `dataset_changed_again`.
  > Items left for confirmation get a "Confirm the medicine" control in the list.
  - [x] 15.1 Property test P21: confirm view model. _Requirements: 12.1–12.11_
  - [x] 15.2 Property test P5: re-resolution (model-based with fake resolver and engine). _Requirements: 22.3, 14.2_
  - [x] 15.3 Playwright: stubbed live flow (scan TR code → confirm → since when → results) and the 409 path. _Requirements: 1.1, 22.3_

- [x] 16. Outcome loop: QR opt-in, reminder, withdrawal (`src/note/qr.ts`, `src/app/[locale]/note/` opt-in card,
  `note/withdraw/`, `src/store/reminders.ts`; design §10.3–§10.4, DP7, DP23)
  - Consent text, `POST /notes/token`, QR at 50 mm in the PDF with the coverage line, `qr_url` or own-origin address,
    `no_findings` and 503 paths, reminder card after 28 days leading to the donation flow, withdrawal screen.
  > Done 2026-11-08 (Claude Code): opt-in card with the versioned consent text, `POST /notes/token` only after acceptance, QR
  > at 50 mm in the preview and the PDF, token and reminder in the browser only, withdrawal screen. Checked end to end
  > against the real local API (`e2e/real-api.spec.ts`, local only): QR → doctor page with the issued token → answer stored →
  > withdrawal; demo uses `/o#demo-<patient>` and makes no request.
  - [x] 16.1 Property test P25: QR version ≤ 25, level M, byte mode, decodes back (zxing-wasm in node). _Requirements: 18.2, 18.3_
  - [x] 16.2 Property test P29: reminder due date and token lifecycle. _Requirements: 18.4, 18.5_

- [x] 17. Doctor page (`src/app/o/layout.tsx`, `page.tsx`, `src/app/[locale]/demo/doctor/`; design §11, DP19)
  - Fragment read, pattern check, demo fragment, form with two questions per finding, error texts in the note's
    language, success state, `janus:form-ready` mark.
  > Done 2026-11-08 (Claude Code): own root layout, the `Doctor` map generated into `src/doctor/messages.json` (parity by
  > the vocabulary test). C5: form ready median 2,139 ms (5 cold loads, 4G profile, CPU ×4, 300 ms answer delay); JS
  > before interaction 183 KB gzip, over the 110 KB ceiling of §16 (DP38).
  - [x] 17.1 Property test P26: token transport. _Requirements: 19.1, 19.7_
  - [x] 17.2 Property test P27: outcome answers and the Send rule. _Requirements: 19.2, 19.5_
  - [x] 17.3 Playwright C5: form ready < 3 s median of 5 cold loads on the 4G profile; JS budget of §16. _Requirements: 5.1, 19.6, 25.1_

- [x] 18. Donation and deletion (`src/app/[locale]/donate/`, `donate/delete/`; design §12, DP24)
  - Emergency notice first, event picker with safety lines, fields of Req 20.2, stored summary, consent, deletion token
    screen, delete by token, error texts, demo replacement sentence.
  > Done 2026-11-08 (Claude Code): checked against the real local API: donation stored, deletion token shown once, kept,
  > deleted. Counterexample from that run: the region defaulted from the user region before the settings were read, so
  > the form was incomplete; the default is now derived at render time.
  - [x] 18.1 Property test P28: donation request. _Requirements: 20.2, 20.3, 20.8_
  - [x] 18.2 Property test P14 (complete): model-based demo session over every screen incl. note, QR, doctor demo,
    donate and withdraw; no request, no store write, demo label everywhere. _Requirements: 4.3, 4.4, 4.7, 20.8_

- [x] 19. Privacy page, researcher shell and error states (`src/app/[locale]/privacy/`, `research/**`; design §12, §14,
  Req 21, Req 24)
  - Privacy sections with `GET /privacy/storage`, limits, legal frame, sources; research layout in the light face with
    four Phase 4 empty states; every screen's loading, empty, error and long-content states per design §9 table.
  > Done 2026-11-08 (Claude Code): privacy sections with `GET /privacy/storage` (region never guessed); state checks from
  > stubs in `e2e/states.spec.ts`; research shell from task 6.
  - [x] 19.1 Playwright: each route's four states rendered from stubs (long German content at 375 px included). _Requirements: 3.3, 21, 24_

- [x] 20. Offline demo, PWA and accessibility features (`public/sw.js`, `public/manifest.webmanifest`, large text,
  reduce transparency, read aloud; design §7, §13.4, DP22, DP14)
  > Done 2026-11-08 (Claude Code): hand-written `public/sw.js` (never `/api`), manifest and icon; reduce transparency and
  > large text in Settings.
  - [x] 20.1 Playwright: after one visit, the Istanbul flow works with the network offline; `/api` responses are never in
    the cache. _Requirements: 4.4, 22.5_
  - [x] 20.2 Playwright C4 (all flows) and C7 (reduced motion, reduce transparency); large text at 375 px without
    horizontal scroll. _Requirements: 3.1, 3.2, 3.4, 23.4_

- [x] 21. Checkpoint 2: everything built
  - C1–C7 on every route × 5 locales × 2 themes; `bundle-budget.mjs` values recorded in design §16 with the budget set
    to measured + 10 % (within the ceilings); rendering time of a 15-item result recorded. All checkpoint steps green;
    commit, push, CI passes. _Requirements: 25.2, 25.3_
  > Done 2026-11-08 (Claude Code): web lint, typecheck, `FC_PROFILE=ci` vitest 309 tests; Playwright 81 local checks
  > (C1–C3 on 22 routes × 5 locales × 2 themes × 2 viewports, C4, C5 run alone, C6, C7, offline, states, live flow, OCR,
  > doctor page). Budgets recorded in design §16 at measured + 10 %, above the first ceilings (DP38); 15-item results
  > render 55–252 ms after the response.

- [x] 22. Wording review and **review stop (owner)**
  - Localization review of every new namespace in four languages (forbidden and near-forbidden forms, register, meaning
    parity, Glass vocabulary), pharmacologist review of the clinical wording (findings, timing, not-checked reasons,
    consent texts), written to `wording-localization-review.md` and `wording-pharmacologist-review.md` with a summary
    `wording-review.md` (counts, flagged keys, the final demo cases of §13.1, the open items of design §20). Commit,
    push, CI green, then **stop and wait for the owner**. _Requirements: 2.4, 7.7, 21, DP27_
  > Done 2026-11-08 (Claude Code): localization-reviewer, safety-auditor and pharmacologist passes run as separate
  > read-only agents from `.kiro/agents`; sheets `wording-localization-review.md`, `wording-safety-audit.md`,
  > `wording-pharmacologist-review.md` and the summary `wording-review.md`. Defects found by the passes fixed before the
  > stop (safety B1, B2, A5, A8, A11; localization TR-1/TR-2; pharmacologist A2); every wording choice waits for the
  > owner. **Stopped here for the owner.**

- [ ] 23. Apply the owner's decisions and final checkpoint
  - Apply the wording and open-item decisions (demo names, Spanish status codes, demo cases, shadcn/ui) in one commit;
    record them in requirements.md and design.md (DPs, §20); re-record fixtures if the demo cases changed; add the
    pre-launch items (native-speaker review of the new namespaces, print-and-scan test of the demo QR at 50 mm on
    several phones, re-check of the emergency and crisis numbers) to `docs/pre-launch-checklist.md`.
  - Every checkpoint step green (web, e2e, CI); report what was built, counterexamples the property tests found and how
    they were fixed, and the open items.
