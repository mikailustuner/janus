# Requirements: Experience (patient, doctor, researcher, judge)

> Draft seed. Functional requirements only. The visual design system is chosen with the `ui-ux-pro-max` skill and recorded in `.kiro/steering/design.md` before this spec's design step. Refine with Kiro, then let Kiro generate `design.md` and `tasks.md`.

## Introduction
The end-to-end product experience across five languages and three regions, including a judge/demo mode, because hackathon judges will not have Turkish (or most EU) medicine boxes at hand and may judge from the video alone.

## Requirements

### Requirement 1: Patient / caregiver flow
**User story:** As a caregiver, I want to scan my mother's medicines and understand in a few minutes what to discuss with her doctor.

#### Acceptance criteria
1. THE flow SHALL be: choose region(s) → scan / photograph / type medicines → confirm each → answer "since when?" (month/year or "don't know") → timeline → findings ("ghosts") → evidence → doctor note.
2. THE first screen SHALL show the emergency notice (112 / 911) and the "information, not medical advice; research prototype" statement.
3. WHEN no finding is produced THE screen SHALL show the no-false-reassurance statement.
4. THE flow SHALL work on a 375 px wide phone screen without horizontal scrolling.

### Requirement 2: Languages and regions
#### Acceptance criteria
1. THE interface SHALL be available in English (primary), Turkish, German, French and Spanish.
2. THE user SHALL be able to switch interface language, doctor-note language and region independently.
3. Dates, numbers and decimal separators SHALL follow the selected locale.

### Requirement 3: Accessibility
#### Acceptance criteria
1. THE interface SHALL meet WCAG 2.2 AA: keyboard navigation, visible focus, alt text, contrast, reduced-motion support for all ghost animations.
2. A large-text mode and text-to-speech reading of findings SHALL be available for older users.
3. Every data view SHALL handle loading, empty, error and long-content states.

### Requirement 4: Judge / demo mode
**User story:** As a hackathon judge without Turkish boxes, I want to try the full flow in two minutes.

#### Acceptance criteria
1. THE home page SHALL offer "Try the demo" without any sign-up.
2. Demo mode SHALL include printable/scannable sample codes (TR, US, FR/ES) for synthetic products clearly labelled "demo", and three synthetic patients (Istanbul, Cologne with mixed TR+DE boxes, Ohio with pharmacy vials).
3. Demo data SHALL be clearly labelled synthetic on every screen and SHALL never be mixed into Collective Memory.
4. Demo mode SHALL work even if external APIs are unavailable (cached snapshot).

### Requirement 5: Doctor and researcher areas
#### Acceptance criteria
1. THE doctor QR page SHALL require no account and SHALL load on a phone in under 3 seconds on a 4G connection.
2. THE researcher area SHALL contain hypothesis cards, the séance view, the retrospective-validation report and dataset export; it SHALL be reachable from the main navigation but not part of the patient flow.

### Requirement 6: Theme with function
#### Acceptance criteria
1. Ghosts SHALL represent cascades, the two-faced mask SHALL switch shadow/light views, the zombie stamp SHALL mark retracted evidence, and the séance table SHALL hold the three witnesses; decorative-only spooky elements SHALL NOT be added.
2. The patient-facing tone SHALL be mysterious and reassuring, never frightening; red is used only for real risk.

### Requirement 7: Safety lines for sensitive events *(Added 2026-11-08 from the `collective-memory` event review)*
**User story:** As a caregiver, I want a result that names a serious symptom to tell me when to get urgent help, so that a count never stands alone.

#### Acceptance criteria
1. WHEN a finding, a Collective Memory result or a donation form shows an event whose Janus key has a `safety_line` (`apps/api/janus/memory/memory_events.csv`) THE client SHALL show that line next to it, in the interface language:
   - `crisis_support` (key `depression`): the crisis line of the user's region (`Memory.crisis.<region>`), after the emergency notice (`medical-safety.md` rule 10);
   - `urgent_care_skin` (key `rash`): a rash that is severe, spreading or blistering, or comes with fever or mouth sores, needs urgent medical care; signs of a severe allergic reaction need a call to the emergency number;
   - `urgent_care_heart` (key `arrhythmia`, including torsade de pointes): fainting, or a racing or irregular heartbeat with chest pain or breathlessness, needs urgent care or a call to the emergency number;
   - `urgent_care_gi` (key `gastric_ulcer_bleed`): vomiting blood or black stools needs urgent medical care; with faintness or feeling very unwell, call the emergency number *(owner decision 2026-11-08)*;
   - `urgent_care_seizure` (key `seizures`): a seizure (convulsion) needs urgent medical care; call the emergency number if it lasts more than 5 minutes, repeats, or comes with an injury or trouble breathing *(owner decision 2026-11-08)*;
   - `urgent_care_breathing` (key `heart_failure`): sudden or worsening breathlessness needs urgent medical care; if severe or with chest pain, call the emergency number *(owner decision 2026-11-08)*.
