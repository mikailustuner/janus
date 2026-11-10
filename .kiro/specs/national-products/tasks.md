# Implementation Plan: National products (Canada, Italy)

> Requirements in `requirements.md`, design in `design.md`. Nothing pushed, merged or deployed.

- [x] 1. Licence re-check on the official pages; `sources.toml`, `NOTICE`, `data-sources.md`
  - _Requirements: 1_
- [x] 2. Pipeline jobs `ca_dpd`, `eu_it_aifa`, CLI registration, tests (`tests/test_national_jobs.py`)
  - _Requirements: 2_
- [x] 3. Pure preparation, mapping additions, loader inputs, migration 0015
  - _Requirements: 3, 4_
- [x] 4. Strength reading for both sources; dose-form table unchanged
  - _Requirements: 5_
- [x] 5. Passport listing, presence, schemas; name search for Italy; Canada target-only
  - _Requirements: 6, 7_
- [x] 6. Web: types, decoders, attribution, passport rows, texts in five languages
  - _Requirements: 6.1, 9_
- [x] 7. Deployment: weekly step in `deploy/titck-refresh.sh`; `sync-data.sh`, `load-data.sh` unchanged
  - _Requirements: 8_
- [x] 8. Playwright with a new target (`e2e/passport-products.spec.ts`, Italy and Canada; the Cologne demo records both)
  - _Requirements: 10.1_
- [x] 9. Automated read-only passes of the safety-auditor and localization-reviewer agents; fixes applied
  (`review-safety-auditor.md`, `review-localization.md`). Expert review has not yet been done.
  - _Requirements: 10.2_
- [x] 10. Checks: ruff, format, pyright, pytest (api, pipelines), notice --check, web lint/types/tests, compose check, shellcheck

## Measured on the real extracts (2026-11-10, full dataset with TITCK, BDPM, CIMA, openFDA, Wikidata)
| | Canada (human DIN) | Italy (authorised, non-homeopathic) |
|---|---|---|
| Products | 11,487 | 85,669 |
| Fully mapped (listable) | 9,963 (86.7 %) | 74,508 (87.0 %) |
| Multi-ingredient fully mapped | 54.2 % | 65.2 % |
| Names mapped | 1,354 of 1,890 | 1,826 of 2,770 |
| Identifier | 100 % DIN | 100 % AIC |
| Form group | 0 % (no reviewed rows) | 0 % (no reviewed rows) |
| Strength normalised | about 19 % of listable lines (per mL / per g, no form group needed) | about 3 % |
| UPC | 0 of 7,617 package lines | no GTIN column |
