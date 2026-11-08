# Requirements: Medication Passport (cross-border list)

> Refined 2026-11-08 from the draft seed (spec author standing in for the Kiro spec workflow). Every criterion and
> property of the seed is kept; refinements are marked *(Refined)*, new criteria *(Added in refinement)*.
> **Scope:** the server endpoint for equivalent presence (`apps/api/janus/passport/`, one index migration, two additive
> fields in the resolution response), the pure list logic in the browser (merge, duplicate detection, request builder)
> and the content and states of the Passport screens.
> **Seam with `experience` (written in parallel):** `experience` owns the app shell, navigation and routes, the themes,
> the shared components (cards, chips, notices, disclaimer, demo label, emergency notice), the browser storage of the
> medicine list and the scan/search flow. This spec owns what the Passport screens say and show, the states they
> handle, the pure functions they call and the API they call. Criteria tagged **[Client: experience spec]** are built
> there.
> **Seam with `doctor-loop`:** the note is built by `POST /notes/document`; this spec only fills the browser-side slots
> (Requirement 3). **Seam with `drug-resolution`:** this spec reads its tables and adds two optional output fields
> (Requirement 6.6); it changes no resolution behaviour.
> Data facts used below were measured on the dev dataset `7db3a513…` (sources TİTCK 2026-11-06, openFDA NDC
> 2026-11-06, BDPM 2026-11-03, Nomenclátor 2026-11-07); see `design.md` §1.

## Introduction
Many families live across borders (for example Turkish families in Germany), and travellers carry boxes from two countries. One person's medicine list often mixes products from Türkiye, the EU and the US under different brand names. The Passport merges them into one ingredient-level list, shows the equivalent ingredient's presence in the other regions, and lets the doctor note be written in the doctor's language. It informs; it never recommends switching products.

## Glossary
- **Ingredient key:** shared cross-region identity (Wikidata item with ATC and RxCUI) from Drug Resolution.
  - *(Refined.)* A Wikidata item id `Q…` or a curated Janus key `J<n>` (`data/janus_ingredients.csv`), pattern
    `^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$`, the same key `drug-resolution` returns for a `mapped` ingredient.
- **Equivalent presence:** whether a product with the same ingredient (and, where known, the same strength and dose form) exists in a region's source data.
  - *(Refined.)* Answered per list item and per source: whether the source lists a product whose `mapped` ingredient
    keys are exactly the item's keys. "Equivalent" is an internal term; user-facing text says "same active ingredient"
    and never "equivalent" (Requirement 8).
- *(Added.)* **Item:** one entry of the browser list: one box, vial or typed medicine, with its origin (region and,
  for the EU, country), its source and source date, its ingredient keys, optional strength and dose-form codes, the
  homeopathic flag, a box count and the name as on the box (browser only).
- *(Added.)* **Checked item:** an item that has at least one ingredient key and is not homeopathic.
- *(Added.)* **Source:** one product database of the resolution dataset: `titck` (TR), `openfda_ndc` (US),
  `eu_fr_bdpm` (EU, France), `eu_es_cima` (EU, Spain). Germany (EU) has no open product database.
- *(Added.)* **Strength code:** a normalised strength: an amount (decimal), a unit (`ug` for mass, `IU`) and a basis
  (`unit`, `mL`, `g`). **Dose-form group:** a code from the curated Janus table `data/dose_form_groups.csv`.
- *(Added.)* **Presence status:** `present`, `not_present`, `not_in_source`, `source_unavailable` (Requirement 2.4).
  **Comparison result:** `matched`, `differs`, `could_not_compare` (Requirement 6).

## Requirements

### Requirement 1: Mixed-region list
**User story:** As a caregiver whose mother brings medicines from Türkiye to Germany, I want all boxes in one list so that nothing is missed.

#### Acceptance criteria
1. THE client SHALL accept items from different regions in one list and SHALL show each item's region and source.
   - *(Refined.)* THE client SHALL show for each item its origin (Türkiye, France, Spain, Germany, United States or
     "other"), the source name and its snapshot date, or "entered by name" for an item typed by name; for Germany it
     SHALL say that there is no open product database and the item was identified by name.