2. THE lines SHALL NOT diagnose, SHALL NOT tell the user to start, stop or change a medicine, and SHALL be shown whatever the counts are (also for `no_reports` and `insufficient_data`).
3. *(Owner decision 2026-11-08.)* THE numbers are in the `Memory` message catalogue in all five languages, with the user's region as the key, and never inside a sentence: `Memory.emergency.<region>` fills `{emergency}` in the urgent-care lines and `Memory.crisis.<region>` fills `{crisis}` in `crisis_support`. Region is one of `US`, `TR`, `EU`, `OTHER`, `UNKNOWN` (the user's own setting, not the FAERS region filter); a missing setting is `UNKNOWN`. Values: emergency US 911, TR 112, EU 112, OTHER and UNKNOWN "your local emergency number"; crisis US "call or text 988 (Suicide and Crisis Lifeline)", TR "call 112", EU "call 112 or your local crisis service", OTHER and UNKNOWN "call your local emergency number". The numbers are re-checked before launch (`docs/pre-launch-checklist.md`).
4. MedDRA Preferred Term names SHALL appear only in a details view, never in a banner, a list badge or a notification. THE default display of an event is its Janus label.
5. THE API returns `event.safety_line` for a Janus key and for a PT (an active key that lists the PT) and `safety_line` on every event row of a combination; the client shows the line wherever the event is shown.
6. THE depression screen SHALL show the abrupt-stop line ("Do not stop this medicine suddenly") beside any antidepressant, beta-blocker or other abrupt-stop class on the same screen as `crisis_support` (`medical-safety.md` rule 4). *(Collective-memory safety review S17.)*
7. THE wording of the six lines and of the regional numbers is in the `Memory` message namespace in en, tr, de, fr, es (`collective-memory` task 12) and passes the forbidden-phrase and word-list checks.

## Properties to test (PBT candidates)
- For every supported locale, every user-facing string key has a translation (no fallback keys rendered).
- For every supported locale, rendered findings contain the mandatory disclaimer and none of the forbidden phrases.
- Demo-mode items never reach contribution or outcome endpoints.
  - *(Added 2026-11-08.)* For every event key with a `safety_line`, every screen that shows the event also shows the line; no banner, badge or notification contains a PT name. (Req 7)

## Open items from cascade-engine (2026-11-07)
- **Evaluation call.** `POST /cascades/evaluate` takes the resolution `dataset_version` and 1-50
  items, each a product `candidate_id` (with `choices` for ambiguous ingredient positions, which
  start at 0) or an ingredient QID, plus `started` as `YYYY-MM` or null. The client never sends
  ATC codes.
- **Re-resolve after 409.** Candidate ids are stable only within one dataset version. The client
  keeps each item's product code (GTIN or NDC) or name in the browser so it can re-resolve after
  `409 dataset_version_mismatch`.
- **Form-unconfirmed findings** (`form_confirmed = false`, e.g. an ingredient typed by name) name
  the matched codes; the client asks the user to confirm the product.
- **Wording.** Results carry codes (`status`, `timing`, `matches_published_pattern`,
  `do_not_stop_suddenly`, `no_pattern_found`, `rule_base_unavailable`, integrity codes) and the
  English canonical sentences. The five-language wording, and showing not-matchable rules (PIPC
  rows 27 and 57) and not-checked ingredients as "cannot be checked", belong to this spec.
- **Homeopathic products** (owner decision 2026-11-07): a product with `homeopathic = true`
  (drug-resolution Req 11.1) is shown as "homeopathic product, not checked"; the evaluation
  result lists its ingredients as `not_checked` with reason `homeopathic_product`.

## Open items from collective-memory (2026-11-08)
Source: `collective-memory` design §5 (contracts), §7 (message catalogue), Requirement 8. All lookups are `POST` with a JSON body.
- **Routes.** `POST /memory/pair` (one ingredient, one event as `{"pt"}` or `{"key"}`), `POST /memory/combination`
  (2 to 20 ingredients), `POST /memory/regions` (1 to 20 ingredients, optional event), `POST /memory/shared`
  (contributions and outcomes, counts only), `GET /memory/snapshot`. A finding carries `faers_locator`; the client calls
  `/memory/pair` with the finding's index ingredient and the Janus key to get the numbers.
- **Words.** The API returns codes, numbers and English sentences; the client renders the `Memory` namespace in the
  interface language (keys `Memory.codes.<code>`, `Memory.screening`, `Memory.attribution`, `Memory.meddra`). Every
  FAERS screen shows the disclaimer, the limits sentences (`spontaneous_reporting`, `not_incidence`,
  `deduplicated_by_case_version_only`), the window sentence, the attribution and, when a PT appears, the MedDRA notice.
  Counts are "reports"; user layers say "donated reports" or "doctor-confirmed outcomes", never people.
