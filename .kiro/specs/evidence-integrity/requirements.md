# Requirements: Evidence Integrity ("No Zombie Evidence")

> Draft seed. Refine with Kiro, then let Kiro generate `design.md` and `tasks.md`.

## Introduction
Retracted papers keep being cited for years (on English Wikipedia, citations to retracted papers persisted for a median of 3.68 years — Shi et al., 2026). Janus must never warn a patient, brief a doctor or propose a hypothesis on the basis of retracted or outdated evidence. Every evidence record is checked for retraction and freshness, and the result is visible.

This is a trust layer inside Janus, not a standalone retraction checker (those exist: scite Reference Check, Feet of Clay Detector, RetractionBot, Zotero alerts). Janus's difference is that the check sits in front of patient-facing medical statements.

## Glossary
- **Evidence record:** a row in `evidence` (rule source paper, statistic snapshot, label, ancient text locator, outcome).
- **Integrity status:** `ok`, `corrected`, `expression_of_concern`, `retracted`, `unknown`.
- **Freshness:** the age of the data snapshot behind the record compared with its expected update cadence.

## Requirements

### Requirement 1: Retraction check
#### Acceptance criteria
1. WHEN an evidence record has a DOI THE system SHALL query Crossref for update notices (retraction, correction, expression of concern, including Retraction Watch data) and store the status with the check date.
2. THE system SHALL re-check every DOI at least weekly and after every rule-base update.
3. WHEN a record is `retracted` THE system SHALL exclude it from patient-facing findings, doctor notes and hypothesis cards, and SHALL disable any cascade rule whose only source is retracted.
4. WHEN a record is `corrected` or `expression_of_concern` THE system SHALL show the notice next to the evidence.
5. WHEN the check cannot be completed THE system SHALL mark the record `unknown` and show it; it SHALL NOT silently treat it as `ok`.

### Requirement 2: Freshness
#### Acceptance criteria
1. Every data source SHALL declare its expected update cadence (e.g. TİTCK weekly, BDPM monthly, FAERS quarterly).
2. WHEN a source snapshot is older than twice its cadence THE system SHALL show a "data may be out of date" notice on the affected results.

### Requirement 3: Visibility
**User story:** As a doctor, I want to see that the sources behind the note are current and not retracted, so that I can trust it.

#### Acceptance criteria
1. THE doctor note SHALL carry an integrity line: number of sources, date checked, and "no retracted sources used" — or the exceptions.
2. THE evidence view SHALL show each source's integrity status and check date.
3. THE researcher area SHALL list any evidence that changed status since the last snapshot.

## Properties to test (PBT candidates)
- No patient-facing finding, note sentence or hypothesis card is ever backed only by `retracted` evidence.
- An `unknown` status is never displayed as `ok`.
- Changing a record's status from `ok` to `retracted` removes it from every output and never adds new findings.
- Re-running the check with unchanged Crossref responses produces identical statuses (idempotence).
