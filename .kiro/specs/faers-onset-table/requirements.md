# Requirements: FAERS time to onset for all 65 PIPC cascades

> Owner request 2026-11-09. Extends the time machine's onset method (`.kiro/specs/time-machine/`, Req 6, design
> §6.1, §7.2: `faers_onset` pipeline, `janus.timemachine.onset`) from three curated cascades to every row of the PIPC
> list, as an open descriptive dataset. The web screen is built later by the `experience` step from the contract in
> design §7; this spec does not touch `apps/web`.

## Introduction
For each PIPC row (drug A's class → adverse event → drug B), how long after starting drug A do FAERS reporters say
the event began? The time machine answered this for three cascades. Researchers need the same descriptive numbers,
made the same way, for all 65 rows, with the count of reports behind each number, the share of reports that could
be used at all, and the caveats that keep the numbers honest: spontaneous reports, a non-representative subset,
heaping at zero days and at the first day of a month, and no causal or incidence meaning.

## Glossary
- **Class members:** ingredient keys with at least one ingredient-level ATC code in drug A's class, matched with the
  cascade engine's `class_match` (form extensions off) on the codes of the prepared resolution dataset.
- **Event terms:** the MedDRA Preferred Terms of the row's Janus event key (`memory_events.csv`; every PIPC row has
  exactly one adverse key).
- **Candidate report:** a FAERS report (one row of the `faers` artifact) in which a class member is a primary or
  secondary suspect (`PS`, `SS`) and an event term is reported.
- **Interval:** for a candidate report, the shortest `faers_onset` interval (earliest complete therapy start of the
  drug line → event date, 0-3650 days) over its class-member suspect lines.
- **Usable share:** reports with an interval / candidate reports.

## Requirements

### Requirement 1: One row per PIPC row
1. THE dataset SHALL contain exactly one row for each PIPC position 1-65, with the PIPC text (system, drug A,
   adverse event, drug B, locator) unchanged.
2. EACH row SHALL name drug A's class, its member keys, the event key and its event terms, and the other positions
   that share the same (class, event key) pair.
3. Rows that share a (class, event key) pair SHALL have the same counts and statistics.

### Requirement 2: Counts and data quality
1. EACH row SHALL give the number of candidate reports, the number with an interval and the usable share.
2. Counts SHALL be named reports, never people; the dataset SHALL state that FAERS is spontaneous reporting, not
   incidence and not deduplicated across cases.
3. THE dataset SHALL give the FAERS window (quarters), the snapshot date, the run ids of `faers`, `faers_onset` and
   the count build, the resolution dataset and the rule-base version, and the global exclusion counts of
   `faers_onset` by reason.
4. EACH row SHALL give the number and share of zero-day intervals and of intervals that rest on a date on the 1st of
   a month, and a sensitivity median without the latter WHEN at least 10 such intervals remain.

### Requirement 3: Statistics (same method as the time machine)
1. WHEN a row has at least 10 reports with an interval, THE row SHALL give the empirical median and quartiles, a 95 %
   percentile bootstrap interval of the median and the Weibull shape with its 95 % likelihood-ratio interval and
   hazard pattern (Cornelius 2012; Hatahira 2017; Hasegawa 2020).
2. WHEN a row has 1-9 reports with an interval, THE row SHALL publish the count only, with no median and no shape,
   and SHALL say why.
3. WHEN a row has 10-29 reports with an interval, THE row SHALL be flagged `small_sample`.
4. WHEN a row has no candidate report or no interval, THE row SHALL say which.
5. THE bootstrap SHALL be seeded from the row's (class, event key) and SHALL NOT depend on the order of the reports.

### Requirement 4: Honest framing
1. EVERY row and the dataset SHALL carry `descriptive_only = true`, `causal = false`, `incidence = false` and
   `counts_are = "reports"`.
2. THE dataset SHALL carry the caveats: descriptive only, not incidence, selection of the dated subset, zero-day
   heaping, first-of-month dates, shared rows, class membership without route, small samples.
3. No text of the dataset SHALL recommend starting, stopping or changing a medicine (medical-safety.md).

### Requirement 5: Licences and outputs
1. THE dataset SHALL be released under CC BY 4.0 with attribution to the PIPC paper (CC BY 4.0) and to FAERS (CC0, not
   an FDA endorsement) and SHALL carry the MedDRA notice.
2. THE build SHALL write JSON and CSV under `<JANUS_DATA_DIR>/onset_table/runs/<run>/`, move `current`, and with
   `--publish` write `data/open/faers-onset/` with a Frictionless `datapackage.json`.
3. THE build SHALL refuse WHEN `faers_onset` or the count build rests on another `faers` run, or the count build on
   another resolution dataset.

### Requirement 6: Read-only API
1. THE API SHALL serve `GET /open/faers-onset` (all rows), `GET /open/faers-onset.csv` and
   `GET /open/faers-onset/{position}` (one row with the caveats), precomputed, as medical routes.
2. 503 `onset_table_unavailable` without a dataset; 404 `unknown_position`; 422 for a position that is not 1-2 digits.
3. THE routes SHALL be in `docs/openapi-public.json`.

### Requirement 7: Review
1. THE statistician agent SHALL review the methods and the pharmacologist agent the class → ingredient mappings, as
   separate read-only reviews; findings and fixes SHALL be recorded in this spec.

### Requirement 8: Quality
1. Property tests: one row per position; shared rows equal; status thresholds; order independence of the
   statistics; count invariants (interval count ≤ candidates, share in [0, 1]); CSV ↔ JSON; fixed framing fields.
2. Route tests: 503, full table, one row, 404, 422.
