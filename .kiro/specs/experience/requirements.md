# Requirements: Experience (patient, doctor, researcher, judge)

> Phase 3, client side (`apps/web`). Refined 2026-11-08 from the draft seed. The seed's criteria are kept, refined in EARS
> form and numbered; additions are marked *(Added in refinement)*. The open items that `cascade-engine`,
> `collective-memory`, `drug-resolution` (Phase 2) and `doctor-loop` left for this spec are now numbered criteria; the
> section "Resolved open items" at the end maps every open-item bullet to its criterion.
> **Owner decisions 2026-11-08, applied:** theme (Two Faces default, Glass in Settings › Appearance, tokens exactly as
> `.kiro/steering/design.md`); fonts; the API decides everything medical; local-first storage; PDF in the browser and the
> token only in the URL fragment; on-device barcode and OCR; demo mode with three synthetic patients and a cached
> snapshot; researcher area as a Phase 3 shell; vitest + fast-check, Playwright with axe for the rendered checks; large
> text, read aloud, reduce transparency. Tags: **[Passport spec]** marks screens built from `medication-passport`
> (this spec gives the shell, the list store and the slots); **[Phase 4]** marks researcher content; **[Phase 5]** marks
> deployment.

## Introduction
The end-to-end product experience across five languages and three regions, including a judge/demo mode, because
hackathon judges will not have Turkish (or most EU) medicine boxes at hand and may judge from the video alone. The client
reads codes and labels on the device, asks the API for every medical result, words the API's codes in the user's
language, and keeps the person's list in the browser.

## Glossary
- **Client:** the Next.js web app in `apps/web` (installable PWA).
- **Paper:** the ivory surface of the doctor note preview and of the doctor page form card; the doctor note PDF is
  printed on white paper. *(Owner decision 2026-11-08, third: the shadow / light faces are gone; every screen of a
  theme uses that theme's tokens, DP48.)*
- **Theme vocabulary:** the words of the theme devices (ghost, zombie stamp, séance table) in Two Faces and their
  plain equivalents in Glass ("possible prescribing cascade", "Retracted", "evidence summary").
- **List:** the person's medicine list, stored in the browser. **Item:** one confirmed medicine of the list (a product
  candidate or an ingredient found by name) with its start month or "don't know" and the name as on the box.
- **Source key:** what the client keeps per item to resolve it again: the filtered scan content, the NDC, or the search
  query with the chosen candidate's identity.
- **Box name:** the name as printed on the box or label (from the resolved product or typed by the user); never sent to
  the server.
- **Finding:** one entry of `findings` in `POST /cascades/evaluate` (a "ghost" in Two Faces).
- **Outbound filter:** the client function that turns a decoded GS1 element string into the content sent to
  `POST /resolve/scan` (AIs (01), (17) and (712) only).
- **Demo patient:** one of three synthetic patients (Istanbul, Cologne, Ohio) whose API responses are fixed fixtures.
- **Demo code:** a synthetic product code printed on the demo sheet, recognised by the client before any API call.
- **Note token:** the opaque string returned by `POST /notes/token` (`doctor-loop` glossary).
- **Deletion token:** the string returned once by `POST /contributions` (`jdt_…`).
- **User region:** the user's setting `US`, `TR`, `EU`, `OTHER` or `UNKNOWN` (emergency and crisis numbers); distinct
  from the scan regions `TR`, `US`, `EU` and from the statistics region.

## Requirements

### Requirement 1: Patient / caregiver flow
**User story:** As a caregiver, I want to scan my mother's medicines and understand in a few minutes what to discuss with her doctor.

#### Acceptance criteria
1. THE flow SHALL be: choose region(s) → scan / photograph / type medicines → confirm each → answer "since when?" (month/year or "don't know") → timeline → findings ("ghosts") → evidence → doctor note.
   - *(Refined.)* THE client SHALL let the user leave and resume the flow at any step; the list is kept between visits (Requirement 9.3).
   - *(Refined.)* THE client SHALL evaluate the list only after every item is confirmed (Requirement 12) and SHALL show findings only from the latest evaluation of the current list.
2. THE first screen SHALL show the emergency notice (112 / 911) and the "information, not medical advice; research prototype" statement.
   - *(Refined.)* THE emergency notice SHALL come first on the home screen and SHALL use the number of the user region (`Memory.emergency.<region>`); THE disclaimer SHALL be `Disclaimer.text` of the interface language.
3. WHEN no finding is produced THE screen SHALL show the no-false-reassurance statement.
   - *(Refined.)* WHEN the result's `statement.code` is `no_pattern_found` THE client SHALL show `medical-safety.md` rule 3 in the interface language, and SHALL NOT show "safe", "no problems", "all clear" or an equivalent in that language.
4. THE flow SHALL work on a 375 px wide phone screen without horizontal scrolling.
5. *(Added in refinement.)* THE client SHALL accept medicines bought without prescription and supplements by name (`cascade-engine` Req 8.8) and SHALL NOT filter items by product type, prescription status or region.
6. *(Added in refinement.)* IF the list holds more than 50 items THEN THE client SHALL NOT send an evaluation and SHALL say that Janus checks at most 50 medicines at once.

### Requirement 2: Languages and regions
#### Acceptance criteria
1. THE interface SHALL be available in English (primary), Turkish, German, French and Spanish.
2. THE user SHALL be able to switch interface language, doctor-note language and region independently.
   - *(Refined.)* "Region" means three independent settings: the scan regions (`TR`, `US`, `EU`, or automatic), the user region (Glossary) and the optional statistics region (`TR`, `EU`, `US`) of the note.
3. Dates, numbers and decimal separators SHALL follow the selected locale.
   - *(Refined.)* Numbers returned by the API as numbers (counts, ratios, ranges, shares) SHALL be formatted by the client for the interface locale; sentences returned as text by `POST /notes/document` SHALL be shown exactly as returned and never re-formatted (`doctor-loop` DP3).
4. *(Added in refinement.)* EVERY user-facing string of the client SHALL come from the message catalogues `apps/web/messages/<locale>.json`, or verbatim from an API response field that is defined as text (published product text, note document text, outcome form text), or from the generated vocabulary of Requirement 2.5. THE client SHALL NOT machine-translate at runtime.
5. *(Added in refinement.)* Cascade names, Janus event labels and ingredient names in the five languages SHALL come from the reviewed files of the API (`apps/api/janus/notes/glossary/*.csv` rows with status `accepted`, `apps/api/janus/memory/memory_events.csv`), copied into the client by a generator and kept equal by a parity test; THE ingredient name SHALL follow `doctor-loop` DP16: accepted name, else the accepted English INN with "name not translated" and the ATC code, else the code with "name not reviewed".
6. *(Added in refinement.)* Product text from a source (TİTCK, openFDA, BDPM, Nomenclátor) SHALL be shown exactly as published, in its own language, never translated by Janus (`drug-resolution` Phase 2 notes).

### Requirement 3: Accessibility
#### Acceptance criteria
1. THE interface SHALL meet WCAG 2.2 AA: keyboard navigation, visible focus, alt text, contrast, reduced-motion support for all ghost animations.
   - *(Refined.)* Contrast SHALL be at least 4.5:1 for text and 3:1 for UI boundaries and focus for every token pair used as text on a surface, in both themes and both colour schemes (`design.md` steering); a test SHALL compute it from the token file.
   - *(Refined.)* Touch targets SHALL be at least 44 × 44 px; THE focus ring SHALL be 3 px `--accent` with 2 px offset; keyboard order SHALL follow reading order.
   - *(Refined; changed 2026-11-08, third, DP48.)* WHEN `prefers-reduced-motion: reduce` is set THE client SHALL stop every non-essential motion (ghost drift).
   - *(Refined.)* An automated check (axe, WCAG 2.2 A and AA rules) SHALL report no violation on every route, in every locale, in both themes.