2. WHEN two items share an ingredient key THE system SHALL flag a possible duplicate ingredient ("same active ingredient under two names") and keep both items visible.
   - *(Refined.)* THE flag SHALL be computed in the browser over checked items only; a combination product shares a key
     with a single-ingredient product when one of its keys is that product's key. THE flag SHALL name the shared
     ingredient and every item that carries it.
3. Duplicate-ingredient flags SHALL be informational and SHALL NOT recommend removing an item.
   - *(Refined.)* THE flag's wording SHALL contain no word of the removal list (`design.md` §7.3) in any of the five
     languages and SHALL end with the allowed framing "This may be worth mentioning to your doctor or pharmacist."
4. *(Added in refinement.)* WHEN the same box is added twice THE client SHALL keep one item and increase its box
   count; WHEN two lists are merged THE result SHALL not depend on the order in which items or lists were added.
   Item identity is defined in `design.md` §6.2. WHEN two identical items differ in start month THE earlier known month
   SHALL be kept.
5. *(Added in refinement.)* WHEN an item is homeopathic (`drug-resolution` Req 11.1) THE client SHALL show
   "homeopathic product, not checked", SHALL leave it out of duplicate flags and SHALL NOT send it to the presence
   endpoint.
6. *(Added in refinement.)* WHEN an item has no ingredient key (every ingredient `unmapped` or `ambiguous`) THE client
   SHALL show "cannot be checked" with the reason and SHALL leave it out of duplicate flags and presence requests.
7. *(Added in refinement.)* THE user SHALL be able to remove an item from the list through the list's own controls
   **[Client: experience spec]**; no Passport text SHALL prompt this action.

### Requirement 2: Equivalents
#### Acceptance criteria
1. WHEN the user opens an item THE system SHALL show, for each other region, whether the ingredient is present in that region's source data, with the source and version date.
   - *(Refined.)* THE detail view SHALL show one row per source in the fixed order TR, EU-FR, EU-ES, EU-DE, US; the row
     of the item's own source SHALL be marked "this box's source" and shown last. Every row SHALL name the source and
     its snapshot date (Requirement 7).
2. WHEN strength and dose form are known in both sources THE system SHALL show whether they match; otherwise it SHALL say they could not be compared.
   - *(Refined.)* The comparison rules are Requirement 6.
3. THE system SHALL NOT present any product as interchangeable or recommend a substitute.
   - *(Refined.)* THE presence answer SHALL contain counts and codes only: no product name, product id, candidate id,
     package code or price of any product in another source (`design.md` DP3).
4. *(Added in refinement.)* THE presence status of an item in a loaded source SHALL be:
   `present` WHEN the source lists at least one non-homeopathic product whose `mapped` ingredient keys equal the item's
   keys and which has no `unmapped` or `ambiguous` ingredient; `not_present` WHEN no such product exists but at least
   one of the item's keys is a `mapped` ingredient of some non-homeopathic product of the source (the answer SHALL
   say how many products contain all the item's keys together with other ingredients, and which of the item's keys
   occur); `not_in_source` WHEN none of the item's keys is a `mapped` ingredient of any non-homeopathic product of the
   source. For a source that is not loaded, or for Germany, the status SHALL be `source_unavailable` with the reason
   `not_loaded` or `no_open_product_database`.
5. *(Added in refinement.)* `not_present` and `not_in_source` SHALL be worded as statements about the source data, never
   as "not available in <country>": the source may list a product under an ingredient name Janus could not map, and
   a product may be on the market without being in the file.
6. *(Added in refinement.)* Homeopathic products of a source SHALL NOT count towards any status or comparison; THE
   answer SHALL give their number (`homeopathic_left_out`) so the client can say that they were not checked.
7. *(Added in refinement.)* WHEN a key is not an ingredient of the current resolution dataset THE answer SHALL list it
   in `unknown_keys` and the status SHALL be computed without it matching any product.

### Requirement 3: Language of care
#### Acceptance criteria
1. THE user SHALL choose the doctor's language (EN, TR, DE, FR, ES) independently of the interface language (see Doctor Note spec).
   - *(Refined.)* THE Passport SHALL hand the merged list to the note flow of `doctor-loop` (`POST /notes/document`
     with the evaluation items of the merged list) with the doctor's language first and the interface language second;
     it adds no server field.
