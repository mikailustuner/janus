# FHIR export review: safety-auditor

**Date:** 2026-11-09
**Reviewer:** safety-auditor (`.kiro/agents/safety-auditor.md`), run as a separate read-only agent pass against
`medical-safety.md`, `privacy.md` and `product.md`. The reviewer edited no files.

## Scope and method
- Files: `apps/web/src/fhir/bundle.ts`, `apps/web/src/components/medicines/FhirExport.tsx`, the `Fhir` namespace in
  `apps/web/messages/{en,tr,de,fr,es}.json`, the spec (`requirements.md`, `design.md` DP1–DP13), and for context
  `bundle.test.ts`, `e2e/fhir-export.spec.ts`, `src/store/list.ts`, `src/api/decode.ts`, `Shell.tsx`.
- Checks: forbidden phrases and near forms in five languages and in the English file texts; advice to start, stop or
  change a medicine; false reassurance; disclaimer on screen and in the file; personal data that can reach the file;
  network calls in the new code; clinical misreading of FHIR fields; demo labelling.

## What passed
No forbidden phrase in any language; no advice; `notChecked` says the file is not a medical record and not checked, the
same in all five languages; the disclaimer is on every screen and in each statement's `note`; no network call (Blob and
object URL only, e2e asserts it); the patient has only a local id; box names are off by default and not stored; scanned
code, NDC, candidate and source ids, dataset version and search text never reach the file; demo data marked with HTEST;
only the ATC and RxNorm system URIs; no combination code on a single ingredient.

## Findings (all advisory) and what was done
| # | Finding | Done |
|---|---|---|
| A1 | `status: active` with only a free-text note could let an importer merge the statements into a clinical list as confirmed | **Fixed:** `informationSource` = `#patient` and `category` = `patientspecified` (R4 `medication-statement-category`) on every statement (DP1). |
| A2 | HTEST only on the Bundle; lost when a collection is split | **Fixed:** `meta.security` HTEST on every statement in demo mode (DP8); P7 checks it. |
| A3 | Items that need confirmation again are exported unflagged | **Fixed:** a second note "Not confirmed again after a Janus data update; the codes may be out of date." (DP14); P7 checks it. |
| A4 | Several ATC codes on one ingredient may let a system read an indication into the file | Kept (they are the codes Janus holds for the ingredient); added to the pre-launch FHIR review. |
| A5 | The card does not say what the file holds or that anyone with it can read it | **Fixed:** new key `Fhir.contents` in five languages, shown on the card. |
| A6 | Export instant to the millisecond | **Fixed:** `dateAsserted` is the day; `Bundle.timestamp` stays an instant (R4 requires it). |
| A7 | e2e did not check `notChecked` | **Fixed:** the per-locale card test asserts it. |

Pre-launch items raised (FHIR Validator and a real EHR import, ATC/RxNorm redistribution terms, EHDS interoperability
claims, privacy-page wording on the downloaded file) were added to `docs/pre-launch-checklist.md`.

## Not checked by the reviewer
No browser or tests run by the reviewer (the implementer ran them: vitest, Playwright); no native-speaker check; no HL7
Validator run.

## Verdict
Pass, nothing blocking. All fixable advisories applied.
