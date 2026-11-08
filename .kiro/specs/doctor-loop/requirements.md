# Requirements: Doctor Note and Outcome Loop

> Draft seed. Refine with Kiro, then let Kiro generate `design.md` and `tasks.md`.

## Introduction
Give the doctor a one-page, cited note in the doctor's language, and let the doctor report the outcome via QR without creating an account — turning patient reports into doctor-confirmed outcomes.

## Requirements

### Requirement 1: Doctor note
**User story:** As a family doctor with 10 minutes per patient, I want a one-page summary with sources in my own language so that I can decide quickly.

#### Acceptance criteria
1. THE system SHALL generate a one-page PDF listing medications (ingredient INN, the product name as on the patient's box, ATC, approximate start), rule-based findings with evidence, relevant FAERS statistics with CI, and abrupt-stop warnings.
2. THE PDF SHALL be rendered in the browser; the server SHALL receive only evidence ids and the note token request.
3. Every sentence written by the narrator agent SHALL reference at least one evidence id; the auditor SHALL remove any sentence that does not, and any sentence whose only evidence is retracted.
4. THE note SHALL contain "Janus provides information, not medical advice. Research prototype — not a medical device." and no forbidden phrases in its language.
5. THE note SHALL be available in English, Turkish, German, French and Spanish; the patient's interface language and the note language SHALL be chosen independently.
6. WHEN the note language differs from the patient's language THE client SHALL show the patient a side-by-side version so they understand what the doctor receives.
7. Clinical terms in translated notes SHALL come from a reviewed glossary (ingredient INNs, MedDRA terms, cascade names); free LLM translation SHALL NOT be used for those terms.

### Requirement 2: QR token
#### Acceptance criteria
1. THE note SHALL carry a QR code encoding only note id, expiry and an HMAC signature.
2. WHEN a token is invalid, expired or already used THE system SHALL reject the outcome submission.

### Requirement 3: Outcome reporting
#### Acceptance criteria
1. WHEN a doctor opens a valid QR link THE system SHALL show a single page, in the note's language, listing the findings with options: cascade confirmed / not a cascade / dose changed / medicine changed / stopped / no change.
2. THE system SHALL store outcomes with week granularity and no personal data, rate-limit submissions, and mark the token as used.
3. WHERE the patient opts in, THE client SHALL remind them after 4 weeks to report whether the symptom resolved (stored in the browser only).

## Properties to test (PBT candidates)
- Any modification of a token's payload invalidates its signature.
- A token can be used at most once.
- The generated note never contains a sentence without a non-retracted evidence id.
- For every supported language, the note contains the mandatory disclaimer and none of that language's forbidden phrases.
- Changing the note language never changes the set of findings or evidence ids in the note.

## Open items from cascade-engine (2026-11-07)
- **Abrupt-stop warnings.** `item_warnings` flags every list item whose ingredient is on the
  abrupt-stop list (16 groups, confirmed by the owner); the note shows "Do not stop this
  medicine suddenly." next to that medicine, not only next to findings.
- **Form-unconfirmed findings.** Decide whether findings with `form_confirmed = false` belong in
  the note's main section or in a separate part.
- **Evidence.** Each finding carries `evidence_ids` (rule, PIPC paper, the window paper for
  `probable`, BMJ 2026 where shown, ThinkCascades where supporting, the form-extension paper),
  already filtered by the integrity snapshot; resolve them with `POST /evidence/resolve` for the
  integrity line. `rule_base_version` and `integrity_version` identify what the note was made
  with.

## Open items from collective-memory (2026-11-08)
- **Numbers in the note.** The note prints the statistics it received from `/memory/pair` (cells, ratio with its range,
  report count, snapshot date and window), each with its `citation` (`dataset:faers` plus the locator); it does not re-query
  later, so a rebuild never changes an issued note. A cell with fewer than 3 reports prints the coverage sentence only.
- **Regions.** Regional statistics are cited by the same record with `region=TR|EU|US` in the locator.
- **Outcomes layer.** `collective-memory` defines the interface (`UserLayerSource`: true contributor counts per cell,
  region TR, EU or US); the outcome store of this spec plugs in by returning cells for (ingredient set, Janus event key,
  direction). Until then `POST /memory/shared` answers `not_available` for `outcomes`. Outcomes are released through the same
  k = 20, noise and sibling rule; they are never summed with donations.
- The note carries the safety lines for events whose Janus key has a `safety_line`.
