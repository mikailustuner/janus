# Requirements: The Séance ("Three Witnesses")

> Draft seed. Refine with Kiro, then let Kiro generate `design.md` and `tasks.md`.

## Introduction
Bring three independent witnesses to the same table for a (substance/drug, condition) pair: the **past** (Ibn Sina's Canon Book 2 from OpenITI, plus 10–20 hand-picked Ottoman samples), the **present** (Collective Memory / Light Face signals) and **science** (molecular and literature evidence). Scope for the hackathon: wounds, burns, ulcers and infection.

## Requirements

### Requirement 1: Ancient-text pipeline (offline ETL)
#### Acceptance criteria
1. THE pipeline SHALL import Canon Book 2 from OpenITI (`0428IbnSina.QanunFiTibb`), recording the exact version and the CC BY-NC-SA 4.0 license.
2. THE pipeline SHALL split Book 2 into one entry per heading and keep a locator (book, heading, line range).
3. WHEN an entry mentions a theme keyword (wounds, burns, ulcers, infection) THE pipeline SHALL extract {substance, use, body part/condition} with the reader agent and store the original Arabic span.
4. Translations SHALL be labelled "machine translation"; identifications SHALL cite their source (Hamdard 1998 cited only, PMC3941892 tables) and be marked "uncertain" when sources disagree.
5. An entry SHALL be marked `reviewed` only after human review; the demo SHALL use reviewed entries for headline claims.
6. Ottoman samples SHALL be entered manually with thesis/edition citation and page, as short quotations.

### Requirement 2: Three-witness synthesis
#### Acceptance criteria
1. WHEN asked about (substance or drug, condition) THE system SHALL return each witness separately: past (entries + locators), present (signals with CI), science (targets, papers).
2. THE system SHALL report how many witnesses independently support the pair (0–3) and each witness's confidence; it SHALL NOT merge them into a single "proven" score.
3. WHEN fewer than three witnesses agree THE system SHALL say which are missing.

### Requirement 3: Licensing
#### Acceptance criteria
1. Derived ancient-text data SHALL be published under CC BY-NC-SA 4.0 with OpenITI attribution, kept in a separate data package from Apache-licensed code.
2. THE system SHALL NOT display bulk text from copyrighted translations.

### Requirement 4: Quality gate
#### Acceptance criteria
1. Headline demo claims SHALL use only `reviewed` entries whose identification matches the PMC3941892 gold table or is marked "uncertain" on screen.
2. THE pipeline SHALL report extraction quality on the reviewed sample (entries checked, agreements, corrections).
3. Science-witness sources SHALL pass Evidence Integrity (no retracted papers).
4. The séance view SHALL be presented in English, Turkish, German, French and Spanish interface text; ancient quotations stay in Arabic with a labelled machine translation.

## Properties to test (PBT candidates)
- Every displayed ancient claim has a locator that resolves to an existing entry.
- The witness count equals the number of non-empty witness sections.
- Removing one witness's data never increases the witness count.
