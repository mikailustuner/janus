# Requirements: Light Face ("Dead Drugs Rise")

> Draft seed. Refine with Kiro, then let Kiro generate `design.md` and `tasks.md`.

## Introduction
For researchers and clinicians: turn side-effect knowledge around to generate drug-repurposing **hypotheses** — inverse signals, side effect → new indication, and patient-reported unexpected benefits. Spontaneous-report signals are weak evidence on their own (literature requires validation in vivo, ex vivo and in trials), so the method's credibility comes from **retrospective validation**: it must rediscover known repurposings and report its misses honestly.

## Requirements

### Requirement 1: Inverse signals
#### Acceptance criteria
1. WHEN the upper 95% CI bound of ROR for (drug, condition) is < 1 THE system SHALL list it as a possible protective association.
2. Every inverse signal SHALL carry a reporting-bias warning (including notoriety and indication bias) and the FAERS snapshot date.

### Requirement 2: Side effect → indication mapping
#### Acceptance criteria
1. THE system SHALL use a curated, cited mapping from adverse-effect terms to therapeutic goals (e.g. hypertrichosis → alopecia; weight loss → obesity).
2. WHEN a drug's OnSIDES side effect maps to a therapeutic goal THE system SHALL propose (drug, condition) as a candidate.
3. WHEN OnSIDES has label data for the drug in several regions (US, EU, UK, JP) THE system SHALL show in which regions the side effect is labelled.

### Requirement 3: Unexpected-benefit reports
#### Acceptance criteria
1. WHEN at least k = 20 consented reports describe the same (ingredient, improvement) THE system SHALL show it as a patient-reported signal (with noise per the privacy spec).

### Requirement 4: Hypothesis cards
**User story:** As a researcher, I want each candidate as a transparent card so that I can judge whether to investigate it.

#### Acceptance criteria
1. Each card SHALL show: candidate (drug, condition), which signal types support it, statistics with CI, sources (integrity-checked), possible mechanism (ChEMBL target, if any), and the label "candidate worth investigating — not a treatment".
2. THE system SHALL let researchers export cards and the anonymized aggregate dataset under an open license.
3. Hypothesis cards SHALL be shown in the researcher area, not in the patient flow; the patient flow only asks the "unexpected improvement?" question.

### Requirement 5: Retrospective validation (credibility gate)
#### Acceptance criteria
1. THE engine SHALL be evaluated on a fixed, cited set of known historical repurposings (at least: minoxidil → alopecia, thalidomide → multiple myeloma / erythema nodosum leprosum, sildenafil → its later indication) using data that does not include the later indication where possible.
2. THE system SHALL publish the evaluation (hits, misses, rank of each known case, data snapshot) in the researcher area and in `docs/`.
3. WHEN the evaluation shows no known case in the top results THE light face SHALL be presented as experimental in the demo.

## Properties to test (PBT candidates)
- A candidate never appears without at least one supporting signal and one non-retracted source.
- Adding unrelated reports never removes an existing candidate's supporting evidence.
- No card text contains forbidden treatment language in any supported language.
- The evaluation is deterministic for a fixed data snapshot.

## Open items from collective-memory (2026-11-08)
- The researcher area reads the same counts file through `janus.memory.reader.CountsReader` (read-only, in process); there is
  no PT search endpoint in `collective-memory` (DP21). Inverse signals use the same statistics (`janus.memory.stats`): Yates
  chi-squared, Woolf interval, Haldane when a cell is zero, `MIN_REPORTS = 3`, and the sensitivity table with N = all reports.
- Lists are ordered by report count, never by the ratio. Every inverse signal carries the screening sentence
  (`Memory.screening`), the limits sentences and the snapshot date and window. Reporting bias (notoriety, indication bias) is
  this spec's own warning. Evans criteria (Yates-corrected chi-squared) are screening criteria and 65 percent of examined pairs
  meet them: do not present them as findings.