2. A large-text mode and text-to-speech reading of findings SHALL be available for older users.
   - *(Refined.)* THE large-text mode SHALL set the base size to 19 px and line height 1.6 (default 16 px), with no loss of content or horizontal scroll at 375 px.
   - *(Refined.)* Read aloud SHALL be off by default; WHERE it is on and the browser has a speech voice for the interface language THE client SHALL offer a "read aloud" control on each finding that reads only that finding's text, its abrupt-stop line and its safety lines, in the interface language, through the Web Speech API; nothing is sent to a server.
3. Every data view SHALL handle loading, empty, error and long-content states.
4. *(Added in refinement; owner decision.)* THE client SHALL offer "Reduce transparency" in Settings › Appearance; WHEN it is on, or `prefers-reduced-transparency: reduce` is set, or `backdrop-filter` is unsupported, THE Glass theme SHALL use solid cards (`#FFFFFF` light, `#1C1F22` dark) and no blur.
5. *(Added in refinement.)* Medicine icons SHALL combine shape and colour; icons SHALL be inline SVG (Lucide shapes, 1.9 px stroke), never emoji; every icon that carries meaning SHALL have a text alternative.
6. *(Added in refinement.)* Confidence-interval bars SHALL carry the same numbers as text next to them; colour SHALL never be the only carrier of meaning.

### Requirement 4: Judge / demo mode
**User story:** As a hackathon judge without Turkish boxes, I want to try the full flow in two minutes.

#### Acceptance criteria
1. THE home page SHALL offer "Try the demo" without any sign-up.
2. Demo mode SHALL include printable/scannable sample codes (TR, US, FR/ES) for synthetic products clearly labelled "demo", and three synthetic patients (Istanbul, Cologne with mixed TR+DE boxes, Ohio with pharmacy vials).
   - *(Refined.)* THE Istanbul patient SHALL be the cascade-engine gate-1 case: a combination box of amlodipine + lisinopril (resolved to amlodipine `C08CA01` and lisinopril `C09AA03`; the box's published code `C09BB03` shown only as published), furosemide started five months later, and the seven other medicines of `apps/api/tests/test_cascades_real_artifacts.py`, giving PIPC row 5 (calcium channel blocker → peripheral edema → diuretic) as `probable`.
   - *(Refined.)* THE Cologne patient SHALL mix Turkish boxes (resolved by code) and German boxes (notice `no_open_product_database`, resolved by on-device text recognition and name search), so that at least one finding is form-unconfirmed. THE Ohio patient SHALL hold pharmacy vials resolved by NDC from the label text.
   - *(Refined.)* THE demo sheet SHALL be a printable page with one code per demo product, each printed with "DEMO — synthetic product, not a medicine"; demo codes SHALL use a code range that no real medicine uses (design §13.2).
3. Demo data SHALL be clearly labelled synthetic on every screen and SHALL never be mixed into Collective Memory.
   - *(Refined.)* WHILE demo mode is on THE client SHALL show the persistent label "Demo · synthetic patient" on every screen, including the note preview and the PDF.
   - *(Refined.)* WHILE demo mode is on THE client SHALL make no request to `POST /contributions`, `POST /contributions/deletions`, `POST /notes/token`, `POST /notes/withdraw`, `POST /outcomes/form` or `POST /outcomes`, and SHALL never send `"demo": true` anywhere (the API rejects it; `privacy` DP21, `doctor-loop` Req 3.6).
   - *(Refined.)* Demo items SHALL never be written to the person's own list, and the person's list SHALL never be shown in demo mode.
4. Demo mode SHALL work even if external APIs are unavailable (cached snapshot).
   - *(Refined.)* Demo mode SHALL work with no network at all after the first visit, and with the Janus API down: every demo screen is served from fixtures recorded from the real local API and the cached app shell.
5. *(Added in refinement.)* THE client SHALL recognise a demo code before any API call; a scanned or typed demo code SHALL never be sent to the API.
6. *(Added in refinement.)* Demo product names and codes SHALL be invented and labelled as such; THE fixtures SHALL contain no TİTCK string (`structure.md`: TİTCK data is not committed); ingredients, findings, statistics and note text SHALL come from the real rule base and data snapshot, whose versions and dates the demo shows.
7. *(Added in refinement.)* THE demo SHALL include the doctor side: the demo note's QR code SHALL open a demo doctor page that shows the recorded form and says that nothing is sent.

### Requirement 5: Doctor and researcher areas
#### Acceptance criteria
1. THE doctor QR page SHALL require no account and SHALL load on a phone in under 3 seconds on a 4G connection. (Requirement 19, Requirement 25.)
2. THE researcher area SHALL contain hypothesis cards, the séance view, the retrospective-validation report and dataset export; it SHALL be reachable from the main navigation but not part of the patient flow.
   - *(Refined, owner decision.)* In Phase 3 THE researcher area SHALL be a shell (Requirement 24); the content of the four parts is **[Phase 4]**.

### Requirement 6: Theme with function
#### Acceptance criteria
1. Ghosts SHALL represent cascades, the zombie stamp SHALL mark retracted evidence, and the séance table SHALL hold the three witnesses; decorative-only spooky elements SHALL NOT be added. *(Changed 2026-11-08, third, DP48: the two-faced mask is the Janus mark only; there is no shadow/light switch.)*
2. The patient-facing tone SHALL be mysterious and reassuring, never frightening; red is used only for real risk.
   - *(Refined.)* `--risk` SHALL be used only for the emergency notice, urgent-care lines and retracted evidence; never for a finding, a ratio or an assessment class.
3. *(Added in refinement; owner decision.)* THE default theme SHALL be Two Faces; THE user SHALL be able to choose Glass in Settings › Appearance. Both themes SHALL use one component set, the same content, the same safety rules and the same layout; only the theme vocabulary and the tokens differ. THE tokens SHALL be exactly those of `.kiro/steering/design.md`.
4. *(Added in refinement; changed by owner decision 2026-11-08, third, DP48.)* THERE SHALL be no light mode and no light face: every screen of Night Pharmacy, the researcher area included, SHALL use the Night Pharmacy tokens, and there SHALL be no mask switch. THE doctor note preview SHALL show the note on paper and THE doctor note PDF SHALL be printed on white paper; THE doctor QR page SHALL show its form on a paper card on the Night Pharmacy page. Glass Janus SHALL keep following the system light / dark preference.
5. *(Added in refinement.)* IN Glass THE client SHALL use the plain vocabulary of the Glossary and SHALL show no theme-device word (ghost, mask, zombie, séance or their translations) on any screen.
6. *(Added in refinement.)* Fonts SHALL be Fraunces (display), Atkinson Hyperlegible (all running text, labels, controls) and IBM Plex Mono (ATC codes, DOIs, ratios, ranges, with tabular numerals) in Two Faces; system UI, then Figtree, and IBM Plex Mono in Glass. Fonts SHALL be served from the Janus origin (no third-party font request).
7. *(Added in refinement.)* THE theme, large text, reduce transparency and read-aloud settings SHALL be applied before first paint (no flash of the wrong theme).

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
   - *(Added in refinement.)* `POST /cascades/evaluate` carries no event key field: THE client SHALL take a finding's Janus event key from its `faers_locator` (`event=` part) and, when the locator is null, from the generated vocabulary (`pipc_positions` of the rule's row), and SHALL look up its `safety_line` in the generated vocabulary.