2. Ingredient names in the note SHALL be shown as INN plus the brand name exactly as on the patient's box.
   - *(Refined.)* THE INN comes from the reviewed glossary on the server (`doctor-loop` §5.7); THE client SHALL fill each
     row's `product_name_slot` with the name as on the box and the item's origin label (`Passport.origin.<country>` in
     the note language, for example "box from Türkiye"); neither SHALL reach the server. The PDF layout is
     **[Client: experience spec]**.

### Requirement 4: Presence API *(Added in refinement)*
#### Acceptance criteria
1. THE API SHALL offer `POST /passport/presence` with a JSON body, registered as a `medical` route
   (`janus/http_policy/routes.py`): `Cache-Control: no-store`, JSON bodies only, the 64 KiB body limit, the access
   line as the only log record.
2. THE endpoint SHALL be stateless: it SHALL run one read-only transaction (`read_only_tx`, REPEATABLE READ, READ ONLY)
   and SHALL write nothing to the database, the file system or a cache keyed by request content.
3. THE request SHALL hold only ingredient keys and, per ingredient, an optional strength code and, per item, an
   optional dose-form group; it SHALL accept no product name, product code, candidate id, region of the item, free
   text, date or `demo` field (strict model, `extra="forbid"`).
4. THE response SHALL hold the resolution `dataset_version`, the dose-form table version, one source block per source
   (Requirement 7), one answer per item in request order with one entry per source, the notices and the rule-9
   disclaimer. Item answers SHALL list the item's keys sorted; key order within an item and the order of items SHALL
   not change any answer.
5. THE response SHALL contain codes and numbers only; the five-language wording is in the client (Requirement 8).

### Requirement 5: Input validation and errors *(Added in refinement)*
#### Acceptance criteria
1. THE request SHALL hold 1 to 50 items; each item 1 to 10 ingredients with distinct keys; at most 50 distinct keys over
   the whole request. A strength code SHALL have an amount matching `^(0|[1-9][0-9]{0,8})(\.[0-9]{0,5}[1-9])?$` greater
   than 0, a unit `ug` or `IU` and a basis `unit`, `mL` or `g`; a dose-form group SHALL be one of the codes of the
   loaded table.
2. IF the body is not JSON, or violates Requirement 5.1 or 4.3 THEN THE API SHALL answer 422
   `{"error": "invalid_request", "fields": [...]}` naming field paths only, never echoing a value.
3. IF there is no database, no current resolution dataset, the dose-form table did not load, or the statement exceeds
   its time limit (3 s) THEN THE API SHALL answer 503 `{"error": "passport_unavailable"}` with no partial answer.
4. A source missing from the current dataset SHALL NOT cause a 503: its block and entries say `source_unavailable` /
   `not_loaded` and the other sources are answered.

### Requirement 6: Strength and dose-form comparison *(Added in refinement)*
#### Acceptance criteria
1. THE system SHALL assert `matched` only when the item's value and the source product's value are both known and
   comparable; this is the seed property "never assert a match when either side is unknown".
