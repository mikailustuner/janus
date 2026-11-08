# Requirements: Doctor Note and Outcome Loop

> Phase 2, server side. Refined 2026-11-08 from the draft seed with the owner's positions of the same day (marked
> "owner position"). Original criteria are kept and refined in EARS form; additions are marked *(Added in refinement)*.
> Out-of-scope criteria keep their text and carry a tag: **[Client: experience spec]** for the PDF layout and the patient
> and doctor screens (Phase 3), **[Later phase: narrator]** for the optional LLM narrator (design DP4), **[Phase 5]** for
> infrastructure. This spec builds what the Phase 3 screens call: the note content API, the five-language glossary, the
> QR token, the outcome store and the outcomes layer of Collective Memory.
> **Owner decisions 2026-11-08 (second round):** DP1 (re-derive, 409 on a version change) accepted; DP2 replaced: the
> token itself carries the note's finding codes in a signed payload, travels only in the URL fragment, and the server
> stores only used note ids until expiry plus the outcomes (no pending record; `privacy.md` unchanged); DP16 (English INN
> with "name not translated" and the ATC code) accepted; DP11, DP13 and DP18 accepted.

## Introduction
Give the doctor a one-page, cited note in the doctor's language, and let the doctor report the outcome via QR without
creating an account, turning patient reports into doctor-confirmed outcomes.

## Glossary
- **Note document:** the structured content of one note in one language (sections, sentences with evidence ids, medicine
  rows, statistic rows), returned by the API. The browser lays it out and renders the PDF.
- **Template:** a reviewed sentence with typed placeholders, keyed by a template id, in en, tr, de, fr and es.
- **Claim sentence:** a sentence that states something about the patient's medicines, a finding, a statistic or a
  source. **Fixed text:** headings, labels, the disclaimer, the abrupt-stop line, safety lines, notices and limits
  sentences; they make no claim of their own and need no evidence id.
- **Clinical glossary:** the reviewed five-language file set for ingredient names (INNs), cascade names (PIPC rows 1–65)
  and the note's fixed and template sentences; the Janus event labels are reused from `collective-memory`.
- **Outcome loop:** the opt-in path in which a note carries a QR code and the doctor reports an outcome once.
- **Note token:** the string in the QR code's URL fragment: a signed payload of codes only (format version, key id, note
  id, issue week, expiry, note language, region, outcome-loop consent version, and per finding the PIPC row, the index and
  marker ingredient keys and ATC codes, the Janus event key, the direction and the form flag) and an HMAC signature.
- **Used-token store:** the server's list of note ids (as hashes) whose token has been used or withdrawn, kept until the
  token's expiry so that each token works once.
- **Outcome:** one doctor answer for one finding of one note.

## Requirements

### Requirement 1: Doctor note
**User story:** As a family doctor with 10 minutes per patient, I want a one-page summary with sources in my own language so that I can decide quickly.

