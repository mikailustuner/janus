# Implementation Plan: FHIR export

> Scope: design.md §2. Properties refer to design §5, decisions to §6. No server change.
> **Checkpoints** run in `apps/web`: `pnpm lint`, `pnpm typecheck`, `FC_PROFILE=ci pnpm test`, then
> `pnpm build` and `E2E_PORT=3402 pnpm exec playwright test e2e/fhir-export.spec.ts`; then commit (only the
> paths below; never `docs/kiro-usage.md`).

- [x] 1. Verify the sources
  - R4 status value set (`valueset-medication-statement-status.html`, 4.0.1): `recorded` is not an R4
    code (DP1). Schema URL `http://hl7.org/fhir/R4/fhir.schema.json` (200, 3 386 892 bytes, draft-06;
    identical to the file in `fhir.schema.json.zip`); licence CC0 (`license.html`, §2.20.2).
  - _Requirements: 1.4, 2.1_

- [x] 2. Schema fixture and validator
  - `src/fhir/schema/fhir.schema.json.gz` + `README.md` (source, date, SHA-256, licence); `validate.ts`
    (Ajv 8.17.1 devDependency, draft-06 meta-schema, root `id` → `$id` in memory; DP10, DP11).
  - `pipelines/sources.toml` entry `fhir_r4_schema`; NOTICE regenerated (`janus-pipelines notice`).
  - _Requirements: 6.1_

- [x] 3. Builder (`src/fhir/bundle.ts`, pure)
  - `itemIngredients`, `buildBundle`, `exportSummary`, `fileName`, `serialise` (design §3; DP1–DP9).
  - _Requirements: 1.1, 1.4, 2.1–2.6, 3.1–3.4, 4.1, 4.2_

- [x] 4. Property tests (`src/fhir/bundle.test.ts`)
  - P1–P8; schema hash; validator rejects a bad month and an unknown element; the three demo patients
    with and without product names; Istanbul summary 9 / 10 / 10; the combination shape.
  - _Requirements: 6.1, 6.2_

- [x] 5. Checkpoint 1: builder verified
  - lint, typecheck, vitest green; commit.

- [x] 6. Card (`src/components/medicines/FhirExport.tsx`) on the medicines screen
  - Design §4; Blob download; checkbox not stored; demo line; live confirmation.
  - _Requirements: 1.2, 1.3, 1.5, 5.1–5.6_

- [x] 7. Texts: namespace `Fhir` in `messages/{en,tr,de,fr,es}.json`
  - Added as one block; `pnpm exec vitest --run src/i18n` (forbidden phrases, parity, no empty strings).
  - _Requirements: 5.2, 5.5, 5.6_

- [x] 8. Reviews
  - `fhir-export-localization-reviewer-review.md`, `fhir-export-safety-auditor-review.md`; fixes applied.
  - _Requirements: 5.6_

- [x] 9. Playwright (`e2e/fhir-export.spec.ts`)
  - Demo session: download, parse, Bundle / collection, entry count, no box names, box names when
    ticked, no request; axe, scroll, targets at 375 and 1280, both themes, five locales (`E2E_LOCALES`).
  - _Requirements: 6.3_

- [x] 10. Checkpoint 2: everything built
  - All checkpoint steps green; screenshots at 375 and 1440, both themes, looked at; pre-launch item
    for full HL7 validation (design §7); commit.
