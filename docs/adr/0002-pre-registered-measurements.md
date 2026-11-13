# 0002. Pre-registered measurements

Status: accepted, 2026-11.

## Context

Accuracy numbers on the site (cascade detection, FAERS calibration, model kit precision) are easy to inflate by
choosing thresholds, samples or analyses after seeing the data.

## Decision

Every scientific measurement has a protocol committed and pushed to the public repository before its results
exist: hypotheses, data, sample size, decision rules and analysis. The push is the timestamp. Changes before the
results are amendments; changes after are deviations, reported with both results. A sample that has been looked at
is never reported again as a fresh measurement.

## Consequences

- Hypotheses can fail and are reported anyway (for example cascade detection sensitivity, H1 not met).
- `scripts/reproduce.sh` recomputes every published number from committed files; a weekly workflow checks it.
