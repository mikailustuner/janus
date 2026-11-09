# Implementation Plan: Weekly data-quality report

> Requirements in `requirements.md`, design and decisions DQ1-DQ9 in `design.md`. No `apps/web` change (the web step
> builds the screen from design §9). No TİTCK string in the repository; upstream drafts stay in `docs/internal/`.

- [x] 1. Spec: requirements (EARS), design with decisions and properties
  - _Requirements: all_
- [x] 2. Pure checks and classification (`janus/quality/checks.py`)
  - Reduction to counts (`ProductView`, `reduce_products`), four checks, reasons, classes. Properties P1-P4, P8.
  - _Requirements: 1, 2, 4.2_
- [x] 3. Pure diff, version and outputs (`janus/quality/report.py`)
  - Stable ids, new/persisting/resolved, class change, version hash, JSON, CSV, Markdown, attribution with dates.
    Properties P5-P7.
  - _Requirements: 3, 4.1, 4.3, 4.4, 5.2, 5.4_
- [x] 4. Offline build (`python -m janus.quality.build [--publish]`)
  - `gather` + `prepare_inputs`, runs/current layout, open copy with `datapackage.json`; counts-only output.
  - _Requirements: 5.1, 5.3, 7.2_
- [x] 5. Read-only routes and public API document
  - `/open/data-quality` (.csv, .md), 503 contract, `docs/openapi-public.json`, `docs/open-api.md`, `docs/open-data.md`.
  - _Requirements: 6_
- [x] 6. Registry and NOTICE
  - `data_quality` with `cadence_days = 7`; `janus-pipelines notice`.
  - _Requirements: 7.1_
- [x] 7. Upstream drafts (private)
  - `docs/internal/upstream-reports/wikidata-edit-list.md`, `titck-letter-draft.md`; marked for pharmacist check; not
    committed, nothing sent.
  - _Requirements: 8_
- [x] 8. Review: safety auditor (read-only); fixes applied (`review-safety-auditor.md`)
- [x] 9. First real run published (`data/open/data-quality/`); checks: ruff, format, pyright, pytest, license guard,
  log guard, `janus-pipelines notice --check`
- [ ] 10. Pharmacist review of the 102 needs-pharmacist findings; confirmed ones into `data/atc_code_exclusions.csv`
- [ ] 11. Weekly scheduling of the build after `titck` (manual today)