6. THE depression screen SHALL show the abrupt-stop line ("Do not stop this medicine suddenly") beside any antidepressant, beta-blocker or other abrupt-stop class on the same screen as `crisis_support` (`medical-safety.md` rule 4). *(Collective-memory safety review S17.)*
7. THE wording of the six lines and of the regional numbers is in the `Memory` message namespace in en, tr, de, fr, es (`collective-memory` task 12) and passes the forbidden-phrase and word-list checks.
8. *(Added in refinement.)* WHERE a safety line or an emergency-symptom event (chest pain, breathing difficulty, signs of stroke, severe allergic reaction) appears on a screen THE emergency notice SHALL come first on that screen (`medical-safety.md` rule 10, `collective-memory` Req 8.9).

### Requirement 8: App shell and navigation *(Added in refinement)*
**User story:** As an older user, I want the same few places on every screen so that I never get lost.

#### Acceptance criteria
1. EVERY screen SHALL carry the disclaimer of `medical-safety.md` rule 9 in the interface language, and THE emergency notice SHALL be reachable from every patient screen in one step.
2. THE main navigation SHALL offer Scan, Medicines, Results and Settings on the patient side, plus an entry to the researcher area ("Research" in the header navigation, the footer and Settings, in both themes; DP48); the researcher area SHALL NOT be a step of the patient flow.
3. THE header SHALL hold the language switcher (language names in their own language), and, WHILE demo mode is on, the demo label and an "exit demo" control.
4. Unknown paths SHALL show the localized not-found page with links back to the home screen.
5. THE shell SHALL host the Passport screens and components of the `medication-passport` spec in the slots of design §15 without changing the shell. **[Passport spec]**
6. THE shell SHALL keep a maximum content width of 720 px for reading screens on desktop and SHALL be checked at 375 px and 1280 px.

### Requirement 9: Settings and local storage *(Added in refinement; owner decision 4)*
#### Acceptance criteria
1. THE settings screen SHALL hold: interface language, doctor-note language, scan regions, user region, statistics region, Appearance (theme, large text, reduce transparency), read aloud, and "delete everything on this device".
2. Theme, large text, reduce transparency and read aloud SHALL be stored in `localStorage` as a per-device convenience and read before first paint.
3. THE list, the settings, the outcome-loop tokens and the reminders SHALL live only in the browser; THE server SHALL persist nothing of them unless the user donates (Requirement 20) or a doctor reports an outcome (Requirement 19).
4. EVERY storage read and write SHALL be wrapped so that a missing, blocked, full or corrupt storage never breaks a screen: THE client SHALL then keep the data in memory for the session and SHALL say once that it cannot be kept on this device.
5. Stored documents SHALL carry a schema version; IF a stored document has an unknown or invalid shape THEN THE client SHALL NOT use it and SHALL say so, without sending it anywhere.
6. WHEN the user chooses "delete everything on this device" THE client SHALL, after a confirmation, remove every Janus key from browser storage and the service worker caches, and SHALL say that donated data and doctor outcomes are deleted only with their deletion token or note token (Requirements 18.5, 20.6).
7. THE client SHALL use no cookies, no analytics, no third-party requests and no device identifier.

### Requirement 10: Scanning codes *(Added in refinement; owner decision 6)*
**User story:** As a caregiver, I want to point the phone at the box and get the medicine without typing.

#### Acceptance criteria
1. THE client SHALL decode DataMatrix (GS1), EAN-13, EAN-8, UPC-A and Code 128 with `zxing-wasm` in the browser, from the camera or from a photo the user picks; THE image SHALL never leave the device and SHALL not be stored.
2. FROM a decoded GS1 code THE client SHALL send `POST /resolve/scan` only the Application Identifiers (01) GTIN, (17) expiry and, if the code carries it, (712) national product reimbursement number; never serial (21), never lot (10), never any other AI. *(`privacy` Req 1.1, `drug-resolution` Req 1.4, DP19 extended, DP42.)*
3. A bare GTIN-8/12/13/14 (a linear barcode) SHALL be sent as digits; a printed CIP13 or EAN-13 typed by the user SHALL be sent as bare digits to the scan route (`drug-resolution` Phase 2 notes).
4. IF the API answers 422 `gs1_serial_not_accepted` THEN THE client SHALL treat it as a client defect: it SHALL show a generic "something went wrong on our side" message, SHALL NOT ask the user to change anything, and SHALL NOT retry.
5. WHEN the camera is not available or permission is refused THE client SHALL offer the photo picker, label recognition and typing, without blocking the flow.
6. THE scan request SHALL carry the scan region when the user set one (`TR`, `US` or `EU`), else no region.
7. WHEN a scan gives a GS1 expiry THE confirm screen MAY show it as information (`scan.expiry`, `expiry_status`); THE client SHALL never use it to say a medicine is or is not safe to take.