#### Acceptance criteria
1. THE system SHALL generate a one-page PDF listing medications (ingredient INN, the product name as on the patient's box, ATC, approximate start), rule-based findings with evidence, relevant FAERS statistics with CI, and abrupt-stop warnings.
   - *(Refined.)* THE note content API (Requirement 4) SHALL return, per language, a medicine row for every list item (ingredient names from the glossary, the item's ingredient-level ATC codes, the start month or "start not known", the abrupt-stop line, and "cannot be checked" with its reason for every ingredient the engine did not check), the findings with their evidence, the FAERS statistics with their range, the integrity line and the fixed texts.
   - *(Refined.)* THE product name as on the box SHALL be a slot that only the browser fills from its own data; THE server SHALL never receive or return it.
   - **[Client: experience spec]** The one-page PDF layout, overflow to a second page, and the PDF rendering itself.
2. THE PDF SHALL be rendered in the browser; the server SHALL receive only evidence ids and the note token request.
   - *(Refined, owner position 2026-11-08.)* THE server SHALL receive only identifiers and codes (the evaluation input of `POST /cascades/evaluate`: dataset version, candidate ids or ingredient keys, choices, start months; version pins; languages; a region code). THE request schema SHALL accept no free-text field, and THE server SHALL never receive the patient's free text or a product photo.
3. Every sentence written by the narrator agent SHALL reference at least one evidence id; the auditor SHALL remove any sentence that does not, and any sentence whose only evidence is retracted.
   - *(Refined.)* THE same rule SHALL apply to every claim sentence of the note, whether it comes from a template or (later) from the narrator: THE auditor SHALL remove a claim sentence unless it carries at least one evidence id and every evidence id it carries is citable in the integrity snapshot (registered, not retracted, with a citable basis). (Stricter than "not only retracted": a sentence lists only the ids it rests on, so each of them must hold.)
   - **[Later phase: narrator]** for sentences written by the narrator (Requirement 6).
4. THE note SHALL contain "Janus provides information, not medical advice. Research prototype — not a medical device." and no forbidden phrases in its language.
   - *(Refined.)* THE English note SHALL contain exactly that sentence (with the em dash of `medical-safety.md` rule 9), and each other language exactly its reviewed translation (Requirement 14). THE note in language L SHALL contain none of the forbidden phrases of L (`medical-safety.md` rule 2), matched as whole words, case-insensitive.
5. THE note SHALL be available in English, Turkish, German, French and Spanish; the patient's interface language and the note language SHALL be chosen independently.
   - *(Refined.)* A language SHALL be offered only when every template, fixed text and cascade name it needs has the status `accepted` in the glossary (Requirement 7); IF a requested language is not available THEN THE API SHALL answer 422 `note_language_unavailable` naming the language field.
6. WHEN the note language differs from the patient's language THE client SHALL show the patient a side-by-side version so they understand what the doctor receives.
   - *(Refined.)* THE API SHALL return up to two languages in one response, built from the same inputs, so that the side-by-side version shows the same content. **[Client: experience spec]** for the side-by-side screen.
7. Clinical terms in translated notes SHALL come from a reviewed glossary (ingredient INNs, MedDRA terms, cascade names); free LLM translation SHALL NOT be used for those terms.
   - *(Refined.)* MedDRA Preferred Terms SHALL be printed as published (English, `collective-memory` Requirement 6.1), never translated; the event's name in the note language comes from the reviewed Janus event labels or the reviewed cascade-name row.
8. *(Added in refinement.)* THE note SHALL show, next to every chain the engine returned, the chain as a sequence of ingredient names with the findings it is built from; it SHALL NOT show the engine's `same_product` pairs as findings.
9. *(Added in refinement.)* THE note SHALL show how many of the 65 published patterns were checked (`rules.checked` of `rules.total`) and list rules that cannot be checked (not matchable, or disabled by evidence integrity) as "cannot be checked", citing `dataset:pipc`.
10. *(Added in refinement.)* WHEN the engine found no pattern THE note SHALL print the no-false-reassurance statement of `medical-safety.md` rule 3 in the note language, and SHALL NOT contain "safe", "no problems", "all clear" or their equivalents in that language (word list in `design.md` §5.4).

### Requirement 2: QR token
#### Acceptance criteria
1. THE note SHALL carry a QR code encoding only note id, expiry and an HMAC signature.
   - *(Changed by owner decision 2026-11-08.)* THE token MAY carry the note's finding codes and SHALL still carry no personal data. It SHALL hold exactly: a format version, a key id, a 128-bit random note id, the issue week and the expiry, the note language, the region (TR, EU or US), the outcome-loop consent version, and per finding the PIPC row id, the index and marker ingredient keys with their matched ATC codes, the Janus event key, the direction and whether the form was confirmed; then an HMAC-SHA256 signature over all of it. It SHALL hold no name, no free text, no start month, no product id, no other medicine of the list and no date finer than a week.
   - *(Added.)* THE QR code SHALL encode the outcome page address with the token in the URL fragment (`…/o#<token>`) only, never in the path or the query; THE outcome page's script sends it in a JSON body. No API route SHALL accept a token in a path or query parameter.
   - *(Added.)* THE whole QR content SHALL fit a QR code of version 25 or lower at error correction level M (byte mode), which prints legibly on A4 at 50 mm or more (module of 0.4 mm or more). IF a note's findings do not all fit THEN THE token SHALL carry the longest prefix of the findings in note order that fits, and THE note SHALL say which findings the QR code covers. The measured worst case of the largest realistic note is recorded in `design.md` §6.6.
   - **[Client: experience spec]** draws the QR code at that size and builds the doctor page.
   - *(Added.)* THE note SHALL carry a QR code only when the patient opted in to the outcome loop (Requirement 12); otherwise the note has no token and no note id.
2. WHEN a token is invalid, expired or already used THE system SHALL reject the outcome submission.
   - *(Added.)* THE system SHALL reject a token with a malformed or non-canonical encoding, an unknown key id or a wrong signature (`invalid_token`); an expired token (`token_expired`); a used token (`token_used`); a withdrawn token (`token_not_usable`). A rejected submission SHALL change nothing.
3. *(Added; owner position.)* THE signing keys SHALL come only from the environment (`JANUS_NOTE_KEYS`, with a key id per key, and `JANUS_NOTE_SIGNING_KEY_ID`), SHALL be at least 32 bytes, SHALL differ from the noise key, and SHALL never be logged or returned. IF no valid key is configured THEN THE token, form, outcome and withdrawal routes SHALL answer 503 `notes_unavailable` and the note document route SHALL still work without a token.
   - *(Added.)* THE signature SHALL be HMAC-SHA256 truncated to its first 128 bits (design DP9), computed over a domain-separated encoding of the whole payload.
4. *(Added; key rotation.)* THE system SHALL verify a token with the key named by its key id, whether or not that key is still the signing key, and SHALL reject it once that key is removed from the configuration. Signing SHALL use only the signing key. A token SHALL NOT verify under any other key id.
5. *(Added.)* Signature comparison SHALL be constant-time (`hmac.compare_digest`).
6. *(Added; expiry decision, design DP11, accepted by the owner 2026-11-08.)* THE expiry SHALL be the Monday 00:00 UTC five weeks after the Monday of the issue week (validity between 28 and 35 days, so no exact issue date is stored or encoded). THE system SHALL treat a token as expired from that instant on, using the server's UTC clock.
7. *(Added; single use.)* A token SHALL be usable for at most one successful outcome submission, also under concurrent submissions; a replay SHALL be rejected with `token_used` and SHALL write nothing.

### Requirement 3: Outcome reporting
#### Acceptance criteria
1. WHEN a doctor opens a valid QR link THE system SHALL show a single page, in the note's language, listing the findings with options: cascade confirmed / not a cascade / dose changed / medicine changed / stopped / no change.
   - *(Refined, design DP13, accepted by the owner 2026-11-08.)* THE options SHALL be two questions per finding: an assessment (`confirmed`, `not_a_cascade`) and an optional action (`dose_changed`, `medicine_changed`, `stopped`, `no_change`), with the medicine the action concerns (`index` or `marker`) required for `dose_changed`, `medicine_changed` and `stopped`. A finding may be left unanswered.
   - *(Refined.)* `POST /outcomes/form` SHALL return, for a usable token, the note's language, the findings carried by the token (cascade name, ingredient names and ATC codes, whether form-confirmed), the option codes with their texts and the page's fixed texts in that language, and SHALL change nothing. **[Client: experience spec]** for the page.
2. THE system SHALL store outcomes with week granularity and no personal data, rate-limit submissions, and mark the token as used.
   - *(Refined.)* Each stored outcome SHALL hold only: the report week (the Monday of the UTC ISO week of submission), the region (TR, EU or US) from the token, the rule id, the index and marker ingredient keys, the Janus event key, the direction, the assessment, the action and its medicine, whether the finding was form-confirmed, the outcome-loop consent version, and a per-outcome deletion hash. No name, email, timestamp, exact date, location, device identifier, note language, ATC code or doctor detail.
   - *(Refined.)* THE outcome rows and the entry of the note id in the used-token store SHALL be written in one transaction; IF any statement fails THEN nothing SHALL be written.
   - *(Refined.)* Rate limiting SHALL be designed now (design §7.6) and built in **[Phase 5]** at the reverse proxy without storing or logging IP addresses, as for donations (`privacy` Requirement 3.7). Until then the known limit (anyone can create tokens and report outcomes) SHALL be stated on the privacy page **[Client: experience spec]**.
3. WHERE the patient opts in, THE client SHALL remind them after 4 weeks to report whether the symptom resolved (stored in the browser only). **[Client: experience spec]**
4. *(Added.)* WHEN a submission is accepted THE system SHALL answer with the number of stored outcomes only; IF an answer names a finding that is not in the note, repeats a finding, or breaks the action rule of 3.1 THEN THE system SHALL answer 422 naming fields only and SHALL write nothing.
5. *(Added.)* THE outcome store SHALL keep outcomes for at most 24 months by report week, with the same purge as donations (`privacy` Requirement 3.6).
6. *(Added.)* Demo mode SHALL never reach the outcome routes: the request schemas reject unknown fields, including `"demo": true` (`collective-memory` Requirement 4.8, `experience` Requirement 4.3).

### Requirement 4: Note content API *(Added in refinement; owner position 1)*
**User story:** As the `experience` spec, I need one call that turns what the patient has already seen into a note document in one or two languages, without the server keeping anything.

#### Acceptance criteria
1. THE API SHALL offer `POST /notes/document` (a medical route: JSON only, at most 64 KiB, `Cache-Control: no-store`, read-only, no body logging).
2. THE request SHALL carry: the evaluation input exactly as sent to `POST /cascades/evaluate` (dataset version, 1–50 items), optional version pins (`rule_base_version`, `integrity_version`, `counts_build_id`), one or two distinct note languages, the user's region (`US`, `TR`, `EU`, `OTHER`, `UNKNOWN`, for emergency numbers), and optionally one statistics region (`TR`, `EU` or `US`).
3. *(Design DP1; accepted by the owner 2026-11-08.)* THE server SHALL re-derive the findings, chains, item warnings, not-checked entries and FAERS statistics from that input inside one read-only transaction (the same engine call and the same pair lookup the client made), and SHALL NOT accept findings, evidence ids or numbers from the client. WHEN a pin differs from the served version THE API SHALL answer 409 `version_mismatch` naming the pinned fields; WHEN the dataset version differs it SHALL answer 409 `dataset_version_mismatch` as the engine does.
4. THE response SHALL carry the versions the note was made with (rule base, resolution dataset, integrity, counts build, glossary), the month it was made, and one note document per requested language.
5. FOR the same request against the same state, THE response SHALL be byte-identical; changing the language SHALL NOT change the sections, the sentence ids, the findings, the evidence ids or the numbers (Requirement 1 property).
6. IF the rule base, the resolution dataset or the evidence snapshot is not loaded THEN THE API SHALL answer 503 `notes_unavailable`; IF only the counts file is missing THEN THE note SHALL be produced with the fixed text `statistics_unavailable` in the statistics section and no number.
7. THE route SHALL NOT write to the database or disk and SHALL log only the access-log fields (`privacy` Requirement 2).

### Requirement 5: Templates and the auditor *(Added in refinement; owner position 1, 2)*
#### Acceptance criteria
1. THE note SHALL be built only from reviewed templates keyed by finding type and section (`design.md` §5.2); each claim sentence SHALL carry the evidence ids its template requires (for example the rule record for a finding, `dataset:faers` for a statistic, the BMJ 2026 record for priority data, the window record for timing within the window).
2. A claim template SHALL contain no digit; every number in a claim sentence SHALL be a placeholder filled from the inputs (engine result, statistics, versions, region tables) and formatted by the fixed rule of the language (`design.md` §5.3).
3. THE auditor SHALL run on every note document before it is returned and SHALL remove a claim sentence that (a) carries no evidence id or an evidence id that is not citable, (b) contains a forbidden phrase or a reassurance word of its language, or (c) contains a number that is not the formatted value of one of its own inputs. A sentence removed in one language SHALL be removed in every language of the response, with the reason as a code.
4. IF a fixed text fails a phrase check THEN THE glossary loader SHALL refuse the glossary at startup (fail loudly); fixed texts are never removed at request time, so the disclaimer and the abrupt-stop line are always present.
5. THE auditor SHALL be a pure function; THE removal record SHALL hold sentence ids and reason codes only.

### Requirement 6: Narrator *(Added in refinement; owner position 2)* **[Later phase: narrator]**
1. THE narrator (Anthropic API) SHALL be optional and off by default; its key SHALL come only from the environment and SHALL never be logged or returned.
2. WHEN the narrator is on it SHALL only reorder or shorten template sentences; THE auditor of Requirement 5 SHALL run on its output and remove any sentence without a citable evidence id, with a forbidden phrase, or with a number not present in the inputs.
3. Tests SHALL never call the real API; they use a fake narrator.
4. *(Design DP4.)* Phase 2 builds no narrator: the contract above is recorded, and `janus/agents/` stays empty. The decision is revisited with the experience spec.

### Requirement 7: Clinical glossary *(Added in refinement; owner position 3)*
#### Acceptance criteria
1. THE glossary SHALL contain, in en, tr, de, fr and es: (a) ingredient names for every ingredient key that can appear in a finding or an abrupt-stop warning of the current rule base (members of the 66 cascade classes and of the abrupt-stop list; 1,129 keys on the current dataset), (b) the cascade name of each of the 65 PIPC rows (Drug A, adverse event, Drug B), (c) every template and fixed text of the note and of the outcome page. Janus event labels SHALL be reused from `apps/api/janus/memory/memory_events.csv` (already reviewed), not copied.
2. Ingredient names SHALL be proposed from the Wikidata labels of the name index (CC0); THE glossary SHALL NOT contain any string taken from the TİTCK list. Cascade names in English SHALL be the PIPC text as published; their translations and the templates SHALL be drafted by the AI assistant and reviewed (no runtime or unreviewed machine translation).
3. Every row SHALL carry a status (`proposed`, `accepted`, `rejected`); only `accepted` rows SHALL be used. THE glossary SHALL be reviewed by the pharmacologist agent and the localization-reviewer agent, recorded in a review sheet, and accepted by the owner before any note uses it (task review stop). Until then no language is available (Requirement 1.5).
4. WHEN an ingredient has no accepted name in the note language THE note SHALL print the accepted English INN with the fixed tag "name not translated" in the note language, plus its ATC code; WHEN it has no accepted English name either THE note SHALL print the ingredient's ATC code with the tag "name not reviewed". (Design DP16; accepted by the owner 2026-11-08: no AI translation of clinical terms.)
5. THE glossary loader SHALL validate: unique keys, five languages, NFC, placeholders identical in every language of a template, no digit in claim templates, no forbidden phrase or reassurance word in any accepted cell of its language, every PIPC row present once with the hash of its English text, every ingredient key well formed. A defect SHALL stop startup with the file, row and column named.
6. THE glossary SHALL have a version (hash of its content) that every note document carries.
7. THE status line "reviewed by the project owner with AI assistance; needs review by a pharmacist or physician and native speakers before any public claim" SHALL be kept with the glossary (same rule as the cascade mapping and the event vocabulary); the clinical and native-speaker review is on `docs/pre-launch-checklist.md`.

### Requirement 8: Abrupt-stop line and form-unconfirmed findings *(Added in refinement; from the cascade-engine open items and owner position 6)*
1. FOR every list item that has an `item_warnings` entry, THE note SHALL show the abrupt-stop line ("Do not stop this medicine suddenly." in the note language) in that item's medicine row, once per item, whether or not the item is in a finding.
2. THE note SHALL show findings with `form_confirmed = false` in a separate section with its own heading that says the product form was not confirmed and the pattern depends on the form (design DP12); confirmed findings SHALL stay in the main findings section. A finding SHALL appear in exactly one of the two sections.
3. THE abrupt-stop line SHALL be fixed text, never removed by the auditor.

### Requirement 9: FAERS statistics in the note *(Added in refinement; from the collective-memory open items)*
1. FOR every finding whose `faers_locator` is set, THE note SHALL print the statistic of `POST /memory/pair` for (index ingredient, the rule's Janus event key, region `ALL`, scope `suspect`), and, when a statistics region is requested, the same for that region: report count, the ratio with its 95 % range, the assessment, the snapshot date and window, and the `citation` (`dataset:faers` and the locator).
2. A cell with fewer than 3 reports SHALL print the coverage sentence only, with no number (`collective-memory` P26).
3. THE note SHALL print the numbers it was built with; a later rebuild of the counts file SHALL NOT change an issued note (the PDF keeps them; the API never re-queries an issued note).
4. THE statistics section SHALL carry the FAERS limits sentences, the screening sentence, the attribution with the snapshot date, the denominator sentence, and the long MedDRA notice (`MEDDRA_NOTICE_LONG`) when a Preferred Term is printed.
5. THE note SHALL carry the safety line of every event whose Janus key has a `safety_line`, with the emergency and crisis numbers of the user's region from the `Memory` tables, placed before the findings (`medical-safety.md` rule 10).
6. Counts SHALL be "reports", never "people"; THE statistics sentences SHALL pass the people-noun and causation word lists of `collective-memory` §7.2 (with the screening-sentence exception).
7. THE note SHALL NOT print user-layer counts (donations, outcomes) in Phase 2 (design DP15).

### Requirement 10: Evidence and integrity in the note *(Added in refinement; from the cascade-engine open items)*
1. Each finding's sentences SHALL carry the finding's `evidence_ids` relevant to them (rule, PIPC paper, window paper for `probable`, BMJ 2026 where shown, ThinkCascades where supporting, the form-extension paper), filtered again with `cite` on the snapshot of the same transaction.
2. THE note SHALL carry the integrity line of `evidence-integrity` (`build_line` over the note's citable ids) as fixed-format sentences: sources checked, by status, the date range of the checks, stale sources, and that no retracted source was used; and per finding the integrity codes (correction notice, expression of concern).
3. THE note SHALL print `rule_base_version`, `integrity_version`, the dataset version, the counts build id and the glossary version (short forms) so that a note identifies what it was made with.

### Requirement 11: Outcomes layer in Collective Memory *(Added in refinement; owner position 5)*
1. THE outcome store SHALL implement `UserLayerSource` (`collective-memory` design §5.3): a cell (ingredient set S, Janus event key, direction, region) counts the stored outcomes with assessment `confirmed` whose ingredient pair contains S, with that event, direction `adverse` and region; the version is a hash of the ids of those outcomes; the siblings are counted as for donations.
2. `POST /memory/shared` with layer `outcomes` SHALL then answer through the same `release_table`, k = 20, discrete Laplace noise and sibling rule as `contributions`, instead of `not_available`; `GET /memory/snapshot` SHALL report the layer as `ok` or `unavailable`.
3. Outcomes SHALL never be summed, compared or combined with donations or FAERS in any response (`collective-memory` Requirement 4.3).
4. `not_a_cascade` and action answers SHALL be stored but SHALL NOT be released in Phase 2.
5. Deleting an outcome (withdrawal) SHALL change the version of every cell it was in.

### Requirement 12: Outcome-loop token and the used-token store *(Added in refinement; owner decision 2026-11-08 replaces design DP2)*
1. THE system SHALL issue a token through `POST /notes/token` (a medical, read-only route): the same note request as Requirement 4 with exactly one language, an accepted outcome-loop consent version (`JANUS_OUTCOME_CONSENT_VERSIONS`) and the outcome region (TR, EU or US). THE server SHALL re-derive the findings as in 4.3, sign them into the token, and return the token, the QR address (when `JANUS_PUBLIC_BASE_URL` is set), the expiry, how many findings the token covers, and the note document built from the same derivation. Issuing SHALL write nothing.
2. THE server SHALL store no finding, no medicine and no note content for the outcome loop. IT SHALL store only (a) in the used-token store, the SHA-256 hash of each used or withdrawn note id with the token's expiry and the state (`used`, `withdrawn`), deleted when the token expires, and (b) the outcomes of Requirement 3.2.
3. *(Alternative rejected by the owner, 2026-11-08.)* A pending server record holding the note's findings between issue and use (design DP2, first version) SHALL NOT be built: it would persist health data from the patient's list on the server, which `privacy.md` allows only for explicit donations.
4. THE patient SHALL be able to withdraw with the token itself (`POST /notes/withdraw`), before or after use and after expiry: THE system SHALL delete every outcome stored from that note, completely, SHALL mark an unexpired token `withdrawn` so it cannot be used afterwards, and SHALL answer the same way whether or not anything was stored.
5. Writes SHALL respect the storage-region guard (`privacy` Requirement 3.4); IF storage is not in an EU region THEN the outcome and withdrawal routes SHALL answer 503 as donations do.

### Requirement 13: Privacy and logging *(Added in refinement)*
1. No note, token, outcome or withdrawal route SHALL log a token, note id, key id, language, region, ingredient, event, rule id or answer; the access log carries request id, route template, status and latency only.
2. Tokens, note ids, ingredient keys and answers SHALL appear only in request bodies and responses, never in a URL path or query string of the API; in the QR address the token is only in the fragment (Requirement 2.1).
3. 422 responses SHALL name fields only and never echo a value; 4xx token errors SHALL carry only the error code.
4. THE database server log settings of `privacy` (terse errors, no statements) SHALL apply to the new tables; CHECK constraints SHALL repeat the API's validation.

### Requirement 14: Disclaimer and language safety *(Added in refinement; owner position 7)*
1. THE note in every language and the outcome page SHALL carry the disclaimer of `medical-safety.md` rule 9: English exactly "Janus provides information, not medical advice. Research prototype — not a medical device.", and in tr, de, fr, es exactly the accepted translations, which SHALL equal `Disclaimer.text` of `apps/web/messages/<lang>.json` (one source, a parity test).
2. EVERY forbidden-phrase check SHALL apply per language: the note and the outcome page in language L SHALL contain none of the phrases of L, and THE glossary loader SHALL check each cell against the list of its language. THE Python phrase lists SHALL equal `apps/web/src/i18n/forbidden-phrases.ts` (parity test).
3. THE API responses of `cascades/evaluate` and `evidence/resolve` SHALL use the same English disclaimer constant (they used a hyphen; design DP18, accepted by the owner 2026-11-08).
4. THE note and the outcome page SHALL contain no sentence that recommends starting, stopping or changing a medicine; the outcome page asks the doctor what was done and gives no advice.

### Requirement 15: Performance *(Added in refinement)*
1. ON the dev machine (`collective-memory` design §1) with the real dataset and counts file, `POST /notes/document` for 15 items with up to 10 findings and two languages SHALL answer within 1.5 s at p95 (measured by a local benchmark, not in CI).
2. THE number of database and counts-file statements of a note request SHALL not depend on the number of languages; CI asserts the statement budget, not time.

## Properties to test (PBT candidates)
- Any modification of a token's payload invalidates its signature.
- A token can be used at most once.
- The generated note never contains a sentence without a non-retracted evidence id.
- For every supported language, the note contains the mandatory disclaimer and none of that language's forbidden phrases.
- Changing the note language never changes the set of findings or evidence ids in the note.
- *(Added.)* A token verifies only under the key its key id names; removing that key rejects it; expiry is enforced at the boundary instant; non-canonical encodings are rejected.
- *(Added.)* Concurrent submissions with one token store outcomes at most once; a failure at any statement leaves the store unchanged.
- *(Added.)* Every number in a claim sentence is the formatted value of one of its inputs; claim templates hold no digit.
- *(Added.)* Every item with an abrupt-stop warning shows the line exactly once; every form-unconfirmed finding is in its own section and nowhere else.
- *(Added.)* The note request schema accepts no free text; the document route is stateless and silent.
- *(Added.)* The outcomes layer follows the release rules of contributions, counts only `confirmed` outcomes, and is never combined with another layer.
- *(Added.)* Withdrawal deletes exactly the outcomes of that note and blocks its token.
- *(Added, owner decision 2026-11-08.)* The token reaches the API only in a JSON body: the QR address carries it only in the fragment, and no route reads a token from a path or query.
- *(Added, owner decision 2026-11-08.)* Every QR address fits version 25 at level M; the token keeps a prefix of the findings in note order, at least 11 of them, and the realistic worst case is measured and recorded.
- *(Added.)* The token's payload decodes to exactly the findings of the note it was issued with, and carries no field outside the allowed list.
- *(Added.)* The glossary loader accepts valid files and names each single defect.

## Resolved open items *(from the seed's two sections, 2026-11-07 and 2026-11-08)*
- **Abrupt-stop warnings** → Requirement 8.1 (per item, from `item_warnings`).
- **Form-unconfirmed findings** → Requirement 8.2 (separate, labelled section; owner suggestion adopted).
- **Evidence** → Requirement 10 (`evidence_ids`, `cite`, `build_line`, versions printed).
- **Numbers in the note** → Requirement 9.1–9.3; **regions** → 9.1 (statistics region, locator with region).
- **Outcomes layer** → Requirement 11.
- **Safety lines and the long MedDRA notice** → Requirement 9.4–9.5.
