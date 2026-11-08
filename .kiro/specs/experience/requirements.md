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
   - `crisis_support` (key `depression`): a crisis or support line for the user's region, after the emergency notice (112 in Türkiye and the EU, 911 in the US; `medical-safety.md` rule 10);
   - `urgent_care_skin` (key `rash`): a rash that is severe, spreading or blistering, or comes with fever or mouth sores, needs urgent medical care or a call to emergency services;
   - `urgent_care_heart` (key `arrhythmia`, including torsade de pointes): fainting, or a racing or irregular heartbeat with chest pain or breathlessness, needs urgent care or a call to emergency services.
2. THE lines SHALL NOT diagnose, SHALL NOT tell the user to start, stop or change a medicine, and SHALL be shown whatever the counts are (also for `no_reports` and `insufficient_data`).
3. THE region's crisis or support line numbers SHALL come from a curated list verified before launch (`docs/pre-launch-checklist.md`); none is hard-coded from memory.
4. MedDRA Preferred Term names SHALL appear only in a details view, never in a banner, a list badge or a notification. THE default display of an event is its Janus label.
5. THE API returns `event.safety_line` for a Janus key and for a PT (an active key that lists the PT) and `safety_line` on every event row of a combination; the client shows the line wherever the event is shown.
6. THE depression screen SHALL show the abrupt-stop line ("Do not stop this medicine suddenly") beside any antidepressant, beta-blocker or other abrupt-stop class on the same screen as `crisis_support` (`medical-safety.md` rule 4). *(Collective-memory safety review S17.)*
7. THE wording of the three lines is in the `Memory` message namespace in en, tr, de, fr, es (`collective-memory` task 12) and passes the forbidden-phrase and word-list checks.

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
- **Safety lines** (Requirement 7 above): `event.safety_line` is `crisis_support`, `urgent_care_skin`, `urgent_care_heart`
  or null; show the line for any result of that event, whatever the counts.
- **Regions.** Show UNKNOWN as a count and a share, and `basis` (occurrence country vs reporter country); the EU link is
  `adrreports_url`, a fixed address with no user value.
- **Privacy page** states the residual limits of `collective-memory` Requirement 5.9 (two-step differencing; padding a cell
  before rate limiting exists) and "hidden under 20, noise added".
- **Errors.** 422 names failing fields only; 503 `memory_unavailable` has no numbers (show `Memory.codes.memory_unavailable`).