2. THE comparison SHALL be given only for status `present`, over the products counted there, as three results:
   `strength` (every ingredient's strength code equal), `dose_form` (same dose-form group) and
   `strength_and_dose_form` (one product with both). Each result SHALL be `matched` WHEN at least one product is
   comparable and equal; `differs` WHEN every counted product is comparable and none is equal; otherwise
   `could_not_compare` with a reason (`not_known_for_item`, `not_known_in_source`, `not_all_comparable`). Each result
   SHALL carry the numbers of comparable and of equal products.
3. Strength codes SHALL be compared after exact unit conversion (mass in micrograms, IU separately, never mass against
   IU) and only on the same basis (`unit`, `mL`, `g`); there SHALL be no tolerance. THE wording of `differs` SHALL say
   that sources may state the amount of a salt or of the base, so a difference in listed strength is not proof of a
   different dose.
4. THE system SHALL use the strength and dose-form data as they exist in the dataset and SHALL say where they are
   missing. On 2026-11-08:
   - TİTCK: no strength and no dose form are stored (strength and form appear only inside the product name and are not
     parsed): never comparable.
   - openFDA NDC: strength per ingredient with a denominator (`5 mg/1`, `250 mg/5mL`, homeopathic `[hp_X]` units) and a
     dose form (142 SPL form names): comparable where parsed and mapped.
   - BDPM: strength per ingredient without its reference quantity (`5 mg`; the "per one tablet" or "per 100 ml" part is
     not loaded) and a pharmaceutical form (358 French strings): strength comparable only when the form group is a
     countable unit form; form comparable where mapped.
   - Nomenclátor (CIMA): strength per ingredient (`dosis_pa` + `unidad_dosis_pa`, `500 mg`), no dose form loaded and no
     route loaded: strength basis unknown, so never comparable; form never comparable.
5. THE dose-form groups SHALL come from the curated, reviewed table `data/dose_form_groups.csv` (Janus, Apache-2.0)
   that maps each published form string of each source to a group or to nothing; an unmapped form SHALL count as
   unknown. Modified-release forms SHALL be separate groups from immediate-release forms.
6. THE resolution response SHALL gain two optional fields computed by the Passport's pure functions from the stored
   values: `ResolvedIngredient.strength_code` and `ProductCandidate.dose_form_group` (null when unknown). Existing
   fields and behaviour SHALL be unchanged.
7. *(Owner confirmation needed, `design.md` DP21.)* FOR an item whose source gives no strength or form (TİTCK, a German
   or other box typed by name) THE user MAY enter the strength and form printed on the box with controlled inputs; THE
   client SHALL label such values "as entered by you" wherever a comparison uses them.

### Requirement 7: Sources and attribution *(Added in refinement)*
#### Acceptance criteria
1. Every source block SHALL carry the source id, region, country (EU), status, snapshot date, whether the source is
   older than its cadence (`stale`), an attribution code and what the source can compare at all (strength, form).
   Every presence entry SHALL refer to its source block, so every answer names its source and snapshot date.
2. THE client SHALL show, wherever a presence answer appears: for the BDPM "Source: Base de données publique des
   médicaments (BDPM), data of <date>. Shown as published; the BDPM does not endorse Janus."; for the Nomenclátor
   "Source: AEMPS, Nomenclátor de prescripción, data of <date>."; for openFDA "Source: openFDA NDC directory, data of
   <date>. Not an FDA endorsement."; for TİTCK "Source: TİTCK list of licensed medicinal products, data of <date>."
   (translated around the fixed source names, which are never translated).
3. Published strings (a BDPM pharmaceutical form, a published strength) SHALL be shown exactly as published and
   labelled with their source; strength codes and form groups SHALL be labelled as Janus's comparison, not as source
   data.
4. WHEN a source is `stale` THE row SHALL say that the source may be outdated (as `source_may_be_outdated` in
   `drug-resolution`).
5. THE Germany row SHALL say that there is no open product database for Germany and that nothing was checked there; it
   SHALL NOT be worded as "not found".

### Requirement 8: Wording in five languages *(Added in refinement)*
#### Acceptance criteria
1. Every Passport text SHALL exist in EN, TR, DE, FR and ES (`apps/web/messages/*.json`, namespace `Passport`), and
   SHALL contain none of the forbidden phrases of its language (`medical-safety.md` rule 2), none of the reassurance
   words (`doctor-loop` design §5.4) and none of the Passport substitution words of its language (`design.md` §7.3).
2. No Passport output SHALL contain substitution language in any supported language (seed property), including
   "equivalent", "interchangeable", "instead", "switch", "replace" and their translations (`muadil`, `eşdeğer`,
   `yerine`; `gleichwertig`, `austauschbar`, `stattdessen`; `équivalent`, `interchangeable`, `à la place`;
   `equivalente`, `intercambiable`, `en lugar de`).
3. Every Passport screen SHALL show the rule-9 disclaimer in the interface language and, on the detail view, the
   sentence "Janus shows listings in public data only. Only your doctor or pharmacist can say which medicine fits you."
4. Texts SHALL be drafted, reviewed by the pharmacologist and localization reviewers and accepted by the owner before
   release (review stop, `tasks.md`).

### Requirement 9: Privacy *(Added in refinement)*
#### Acceptance criteria
1. THE list SHALL live in the browser (`privacy.md`); THE server SHALL receive only ingredient keys, strength codes and
   dose-form groups for the presence endpoint, and SHALL NOT receive or persist the list, a product name or the box
   count.
2. THE presence endpoint SHALL log nothing but request id, route, status and latency; no key, code or body.
3. Demo items SHALL never be sent to the contribution or outcome endpoints (`experience` Req 4.3).

### Requirement 10: Passport screens and accessibility *(Added in refinement; layout and components **[Client: experience spec]**)*
#### Acceptance criteria
1. THE Passport list screen SHALL show the merged list (origin, source and date, ingredient names, box count, the
   homeopathic and "cannot be checked" labels), the duplicate flags next to the items they concern, and an entry point to
   Collective Memory for the list's checked keys (Requirement 11).
2. THE item detail screen SHALL show the presence rows of Requirement 2.1 with status, counts, the three comparison
   results with their reasons, attributions, notices and the sentence of Requirement 8.3.
3. Both screens SHALL handle loading (skeleton, `aria-busy`), empty list (how to add a box), error (503 or offline:
   "could not be checked now" with retry, never "not found"), partial (some sources unavailable) and long content (50
   items, long names wrapped, never truncated) states.
4. Status and comparison results SHALL be conveyed by text and an icon shape, never by colour alone; `--risk` (red) SHALL
   NOT be used on these screens; the presence rows SHALL be a table with row headers on wide screens and a labelled list
   at 375 px, with no horizontal scroll.
5. THE screens SHALL be operable by keyboard in reading order with the visible focus ring, touch targets of at least
   44 × 44 px, the large-text mode and both themes; the completion of loading SHALL be announced in a polite live
   region; contrast follows `design.md` (steering).

### Requirement 11: Collective Memory from the list *(Added in refinement; from the collective-memory open items)*
#### Acceptance criteria
1. THE list's distinct checked keys, sorted, SHALL be the keys of `POST /memory/combination` (2 to 20 keys, default scope
   `any`) and `POST /memory/regions` (1 to 20); ingredient order, box counts and duplicates SHALL change nothing.
