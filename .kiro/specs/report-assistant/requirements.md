# Requirements: Report Assistant ("Prepare a report to the authority")

> Written 2026-11-09 as enhancement item 4 of 6 (owner-approved). Web only: no API route is added or
> changed and nothing is sent anywhere. Builds on `experience` (results, finding detail, medicines,
> settings, demo mode, cards system Req 29), `doctor-loop` (the doctor QR page and its demo) and
> `collective-memory` (the Janus event vocabulary). Channel facts come from
> `data/report_channels.csv`, checked on official sites on 2026-11-09.

## Introduction

Most suspected side effects are never reported to a medicines authority. A systematic review of 37
studies found a median under-reporting rate of 94 % (interquartile range 82–98 %) (Hazell & Shakir,
Drug Saf 2006;29(5):385–396). Reporting is open to patients in Türkiye (TÜFAM), the US (FDA
MedWatch Form 3500B) and the EU (each national authority), but the official forms are long and
written in the authority's own words. The Report Assistant prepares, on the device, a draft of the
facts Janus already holds (the medicine as on the box, its ingredient, the event in plain words,
when it started, the other medicines, the outcome the person chooses) and shows, field by field,
where each value goes on the chosen official form. The person copies the values into the official
form and submits it themselves. Janus never submits anything.

## Glossary

- **Channel:** one row of `data/report_channels.csv` (an online form, a PDF or Word form, an
  e-mail address, a phone line, a guidance page or a directory).
- **Verified field list:** the `fields` of the channel named in a channel's `field_source`, when its
  `fields_status` is `verified`, `derived` or `partial` (the labels that were read).
- **Draft:** the values the assistant prepares: medicine (box name and ingredient), event, onset
  month, outcome, other medicines. Held in memory only.
- **Field mapping:** for a channel, an ordered list (form order) of (draft value → native label of
  the verified field list). A draft value without a mapped field is shown under the Janus label.
- **Rule-10 event:** an event of the vocabulary with a `safety_line` (medical-safety rule 10).
- **Doctor fragment:** `#src=doctor&…` with codes only (rule id, ingredient keys), the demo flag.

## Requirements

### Requirement 1: Channel data

#### Acceptance criteria

1. THE repository SHALL hold `data/report_channels.csv` with, for every row, a channel id, region,
   country, authority, channel name, audience, kind, URL, form id and version, language, whether a
   patient may report, field status, field source, fields and required fields as published, outcome
   field and options, `source_url`, `checked_on` and notes; and `data/report_channels.meta.json`.
2. EVERY row SHALL have an `https:` URL (or `mailto:` / `tel:` for the e-mail and phone channels),
   an `https:` `source_url` and a `checked_on` date.
3. WHERE the research could not confirm an item THE row SHALL say `UNVERIFIED` and THE client SHALL
   build no field mapping, no option list and no required-field list on it.
4. THE client SHALL use a JSON generated from the CSV (`apps/web/src/report/channels.json`); a test
   SHALL fail when the JSON differs from the CSV.
5. THE CSV and the client SHALL hold no MedDRA term (DP3).

### Requirement 2: Entry points

#### Acceptance criteria

1. THE finding detail and every finding card of the results screen SHALL offer "Prepare a report to
   the authority", opening the assistant prefilled with the finding's first medicine (its items in
   the list and its ingredient) and its event.
2. THE medicines screen SHALL offer the same link without a finding; the person then chooses a
   medicine from the list and an event (from the Janus vocabulary or in their own words).
3. THE doctor page (`/o`, the doctor form) and its demo (`/demo/doctor`) SHALL offer the same link per
   finding, opening the assistant in the doctor's view prefilled from the note's codes only.
4. THE prefill SHALL travel in the URL fragment only (never a path or query), with codes and item
   positions only, never a box name, a date or free text.
5. IF the fragment is missing, malformed or names an item that is not in the list THEN THE client
   SHALL open the assistant without that prefill and SHALL NOT throw.

### Requirement 3: Region and channel

#### Acceptance criteria

