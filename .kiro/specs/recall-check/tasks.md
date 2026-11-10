# Implementation Plan: Recall check (US, FDA enforcement reports)

> Requirements in `requirements.md`, design and decisions DP-R1-DP-R10 in `design.md`. No database change. Nothing
> pushed, merged or deployed in this work.

- [x] 1. Spec: requirements (EARS), design with decisions and properties
  - _Requirements: all_
- [x] 2. Source and licence
  - `openfda_enforcement` in `pipelines/sources.toml` (CC0 1.0, FDA credit, FDA's two limits), NOTICE regenerated,
    `.kiro/steering/data-sources.md` row.
  - _Requirements: 1.1_
- [x] 3. Pipeline job `us_recalls` (`pipelines/janus_pipelines/jobs/us_recalls.py`)
  - Bulk download through the shared fetcher; one row per record; text as published; ISO dates; exclusions with
    reasons; count check against the index. Tests on synthetic files, no network. First real run recorded in
    design §3.
  - _Requirements: 1.2, 1.3, 2_
- [x] 4. Pure text reading and matching (`janus/recalls/codes.py`, `match.py`)
  - NDC keys from the record's text, lot codes, query, index, order. Properties P1-P8.
  - _Requirements: 3_
- [x] 5. Store and route (`store.py`, `router.py`, `main.py`)
  - In-memory index reloaded when `current` moves; `POST /recalls/check`; 422 without echo; 503; notices; the
    contract fixture for the web app. Property P9 and route tests.
  - _Requirements: 4, 7.1_
- [x] 6. The lot on the device (`scan/gs1.ts`, `flow/pending.ts`, `store/list.ts`, `recall/lot.ts`)
  - Properties W1, W2; the outbound-filter property extended.
  - _Requirements: 5_
- [x] 7. Query, client, hook and notice (`recall/*`, `components/recall/RecallCheck.tsx`), confirm screen and
  medicine list, texts in five languages
  - Properties W3-W7.
  - _Requirements: 6_
- [x] 8. Playwright with axe (`e2e/recall.spec.ts`): five languages × two themes × 375 px and 1280 px
  - _Requirements: 6.9, 8.2_
- [x] 9. Deployment data path: weekly `us_recalls` step in `deploy/titck-refresh.sh`; `sync-data.sh` and
  `load-data.sh` unchanged
  - _Requirements: 7_
- [x] 10. Automated read-only passes of the safety-auditor and localization-reviewer agents; fixes applied
  (`review-safety-auditor.md`, `review-localization.md`). Expert review has not yet been done.
  - _Requirements: 8.4_
- [x] 11. Checks: ruff, format, pyright, pytest (api, pipelines, mcp), `janus-pipelines notice --check`, web lint,
  types, unit tests, Playwright, compose check, shellcheck
- [ ] 12. Open items (design §11): first run of the weekly step on the server; MCP tool; a readable record link;
  lot ranges and "all lots"; other regions' recall sources; expert review of the wording