2. WHEN the list has more than 20 distinct checked keys THE client SHALL say that Collective Memory looks at up to 20
   ingredients at once and let the user choose them; it SHALL NOT drop keys silently.
3. THE Collective Memory screens and wording are those of `collective-memory` (level shown, lower-bound counts, no
   interaction claim, no recommendation) **[Client: experience spec]**.

### Requirement 12: Demo mode *(Added in refinement)*
#### Acceptance criteria
1. THE Cologne synthetic patient (`experience` Req 4.2) SHALL have a Passport list of mixed TR and DE boxes with
   invented product names and real ingredient keys, including one shared ingredient between a Turkish combination box
   and a German box (so the duplicate flag shows), one homeopathic German box (shown as not checked) and at least one
   item with a strength entered as on the box (if DP21 is accepted).
2. THE demo SHALL call the live presence endpoint; WHEN it is unreachable THE client SHALL show a recorded answer stored
   with the demo (same schema, its dataset version and source dates), labelled "recorded answer of <date>".
3. Every demo screen SHALL carry the "Demo · synthetic patient" label; demo items SHALL be flagged so that Requirement
   9.3 holds.

### Requirement 13: Performance *(Added in refinement)*
#### Acceptance criteria
1. THE endpoint SHALL answer a 15-item list of common ingredients within 500 ms at p95 on the dev machine with the full
   dataset, and the worst case (50 of the most frequent keys) within 2 s; the database time limit is 3 s (Req 5.3).
2. THE number of SQL statements per request SHALL not depend on the number of items.

## Properties to test (PBT candidates)
- Merging lists is order-independent and idempotent (adding the same item twice changes nothing but the count). (Req 1.4) → design P1
- Two items are flagged as duplicates if and only if they share an ingredient key. (Req 1.2) → design P2 *(Refined: checked items only, Req 1.5, 1.6.)*
- Equivalent-presence results never assert a strength/form match when either side is unknown. (Req 6.1) → design P3
- No Passport output contains substitution language in any supported language. (Req 8.2) → design P4
- *(Added.)* Seventeen further properties (P5–P21) in `design.md` §11.

## Open items from collective-memory (2026-11-08)
- The merged list's ingredient keys (Wikidata `Q…` or Janus `J<n>`) are the keys of `POST /memory/combination` (2 to 20 keys,
  default scope `any`) and `POST /memory/regions`. The response says which level it shows (`combination`, `pairwise`,
  `single`), that the counts are lower bounds for sets, and that the comparison group includes reports naming only some of
  the medicines. It never says the medicines interact or recommends a change. Ingredient order and duplicates in the list
  change nothing.
  - *(Taken into Requirement 11.)*
