# Requirements: Collective Memory

> Draft seed. Refine with Kiro, then let Kiro generate `design.md` and `tasks.md`.

## Introduction
Show how often the same medicines and events appear together in public adverse-event **reports** (FDA FAERS from day one), plus consented Janus contributions and doctor-confirmed outcomes, with standard pharmacovigilance statistics and strong privacy. Counts are always described as reports, never as people.

## Glossary
- **2×2 table** for drug D and event E: a = reports with D and E; b = D without E; c = E without D; d = neither.
- **PRR** = (a/(a+b)) / (c/(c+d)). Signal (Evans): PRR ≥ 2, χ² ≥ 4, a ≥ 3.
- **ROR** = (a·d)/(b·c); 95% CI = exp(ln ROR ± 1.96·√(1/a+1/b+1/c+1/d)); signal if lower bound > 1.
- **Layers:** `faers` (public), `contributions` (Janus users), `outcomes` (doctor-confirmed). Never mixed into one number.
- **Reporter region:** TR, EU or US, derived from the FAERS occurrence/reporter country field where present.

## Requirements

### Requirement 1: Statistics
#### Acceptance criteria
1. WHEN asked for (D, E) THE system SHALL return a, b, c, d, PRR, ROR with 95% CI, χ², the snapshot date and the layer.
2. WHEN any cell is zero THE system SHALL apply the Haldane correction (+0.5) and mark the result as corrected.
3. WHEN a < 3 THE system SHALL label the result "insufficient data" and SHALL NOT call it a signal.
4. THE system SHALL state on every FAERS result that it is spontaneous reporting, not incidence, and not deduplicated.
5. All user-facing text SHALL describe counts as "reports" (e.g. "2,300 reports"), never as "people" or "people like you".

### Requirement 2: Combination view
**User story:** As a caregiver, I want to see how often these same medicines appear together in reports so that I know this pattern has been seen before.

#### Acceptance criteria
1. WHEN given a set of ingredients THE system SHALL return the count of FAERS reports containing all of them and the top reported events with their statistics.
2. WHEN the combination count is below the display threshold THE system SHALL fall back to pairwise results and say so.

### Requirement 3: Regional view
#### Acceptance criteria
1. WHERE the reporter country is present THE system SHALL let the user filter FAERS results by reporter region (TR, EU, US, other) and SHALL show how many reports lack a country.
2. THE system SHALL link to EudraVigilance public reports (adrreports.eu) for EU users and SHALL NOT ingest EudraVigilance data.

### Requirement 4: Contributions and outcomes
#### Acceptance criteria
1. WHEN a user donates with explicit consent THE system SHALL store only the fields allowed by the privacy spec and return a deletion token.
2. Doctor-confirmed outcomes SHALL be reported separately from patient reports.

### Requirement 5: Privacy of aggregates
#### Acceptance criteria
1. THE system SHALL NOT display any aggregate from `contributions` or `outcomes` for a group smaller than k = 20.
2. THE system SHALL add Laplace noise (configured ε) to counts from `contributions` and `outcomes`, clamp at zero and round to integers.
3. FAERS counts SHALL be shown without noise.

## Properties to test (PBT candidates)
- PRR and ROR are always positive and finite after correction; ROR's CI lower bound ≤ ROR ≤ upper bound.
- Swapping the roles of "exposed" and "unexposed" inverts ROR (ROR' = 1/ROR) for tables without zero cells.
- Scaling all four (non-zero) cells by the same factor k > 1 leaves PRR and ROR unchanged and narrows the ROR CI.
- Regional counts sum to the total (TR + EU + US + other + unknown = all).
- No output from user layers ever represents a group with fewer than 20 people.
- Noised counts are never negative and never non-integer.
- The result for (D, E) does not depend on the order in which reports were loaded.
- No rendered sentence uses "people" for a FAERS count.

## Open items from cascade-engine (2026-11-07)
- **FAERS statistics in findings.** A finding's `evidence_ids` has room for `faers_stat:` ids
  (cascade-engine Req 2.7, Phase 2). They must be registered as evidence and pass the same `cite`
  filter. Counts are reports, never people.
