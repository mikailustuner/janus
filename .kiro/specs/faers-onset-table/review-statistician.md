# Statistician review (agent `.kiro/agents/statistician.md`, read-only), 2026-11-09

Two passes on the code and the real output. AI review; a human statistician has not reviewed this yet.

## First pass: 3 blockers, 8 should-fix, 3 notes
| # | Finding | Severity | Resolution |
|---|---|---|---|
| S1 | One event date per report, not per term (74-100 % of dated reports list several terms) | blocker | Caveat `event_date_report_level`; per-row `multi_event_reports` |
| S2 | Clusters of identical date pairs across distinct cases dominate rows 3, 6, 38, 48 | blocker | `largest_date_cluster`, `reports_in_clusters_ge3`, status `cluster_dominated` (> 25 %) with counts only; `median_days_distinct_date_pairs`; caveat `clusters` |
| S3 | Percentile bootstrap gives zero-width median intervals on tied data | blocker | Exact order-statistic interval with coverage added and made primary; `median_ci_degenerate` |
| S4 | Weibull shape mostly measures heaping and truncation | should-fix | Shape only for n ≥ 30, zero-day share ≤ 0.5, ≥ 5 distinct intervals; renamed `weibull_shape_class`; caveat `weibull`. Interval-censored likelihood: open item |
| S5 | Shortest-interval rule biases after within-class switches | should-fix | Method reworded; `multi_line_reports`, `median_days_earliest_class_start` |
| S6 | Day-one flag nondeterministic on tied lines | should-fix | `bool_or` over the tied shortest lines |
| S7 | Day-one sensitivity silent when skipped; 1 January not split | should-fix | `reports_without_day_one`, `sensitivity_omitted_reason`, `jan_one_reports`; caveat says it is not a correction |
| S8 | No per-row exclusion breakdown | should-fix | `faers_onset` `pairs` side table; `candidates_without_interval_by_reason` |
| S9 | Shares published on count-only rows | should-fix | Null on `count_only` |
| S10 | Overstating wording (selection, small sample, unit vs dedup) | should-fix | Reworded ("may", "estimates are unstable", case-id unit) |
| S11 | Window ambiguous (receipt vs event dates) | should-fix | `faers_receipt_quarters`; `event_year_min/max`; caveat `receipt_window` |
| S12-S14 | Interpolated quartiles; seed reproducibility; researcher needs | notes | Method states interpolation and Python 3.12 `random.Random`; `distinct_intervals` |

## Second pass: fixes hold, 2 should-fix, 3 notes
- Two median intervals, none primary → `method.primary_median_interval = "exact"`, caveat reworded, exact columns
  first in the CSV. **Fixed.**
- Median only shows heaping when most intervals are 0 days (rows 23, 47, 52) → `median_reflects_zero_heaping` and a
  sentence in caveat `zero_day`. **Fixed.**
- Notes: the share-based cluster rule leaves a 21-case cluster in row 2 (7.6 %; the distinct-date-pairs median covers
  it); all 18 shapes are `early` (summary now counts shape classes); the route filter moved counts (pharmacologist
  confirmed the topical exclusion intent).
