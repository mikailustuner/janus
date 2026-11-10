# Requirements: Medicine information in your own language

> Owner request 2026-11-10. A new bounded area: `apps/api/janus/plaininfo/`, the `us_labels` pipeline job, and one
> page in `apps/web` reached from each row of the medicine list. It reads one new source (the "Indications and
> Usage" section of US drug labels, openFDA, CC0 1.0) and three existing artifacts (`eu_fr_bdpm`, `eu_es_cima`, the
> abrupt-stop list). It changes no cascade, memory or resolution logic.

## Introduction
A person holds a box they cannot read: a migrant with a box from the new country, a traveller, a carer of a
relative who brought medicines from abroad. For a medicine on the list Janus shows one short page, in the
interface language (en, tr, de, fr, es), that says

1. which ingredient(s) the medicine contains, by the reviewed name of that language;
2. what the **group** of medicines the ingredient belongs to is used for, in one or two fixed sentences;
3. what the official source says: for a US product the "Indications and Usage" section of its label as published,
   in English, marked as a quotation that is not translated; for a French or Spanish product a link to the
   product's page in the national database (BDPM, CIMA), in French or Spanish.

Janus has no language model at run time and none is added. No text is generated and no label text is translated
by a machine: a clinical text that experts have not translated must not be presented as a translation. The group
sentences are written once, in five languages, for a short list of ATC groups for which a statement at group level
is true of the whole group. The page never gives a dose, never says how to take a medicine and never says that a
medicine is right for the person; it sends the person to a pharmacist or doctor.

No health professional has reviewed the wording. Every group sentence is shown with that status.

## Glossary
- **Covered group:** a row of `apps/api/janus/plaininfo/groups.csv`: an id, one or more ATC prefixes, single
  excluded codes, a group name and a use text in five languages, a review status.
- **Group sentence:** the use text of a covered group in one language. It always starts "Medicines in this group".
- **Ingredient codes:** the ingredient-level ATC codes (seven characters) that drug resolution gives one ingredient
  of a list item; for a product they are already selected by route.
- **Ingredient status:** `single` (every code of the ingredient is in the same covered group), `mixed` (at least
  one code is in a covered group, and the codes fall in more than one group or some fall in none), `none`.
- **Official text:** the paragraphs of `indications_and_usage` of one US label (SPL set id), as openFDA publishes
  them.
- **Product page:** the address of a product in BDPM (by CIS code) or CIMA (by registration number).
- **Review status:** `not_reviewed` or `expert_reviewed`, per covered group. Today every row is `not_reviewed`.

## Requirements

### Requirement 1: No generated or machine-translated clinical text
1. THE API and the web app SHALL NOT call a language model or a translation service for this feature, and SHALL
   NOT build a clinical sentence from parts at run time.
2. A group sentence SHALL be shown only as a whole text of `groups.csv`, in the asked language.
3. THE official text SHALL be shown only in the language it is published in, unchanged, marked as a quotation,
   with its language named and the words "not translated".
4. WHEN the official text is longer than the limit, THE shown text SHALL be a prefix of the published text, cut
   between paragraphs where possible, and SHALL be flagged as cut with a link to the full label.

### Requirement 2: Covered groups (pure)
1. THE table SHALL list every covered group with its ATC prefixes and excluded codes; an ATC code SHALL belong to
   at most one group (no prefix repeats or contains another).
2. A group sentence SHALL be returned for an ingredient IF AND ONLY IF at least one of its ingredient codes falls
   under a prefix of that group and is not excluded; the matched codes SHALL be returned and SHALL be a subset of
   the codes asked.
3. WHEN the codes of one ingredient fall in more than one covered group, or some fall in none, THE status SHALL be
   `mixed` and the page SHALL say that the ingredient is in more than one kind of medicine and that Janus cannot
   tell which one this medicine is; `other_uses` SHALL be true exactly when some code is in no covered group.
4. THE answer SHALL NOT depend on the order or repetition of the codes.
5. THE loader SHALL refuse the table when a text is empty or longer than 400 characters, when a use text
   contains a digit or does not end with a full stop, when any text contains a forbidden phrase, a reassurance
   word (medical-safety rules 2 and 3) or the word "AI" (or its equivalent abbreviation), when an id, a prefix or an
   excluded code is malformed or repeated, or when a status is unknown.
6. EVERY group SHALL have a name and a use text in all five languages.

### Requirement 3: Official text and product page
1. THE source SHALL be recorded in `pipelines/sources.toml` as `openfda_label_indications` (CC0 1.0, the FDA credit
   line, "Not an FDA endorsement", openFDA's statement that the labeling is neither altered nor verified by FDA and
   may differ from the labeling on distributed products), region US, storage `cache`, weekly cadence; NOTICE SHALL be
   generated from it and `.kiro/steering/data-sources.md` SHALL list it.