### Requirement 11: Label text recognition, NDC and name search *(Added in refinement)*
#### Acceptance criteria
1. THE client SHALL offer on-device text recognition (`tesseract.js`) of a box or a pharmacy label photo; recognition SHALL run in the browser; the image SHALL never leave the device.
2. THE client SHALL NOT send recognised text as a whole. FROM recognised text THE client SHALL extract locally (a) strings shaped like an NDC, offered for `POST /resolve/ndc`, and (b) words or lines the user taps, offered as a query (2 to 100 characters) for `POST /resolve/search`; nothing SHALL be sent before the user chooses it. (Pharmacy labels carry the patient's name, the prescriber and the pharmacy.)
3. WHEN on-device OCR produces text THE client SHALL show candidates for confirmation; unconfirmed OCR results SHALL NOT be used. (`drug-resolution` Req 6.1.)
4. THE user SHALL be able to type a name (product or ingredient, any of the five languages) or an NDC; typed national codes that are not GTINs (CIP7, a printed Spanish CN, a German PZN) SHALL NOT be sent as codes: THE client SHALL say they cannot be looked up as codes and offer name search.
5. WITH scan region `EU` or none, name search SHALL send the region as set (`EU` or absent) so that German, French and Spanish ingredient names are found.

### Requirement 12: Confirming a medicine *(Added in refinement)*
#### Acceptance criteria
1. THE client SHALL show every candidate of a resolution for the user to choose and SHALL NOT pre-confirm any; an item enters the list only after the user confirms one candidate.
2. FOR each candidate THE confirm screen SHALL show the region and source, the product text as published, the ingredients with their resolved names and ATC codes, and the published product code (`published_atc`) labelled "as published"; a combination product's published code SHALL never be shown as an ingredient's code.
3. WHEN an ingredient position is `ambiguous` THE client SHALL ask the user to choose among `key_candidates` (with names) or "don't know"; a chosen key SHALL be sent as a `choice` (positions start at 0); "don't know" sends no choice and the engine reports the position as not checked.
4. WHEN `matched_by` is `ntin_digits` or `ai_712` THE client SHALL say that the match came from the digits of the code, not from a listed product code, and is less certain.
5. WHEN a result has the notice `no_open_product_database` with a `country` THE client SHALL offer on-device text recognition and name search, SHALL NOT guess a product, and SHALL NOT word it as "not found". THE notice `region_adapter_not_available` SHALL be worded as "this region is not supported yet".
6. WHEN a resolution has no candidate THE client SHALL say "not found" with the regions searched and each source's name and update date; IF the API answers 503 `resolution_unavailable` THEN THE client SHALL say that the data is not available right now and SHALL NOT say "not found" (also for region `EU` when the French or Spanish data are not loaded).
7. THE client SHALL show source attribution on every product card: source name and update date (`source.snapshot_date`); for the BDPM also that the data are shown as published and that the BDPM does not endorse Janus; for the Nomenclátor (CIMA) the attribution of Ley 37/2007; for openFDA and TİTCK their source name and date.
8. `status_published` SHALL be shown on the product card as information: French BDPM strings as published; Spanish machine strings (`commercialised:true|false`, `registration_status:<code> <date>`, `presentation_status:<code> <date>`, `serialised:true|false`) worded in the interface language, with numeric status codes shown as published until their meaning is confirmed against the AEMPS documentation (design open item 2). `marketing_end_date` SHALL be shown as a date. THE client SHALL never use these fields to say that a medicine is or is not safe or needed.
9. A product with `homeopathic = true` SHALL be shown as "homeopathic product, not checked", in every region.
10. An ingredient with `atc_selection = component_code` (for example imipenem with `J01DH51`) SHALL be shown as a normal mapped ingredient with its code labelled "combination code"; THE client SHALL NOT present `J01DH51` as imipenem's own WHO code, and never as the code of cilastatin.
11. A candidate with `rxcui_status = not_in_wikidata` or an ingredient with `status = unmapped` SHALL be shown with its reason as "cannot be checked" text; THE notice `unmapped_ingredients` SHALL say that some ingredients cannot be checked.
12. THE confirm screen SHALL let the user edit the box name (pre-filled from `product_name` or the typed query) and SHALL ask "since when?" (Requirement 13.1) before the item is added.

### Requirement 13: "Since when", the medicine list and the timeline *(Added in refinement)*
#### Acceptance criteria
1. "Since when?" SHALL accept a month and year (not later than the current month) or "don't know", in the locale's month names; THE client SHALL send it as `started: "YYYY-MM"` or `null`.
2. THE medicine list SHALL show each item's box name, ingredients, region and source, start month or "start not known", and the abrupt-stop line for items with an `item_warnings` entry after an evaluation; THE user SHALL be able to edit the start month, the box name and the ingredient choices, and remove an item.
3. THE timeline SHALL show the items with a start month in time order, items with unknown start in a separate lane, and, after an evaluation, each finding as a link from its index items to its marker items, with the months between when known.
4. THE list SHALL show each item's region and source; duplicate-ingredient flags and cross-region equivalents are the Passport's. **[Passport spec]**
5. WHEN any item changes THE client SHALL mark the last evaluation as out of date and SHALL NOT show its findings as current.

### Requirement 14: Evaluation and findings *(Added in refinement; from the cascade-engine open items)*
**User story:** As a caregiver, I want each pattern explained in plain words, with what to say to the doctor and nothing that frightens or instructs.

#### Acceptance criteria
1. THE client SHALL call `POST /cascades/evaluate` with the resolution `dataset_version` and 1–50 items, each a product `candidate_id` (with `choices` for ambiguous ingredient positions, which start at 0) or an ingredient QID, plus `started` as `YYYY-MM` or null. THE client SHALL never send ATC codes.
2. THE client SHALL keep each item's source key (GTIN content, NDC or name query) in the browser so that it can re-resolve after `409 dataset_version_mismatch` (Requirement 22.3).
3. EVERY finding SHALL show: the cascade as the rule's class names and event label in the interface language, the two medicines (box names and ingredient names), the order and months between when known, the status and timing worded in the interface language, whether it is low priority, priority data with its range when present (BMJ 2026), a supporting source when present, the form-extension note when `via_form_extension`, the integrity notices of `integrity_codes`, and "This may be worth discussing with your doctor." THE finding SHALL be worded as a pattern match ("These two medicines match a prescribing-cascade pattern described in the literature"), never as a verdict.
4. Form-unconfirmed findings (`form_confirmed = false`, for example an ingredient typed by name) SHALL be shown in a separate group with its own heading that names the matched codes and asks the user to confirm the product; a finding SHALL appear in exactly one group.
5. FOR every item with an `item_warnings` entry THE client SHALL show "Do not stop this medicine suddenly." in the interface language once per item, in the list and on every results screen that shows the item, whether or not the item is in a finding (`medical-safety.md` rule 4).
6. THE client SHALL show `rules.checked` of `rules.total` patterns checked, and SHALL list not-matchable rules (PIPC rows 27 and 57) and rules disabled by evidence integrity as "cannot be checked" with the rule's name; every `not_checked` entry SHALL be shown on its item as "cannot be checked" with its reason worded in the interface language.
7. A product with `homeopathic = true` SHALL be shown as "homeopathic product, not checked"; the result lists its ingredients as `not_checked` with reason `homeopathic_product` (owner decision 2026-11-07).
8. THE results SHALL show chains as a sequence of ingredient names with the findings they are built from; `same_product` pairs SHALL NOT be shown as findings; WHEN `notices` holds `chains_truncated` THE client SHALL say that not all chains are shown.
9. WHEN `statement.code` is `rule_base_unavailable` or the API answers 503 `cascades_unavailable` THE client SHALL say that the check is not available right now and SHALL NOT show the rule-3 sentence or any finding.
10. Results carry codes and English canonical sentences; THE client SHALL render the codes in the interface language from the message catalogues and SHALL NOT display the English canonical sentences except the PIPC text when the rule's row has no accepted translation.
11. IN Two Faces each finding SHALL be presented as a ghost (shape and label, drifting 6 s / 3 px unless reduced motion); IN Glass as "possible prescribing cascade". Neither SHALL use `--risk`.

### Requirement 15: Evidence and the integrity line *(Added in refinement; from evidence-integrity [Client] criteria)*
#### Acceptance criteria
1. THE evidence view of a finding SHALL call `POST /evidence/resolve` with the finding's `evidence_ids` and SHALL show, for each source, its title, DOI or locator, its integrity status and check date, its notices (correction, expression of concern, with links), its freshness, and its root sources.
2. A source with status `retracted` SHALL be shown only among the excluded sources, with the zombie stamp (Two Faces) or a plain "Retracted" label (Glass) and the sentence that Janus did not use it; THE stamp SHALL never appear on a source that a finding uses.
3. THE evidence view SHALL show the integrity line: number of sources, how many were checked by DOI, counts per status, the date range of the checks, stale sources, and "no retracted source used" when `no_retracted_used` is true, otherwise the exceptions; the line SHALL state nothing about the person's medicines.
4. THE PIPC correction notice (10.1007/s41999-025-01378-7) SHALL appear with every PIPC rule record that carries it, as data from the API.
5. IF the API answers 503 `integrity_unavailable` THEN THE evidence view SHALL say that source checks are not available right now and SHALL still show the evidence ids the finding cites.

### Requirement 16: Collective Memory panels *(Added in refinement; from the collective-memory open items)*
#### Acceptance criteria
1. FOR a finding with a `faers_locator` THE client SHALL call `POST /memory/pair` with the finding's index ingredient key and the Janus event key (`{"key"}`), region `ALL` and scope `suspect`, and MAY add the same call for the user's statistics region.
2. FOR the list THE client SHALL offer `POST /memory/combination` (2 to 20 distinct ingredient keys of the list, default scope `any`), `POST /memory/regions` (1 to 20 keys, optional event) and `POST /memory/shared` for the layers `contributions` and `outcomes` (counts only); all lookups are `POST` with a JSON body. IF the list has more than 20 distinct ingredient keys THEN THE client SHALL ask the user which to compare.
3. THE API returns codes, numbers and English sentences; THE client SHALL render the `Memory` namespace in the interface language (keys `Memory.codes.<code>`, `Memory.screening`, `Memory.attribution`, `Memory.meddra`). EVERY FAERS panel SHALL show the disclaimer, the limits sentences (`spontaneous_reporting`, `not_incidence`, `deduplicated_by_case_version_only`), the window sentence, the screening sentence, the attribution with the snapshot date and, when a PT appears, the MedDRA notice `Memory.meddra` (English in all languages).
4. Counts SHALL be "reports"; user layers SHALL say "donated reports" or "doctor-confirmed outcomes", never people.
5. THE assessment (`disproportionate`, `weak`, …) SHALL be shown only in a detail view with its range and report count, never as a badge, colour or icon in a list; event lists SHALL show the report count and the interval first and SHALL be ordered as the API returns them (by report count).
6. EVERY ratio SHALL be shown with `estimates.ror_ci` as text and as a confidence-interval bar (axis, a mark at 1 "no difference", the range, the point estimate); a ratio or bound above 1,000 SHALL be shown as "over 1,000".
7. FOR `insufficient_data` and `no_reports` the API returns no ratios: THE client SHALL show the coverage sentence and `absence_is_not_reassurance`, and no number other than the report count.
8. THE three layers (FAERS, donated reports, doctor-confirmed outcomes) SHALL be in separate panels; THE client SHALL never sum, compare or combine numbers across layers. Hidden cells SHALL be shown as "Hidden under 20, noise added" (`hidden_under_20_noise_added`); `layer_unavailable` and `not_available` SHALL be worded from their codes.
9. THE regions panel SHALL show UNKNOWN as a count and a share, and `basis` (occurrence country vs reporter country); THE EU link SHALL be `adrreports_url` (`https://www.adrreports.eu`), a fixed address with no user value; `regions_not_comparable` and `tr_reports_small_self_selected` SHALL be shown where the API returns them.
10. THE combination panel SHALL say which level it shows (`combination`, `pairwise`, `single`), that set counts are lower bounds, and that the comparison group includes reports naming only some of the medicines; it SHALL never say the medicines interact or recommend a change.
11. Errors: 422 names failing fields only (a client defect: generic message); 503 `memory_unavailable` has no numbers (show `Memory.codes.memory_unavailable`).
12. THE client SHALL read `GET /memory/snapshot` for the snapshot date, window, staleness and layer status, and SHALL show `source_may_be_outdated` and `counts_built_against_other_dataset` when returned.

### Requirement 17: Doctor note preview and PDF *(Added in refinement; from the doctor-loop open items)*
**User story:** As a caregiver, I want to print one cited page for the doctor in the doctor's language and see what it says in mine.

#### Acceptance criteria
1. THE client SHALL call `POST /notes/document` with the body of `POST /cascades/evaluate` as `evaluation`, `pins` (`rule_base_version`, `integrity_version`, `counts_build_id` the patient saw), one or two `languages` (note language, then the patient's language for the side-by-side view), the user `region` and an optional `statistics_region`.
2. IF the API answers 409 `version_mismatch` (or `dataset_version_mismatch`) THEN THE client SHALL re-run the evaluation, show the patient the new result, and allow printing only after that.
3. THE response holds one document per language with the same sections and ids; THE client SHALL lay it out and SHALL NEVER re-word, re-order within a section, translate or drop any sentence.
4. Each medicine row has `product_name_slot: true`: THE client SHALL fill it from the browser's own data (the box name of the list item with the row's `item` index). THE box name SHALL never go to the server.
5. An ingredient whose name is not in the reviewed glossary comes with `name_basis` and a `tag` ("name not translated" or "name not reviewed"): THE client SHALL show the tag and the ATC codes next to the name; a `combination_code` label SHALL be shown next to its code.
6. Sections SHALL be laid out in the API's order: safety lines before the findings; form-unconfirmed findings as a separate section with its own heading; the abrupt-stop line in the medicine row; empty sections keep their heading.
7. A note may not fit one page: the findings section is ordered, overflow goes to a second page; THE PDF SHALL repeat the disclaimer and the page number on every page.
8. THE PDF SHALL be rendered in the browser (white paper, paper tokens, Fraunces / Atkinson Hyperlegible / IBM Plex Mono embedded), A4 and US Letter, with selectable text; THE medicine list SHALL never need to reach the server to produce it.
9. WHEN the note language differs from the interface language THE client SHALL show the side-by-side view: the note language and the patient's language block by block, paired by id, so the patient understands what the doctor receives.
10. WHILE demo mode is on THE preview and the PDF SHALL carry "Demo · synthetic patient" on every page.
11. IF the API answers 422 `note_language_unavailable` THEN THE client SHALL say that the note is not yet available in that language and offer the available ones.
12. IF the API answers 503 `notes_unavailable` THEN THE client SHALL say that the note cannot be made right now; the findings screen SHALL stay usable.

### Requirement 18: Outcome loop: QR opt-in, reminder and withdrawal *(Added in refinement; from the doctor-loop open items)*
#### Acceptance criteria
1. THE QR code SHALL be opt-in: THE note preview SHALL offer it with the outcome-loop consent text (what the doctor is asked, what is stored, for how long, how to withdraw) and SHALL call `POST /notes/token` only after the user accepts, with one language, `consent_version` of that text and `outcome_region` (TR, EU or US from the user region; the client SHALL ask when the user region is `OTHER` or `UNKNOWN`).
2. THE response returns `token`, `qr_url` (`https://<host>/o#<token>`), `expires_on`, `findings_covered`, `findings_total` and the note with an `outcome_loop` section; THE client SHALL print the QR code at 50 mm or more (version 25 at most, level M, byte mode) and SHALL print the note returned with the token (not an earlier document). WHEN `qr_url` is null THE client SHALL build the address from its own origin as `<origin>/o#<token>`.
3. THE token SHALL live only in the URL fragment and in the browser's storage of the patient; THE client SHALL never put it in a path, a query string, a log or analytics. IF the API answers 422 `no_findings` THEN THE client SHALL say that there is nothing for the doctor to report.
4. WHERE the patient opts in, THE client SHALL remind them after 4 weeks to report whether the symptom resolved; THE reminder SHALL be stored in the browser only (`doctor-loop` Req 3.3) and shown inside the app; reporting leads to the donation flow (Requirement 20) with the event pre-selected.
5. THE patient SHALL be able to withdraw with the same token (`POST /notes/withdraw`), also after use and after expiry; THE client SHALL show the same confirmation whether or not outcomes were stored, and SHALL keep the token until the API confirms.
6. IF the API answers 503 `notes_unavailable` for the token THEN THE client SHALL offer the note without a QR code.

### Requirement 19: Doctor QR page *(Added in refinement; from the doctor-loop open items)*
**User story:** As a family doctor, I want to scan the QR code on the note and answer in under a minute, without an account.

#### Acceptance criteria
1. THE page at `/o` SHALL require no account, SHALL read the token from `location.hash`, and SHALL post it in a JSON body to `POST /outcomes/form` and `POST /outcomes`; THE token SHALL never be put in a path, a query string, a log, storage or analytics, and the page SHALL send no referrer.
2. THE form SHALL list the token's findings in the note's language (texts from the API) with two questions per finding: the assessment (`confirmed`, `not_a_cascade`) and an optional action (`dose_changed`, `medicine_changed`, `stopped`, `no_change`) with the medicine it concerns ("First medicine: {name}", "Second medicine: {name}") required for `dose_changed`, `medicine_changed` and `stopped`. A finding MAY be left unanswered; THE send control SHALL be enabled only with at least one answer.
3. THE page SHALL show the API's texts (`heading`, `intro`, `stored_fields`, `limits`, the questions, the disclaimer) exactly as returned, on a paper card (DP48).
4. Errors SHALL be worded in the note's language when known, else the browser's language among the five: `invalid_token` (400) "this link is not valid"; `token_expired` (410); `token_not_usable` (410, withdrawn by the patient); `token_used` (409, "an answer was already sent"); 503 "not available right now, try later"; a network failure offers a retry that sends the same answers.
5. WHEN the submission is accepted (`{stored: n}`) THE page SHALL confirm and SHALL disable further submission.
6. THE page SHALL be usable on a phone at 375 px and SHALL become interactive in under 3 seconds on a 4G connection (Requirement 25.1).
7. IF the fragment is a demo fragment THEN THE page SHALL show the demo form from fixtures with the demo label and SHALL send nothing (Requirement 4.7).
8. THE page SHALL give no advice: it asks what was done.

### Requirement 20: Donation with consent and deletion token *(Added in refinement; from the privacy [Client] criteria)*
**User story:** As a user, I want to choose exactly what I share and be able to take it back.

#### Acceptance criteria
1. WHEN a user chooses to donate THE client SHALL show a specific consent screen, in the user's language, listing every field to be shared and the legal basis (explicit consent). (`privacy` Req 3.1.)
2. THE donation form SHALL offer exactly the stored fields: 5-year age band (20, 25, …, 85, "90 and over"; no band under 20), optional sex (`female`, `male`, not given), region (TR, EU, US only), ingredients (1–20 distinct keys chosen from the list), event (one Janus event key, shown by its label), direction (adverse / benefit); the screen SHALL show what will be stored and that the week is set by the server.
3. THE client SHALL send `POST /contributions` only after the user ticks the explicit consent; the request SHALL carry `consent: {version, explicit: true}` and the fields of 20.2 only.
4. WHEN the donation is stored THE client SHALL show the deletion token once, with the stored record (`stored`), and SHALL offer to keep the token on this device or copy it; THE client SHALL say that without the token the donation cannot be deleted before the 24-month purge.
5. THE donation event picker SHALL show the emergency notice first and the event's safety line (Requirement 7).
6. THE user SHALL be able to delete a donation with its token (`POST /contributions/deletions`, token in the body); `{deleted: true}` SHALL be confirmed; 404 `no_donation_for_token` SHALL say that no donation was found for this token (already deleted or never stored).
7. Errors: 503 `donations_unavailable` "donations are not possible right now"; 422 `invalid_donation` naming `consent.version` "the consent text was updated: please read it again"; other 422 a client defect; 422 `demo_donation_rejected` SHALL never occur (demo never reaches the route).
8. WHILE demo mode is on THE donation entry SHALL be replaced by a sentence that demo data is never donated.

### Requirement 21: Privacy page *(Added in refinement; from privacy, collective-memory and doctor-loop [Client] criteria)*
#### Acceptance criteria
1. THE privacy page SHALL explain, in all supported languages, what stays on the device (images, recognised text, the list, box names, settings, tokens, reminders), what is sent (codes and ids, typed search text, the choices of Requirement 23), what is stored (donations; doctor outcomes; used note ids until expiry), for how long (24 months; tokens 28–35 days), and how to delete it (deletion token; note token withdrawal; "delete everything on this device").
2. THE page SHALL state the hosting region of donated data from `GET /privacy/storage` (`donation_storage_region`, `in_eu`) and whether donations are enabled; IF the endpoint fails THEN THE page SHALL say that the region cannot be shown right now, not guess it.
3. THE page SHALL state the retention period (24 months) and "hidden under 20, noise added", and SHALL NOT claim formal differential privacy for the release as a whole.
4. THE page SHALL state the residual limits: two-step differencing (A) − (A,B) − (A,C) + (A,B,C) is not covered; until rate limiting exists (Phase 5) someone who can add donations can pad a cell and re-draw its noise; and anyone can create note tokens and report outcomes, so a cell of the outcomes layer can be padded in the same way.
5. THE page SHALL state the regional frame plainly (GDPR explicit consent; KVKK explicit consent; in the US Janus is not a HIPAA covered entity and follows the strictest rule set) and SHALL NOT claim certification, compliance audits or regulatory clearance; it SHALL say that Janus is a research prototype, not a medical device.
6. THE page SHALL list the data sources and their attributions shown in the app (openFDA/FAERS, TİTCK, BDPM, CIMA, Wikidata, PIPC, OnSIDES where used, Crossref/Retraction Watch, MedDRA notice).

### Requirement 22: API client, errors and version changes *(Added in refinement)*
#### Acceptance criteria
1. THE client SHALL reach the API on its own origin under `/api/…` only, with JSON bodies, `POST` for every medical, donation and loop route, a timeout on every call, and no retry of a write (`POST /contributions`, `/contributions/deletions`, `/outcomes`, `/notes/withdraw`) unless the user asks.
2. THE client SHALL validate every response against the contract of design §5 before showing it; IF a response does not match THEN THE client SHALL show a generic error and SHALL NOT show partial medical content.
3. WHEN `POST /cascades/evaluate` or `POST /notes/document` answers 409 `dataset_version_mismatch` THE client SHALL re-resolve every item from its source key, replace an item only when the new resolution gives exactly one equivalent candidate (design DP20), keep its start month, box name and still-valid choices, ask the user to confirm every other item, and then evaluate once more; it SHALL never evaluate items of two dataset versions together.
4. EVERY error code of the routes the client calls SHALL map to a message in the interface language; an unknown code SHALL map to a generic message; 422 bodies name fields only and SHALL never be shown raw.
5. A network failure or timeout SHALL be shown as "cannot reach Janus" with a retry; medical results SHALL never be served from a cache (the service worker does not cache `/api`).

### Requirement 23: Privacy of client traffic *(Added in refinement; owner decisions 3, 4, 6)*
#### Acceptance criteria
1. THE client SHALL never send to the server: an image or recognised text as a whole, a box name, an ATC code, AI (21) or (10) or their values, the note token outside a JSON body, a device identifier, or any personal data.
2. EVERY request body SHALL hold only the fields of its route's request model (design §5.1); the only free text sent is a search query the user typed or chose (Requirement 11.2).
3. THE client SHALL compute no medical result: no cascade, timing, ratio, assessment, statistic or integrity verdict; it SHALL only show what the API returned and word its codes.
4. THE client SHALL send no request to any origin but its own; fonts, OCR language data and WebAssembly files SHALL be served from the Janus origin.

### Requirement 24: Researcher area shell *(Added in refinement; owner decision 8)*
#### Acceptance criteria
1. THE researcher area SHALL be reachable from the main navigation ("Research"), SHALL use the normal theme (DP48), and SHALL NOT be a step of the patient flow.
2. THE area SHALL have four entries: hypothesis cards, the séance view (Glass: evidence summary), the retrospective-validation report and dataset export; in Phase 3 each SHALL show an honest empty state ("coming in Phase 4") and SHALL show no example result, number or hypothesis. **[Phase 4]** for the content.
3. THE area SHALL say that repurposing outputs will be researcher-facing "candidates worth investigating — not treatments" (`medical-safety.md` rule 7) and SHALL carry the disclaimer.

### Requirement 25: Performance *(Added in refinement)*
#### Acceptance criteria
1. THE doctor QR page SHALL show the form (form texts visible and controls usable) within 3 seconds on a phone profile with 4G throttling (design §16), including the `POST /outcomes/form` round trip on a local API; measured by an automated check.
2. EACH route's JavaScript sent before interaction SHALL stay within the budget of design §16, measured on the production build by a script; the barcode, OCR and PDF code SHALL load only when used.
3. A 15-item list SHALL show its findings within 2 seconds of the evaluation response on the dev machine (rendering only).

### Requirement 26: Passport seam *(Added in refinement)*
#### Acceptance criteria
1. THE list store of this spec SHALL keep, per item, the region, the country when known, the source and its date, and the ingredient keys with their ATC codes, so that the `medication-passport` spec can compute duplicate-ingredient flags and equivalents without another store. **[Passport spec]**
2. THE item view and the list view SHALL expose the slots of design §15 for Passport components; THE shell, the theme and the shared components SHALL be used by the Passport screens unchanged.
3. THE client SHALL send the list's distinct ingredient keys to `POST /memory/combination` and `POST /memory/regions` in any order; ingredient order and duplicates in the list SHALL change nothing (`medication-passport` open item).

### Requirement 27: Desktop layout *(Owner decision 2026-11-08)*
**User story:** As a visitor on a laptop, I want Janus to be a real website, not a phone column in the middle of the screen.

#### Acceptance criteria
1. Below 768 px THE client SHALL use the phone layout with the bottom tab bar. From 768 px THE navigation SHALL move into the header (Scan, Medicines, Results, Settings and Research in both themes, DP48) with the language and theme controls on the right; from 768 to 1023 px the content stays one column.
2. From 1024 px THE results screen SHALL use two columns within about 1,120 px: the findings on the left (wider) and a sticky aside with "Medicines checked", "What Janus checked", the timeline summary and the primary actions (doctor note, reports for the whole list). Reading text SHALL stay within 72 characters per line.
3. From 1024 px THE medicines list SHALL show the timeline beside it; Collective Memory SHALL place panels side by side where it helps; the note preview SHALL show the paper page centred at A4-like proportions with the actions in an aside; Settings SHALL be a two-column page.
4. THE home page SHALL be a website home: the emergency notice first, a hero with the product sentence (no forbidden or "first" claims), "Try the demo" as the main action, "How it works" in three steps, the three regions and five languages, privacy in one sentence and the disclaimer. The hero is a theme scene (6).
5. Axe (WCAG 2.2 A/AA) and no horizontal scroll SHALL hold at 1280 px as at 375 px; screenshots at 1280 and 1440 px are reviewed for home, results, memory, note and settings in both themes.
6. *(Owner decision 2026-11-08, second)* THE themes SHALL be named Night Pharmacy (default, was Two Faces) and Glass Janus (was Glass) in all five languages. THE Night Pharmacy home SHALL be a scene: the night pharmacy diorama with code-made ghosts rising from its windows, a door transition video played on "Step inside" (Req 27.9), and the medicine cabinet where the ghosts line up as the Istanbul demo's findings (each a keyboard-focusable button with an accessible name that opens the finding in the demo) and the note becomes "Prepare the doctor note". THE Glass Janus home SHALL show the glass head full-bleed with a light sweep, capsule highlights and a gentle tilt, without ghosts. The hero SHALL fill the first viewport, with the emergency notice as a one-line expandable bar on it (Req 1.2 still holds). Headline, sub-headline and actions SHALL be real translated text over a scrim (contrast ≥ 4.5:1); images SHALL have alt text in five languages; the video SHALL be decorative.
7. *(Changed 2026-11-08, third, DP49.)* WHEN reduced motion is requested, Save-Data is on, the connection is slow or the video cannot play, "Step inside" SHALL cross-fade straight to the medicine cabinet (scene 3) with still ghosts, without parallax or drift, and THE home SHALL NOT request the video.
8. THE hero SHALL not shift the layout; the active theme's first image SHALL be preloaded at the right size and the other theme's never requested; the video SHALL load lazily; the hero motion SHALL be its own chunk; LCP on a throttled desktop SHALL be measured and recorded (target < 2.5 s).

9. *(Owner decision 2026-11-08, third, DP49.)* No part of the home SHALL be driven by scroll: no pinned or sticky section, no scroll listener doing per-frame work. Below the hero copy a "Step inside" button (play icon, with a small animated scroll-down cue under it that does the same) SHALL play the door transition once, full-bleed, at normal speed, with a Skip control; at its end (or on Skip) the home SHALL cross-fade into the medicine cabinet (scene 3) and move focus to the scene 3 heading; scene 3 SHALL offer Replay. THE video SHALL be preloaded only once the page is idle, with a poster while it loads; if it cannot play, the home SHALL go straight to scene 3. Ambient motion (ghosts, fireflies, light sweep) SHALL animate transform and opacity only and SHALL pause while off-screen or while the tab is hidden. Scrolling the home at 1440 px and 375 px SHALL show no long task over 50 ms (measured, design §16).
10. *(Owner review 2026-11-08, third, DP49.)* THE Glass Janus colour fields SHALL stay fixed to the viewport on pages of any length; THE desktop hero ghosts of Night Pharmacy SHALL be about 25 % larger with a slightly stronger glow than in the first build, still subtle.

### Requirement 28: Wording decisions of the review *(Owner decision 2026-11-08)*
**User story:** As a patient or a doctor, I want the wording to say no more than the data support, so that a timing class is not read as a verdict and a consent text does not understate.
1. THE finding chip SHALL describe the order from the timing ("Order fits the pattern", "Order fits, later than the usual window", "Order not confirmed") in every language, and the doctor note SHALL print the same wording for each finding; the engine codes stay `probable` / `possible` and are not shown.
2. WHEN the order of the two medicines is not known (`same_month`, `date_unknown`) THE card SHALL name them by role ("First medicine of the pattern … Second …"), never with "then".
3. THE outcome-loop and donation consent texts SHALL be version `2026-11-v2`; the donation SHALL be described as "a donated report, without your name or contact details", and no user-facing text SHALL call donated data anonymous.
4. EACH language SHALL use one word for a report (EN report, TR bildirim, DE Meldung, FR signalement, ES notificación) across the app, Collective Memory and the note.
5. THE caveats `spontaneous_reporting`, `not_incidence` and the weak-pattern label SHALL be visible without expanding wherever report counts are shown.
6. THE note screen SHALL show the emergency notice first when the note has a safety section, and Print SHALL produce the PDF (disclaimer, demo label and page numbers on every page).

### Requirement 29: Card design *(Owner request 2026-11-09, enhancement item 1)*
**User story:** As a patient on a phone or a laptop, I want the screens to read like a calm, well-made health app (grouped rounded cards, one clear title, the key number large), so that I find what matters without reading every sentence, while every required sentence is still there.

#### Acceptance criteria
1. THE client SHALL provide shared card primitives in `src/components/cards/` (large title, inset grouped list with rows, summary card, stat tile, disclosure, segmented control) built on the design tokens only, used by the results, finding detail, evidence, FAERS pair, passport list and item, Collective Memory, research, light-face (hypotheses, validation, export) and séance screens; the home scenes and the note paper SHALL NOT change.
2. EACH of those screens SHALL start with one large title (`h1`); WHERE a screen has a one-line summary of its data (results: the finding count and the medicines checked, fully and partly counted separately, owner decision 2026-11-09, DP57; passport list: medicines and boxes; passport item: "Listed in n of m countries"; Collective Memory: the number of active ingredients), THE summary SHALL be one line of text under the title.
3. WHEN items of the same kind are listed (medicines checked, sources, countries, regions, cited evidence, rules not checked), THE client SHALL show them as an inset grouped list: one rounded surface per group, rows of at least 44 px separated by hairlines inset from the leading edge, an optional section header above the group and an optional footer under it.
4. WHERE a number is the main fact of a card (reports of a pair, report count of the combination, sources of the integrity line, patterns checked, hypothesis cards of a condition, witnesses of a séance pair), THE client SHALL show it as a stat tile (large tabular figure with a short label); THE full sentence with the same number SHALL stay in the accessible name of the tile, and SHALL stay visible as secondary text where a requirement names it (the integrity line, Req 15.2; the visible caveats, Req 28.5).
5. THE ratio confidence-interval bar SHALL keep its axis, the mark at 1, the range and the point estimate with the same numbers as text (Req 16.6) and SHALL use neutral colours only.
6. WHEN detail is folded, THE client SHALL use one disclosure component built on `<details>`/`<summary>` (keyboard and screen-reader semantics of the platform, content in the document while closed) with a chevron and a short opening animation of opacity and transform only; under `prefers-reduced-motion: reduce` it SHALL open without animation.
7. WHERE the person chooses one of a few views or filters (Collective Memory panels, passport item countries or comparison, hypothesis conditions, séance conditions), THE client SHALL use a segmented control with radio-group semantics (native radio inputs, arrow keys move the choice, visible focus, 44 px targets); the Collective Memory filter SHALL default to all panels (everything shown before this requirement); a view switch (passport item) SHALL keep the attribution line of every row in each view.
8. WHEN the person moves to another route inside the app, THE main content SHALL enter with a short animation of opacity and transform only (no layout property); the first page load and `prefers-reduced-motion: reduce` SHALL have no animation.
9. THE spacing scale, radii (card, group, tile, segment) and motion durations SHALL be tokens in `src/theme/tokens.css` used through Tailwind, with values per theme (Night Pharmacy, Glass Janus light and dark, reduced transparency); no new colour pair SHALL be introduced without the contrast test (Req 3.1).
10. EVERY required sentence SHALL stay where it was required: the disclaimer, the emergency notice first, safety lines, abrupt-stop lines, "This may be worth discussing with your doctor", the integrity line, the caveats `spontaneous_reporting` and `not_incidence` and the weak-pattern label visible without expanding wherever counts are shown, attribution and source lines, the demo label and the rule-7 labels. No assessment SHALL appear in a list, row header, tile or segment; `--risk` SHALL stay limited to real risk (Req 16.5, 16.7, design.md).
11. THE desktop layouts of Req 27 SHALL stay; at 1440 px the finding detail SHALL use two columns (the finding beside its evidence and reports), and every screen of this requirement SHALL pass axe, no horizontal scroll and 44 px targets at 375 px and 1280 px in both themes.

## Properties to test (PBT candidates)
- For every supported locale, every user-facing string key has a translation (no fallback keys rendered).
- For every supported locale, rendered findings contain the mandatory disclaimer and none of the forbidden phrases.
- Demo-mode items never reach contribution or outcome endpoints.
  - *(Added 2026-11-08.)* For every event key with a `safety_line`, every screen that shows the event also shows the line; no banner, badge or notification contains a PT name. (Req 7)
- *(Added.)* The outbound filter keeps exactly AI (01), (17) and (712) of any element string and nothing of (21), (10) or other AIs. (Req 10.2)
- *(Added.)* No request body contains a box name, an ATC code, an image, recognised text as a whole, or a field outside its route model. (Req 23)
- *(Added.)* The evaluation input preserves item order, sends one kind per item and valid start months, and the note's product-name slots are filled from the item with the same index. (Req 14.1, 17.4)
- *(Added.)* After a dataset change an item is replaced only by a unique equivalent candidate; otherwise the user is asked. (Req 22.3)
- *(Added.)* Every finding is in exactly one group; the abrupt-stop line appears once per warned item; `same_product` is never a finding. (Req 14)
- *(Added.)* No list view carries an assessment; every ratio has its range; layers are never combined. (Req 16)
- *(Added.)* Storage failures never break a screen; stored documents round-trip. (Req 9)
- *(Added.)* Every token pair used as text passes the contrast rule in both themes and colour schemes. (Req 3.1)
- *(Added.)* The doctor page sends the token only in a JSON body; answers satisfy the action rule. (Req 19)
- *(Added.)* Every QR address fits version 25 at level M and decodes back to itself. (Req 18.2)
- *(Added.)* Glass shows no theme-device word in any language. (Req 6.5)
- *(Added 2026-11-09.)* The passport summary never claims more listings than the sources show; card primitives keep every required sentence in the markup and outside any fold where Req 28.5 asks; every stat tile carries its sentence; the Collective Memory filter shows every panel by default. (Req 29)

## Resolved open items *(from the seed's four sections, 2026-11-07 and 2026-11-08)*
**cascade-engine (2026-11-07)**
- Evaluation call (dataset version, 1–50 items, candidate id with choices from position 0 or QID, `started`, no ATC) → 14.1, 23.1.
- Re-resolve after 409 (keep product code or name in the browser) → 14.2, 22.3.
- Form-unconfirmed findings name the matched codes; ask the user to confirm the product → 14.4.
- Wording: codes and English canonical sentences; five-language wording; not-matchable rows 27 and 57 and not-checked ingredients as "cannot be checked" → 14.6, 14.10.
- Homeopathic products → 12.9, 14.7.

**collective-memory (2026-11-08)**
- Routes (`/memory/pair`, `/combination`, `/regions`, `/shared`, `GET /memory/snapshot`; pair from the finding's locator) → 16.1, 16.2, 16.12.
- Words (`Memory` namespace; disclaimer, limits, window, attribution, MedDRA notice; reports, donated reports, doctor-confirmed outcomes) → 16.3, 16.4.
- Display rules (assessment in the detail view; ratio with interval; "over 1,000"; no ratios for `insufficient_data`/`no_reports`; separate panels) → 16.5–16.8.
- Safety lines → Requirement 7, 16.3.
- MedDRA notice (short on screen; long form in the note, NOTICE and exports) → 7.4, 16.3, 17.3.
- Regions (UNKNOWN count and share, `basis`, `adrreports_url`) → 16.9.
- Privacy page limits (two-step differencing; padding; "hidden under 20, noise added") → 21.3, 21.4.
- Errors (422 fields only; 503 `memory_unavailable`) → 16.11.

**drug-resolution Phase 2 (2026-11-08)**
- Regions (`EU`, `country`, candidate ids `EU:…`, new `matched_by` values; digits-based matches less certain) → 10.6, 11.5, 12.4.
- AI (712), never (21)/(10); `gs1_serial_not_accepted` is a client defect → 10.2, 10.4.
- Germany and countries without an open product database (`no_open_product_database`; `region_adapter_not_available`) → 12.5.
- Source attribution (BDPM, Nomenclátor) and product text as published → 2.6, 12.7.
- Status fields (`status_published`, `marketing_end_date`) → 12.8.
- Homeopathic EU products → 12.9.
- Name search by language; typed national codes not sent as codes; CIP13/EAN-13 as bare digits → 10.3, 11.4, 11.5.
- 503 for a missing EU source → 12.6.
- Status strings (French as published, Spanish machine strings worded; numeric codes to confirm) → 12.8, design open item 2.
- `atc_selection = component_code` (imipenem `J01DH51`) → 12.10.

**doctor-loop (2026-11-08)**
- Note document (`POST /notes/document`, pins, one or two languages, region, statistics region; 409 `version_mismatch`; lay out, never re-word) → 17.1–17.3.
- Product names (`product_name_slot`, filled in the browser) → 17.4, 23.1.
- Names and tags (`name_basis`, `tag`, ATC codes) → 17.5.
- Sections (safety first, form-unconfirmed section, abrupt-stop line in the row, empty sections keep headings, overflow to page 2) → 17.6, 17.7.
- QR code (opt-in, `POST /notes/token`, `qr_url`, 50 mm, version ≤ 25, level M, byte mode; token only in the fragment) → 18.1–18.3, 19.1.
- Doctor page (no account; two questions; error codes) → Requirement 19.
- Withdrawal (`POST /notes/withdraw`, same answer either way) → 18.5.
- Privacy page (outcomes padding limit until Phase 5) → 21.4.
- Reminder (4 weeks, browser only) → 18.4.