1. THE assistant SHALL offer the regions Türkiye, European Union and United States, preselecting
   the user region of Settings (the demo patient's region in demo mode) and none otherwise.
2. WHEN the region is the EU THE assistant SHALL offer Germany, France, Spain and "Another EU
   country"; for another EU country it SHALL show the EMA guidance and the national authority
   finder (`eu-adr-national`) and a draft under the EMA "What to report" headings.
3. WHERE a country has more than one form channel THE assistant SHALL offer them (online first).
4. THE assistant SHALL NOT store the region, country or channel chosen (DP7).
5. THE assistant SHALL show, for the chosen channel, the authority, the channel name, the form id and
   version as recorded (UNVERIFIED when so recorded), the date the channel was checked and its source.
6. WHERE the country has e-mail or phone channels THE assistant SHALL list them with their verified
   addresses (`mailto:` / `tel:` links).

### Requirement 4: The draft

#### Acceptance criteria

1. THE draft SHALL hold: the medicine as on the box (the item's box name, editable) and its
   ingredient name (doctor-loop DP16 rule); the event in plain words (the Janus lay label of the
   vocabulary or the person's own words, editable); the onset month (or "don't know"); the outcome;
   the other medicines.
2. THE other medicines SHALL be the other items of the list (in doctor view, the other ingredients of
   the note), each with a checkbox, ticked by default; the draft SHALL contain exactly the ticked ones,
   in list order.
2a. *(Owner decision 2026-11-09, DP13.)* WHEN the form asks for prescription and over-the-counter medicines in
   separate fields (FDA 3500B E11 and E10), THE draft SHALL put an other medicine under E10 WHEN the resolver's
   product type says it is sold over the counter, under E11 WHEN it says prescription, and under E11 WHEN the type is
   unknown; THE draft SHALL then name the medicines of unknown type and say that they were put under E11 and that a
   medicine bought without a prescription belongs under E10. Forms without the split SHALL keep all other medicines
   in one field.
3. WHERE the channel's outcome options were read THE assistant SHALL offer exactly those options
   (native label with a translation); otherwise a free-text outcome.
4. THE event SHALL be in plain words: the Janus lay label or the person's text. No MedDRA term SHALL
   be shown, suggested or stored (DP3).
5. THE draft SHALL be built on the device from the list in the browser (or the demo fixture) and
   SHALL be held in memory only; nothing of it SHALL be written to storage.

### Requirement 5: Field mapping, review and copy

#### Acceptance criteria

1. THE draft SHALL be shown as rows in the chosen channel's form order: the native label as published
   (with its form section and `lang`), its translation in the interface language, and the value.
2. EVERY native label shown SHALL be in the channel's verified field list; a value with no verified
   field SHALL be shown under the Janus label with "No matching field recorded for this form".
3. WHERE the field list comes from another edition of the form (`field_source`, e.g. the 3500B
   online form uses the PDF's labels) THE assistant SHALL say so.
4. EVERY row SHALL have "Copy" and THE draft SHALL have "Copy all"; the copy-all text SHALL be the
   rows in form order, one `label: value` line each, preceded by the demo line in demo mode.
5. THE assistant SHALL list the channel's recorded required fields that the draft does not fill
   ("Fields the form asks for that Janus does not fill"), as recorded; none when UNVERIFIED.
6. THE draft SHALL be printable: a print stylesheet shows the draft, the not-sent sentence, the
   disclaimer and the demo label, and hides navigation and controls.
7. THE assistant SHALL offer "Open the official form" as an external link (`target="_blank"`,
   `rel="noopener noreferrer"`) to the channel's verified URL from the CSV.
8. IF copying fails (no clipboard permission) THEN THE assistant SHALL say so and keep the text
   selectable; it SHALL NOT throw.

### Requirement 6: Nothing is sent

#### Acceptance criteria

1. THE assistant SHALL send nothing: no request to `/api` and none to any other origin while it is
   open, in live and in demo mode (the app's own static files, such as the vocabulary chunk, excepted;
   safety audit A8).
2. THE assistant SHALL say plainly: "Janus does not send this report. You submit it yourself on the
   official form."
3. THE assistant SHALL NOT count its use (no tally, no analytics, nothing stored) (DP8).

### Requirement 7: Safety and wording

#### Acceptance criteria

1. THE emergency notice SHALL come first on the assistant (medical-safety rule 10); WHEN the event is a
   rule-10 event THE assistant SHALL also show its safety line before the draft.
2. THE texts SHALL give no advice, SHALL NOT say the person should or must report, and SHALL say that
   reporting a suspicion is the person's own choice and that a report is a suspicion, not a proof that
   the medicine caused the event.
3. THE under-reporting fact SHALL be shown with its citation and its uncertainty (median across 37
   studies, interquartile range), worded as a fact about reports, not as pressure.
4. THE forbidden phrases of medical-safety rule 2 SHALL NOT appear in any of the five languages; Glass
   Janus SHALL use no theme-device word.
5. THE disclaimer of rule 9 SHALL be on the screen and in the printed draft.

### Requirement 8: Doctor view

#### Acceptance criteria

1. THE doctor link SHALL carry codes only (rule id, the finding's first-medicine ingredient key, the
   other ingredient keys of the note, the demo flag); the doctor page SHALL stay stateless (it stores
   nothing and sends nothing new).
2. THE assistant SHALL name ingredients and the event through the vocabulary (ingredient name rule,
   `eventKeyForRule`); without a box name, the medicine is the ingredient name, editable.
3. WHERE the research shows a separate health-professional route THE assistant SHALL say so, linking
   only verified URLs: TÜFAM (the e-form takes health-professional reports; the separate
   health-professional form is named, its address not linked); FDA (Form 3500 is for health
   professionals, the MedWatch forms page is linked); and SHALL use a channel's field mapping only
   when its audience includes health professionals (otherwise Janus labels only).

### Requirement 9: Demo mode

#### Acceptance criteria

1. IN demo mode (a demo patient, or the doctor demo fragment) THE assistant SHALL work offline from the
   demo patient's data and SHALL show the "Demo · synthetic patient" label.
2. THE draft SHALL carry "Demo · synthetic patient — do not submit" on screen, in the copy-all text
   and in print, if and only if it is a demo.

### Requirement 10: Quality

#### Acceptance criteria

1. Texts in a new `ReportAssistant` namespace in five languages, each language's word for a report
   (EN report, TR bildirim, DE Meldung, FR signalement, ES notificación).
2. Axe (WCAG 2.2 A/AA), no horizontal scroll and 44 px targets at 375 and 1280 px in both themes;
   loading, empty (no medicine in the list), error (vocabulary not loaded) and long-content states.
3. Reviews: safety-auditor, pharmacologist, statistician (the under-reporting sentence) and
   localization-reviewer, each in its own file in this folder; findings applied.
4. Pre-launch checklist lines: legal review per region, re-verification cadence with dates, the
   UNVERIFIED items, the MedDRA decision.