2. THE pipeline `us_labels` SHALL write one row per label that names at least one product NDC, whose link to the
   NDC directory names the label's own set id, whose product type is a human prescription or OTC drug, whose
   application numbers are all NDA, ANDA or BLA numbers, and that has a non-empty indications section; every other
   label SHALL be excluded with a reason and counted. The paragraphs SHALL be kept exactly as published. No other
   section of the label SHALL be carried.
3. WHEN the number of label records read differs from the number the download index lists, THE run SHALL fail.
4. THE API SHALL return the official text for a US product code IF AND ONLY IF exactly one label of the current
   run names that product code; WHEN several labels name it, THE API SHALL return none and say so
   (`several_labels`).
5. THE API SHALL return a product page for a French or Spanish product IF AND ONLY IF exactly one CIS code or one
   registration number of the current run carries the product name exactly as published.
6. THE answer SHALL carry the source id, run id, data date and licence of the run it was read from, the label's
   set id, version and effective date, and a link to the full label at DailyMed.
7. WHEN no run is installed, THE API SHALL still answer the group sentences and SHALL report
   `source_unavailable` for the official part.

### Requirement 4: API route
1. `POST /medicine-info` SHALL be a medical route (no-store; nothing of the body logged or stored) and SHALL be
   read-only and stateless.
2. THE body SHALL be validated: `language` one of the five; `ingredients` a list of at most 12 entries, each
   with at most 20 ingredient-level ATC codes; `product` optional, with `country` US and an NDC, or `country` FR or
   ES and a product name of at most 300 characters; no other field.
3. A refused body SHALL get 422 with fixed field names and SHALL never echo input; an NDC that is malformed or
   ambiguous (ten plain digits) SHALL get 422 `ndc_malformed`.
4. WHEN the group table or the abrupt-stop list cannot be loaded, THE route SHALL answer 503
   `medicine_info_unavailable`: a group sentence is never served without the abrupt-stop flag.
5. THE answer SHALL carry, per ingredient in request order: the status, the groups (id, name, sentence, matched
   codes, review status), `other_uses` and `abrupt_stop`; the official part with its status; fixed notice codes;
   the disclaimer.
6. `abrupt_stop` SHALL be true IF AND ONLY IF a code of the ingredient is on the abrupt-stop list of the cascade
   rule base (`data/abrupt_stop_classes.csv`), whether or not the code is in a covered group.
7. WHEN the label data is older than twice its cadence, THE answer SHALL carry `snapshot_outdated`.

### Requirement 5: Page
1. EVERY row of the medicine list SHALL link to the page of that medicine (`/medicines/info#<item id>`; the id is
   in the URL fragment and reaches no server).
2. THE page SHALL show, in the interface language: the emergency notice first; the box name; per ingredient the
   sentence "This medicine contains …" with the name by the vocabulary's rule (reviewed name, else the English
   name tagged as not translated or not reviewed); the group name, its ATC code(s) and the group sentence; the
   abrupt-stop line when the flag is set; the three fixed sentences (group, not the person; no dose and no
   instructions; ask a pharmacist or doctor); the official part.
3. EVERY group sentence SHALL be shown with "Expert review has not yet been done." (the text of
   `TimeMachine.review` in each language) and with the statement that the sentence is a fixed text chosen
   automatically by the medicine's ATC code. The words "AI" and "reviewed by" SHALL NOT appear.
4. THE official text SHALL be rendered as a quotation with `lang="en"`, its heading SHALL name the country, the
   language and "not translated", and the notes SHALL say that the company that markets the product wrote the text,
   that FDA has not verified it, and that it may differ from the text in the box.
5. A product page link SHALL say the language of the page, that Janus found it by the product's name, and ask the
   person to compare the name on the page with the box.
6. WHEN no ingredient has a group sentence and there is no official text or page, THE page SHALL show a clear
   "no information for this medicine" state that says this is no statement about the medicine.
7. THE page SHALL have loading, error (with retry), item-not-found and long-content states, SHALL work at 375 px
   and 1280 px in both themes and in large-text mode, SHALL meet WCAG 2.2 AA (axe), and SHALL use `--risk` only in
   the emergency notice.
8. THE request SHALL carry only the language, the ingredient codes, and for a US product its NDC or for a French
   or Spanish product its published name; never the box name the person typed, the lot, the start month or the
   item id. In demo mode THE request SHALL carry no product (the demo products are invented).
9. An ingredient that drug resolution could not check (unmapped, ambiguous without a choice, homeopathic) SHALL
   be shown with its reason and SHALL NOT be asked about; a homeopathic product SHALL NOT be asked for an official
   text.

### Requirement 6: Safety and language
1. NO text of this feature, in any language, SHALL name a dose, a frequency or a way of taking a medicine, say
   that a medicine is safe, right or suitable for the person, or advise starting, stopping or changing one.
2. THE forbidden-phrase and reassurance lists SHALL hold for every catalogue text and every group text in five
   languages, checked by tests in the API and the web app.
3. EVERY locale SHALL have every key of the feature with the same parameters.
4. Reviews by the safety-auditor and localization-reviewer agents SHALL be recorded as automated read-only passes.
   Expert review has not yet been done.