- **Display rules.** The assessment (`disproportionate`, `weak`, ...) is shown in a detail view with its range and report
  count, never as a badge, colour or icon in a list. Show `estimates.ror_ci` with every ratio; a ratio above 1,000 as
  "over 1,000". For `insufficient_data` and `no_reports` the API returns no ratios: show the coverage sentence and
  `absence_is_not_reassurance`. Separate panels for the three layers; never a sum or a comparison across layers.
- **Safety lines** (Requirement 7 above): `event.safety_line` is `crisis_support`, `urgent_care_skin`, `urgent_care_heart`,
  `urgent_care_gi`, `urgent_care_seizure`, `urgent_care_breathing` or null; show the line for any result of that event,
  whatever the counts, with the numbers of the user's region (`Memory.emergency.<region>`, `Memory.crisis.<region>`).
- **MedDRA notice.** Wherever a Preferred Term is shown, show the short notice `Memory.meddra` ("MedDRA® trademark is registered by IFPMA on behalf of ICH.", English in all
  languages); the long notice (NOTICE, exports, the doctor note) is `MEDDRA_NOTICE_LONG` in `messages.py` *(owner decision 2026-11-08)*.
- **Regions.** Show UNKNOWN as a count and a share, and `basis` (occurrence country vs reporter country); the EU link is
  `adrreports_url` (`https://www.adrreports.eu`), a fixed address with no user value.
- **Privacy page** states the residual limits of `collective-memory` Requirement 5.9 (two-step differencing; padding a cell
  before rate limiting exists) and "hidden under 20, noise added".
- **Errors.** 422 names failing fields only; 503 `memory_unavailable` has no numbers (show `Memory.codes.memory_unavailable`).

## Open items from drug-resolution Phase 2 (2026-11-08)

Source: `drug-resolution` requirements 1.4, 4, 12 and design §13, §19. The API contract grows; nothing here is built in the client yet.
- **Regions.** Scan and search requests accept `region: "EU"` (France and Spain adapters; any German-prefix code gets a notice). Result candidates carry `region: "EU"` and
  `country` (`FR` or `ES`); candidate ids look like `EU:eu_fr_bdpm:123`. `matched_by` has new values: `cip13`, `ntin`, `gtin`, `ai_712`,
  `ntin_digits`. For `ntin_digits` and `ai_712` say that the match came from the digits of the code, not from a listed product code
  (`eu-code-encodings.md`: less certain than a table hit).
- **AI (712), owner decision 2026-11-08: approved (`drug-resolution` DP19 extended, DP42).** The client sends exactly AI (01), (17) and, when the code carries it, (712) (a national product reimbursement number, not a serial); never serial (21) and never lot (10). The API rejects any element string that carries AI (21) with 422 `gs1_serial_not_accepted`; the client must strip it before sending and treat that error as a client defect, not as a user error.
- **Germany and other countries without an open product database.** The result has the notice `no_open_product_database` with `country`: offer on-device OCR and name search, never a guessed product,
  and do not word it as "not found". The notice `region_adapter_not_available` remains for any future region.
- **Source attribution (BDPM, Nomenclátor).** Show the source name, its update date (`source.snapshot_date`) and, for the BDPM, that the data are shown as published and that the BDPM does not endorse Janus; product text is shown
  exactly as published (French or Spanish, not translated by Janus). The licence asks for source and date.
- **Status fields.** `status_published` is a list of strings as published (authorisation and marketing status); show it on the product card as information. Products with a stop declaration
  have `marketing_end_date`; never use these fields to say that a medicine is or is not safe or needed.
- **Homeopathic EU products.** BDPM products with the homeopathic marker have `homeopathic = true`: show "homeopathic product, not checked" as for the US (Requirement 11.1 of `drug-resolution`).
- **Name search by language.** With region `EU` or none, ingredient search finds German, French and Spanish names; typed national codes (CIP7, a printed Spanish CN, a German PZN) are not accepted as codes: send OCR text to name search, and send a printed CIP13 or EAN-13 as bare digits to the scan route.
- **503 for a missing EU source.** `resolution_unavailable` for region `EU` means the French or Spanish data are not loaded; do not say "not found". A scan whose code has a French GS1 prefix and a request for region `EU` answer 503 on a dataset without the BDPM or the Nomenclátor; a Turkish or US scan works on the same dataset.
- **Status strings (built in task 23).** French `status_published` entries are the BDPM strings as published (for example `Autorisation active`, `Déclaration de commercialisation 16/03/2011`). Spanish entries are machine strings: `commercialised:true|false`, `registration_status:<code> <date>`, `presentation_status:<code> <date>`, `serialised:true|false`; the client words them in the user's language. The meaning of the numeric status codes is not in the artifact: confirm it against the AEMPS documentation before the client labels any of them.
- **`atc_selection = component_code` (task 27).** An ingredient may carry the combination code `J01DH51` when its key is the curated imipenem key `J2` (a reviewed pair, `drug-resolution` DP43). Show it as a normal mapped ingredient; do not present `J01DH51` as imipenem's own WHO code, and never as the code of cilastatin, which has none.
