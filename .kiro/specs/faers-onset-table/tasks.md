# Implementation Plan: FAERS time to onset for all 65 PIPC cascades

> Requirements in `requirements.md`, design and decisions DP-O1-DP-O10 in `design.md`. Reuses the time-machine onset
> method (`janus.timemachine.onset`). No `apps/web` change; the web step builds from design §7.

- [x] 1. Spec: requirements (EARS), design with decisions and properties
- [x] 2. Pure table (`janus/onset_table/table.py`)
  - Thresholds, exact and bootstrap median intervals, clusters, shape gating, sensitivities, framing fields.
    Properties P1-P5, P7-P9.
  - _Requirements: 1, 2.4, 3, 4.1_
- [x] 3. Dataset, caveats, CSV (`dataset.py`); route groups (`routes.py`, P10)
  - _Requirements: 2.2, 2.3, 4.2, 5.1, 5.2_
- [x] 4. `faers_onset` side table `pairs` (route, dose form, reason per report-drug pair); pipeline re-run on the local
  data (same 456,948 rows)
  - _Requirements: 2.1, DP-O3_
- [x] 5. Offline build (`python -m janus.onset_table.build [--publish]`) with consistency refusals; curated
  `data/onset_key_exclusions.csv` and `data/onset_row_notes.csv`
  - _Requirements: 5.2, 5.3_
- [x] 6. Read-only routes, public API document
  - _Requirements: 6_
- [x] 7. Reviews: statistician and pharmacologist agents, two passes each, read-only; fixes applied
  (`review-statistician.md`, `review-pharmacologist.md`)
  - _Requirements: 7_
- [x] 8. First build published (`data/open/faers-onset/`); full checks
- [ ] 9. Open items (design §11): vocabulary terms, doxepin and oral-iron name mapping, interval-censored Weibull,
  human expert review
