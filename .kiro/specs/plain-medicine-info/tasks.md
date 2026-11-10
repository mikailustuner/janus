# Implementation Plan: Medicine information in your own language

> Requirements in `requirements.md`, design and decisions in `design.md`. No database change. Nothing pushed, merged
> or deployed in this work. Expert review has not yet been done.

- [x] 1. Spec: requirements (EARS) and design with decisions and properties
  - _Requirements: all_
- [x] 2. Source and pipeline `us_labels` (`pipelines/janus_pipelines/jobs/us_labels.py`)
  - openFDA label source in `pipelines/sources.toml`, NOTICE regenerated, steering row; tests on synthetic files.
  - _Requirements: 3.1-3.3_
- [x] 3. Covered groups (`apps/api/janus/plaininfo/groups.csv`, `groups.py`)
  - 31 ATC groups, name and one sentence per group in five languages, written once, never composed; status per row.
  - _Requirements: 2_
- [x] 4. Official texts and route (`official.py`, `router.py`, `main.py`)
  - Label section quoted as published (English, never translated), cut only at the end and flagged; medicine-info route.
  - _Requirements: 3.4-3.7, 4_
- [x] 5. API properties and tests (`apps/api/tests/test_plaininfo_properties.py`)
  - Also regenerates the design table, the recorded demo file and the web fixture.
- [x] 6. Web: query, client, hook, model (`apps/web/src/plaininfo/*`), page and component
  (`components/plaininfo/MedicineInfo.tsx`), link from the medicine list, texts in five languages
  - Loading, empty, error with retry, demo mode from the recorded file, not-on-the-list state.
  - _Requirements: 5_
- [x] 7. Review fixes: wording, quotation note, derived files regenerated
- [x] 8. End-to-end tests (`apps/web/e2e/plain-info.spec.ts`, `routes.spec.ts`)
  - Five languages, phone and desktop, accessibility checks; the US item uses a real lisinopril (C09AA03) ingredient.
- [ ] 9. Open items
  - Review of every template sentence (`groups.csv`, all five languages) by a health professional who speaks the
    language. Expert review has not yet been done; rows keep their review status until then.
  - Deploy and the first real `us_labels` run on the server (not part of this branch).
