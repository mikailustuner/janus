# Requirements: The Séance ("Three Witnesses")

> Refined 2026-11-08 for Phase 4. Requirements 1–4 are the original ones; every original
> criterion keeps its number and wording, with refinements in EARS form as sub-bullets.
> Requirements 5–7 were added in the refinement. Criteria tagged **[Client: …]** describe what
> the séance screen shows; this spec provides the data and the contract (design §7), and the
> screen is built by `experience` in `apps/web`.
> Owner decisions of 2026-11-08: experts review after Phase 4; two labelled AI review passes
> (historian, pharmacologist) over 30–50 extracted entries stand in until then; the spec's human
> `reviewed` status stays reserved for the experts.

## Introduction
Bring three independent witnesses to the same table for a (substance/drug, condition) pair: the **past** (Ibn Sina's Canon Book 2 from OpenITI, plus 10–20 hand-picked Ottoman samples), the **present** (Collective Memory / Light Face signals) and **science** (molecular and literature evidence). Scope for the hackathon: wounds, burns, ulcers and infection.

The séance is researcher-facing. Its output is a set of hypotheses with their evidence, never a treatment claim: overlaps between an old text and a modern study are hypotheses (medical-safety rule 8), and a candidate is "worth investigating — not a treatment" (rule 7).

## Glossary
- **Entry:** one heading of Canon Book 2 in the OpenITI text, with its body (844 headings).
- **Locator:** where a passage sits: book 2, entry id, the source lines of the pinned OpenITI file, and the printed page of the edition behind it.
- **Theme span:** a clause of an entry that names a theme term (wound, burn, ulcer, or a putrefaction / pus / spreading-ulcer term for infection).
- **Claim:** one (substance, condition) statement taken from a theme span, with its Arabic span and locator.
- **Reader step:** turning a theme span into {substance, use, condition} and a machine translation. Deterministic rules first; then an LLM reader.
- **AI review pass:** an independent review of the reader's output by one Janus agent (historian or pharmacologist), recorded as a labelled file. Not a human review.
- **Expert review:** a human expert's review. Only this sets a claim's status to `reviewed`.
- **Gold table:** the identification columns of PMC3941892 Tables 1–2 (Canon remedies for burns).
- **Witness:** one of past, present, science. A witness **supports** a pair when its section has at least one supporting item.
- **Exposure match:** how the FAERS ingredient relates to the ancient substance: `same`, `component` (e.g. vinegar → acetic acid) or `different` (e.g. topical salt vs intravenous sodium chloride).

## Requirements

### Requirement 1: Ancient-text pipeline (offline ETL)
#### Acceptance criteria
1. THE pipeline SHALL import Canon Book 2 from OpenITI (`0428IbnSina.QanunFiTibb`), recording the exact version and the CC BY-NC-SA 4.0 license.
   - 1.1a THE `canon` pipeline SHALL read the primary version `Shamela0010706-ara1` at one pinned commit of `OpenITI/0450AH` and SHALL refuse any file whose git blob hash differs from the pinned one.
   - 1.1b THE run manifest SHALL record the source URL, commit date as snapshot date, source hash, licence and code version; the data package SHALL carry the OpenITI release DOI and OpenITI's own issue flags (typos, pagination, missing parts).
2. THE pipeline SHALL split Book 2 into one entry per heading and keep a locator (book, heading, line range).
   - 1.2a WHEN the number of headings differs from 844 THE run SHALL end as `needs_review` and SHALL NOT be promoted.
   - 1.2b Every source line between the Book 2 title and the Book 3 title SHALL belong to exactly one entry, and each locator SHALL resolve to source lines that start with the entry's heading.
3. WHEN an entry mentions a theme keyword (wounds, burns, ulcers, infection) THE pipeline SHALL extract {substance, use, body part/condition} with the reader agent and store the original Arabic span.
   - 1.3a Theme terms SHALL be matched on a normalised form (no diacritics or tatweel, one alef), with the prefix forms of Arabic (wa-, fa-, bi-, li-, and li- + al- written `لل`) and pronoun suffixes; section-label words alone SHALL NOT make a span.
   - 1.3b THE deterministic rules SHALL tag preparation form, vehicle, plant part and action from a fixed glossary; the reader SHALL then write the structured fields and a machine translation.
   - 1.3c WHERE an Anthropic API key is configured THE reader SHALL be an LLM call behind an interface that tests replace with a fake; WHERE no key is configured THE reading SHALL be done offline by the reader agent and stored as an AI artifact with its provenance (model, date, method).
   - 1.3d Span ids SHALL contain a hash of the span text, so that a review of one text can never attach to a changed text.
4. Translations SHALL be labelled "machine translation"; identifications SHALL cite their source (Hamdard 1998 cited only, PMC3941892 tables) and be marked "uncertain" when sources disagree.
   - 1.4a An identification SHALL be `matches_gold` only when it agrees with its gold row; `uncertain` when sources disagree on the genus, or agree on the genus only, or a review pass marks it so; `not_in_gold` when the gold table has no row for it.
   - 1.4b Hamdard 1998 SHALL be cited by letter chapter, entry number and page only; no Hamdard text SHALL be stored or shown.
5. An entry SHALL be marked `reviewed` only after human review; the demo SHALL use reviewed entries for headline claims.
   - 1.5a Until the experts have reviewed them, claims SHALL carry `expert_review = pending` and the AI status of Requirement 5; the assembly SHALL never write `reviewed`.
   - 1.5b *(Owner decision 2026-11-08.)* Until expert review, headline demo claims SHALL use only claims that passed both AI passes (Requirement 4.1 as refined).
6. Ottoman samples SHALL be entered manually with thesis/edition citation and page, as short quotations.
   - 1.6a Ottoman samples SHALL be added only from a source the team has read, with citation and page. WHEN no such source can be verified THE package SHALL say that none were added and why.

### Requirement 2: Three-witness synthesis
#### Acceptance criteria
1. WHEN asked about (substance or drug, condition) THE system SHALL return each witness separately: past (entries + locators), present (signals with CI), science (targets, papers).
   - 2.1a THE past witness SHALL list the claims of the pair that passed both AI passes, each with its Arabic span, labelled machine translation and locator.
   - 2.1b THE present witness SHALL read Collective Memory pair counts through the existing memory reader (suspect scope, all regions) for the substance's ingredient key and the condition's group of MedDRA Preferred Terms. It SHALL support the pair only WHEN the exposure match is `same` or `component`, at least 3 reports name both, and the upper bound of the 95 % ROR interval is below 1 (light-face Req 1.1). An exposure that is `different` SHALL be shown as context and never counted.
   - 2.1c THE science witness SHALL list the studies curated for the pair that pass Evidence Integrity and report a supporting result. Studies about the historical text itself SHALL NOT be listed as science. Targets are an open item (design §10).
2. THE system SHALL report how many witnesses independently support the pair (0–3) and each witness's confidence; it SHALL NOT merge them into a single "proven" score.
   - 2.2a Confidence is per witness (`none`, `low`, `moderate`): past is `low` until expert review; present is `low` (spontaneous reports); science is `moderate` only with a supporting systematic review, otherwise `low`.
   - 2.2b THE response SHALL contain no score, strength, overall or "proven" field.
3. WHEN fewer than three witnesses agree THE system SHALL say which are missing.
   - 3a Each missing witness SHALL carry one fixed reason code (e.g. `no_faers_mapping`, `too_few_reports`, `no_citable_study`).
   - 3b A missing counts file or evidence store SHALL make that witness missing with its reason; it SHALL NOT fail the request.

### Requirement 3: Licensing
#### Acceptance criteria
1. Derived ancient-text data SHALL be published under CC BY-NC-SA 4.0 with OpenITI attribution, kept in a separate data package from Apache-licensed code.
   - 3.1a The package SHALL live in `datasets/canon/` with the full licence text, an attribution README that names the changes made, and the pinned version. Nothing derived from the Canon text SHALL be written under `data/` or into code.
2. THE system SHALL NOT display bulk text from copyrighted translations.
   - 3.2a Only the name columns of the gold table SHALL be stored; Hamdard 1998 is cited only.

### Requirement 4: Quality gate
#### Acceptance criteria
1. Headline demo claims SHALL use only `reviewed` entries whose identification matches the PMC3941892 gold table or is marked "uncertain" on screen.
   - 4.1a *(Owner decision 2026-11-08.)* Until expert review, "reviewed" here reads "passed both AI passes". A claim from a substance flagged toxic or caustic SHALL NOT be headline-eligible.
2. THE pipeline SHALL report extraction quality on the reviewed sample (entries checked, agreements, corrections).
   - 4.2a THE report SHALL count rule-versus-reader agreement, each pass's verdicts, agreement between the passes, condition and translation corrections, and identification corrections; it SHALL be reproducible from the committed files.
3. Science-witness sources SHALL pass Evidence Integrity (no retracted papers).
4. The séance view SHALL be presented in English, Turkish, German, French and Spanish interface text; ancient quotations stay in Arabic with a labelled machine translation. **[Client: experience]**

### Requirement 5: AI review passes (added 2026-11-08)
#### Acceptance criteria
1. THE historian and the pharmacologist agents SHALL each review the same 30–50 extracted clauses independently and write one labelled file each, with a verdict per clause (`accept`, `correct`, `reject`) and a note for every correction or rejection.
2. A claim SHALL be kept only WHEN neither pass rejects its clause, and SHALL keep only the conditions both passes leave standing.
3. Every claim SHALL be shown as "AI-reviewed, pending expert review" until Requirement 1.5 is met.

### Requirement 6: Séance API (added 2026-11-08)
#### Acceptance criteria
1. `POST /seance/pair` with `{substance, condition}` SHALL return the three witnesses, the count and the missing witnesses (design §7). It is a medical route: JSON body only, `no-store`, read-only, nothing logged but the access line.
2. WHEN the substance is unknown or a field is invalid THE route SHALL answer 422 naming the field, without echoing the value. WHEN the catalogue is not installed it SHALL answer 503.
3. `GET /seance/catalogue` SHALL list the substances with their identifications and the pairs that have at least one passage or study.

### Requirement 7: Séance view contract (added 2026-11-08) **[Client: experience]**
#### Acceptance criteria
1. THE séance screen SHALL show the three witnesses as three separate places at one table, each with its own confidence, its items and, when silent, its localised missing reason; it SHALL show the count as "n of 3 witnesses" and never as a score.
2. THE screen SHALL show the identification label (`identified` or `uncertain`), the hazard flag, "machine translation" next to every translation, "AI-reviewed, pending expert review" on every passage, the caveat codes of the present witness, and "candidate worth investigating — not a treatment".
3. THE screen SHALL use only the data contract of design §7 and SHALL render the disclaimer (rule 9).

## Properties to test (PBT candidates)
- Every displayed ancient claim has a locator that resolves to an existing entry.
- The witness count equals the number of non-empty witness sections.
- Removing one witness's data never increases the witness count.
- (Added) A retracted or unregistered study is never a science item; a `different` exposure never supports.
- (Added) The assembly never adds a condition neither pass gave and never marks a claim expert-reviewed.
