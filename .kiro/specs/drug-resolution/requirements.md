# Requirements: Drug Resolution (Türkiye · European Union · United States)

> Refined 2026-11-07 for Phase 1. **Phase 1 scope: the Türkiye (`tr`) and United States (`us`)
> adapters, the shared resolution core and the API in `apps/api`.**
> Criteria tagged **[Phase 2: eu_fr]**, **[Phase 2: eu_es]** or **[Phase 2: eu_name]** stay here
> as requirements but are designed and built in Phase 2 (`docs/internal/PLAN.md` Phase 2).
> Criteria tagged **[Client: experience spec]** are implemented in the `experience` spec (Phase 3).
> Owner decisions given with the task (2026-11-07): the 155 TİTCK rows excluded as
> `invalid_barcode` are not repaired and stay reachable by name search only; the 52 barcodes that
> map to more than one row return every candidate. Medical endpoints follow the `privacy` spec.
> Owner decisions on the design (2026-11-07): DP3–DP6, DP9–DP11, DP14, DP15, DP18 and DP22
> confirmed; DP19 — the client sends only AI (01) and (17), the API still drops serial and lot
> (Req 1.4); DP20 — US products get route-based ATC selection now (Req 5.1, 5.4).
> Criteria marked *(Added in refinement)* are new; no original criterion or property was dropped.
>
> **Phase 2 refinement (2026-11-08): the EU adapters `eu_fr`, `eu_es`, `eu_name` and the name
> rules.** The criteria tagged **[Phase 2: …]** are now designed (design §11–§19) and planned
> (tasks 15–28). Criteria added in this refinement are marked *(Phase 2)*. Two original sentences
> changed by owner decision and are marked *(Changed 2026-11-08)*: Req 4.2 (Spanish codes resolve
> from the `eu_es_cima` Nomenclátor loaded into PostgreSQL, not from the live CIMA API) and the
> CIMA mention in Req 7.1; the reason is recorded in Req 4.2 and DP27. New requirements: 12 (name
> rules), 13 (coverage before and after), 14 (imipenem). No original criterion or property was
> dropped. **Owner decisions of 2026-11-08 on the two open points (design §19):** imipenem:
> option (b), a narrow reviewed component-code exception for one curated key (Req 14, DP43);
> AI (712): approved, DP19 is extended to AI (01), (17) and (712), and the API now **rejects** AI
> (21) with 422 instead of dropping it (Req 1.4, DP19, DP42). Everything else is accepted as
> designed; tasks run in order and stop at task 20.

## Introduction
Turn what the user scans, photographs or types — in Türkiye, the EU or the US — into a precise list of **active ingredients**, each with its own ATC code (and RxCUI and Wikidata id where available), so every later component works on ingredients, not brand names or combination codes.

## Glossary
- **API:** the FastAPI service in `apps/api`.
- **Client:** the Next.js PWA in `apps/web`.
- **GS1 element string:** decoded DataMatrix content with Application Identifiers (01) GTIN, (21) serial, (17) expiry, (10) lot.
- **FNC1 form:** an element string whose variable-length fields are ended by the GS character (ASCII 29), optionally preceded by the symbology identifier `]d2`.
- **Parenthesised form:** the human-readable form, e.g. `(01)08680199094206(17)280531(10)AB12`.
- **GTIN:** Global Trade Item Number; GTIN-8, -12, -13 and -14 are compared as GTIN-14 (left-padded with zeros).
- **RegionAdapter:** the interface each region implements: `parse(code) → product key`, `lookup(product key) → product + ingredient names`, plus its source name and version date.
- **Product key:** a region-specific product identifier (TR: 13-digit barcode; US: NDC).
- **NDC:** US National Drug Code. A 10-digit NDC has three segments in one of three layouts: 4-4-2, 5-3-2 or 5-4-1. The **canonical NDC** is the 11-digit 5-4-2 form, made by left-padding the short segment with one zero.
- **NDC GTIN:** a GTIN-14 that embeds a 10-digit NDC: indicator digit, `03`, the 10 NDC digits, check digit.
- **Source:** a dataset produced by a pipeline (`data-pipelines` spec): `titck`, `us_ndc`, `wikidata_ingredients`.
- **Source version:** the pipeline run (run id, snapshot date, content hash) a source was loaded from.
- **Dataset version:** the identifier of one complete, consistent load of all sources into the database.
- **Ingredient key:** the shared cross-region identity of an active ingredient: Wikidata item id, with its ATC code(s) (P267) and RxNorm CUI (P3345).
- **Salt normalisation:** removing salt/ester words from an ingredient name ("amlodipin besilat" → "amlodipin"; "metformin hcl" → "metformin") before matching.
- **Spelling key:** a form of an ingredient name in which regular Turkish/English/INN spelling differences are removed (e.g. "siprofloksasin" and "ciprofloxacin" give the same key).
- **Ingredient-level ATC code:** a 7-character ATC code (`^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$`) that describes one active substance.
- **Combination ATC:** an ATC code that describes a combination product (e.g. `C09BB03`, ACE inhibitor + calcium-channel blocker).
- **Unmapped ingredient:** an ingredient with no ingredient key or no ingredient-level ATC code.
- **Candidate:** one possible product (or ingredient) for an input; a result may hold several.
- **Name-only row:** a TİTCK row whose barcode is invalid; it can be found by name, never by barcode.
- **Coverage report:** the measured share of source ingredient names and products that map to an ingredient key and an ingredient-level ATC code.
- *(Phase 2.)* **BDPM:** the French public medicines database (`eu_fr_bdpm` artifact). **CIP13:** the 13-digit French presentation code (starts `3400`). **CIS:** the BDPM specialty code. **SA / FT:** composition lines of the BDPM: `SA` is the substance as formulated (often a salt, e.g. `CHLORHYDRATE DE TRAMADOL`), `FT` is the therapeutic fraction (the moiety, e.g. `TRAMADOL`); a pair shares a link number.
- *(Phase 2.)* **Nomenclátor:** the AEMPS prescription list (`eu_es_cima` artifact). **CN:** the 6-digit Spanish national code (`cod_nacion`). **NTIN:** a GS1 code `0847000` + CN + check digit. **AI (712):** the GS1 element for the Spanish CN.
- *(Phase 2.)* **EU adapter:** a region adapter whose region is `EU` and whose country is `FR` or `ES`. **No-open-database country:** an EU country whose products cannot be resolved from an open product-code database (today: Germany).
- *(Phase 2.)* **Language (`lang`):** `tr`, `en`, `fr` or `es`; the language of the source a published ingredient name comes from (TİTCK `tr`; openFDA and FAERS `en`; BDPM `fr`; Nomenclátor `es`). Wikidata labels exist in five languages (including `de`) and are language-neutral index entries.
- *(Phase 2.)* **Anion-acid table:** a reviewed table that maps the anion form of a salt or ester name to the label of its acid (`MYCOPHENOLATE` → `mycophenolic acid`), used as a ladder step. **Biologic suffix:** the hyphen and four letters FDA appends to the name of an originator or biosimilar biologic (`INFLIXIMAB-DYYB`).

## Requirements

### Requirement 1: Parse GS1 DataMatrix content
**User story:** As a caregiver, I want to scan the code on a medicine box so that the exact product is identified without typing.

#### Acceptance criteria
1. WHEN the client submits a GS1 element string THE system SHALL extract AI (01), (21), (17) and (10), supporting both FNC1/GS-separated and parenthesised forms.
   - *(Added in refinement.)* THE API SHALL accept the FNC1 form with or without the `]d2` symbology identifier, and SHALL treat the GS character and a leading FNC1 as separators only.
   - *(Added in refinement.)* IF the element string contains an Application Identifier that is not on the API's supported list THEN THE API SHALL reject it with a clear error naming the problem (not the content), and SHALL NOT guess field boundaries.
   - *(Added in refinement.)* IF an AI appears twice with different values THEN THE API SHALL reject the element string.
   - *(Added in refinement.)* WHEN the client submits only digits forming a GTIN-8, GTIN-12 (UPC-A), GTIN-13 (EAN-13) or GTIN-14 THE API SHALL treat them as AI (01) without other fields.
   - *(Phase 2.)* WHEN AI (712) is present THE API SHALL keep its value as `national_code` (Spanish CN: 7 digits, the 6-digit CN and its control digit; only the first six digits are used, design §12.2) and SHALL ignore the values of AI 710, 711 and 713–716 (parsed as before, not interpreted: their country assignment is not confirmed, `eu-code-encodings.md`). IF the AI (712) value is not 7 digits THEN THE API SHALL drop it and SHALL still resolve the GTIN.
2. WHEN AI (01) is present THE system SHALL validate the GTIN-14 check digit and reject invalid codes with a clear error.
   - *(Added in refinement.)* IF AI (01) is missing, not 14 digits, or has a wrong check digit THEN THE API SHALL respond with HTTP 422 and SHALL NOT perform a lookup.
3. WHEN AI (17) is present THE system SHALL parse it as an expiry date (YYMMDD, where DD = 00 means end of month).
   - *(Added in refinement.)* THE API SHALL choose the century with the GS1 rule relative to the current date, and IF the month or day is impossible THEN THE API SHALL reject the expiry field while still resolving the GTIN, and say so in the result.
4. THE system SHALL NOT require serial or lot numbers and SHALL NOT store them.
   - *(Owner decision.)* The serial number identifies a single box, so it SHALL NOT leave the device: THE client SHALL send only AI (01) and, if present, AI (17) to the API. **[Client: experience spec]**
   - *(Added in refinement, defence in depth.)* IF an element string with serial (21) or lot (10) reaches the API THEN THE API SHALL drop both values inside the parser and SHALL NOT return, log or persist them; the result SHALL state only whether they were present.
   - *(Phase 2, owner decision 2026-11-08: approved.)* AI (712) is a national product reimbursement number, not a serial and not a person identifier. WHERE a scanned code carries AI (712) THE client SHALL send it together with AI (01) and (17) (DP19 extended: the fields the client may send are exactly (01), (17) and (712)), so that a Spanish pack whose GTIN is not in the Nomenclátor still resolves (Req 4.2). The client still sends no serial (21) and no lot (10). **[Client: experience spec]**
   - *(Phase 2, owner decision 2026-11-08, replaces the "drop" bullet above for AI 21.)* IF an element string with serial (21) reaches the API THEN THE API SHALL reject the whole request with HTTP 422 and the fixed code `gs1_serial_not_accepted`, SHALL NOT look anything up, and SHALL NOT echo, log or persist any part of the input. The serial identifies a single box and must never leave the device, so a client that sends it is defective and is told so. Lot (10) stays as before: read only to find the field end, never stored, returned or logged. `ScanInfo.serial_present` stays in the result for contract compatibility and is always `false`.
5. WHEN a GTIN is decoded THE system SHALL determine the candidate region adapter(s) from the GTIN structure and SHALL let the user override the region.
   - *(Added in refinement.)* WHEN no override is given THE API SHALL ask every enabled adapter whose `parse` accepts the GTIN, order the candidates by the structural hint (GS1 prefix 868–869 → TR; NDC GTIN → US), and return the hits of all of them.
   - *(Added in refinement.)* WHEN the user gives a region override THE API SHALL use only that region's adapter.
   - *(Added in refinement.)* WHEN the structure points to a region whose adapter is not enabled in this phase (e.g. France, Spain, Germany) THE API SHALL say which region it is and that its adapter is not available yet. **[Phase 2: eu_fr, eu_es, eu_name]** for the adapters themselves.
   - *(Phase 2.)* WHEN the EU adapters are enabled THE API SHALL look up a French or Spanish structure (Req 4.1, 4.2) and SHALL answer a German structure with the notice of Req 4.3; `region_adapter_not_available` remains for any structural hint without an enabled adapter. A region override `EU` asks every EU adapter (France, Spain, no-open-database countries) and no other.

### Requirement 2: Türkiye adapter
#### Acceptance criteria
1. WHEN a GTIN-14 starts with "0" and the remaining 13 digits match a row in the current TİTCK list THE system SHALL return product name, all active ingredients and the list version date.
   - *(Added in refinement, owner decision.)* WHEN the 13 digits match more than one row THE API SHALL return every matching row as a separate candidate, in a stable order, and SHALL NOT choose one (52 such barcodes in the list of 2026-11-06).
   - *(Added in refinement.)* THE result SHALL include, for each candidate, the published ATC code as published, the published ingredient text and the suspension status.
2. THE system SHALL refresh the TİTCK list weekly at runtime and SHALL NOT commit the list to the repository.
   - *(Added in refinement.)* In Phase 1 the refresh is run from the pipeline command line and loaded with the loader (Req 9); the weekly schedule is set up in Phase 5 (`data-pipelines` DP11).
   - *(Added in refinement.)* WHEN the loaded TİTCK snapshot is older than twice its cadence (14 days for the weekly list; the shared freshness rule of `evidence-integrity` Req 2.2, cadence from `pipelines/sources.toml`) THE result SHALL say that the list may be out of date, with its date. *(Changed 2026-11-07 by owner decision, `evidence-integrity` DP17: the 14 days are no longer a constant in the code.)*
3. *(Added in refinement, owner decision.)* THE system SHALL NOT repair TİTCK rows whose barcode is invalid (155 rows in the list of 2026-11-06). THE system SHALL keep them as name-only rows: a barcode lookup SHALL never return them, and a name search SHALL find them like any other product.
4. *(Added in refinement.)* WHEN the user searches by name in Türkiye THE API SHALL search TİTCK product names and ingredient names (Turkish, as published), and ingredient names in English/INN and Turkish through the ingredient key, and SHALL return ranked candidates for confirmation.
5. *(Added in refinement.)* THE Türkiye adapter SHALL map Turkish ingredient names to ingredient keys without relying on Wikidata's Turkish labels alone (1,269 of 3,766 items have one), using salt normalisation, the spelling key, English/INN and other-language labels, and TİTCK's own single-ingredient products (Req 5).

### Requirement 3: United States adapter
**User story:** As a caregiver in the US, I want my parent's medicines recognised even though they come in pharmacy vials.

#### Acceptance criteria
1. WHEN a GTIN encodes an NDC THE system SHALL extract the NDC and resolve it via the openFDA NDC directory.
   - *(Added in refinement.)* THE API SHALL recognise an NDC GTIN (indicator digit, `03`, 10 NDC digits, check digit) and a UPC-A starting with `3`, and SHALL extract the 10 NDC digits.
   - *(Added in refinement.)* Because 10 digits without hyphens do not say which layout they use, THE API SHALL try all three layouts and SHALL return every package that matches; IF more than one matches THEN THE API SHALL return all of them as candidates.
   - *(Added in refinement.)* THE API SHALL resolve against the local copy of the openFDA NDC directory loaded from the `us_ndc` pipeline (138,262 products, export of 2026-11-06), not the live API.
2. WHEN the user enters or the on-device OCR reads an NDC from a pharmacy label THE system SHALL normalise 10-digit NDC formats (4-4-2, 5-3-2, 5-4-1) and resolve it.
   - *(Added in refinement.)* THE API SHALL also accept the 11-digit 5-4-2 form (with or without hyphens), the product NDC without package segment (4-4, 5-3, 5-4), and common label prefixes (`NDC`, `NDC:`, `N`), ignoring spaces.
   - *(Added in refinement.)* IF the input has the wrong number of digits, a segment of the wrong length, or non-digit characters other than hyphens, spaces and the allowed prefixes THEN THE API SHALL reject it with HTTP 422.
   - *(Added in refinement.)* WHEN a product NDC without package segment is given THE API SHALL return the product with all its packages.
3. WHEN only a drug name is available THE system SHALL return ranked RxNorm candidates for confirmation.
   - *(Added in refinement.)* THE API SHALL search openFDA brand and generic names and ingredient names (English/INN, through the ingredient key) and SHALL return ranked candidates that carry RxNorm CUIs where the sources have them.
   - *(Added in refinement.)* Most US patients receive pharmacy vials; THE NDC-from-label (3.2) and name (3.3) paths SHALL return the same product data as a box scan of the same product.
4. *(Added in refinement; route and dosage form added by owner decision DP20.)* THE result SHALL include the openFDA product type, route(s), dosage form and marketing end date, so that products no longer marketed and non-finished products (e.g. bulk ingredients) are visible as such.

### Requirement 4: European Union adapters
#### Acceptance criteria
1. WHEN a code resolves to a French CIP13 THE system SHALL resolve it with the current BDPM files (presentations → specialty → composition) and record the BDPM update date. **[Phase 2: eu_fr]**
   - *(Phase 2.)* THE France adapter SHALL accept a GTIN-14 that matches `^0(3400[0-9]{9})$` and has a valid check digit, and SHALL take the last 13 digits as the CIP13 (`eu-code-encodings.md`: verified on all 20,918 CIP13 of the BDPM of 2026-11-07). It SHALL NOT accept any other GTIN, and SHALL NOT derive a CIP13 from a different layout.
   - *(Phase 2.)* THE system SHALL resolve the CIP13 against the `eu_fr_bdpm` artifact as loaded into PostgreSQL: the presentation row (`CIS_CIP_bdpm`), its specialty (`CIS_bdpm`: denomination, pharmaceutical form, routes, authorisation and commercialisation status) and its composition (`CIS_COMPO_bdpm`), as published. WHEN more than one row has the CIP13 THE system SHALL return every row (none exist in the BDPM of 2026-11-03; the rule is the same as Req 2.1). Name-only rows SHALL never be returned for a code and SHALL be found by name (Req 2.3 applies).
   - *(Phase 2.)* THE result SHALL record the BDPM update date as the source version's snapshot date (the oldest of the three file dates, `data-pipelines` Req 11.1) and SHALL show product text exactly as published (no translation, trimming or correction: licence ouverte). THE result SHALL NOT suggest that the BDPM or ANSM has reviewed or endorsed a Janus finding. **[Client: experience spec]** shows the source name, the date and that wording.
   - *(Phase 2.)* WHEN the loaded BDPM snapshot is older than twice its cadence (30 days from `pipelines/sources.toml`, so 60 days) THE result SHALL carry `source_may_be_outdated` with the date (Req 2.2 rule).
2. *(Changed 2026-11-08, owner decision.)* WHEN a code resolves to a Spanish national code THE system SHALL resolve it with the AEMPS Nomenclátor de prescripción, loaded from the `eu_es_cima` artifact into PostgreSQL, and record the Nomenclátor's update date (`listprescriptiondate`). **[Phase 2: eu_es]**
   - *(Changed 2026-11-08.)* **Was:** "THE system SHALL resolve it with the AEMPS CIMA API and record the response date." **Why changed:** (a) DP6: a live call would send a product code and the user's request time from the Janus server to AEMPS; the data are public and small, so they are loaded ahead of time like TİTCK and openFDA. (b) The Nomenclátor lists the NTIN and GTIN values of each presentation (17,855 presentations with an NTIN and 4,552 with a GTIN on 2026-11-08, 210 with both), which is what lets the adapter go from AI (01) to a national code without calling anything (`eu-code-encodings.md`); it is the source the `eu_es_cima` pipeline already ingests (`data-pipelines` DP24). (c) Same input and same dataset version give the same answer (Req 7.3), offline and in tests, and AEMPS being unreachable cannot break a scan. THE system SHALL NOT call the CIMA REST API from the request path or from a loader.
   - *(Phase 2.)* THE Spain adapter SHALL look the scan up in this order and SHALL use the first step that finds a presentation, labelling the result by the step (`matched_by`); it SHALL NOT combine steps and SHALL NOT guess: (1) AI (01) in the NTIN lists of the Nomenclátor; (2) AI (01), padded to 14 digits, in the GTIN lists; (3) AI (712): its first six digits as the CN, labelled `ai_712` (the seventh digit, the control digit, is not validated: no official algorithm was found); (4) AI (01) of the form `^0847000[0-9]{7}$` with a valid check digit: the CN is digits 8 to 13, labelled `ntin_digits` (less certain than the table); else no candidate.
   - *(Phase 2.)* WHEN an NTIN or GTIN is published on more than one presentation (2 values on 2026-11-08) THE system SHALL return every presentation that publishes it. An NTIN whose embedded CN differs from the presentation's CN (3 on 2026-11-08) SHALL be resolved through the table (step 1), not through its digits.
   - *(Phase 2.)* THE result SHALL show the AEMPS legal-notice wording the licence asks for: source and update date. WHEN the loaded snapshot is older than twice its cadence (7 days, so 14 days) THE result SHALL carry `source_may_be_outdated`.
   - *(Phase 2.)* A presentation without a listed ingredient (512 of 30,900 on 2026-11-08) SHALL be returned with an empty ingredient list; THE system SHALL NOT infer ingredients from its name.
3. WHEN a code belongs to a country without an open product-code database (e.g. Germany) THE system SHALL say so and offer OCR or name search; it SHALL NOT guess a product. **[Phase 2: eu_name]**
   - *(Phase 2.)* THE `eu_name` adapter SHALL answer a GTIN whose GS1 prefix belongs to a no-open-database country (today: 400–440, Germany) with the notice `no_open_product_database` naming the country. THE notice means "this country's products cannot be looked up", not "not found": THE system SHALL NOT return a candidate for that country, SHALL NOT add that country to the searched regions, and SHALL NOT use the "not found" wording of Req 6.2 for it. A French or Spanish source MAY still return a candidate when the GTIN is an exact table hit there (a Spanish presentation can carry a foreign company GTIN); no candidate comes from a guess. THE client offers on-device OCR and name search. **[Client: experience spec]**
   - *(Phase 2.)* THE country table (prefix range → country → no-open-database) SHALL be reviewed data with the source and date of each row. Prefixes of other EU countries stay unlisted until they are verified against the GS1 prefix list (pre-launch checklist); an unlisted prefix gives no hint and no notice.
4. Name search for EU users SHALL accept ingredient names in German, French and Spanish (and English/INN) through the ingredient key. **[Phase 2: eu_name]**
   - *(Phase 2.)* WHEN the region is `EU` or absent THE name search SHALL find an ingredient by any label or alias in German, French or Spanish as well as English and Turkish, with the same folding and ranking as Req 2.4. German, French and Spanish ingredient labels SHALL belong to region `EU`: a search with region `TR` or `US` SHALL NOT return an ingredient only because of such a label, and English/INN labels SHALL stay reachable from every region.
   - *(Phase 2.)* THE name index SHALL also hold the BDPM denominations and the Nomenclátor medicine and presentation names as product names, and the published ingredient names of mapped EU ingredients as ingredient names (as for TİTCK, Req 2.5).
5. *(Added in refinement.)* Adding the EU adapters SHALL NOT change the resolution core, the result model or the cascade-engine input (Req 10).
   - *(Phase 2.)* THE result model SHALL gain only optional or enumerated additions (region `EU`, `country`, `status_published`, new `matched_by` and notice codes); every TR and US field, name and meaning SHALL stay as in Phase 1, and the response to a TR or US request SHALL differ only by those additions.
6. *(Phase 2.)* THE result for an EU product SHALL carry, as published and for display only, the authorisation and marketing status (BDPM: authorisation status, commercialisation status of the presentation and its declaration date; Nomenclátor: commercialisation flag, registration status and presentation status with their dates), so that products no longer marketed are visible as such (Req 3.4 for the US). No rule SHALL read these fields.
7. *(Phase 2.)* Typed or OCR-read national codes (CIP7, a printed CN with its dot, a German PZN) are not accepted as codes in this phase: OCR text goes to name search, and a printed CIP13 or EAN-13 can be sent as bare digits (Req 1.1). *(Scope note, not a dropped criterion.)*

### Requirement 5: Ingredient decomposition and normalisation (all regions)
**User story:** As the cascade engine, I need every ingredient as its own ATC code so that no cascade is missed in a combination product.

#### Acceptance criteria
1. WHEN a product contains several active ingredients THE system SHALL return each ingredient separately with its own ingredient-level ATC code.
   - *(Added in refinement.)* THE system SHALL take ingredient-level ATC codes from the ingredient key (Wikidata P267) and from TİTCK single-ingredient products of the same ingredient key, never from the ATC code of a product with more than one ingredient.
   - *(Added in refinement.)* WHEN an ingredient key has several ingredient-level ATC codes THE system SHALL select the codes that fit the product (by its own ATC group where known) and SHALL record how they were selected.
   - *(Added in refinement.)* THE system SHALL emit only codes of the form `^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$`; IF a published code is shorter or malformed (1,044 TİTCK rows, e.g. `B05D`, `S03CA0l`) THEN THE system SHALL keep it as published for display and SHALL NOT use it as an ingredient code.
   - *(Added in refinement.)* THE system SHALL record the source of every ingredient-level ATC code (Wikidata, or the TİTCK product it was observed on).
   - *(Owner decision, DP20.)* WHEN a US product has a published route of administration THE system SHALL keep only the ingredient's codes whose ATC group is allowed for that route by a reviewed route-to-ATC-group map (e.g. a topical betamethasone cream keeps `D07…` codes and drops the systemic `H02AB01`), and SHALL record the selection as route-based.
   - *(Owner decision, DP20.)* IF no code of the ingredient is allowed for the product's routes THEN THE system SHALL mark the ingredient `unmapped` with the reason "no ingredient-level ATC code for this route"; it SHALL NOT fall back to codes of another route.
   - *(Owner decision, DP20.)* IF a product's route is missing or not in the map THEN THE system SHALL keep all the ingredient's codes and mark the selection as not route-confirmed.
2. THE system SHALL NOT pass a combination ATC code to the cascade engine as an ingredient code.
   - *(Added in refinement.)* THE system SHALL classify ATC codes as combination codes with one deterministic, tested function and a reviewed list (design §5.4), and SHALL fail loudly IF a code classified as a combination code would be emitted as an ingredient code.
   - *(Added in refinement.)* Example: AMLIPIN (barcode 8680199094206, `amlodipin besilat` + `lisinopril dihidrat`, ATC `C09BB03`) SHALL resolve to amlodipine with `C08CA01` and lisinopril with `C09AA03`, and `C09BB03` SHALL appear only as the product's published code.
3. WHEN mapping a name to an ingredient key THE system SHALL apply salt normalisation and multilingual synonyms from the Wikidata extract.
   - *(Added in refinement.)* THE system SHALL try the most specific form first (exact name, then salt-normalised name, then spelling key) and SHALL record which step matched.
   - *(Added in refinement.)* IF a name matches more than one ingredient key at the first step that matches THEN THE system SHALL return all of them as candidates and mark the ingredient `ambiguous`; it SHALL NOT choose one.
   - *(Added in refinement.)* IF one published "ingredient" name contains two or more known ingredient names (e.g. `metformin pioglitazon`) THEN THE system SHALL mark it as a possible unsplit combination and SHALL NOT give it the product's ATC code.
4. WHEN an ingredient cannot be mapped to an ATC code THE system SHALL mark it `unmapped`, show it to the user, and exclude it from rule matching with a visible notice.
   - *(Added in refinement.)* THE result SHALL give the reason: no ingredient key, possible unsplit combination, no ingredient-level ATC code, or no ingredient-level ATC code for the product's route. An `ambiguous` ingredient (5.3) is excluded from rule matching in the same way and shows its candidate keys.
   - *(Added in refinement.)* THE result SHALL keep unmapped ingredients in the product's ingredient list, in published order, so the user sees every ingredient.
5. WHEN an ingredient key is found THE system SHALL attach RxCUI (via Wikidata or RxClass) where available and record when it is not.
   - *(Added in refinement.)* In Phase 1 RxCUIs come from the Wikidata extract only (design DP7).
6. *(Added in refinement.)* THE loader SHALL produce a coverage report per source: share of distinct ingredient names and of ingredient occurrences mapped, share of products whose ingredients are all mapped, share mapped at each matching step, number of ambiguous and possible unsplit names, and the agreement between the mapped ingredient's ATC codes and the TİTCK ATC code of single-ingredient products.
7. *(Added in refinement.)* Salt and spelling rules SHALL be data in the code (word lists and rewrite rules), reviewed by the pharmacologist agent, and changing them SHALL change the dataset version.
8. *(Phase 2.)* WHEN a BDPM presentation has composition lines THE system SHALL build its ingredient list from the lines grouped by link number, in the order in which each link first occurs in the file: for a link with at least one `FT` line, each `FT` name is an ingredient (the `SA` lines of that link are not ingredients of their own); for a link with only `SA` lines, each `SA` name is an ingredient. THE ingredient's strength SHALL be the dosage of the line it was named from. Every composition line SHALL be accounted for in the result's source record (used or superseded by the `FT` line of its link). Measured: choosing `FT` before `SA` maps 63.9 % of ingredient occurrences against 45.6 % with `SA` only (design §11).
   - *(Phase 2.)* WHEN a presentation's CIS has no composition line THE ingredient list SHALL be empty (Req 4.2, last bullet applies in the same way).
9. *(Phase 2.)* WHEN a BDPM product has no published ATC code and routes of administration THE system SHALL select the ingredient's codes by route as in Req 5.1 (owner decision DP20), using a reviewed map of the French route strings (the `routes` text split at `;`; 68 distinct strings on 2026-11-03; the 30 most frequent hold every route of 99.2 % of presentations). A route string not in the map counts as unmapped; the rest of Req 5.1 (no fallback, `all_codes` when no route is mapped) applies unchanged.
10. *(Phase 2.)* WHEN a Nomenclátor presentation has a published ATC code THE system SHALL use it as the product code `p` of design §5.5 (single-ingredient product, therapeutic group, anatomical group), exactly as for a TİTCK product, and SHALL treat a combination code there as display only. THE Nomenclátor's routes (numeric codes) SHALL NOT be used in this phase.
11. *(Phase 2.)* WHEN a BDPM substance name or strength is a homeopathic one (Req 12.10) THE product SHALL be flagged homeopathic (Req 11.1 applies: not evaluated, not counted in coverage).

### Requirement 6: Confirmation and OCR
#### Acceptance criteria
1. WHEN on-device OCR produces text THE client SHALL show candidates for confirmation; unconfirmed OCR results SHALL NOT be used. **[Client: experience spec]**
   - *(Added in refinement, server side.)* THE API SHALL return candidates and SHALL NOT mark any candidate as confirmed; confirmation is the client's.
2. WHEN a scanned or typed product is not found THE system SHALL return "not found" with the region and source version searched; it SHALL NOT guess.
   - *(Added in refinement.)* THE API SHALL return "not found" only WHEN the sources it searched are loaded; IF a needed source is not loaded THEN THE API SHALL respond with HTTP 503 `resolution_unavailable` and SHALL NOT say "not found".
   - *(Added in refinement.)* A "not found" result SHALL be HTTP 200 with an empty candidate list and the searched regions, sources and source versions.
   - *(Phase 2.)* A region whose adapter searched no source (a no-open-database country, Req 4.3) SHALL be reported as "not searched", never as "not found". WHEN a region override `EU` is given and one of the EU sources is not loaded THE API SHALL respond 503 `resolution_unavailable` (a partial EU search would be a partly false "not found").

### Requirement 7: Reliability and provenance
#### Acceptance criteria
1. THE system SHALL apply timeouts and caching to openFDA, RxNav, CIMA and Wikidata calls and SHALL degrade gracefully when they are unavailable (cached results, clearly labelled).
   - *(Added in refinement.)* In Phase 1 the request path makes no external calls: openFDA and Wikidata data come from pipeline artifacts loaded into PostgreSQL (design DP6). Any external call added later (RxNav if chosen) SHALL use the `data-pipelines` HTTP policy (timeouts, retries only for idempotent requests) and a labelled cache.
   - *(Changed 2026-11-08, owner decision.)* **Was:** "(CIMA in Phase 2; RxNav if chosen)" and "**[Phase 2: eu_es]** for CIMA". Spanish data come from the Nomenclátor artifact (Req 4.2), so Phase 2 also makes no external call on the request path. A test SHALL block the network and run every resolution route (design P31).
2. THE resolution result SHALL include the source, region and version date used for every field.
   - *(Added in refinement.)* Every result SHALL include the dataset version, and every candidate and ingredient SHALL reference the source version (source id, run id, snapshot date) of each field it uses.
3. *(Added in refinement.)* WHEN the same input is resolved twice against the same dataset version THE API SHALL return identical results.

### Requirement 8: Medical-endpoint privacy *(Added in refinement)*
**User story:** As a user, I want my scans and searches forgotten as soon as Janus has answered.

#### Acceptance criteria
1. THE resolution routes SHALL be medical routes (`privacy` spec Req 2.1): JSON bodies only, at most 64 KiB, `Cache-Control: no-store`, database access only through read-only transactions, nothing written to any store.
2. THE resolution routes SHALL take codes and names only in the JSON request body (POST), never in the URL path or query string.
3. THE API SHALL NOT log codes, names, ingredients, ATC codes, expiry dates or results; logging goes through the `privacy` allowlist formatter only.
4. IF an error message would contain user input THEN THE API SHALL replace it with a fixed error code; 422 responses SHALL NOT echo serial or lot values.

### Requirement 9: Loading sources *(Added in refinement)*
**User story:** As a maintainer, I want to load new pipeline artifacts without the API ever serving a half-loaded or mixed list.

#### Acceptance criteria
1. THE loader SHALL read the `current` artifact (rows and manifest) of `titck`, `us_ndc` and `wikidata_ingredients` from the data directory and SHALL refuse an artifact whose rows do not hash to its manifest's content hash.
2. WHEN a load completes THE loader SHALL switch the API to the new dataset version in one transaction; IF the load fails THEN THE API SHALL keep serving the previous dataset version unchanged.
3. THE loader SHALL record, for each source version, the source id, run id, region, snapshot date, licence and source URL (the `evidence_source.json` of the run).
4. THE dataset version SHALL change whenever any source version or any mapping rule changes, and SHALL be the same for the same inputs.
5. THE loader SHALL write only reference data (no user data) and SHALL be the only writer of the resolution tables.
6. THE TİTCK list SHALL be loaded only into the database and the data directory, never into the repository (Req 2.2).
7. *(Phase 2.)* THE loader SHALL read the `current` artifacts of `eu_fr_bdpm` and `eu_es_cima` under the same rules as Req 9.1–9.3 (manifest, content hash, schema versions `eu_fr_bdpm-1` and `eu_es_cima-1`, source version record with the licence text of the registry). THE two EU sources SHALL be optional: IF one is absent THEN THE loader SHALL load the dataset without it, SHALL print and log which sources the dataset holds, and THE API SHALL answer 503 `resolution_unavailable` to any request that needs the missing source (Req 6.2). IF an EU artifact is present but invalid THEN THE loader SHALL refuse the whole load, as for the other sources.
8. *(Phase 2.)* THE dataset version SHALL also change whenever a language word list, the anion-acid table, the biologic-suffix rule, the French route rows, the country table or an EU source version changes (Req 5.7, 12.2).
9. *(Phase 2.)* THE loader SHALL NOT write the BDPM or Nomenclátor files into the repository; the raw files stay in the data directory (`data-pipelines` Req 11.8, 12.8).

### Requirement 10: Region adapters *(Added in refinement)*
#### Acceptance criteria
1. THE region-specific code (code parsing, product lookup, ingredient names) SHALL live behind the `RegionAdapter` interface; the resolution core, the result model and the cascade-engine input SHALL be the same for every region.
2. THE result SHALL carry, for every ingredient, its ingredient key, ingredient-level ATC codes, RxCUIs, mapping status and provenance in the same shape for every region.

### Requirement 11: Homeopathic products and curated Janus keys *(Owner decisions, 2026-11-07)*
#### Acceptance criteria
1. WHEN any ingredient strength of a product is given in homeopathic units (openFDA `[hp_X]`, `[hp_C]`, `[hp_M]`, `[hp_Q]`, `[kp_C]`) THE API SHALL mark the product as homeopathic (`homeopathic = true`). Such products contain negligible active substance: THE cascade engine SHALL NOT evaluate their ingredients and SHALL list each of them as `homeopathic_product`, not checked; the coverage report SHALL NOT count or hint them. **[Client: experience]** shows "homeopathic product, not checked".
2. WHERE no Wikidata item in the extract carries an ingredient-level ATC code for a substance that a PIPC class needs, THE system MAY give it a curated Janus ingredient key `J<n>` in `data/janus_ingredients.csv` (labels in the five languages, ingredient-level codes, the date, a note citing the code check). Janus keys SHALL behave like Wikidata keys in matching and code selection; their own codes SHALL cite the source `janus_curated`, recorded as a source version of the dataset; the file's hash SHALL be part of the dataset version. First key: J1 dimenhydrinate, `R06AA11` (not mapped to diphenhydramine, whose code would drop the antiemetic and vestibular classes).
3. THE loader SHALL refuse a curated row with a malformed or repeated key, a code that is not ingredient-level, a missing English label or a malformed date, naming the row only.

### Requirement 12: Name rules for French, Spanish and English sources *(Phase 2, 2026-11-08)*
**User story:** As a caregiver with French or Spanish boxes, and as Collective Memory counting FAERS reports, I want `CHLORHYDRATE DE TRAMADOL`, `AMLODIPINO BESILATO` and `INFLIXIMAB-DYYB` to be recognised as the substances they name, without any name being guessed.

#### Acceptance criteria
1. THE name functions (`strip_salts`, `spelling_key` and the ladder `map_name`) SHALL take a language (`tr`, `en`, `fr`, `es`). FOR `tr` and `en` and any name that contains no word added in Phase 2, THE result SHALL equal the Phase 1 result, so that TİTCK and openFDA mapping changes only where a reviewed Phase 2 rule applies.
2. THE salt, ester, hydrate and counter-ion words of each language, the connector words and the rewrite rules SHALL be data in the code, one list per language, with the evidence behind every word (number of names it touches in the real sources, an example, and where the source publishes an ATC code the agreement of the mapped ingredient's codes with it). Changing any list SHALL change `RULES_VERSION` and therefore the dataset version (Req 5.7, 9.8).
3. THE connector words of a language (`de`, `d`, `du`, `des` for French; `de`, `del` for Spanish; folded, so `D'` gives `d`) SHALL be removed only when they stand at the start or end of the name after salt words were removed, never inside a name.
4. Words that make a different substance SHALL stay in the name, as in Phase 1 (pharmacologist review of 2026-11-07): counter-ions that are substances (`NOT_ALONE`), and ester words with a code of their own (`furoate`, `butylbromide`, `mononitrate`, `disoproxil`, `alafenamide`). Ester words that exist only in prodrugs with their own INN (`lauroxil`, `enacarbil`) SHALL NOT be added: the owner's standing rule is to leave those names unmapped and listed.
5. THE spelling key of `es` and `fr` names SHALL remove the regular differences between Spanish or French INN forms and the English/INN label (Spanish final `-a`, `-o`; the acid word order `ACIDE X-IQUE`, `X-ICO ACIDO` against `X-ic acid`) and SHALL keep the idempotence and non-empty guarantees of Req 5.3.
6. THE ladder SHALL gain two steps after the existing ones and before the unsplit check, each recorded in `match_step`: `anion_acid` (Req 12.7) and `biologic_suffix` (Req 12.8). A name that an earlier step maps SHALL NOT be changed by them.
7. THE `anion_acid` step SHALL rewrite the anion of a salt or ester name (after salt words are removed) to the label of its acid, from a reviewed table (`data/anion_acid_forms.csv`: language, anion form, acid label, note with the evidence). THE step SHALL only look the rewritten name up through the label steps, so it can only land on an existing ingredient key. THE loader SHALL refuse a table with a repeated (language, anion) pair, an acid label that no eligible ingredient carries, or an empty note. The generic rewrite "-ate → -ic acid" SHALL NOT be used: it would map magnesium, calcium and diethylamine salicylate (analgesics) to salicylic acid, a different substance with different codes (design §11).
8. WHEN an `en` name ends in a hyphen and exactly four ASCII letters and its base (the part before the hyphen) maps by a label step to exactly one key, THE `biologic_suffix` step SHALL map the name to that key. A base that is ambiguous or unmapped, a suffix of another length, and a name with no hyphen SHALL NOT be affected. THE step SHALL NOT depend on a list of biologic stems (insulin, immunoglobulin and interferon names carry the suffix and have none).
9. THE system SHALL NOT map a part of a combination string, or a name with an unknown word, to a substance by guessing (e.g. `CARBIDOPA` from `CARBIDOPA\LEVODOPA` when the substance has no ingredient-level code of its own). WHEN a reviewed single ingredient is named by several parts (e.g. the three components of pancrelipase), the part names MAY be added to the curated synonym file (owner review, Req 5.3 step 0). All other part names stay unmapped and are listed in the coverage report.
10. THE system SHALL treat a BDPM substance name that contains "POUR PRÉPARATIONS HOMÉOPATHIQUES" (folded, any case; 274 presentations on 2026-11-03, of which the 99 with the procedure "Enreg homéo" are a subset) as a homeopathic name (Req 11.1, 5.11).
11. NO rule data of Req 12 SHALL be used in a loaded dataset before the pharmacologist agent has reviewed it and the owner has accepted the review sheet `.kiro/specs/drug-resolution/name-rules-review.md` (same method as `cascade-engine/mapping-review.md`). THE sheet SHALL list, for every word, rule and table row, the names it touches (counts only in the repository; names stay in the data directory), the mapped ingredient, and the evidence.
12. THE unsplit check (Req 5.3) SHALL, for French and Spanish names, ignore spans made only of salt or connector words, so that a name made of one known ingredient and salt words (`MALÉATE D'ÉNALAPRIL`) is mapped or unmapped by the ladder and never reported as a possible unsplit combination. Two known ingredients side by side in one name SHALL still be reported. *(Scope decided at task 18: Turkish and English keep the Phase 1 behaviour exactly, Req 12.1; French and Spanish are new sources with nothing to preserve. A connector between two ingredients is not a separator, so `A de B` is not reported as unsplit.)*

### Requirement 13: Coverage before and after *(Phase 2, 2026-11-08)*
**User story:** As the project owner, I want to see how many names and products each source resolves before and after the new rules, so that I can judge the rules by numbers.

#### Acceptance criteria
1. BEFORE any Phase 2 rule data is enabled, THE system SHALL write a baseline coverage report for TİTCK, openFDA, BDPM, Nomenclátor and FAERS names, using the Phase 1 code on the current artifacts, to the data directory (never the repository). AFTER the rules are enabled it SHALL write the same report with the same code path, and the task report SHALL give both sets of numbers.
2. THE loader's coverage report SHALL gain sections `eu_fr_bdpm` and `eu_es_cima` with the metrics of Req 5.6 (names and occurrences mapped per step, products fully mapped, multi-ingredient products fully mapped, ambiguous and unsplit names, top 50 unmapped names), homeopathic products left out. THE FAERS builder's coverage report (`data-pipelines` Req 15.2) SHALL keep its metrics and SHALL use the Phase 2 ladder in `en` mode.
3. THE report SHALL list the number of names whose result changed between baseline and after, by kind: unmapped to mapped, unmapped to ambiguous, mapped to ambiguous, mapped to a different key, mapped to unmapped. A name that was `mapped` SHALL NOT change to a different key or to unmapped; each such case, and each mapped-to-ambiguous case, SHALL be listed with counts and handled in the review before the rule data is accepted.
4. THE targets are reported, not gates (as DP22): BDPM and Nomenclátor ≥ 80 % of ingredient occurrences mapped (non-homeopathic), FAERS ≥ 86 % of occurrences (84.0 % today; the biologic suffix adds 1.8 points and the acid rows about 0.4, so the target needs both rules), TİTCK and openFDA not lower than the baseline snapshot of 2026-11-08 (84.6 % of TİTCK occurrences; 93.3 % of openFDA Rx products fully mapped; the Phase 1 task 9 figures were 83.9 % and 92.6 %, before the synonym review). A missed target SHALL be reported with its cause.

### Requirement 14: Imipenem *(Phase 2; follow-up from `cascade-engine`; owner decision 2026-11-08: option (b), design §19 O1)*
**User story:** As the cascade engine, I need imipenem recognised as a carbapenem for PIPC row 58, without a combination code being treated as an ingredient code.

#### Acceptance criteria
1. THE system SHALL NOT use `J01DH51` ("imipenem and cilastatin", the only WHO code that names imipenem) as an ingredient code of imipenem without an explicit, reviewed, key-specific exception (Req 5.2 stays the rule). *(Finding, 2026-11-08: the WHOCC page of J01DH, checked that day, lists no code for imipenem alone; its only entry is the combination code J01DH51 with the note "Refers to imipenem". The follow-up of 2026-11-07 assumed that a separate ingredient-level carbapenem code could be found; none exists, and a stand-in code of another carbapenem would be a proxy, which the owner's standing rule forbids.)*
2. *(Owner decision 2026-11-08: option (b).)* THE system SHALL give imipenem a curated Janus key (`J2`, `data/janus_ingredients.csv`) and SHALL let the one combination code `J01DH51` reach `rule_input` for that key only, through a reviewed file `data/component_codes.csv` with one row per (key, code) pair (key, code, evidence, WHOCC URL and lookup date, reviewer note). The pair SHALL be recorded in the dataset (`res_component_code`), selected as `atc_selection = component_code`, and cited to the source `janus_curated`. `J01DH51` SHALL stay a combination code everywhere else: the combination classifier, the leak guard and the engine's input guard keep refusing it for every other ingredient, and no other combination code gets this treatment unless a row of the reviewed file names it. The loader SHALL refuse a row whose code is not a combination code of the dataset, whose key is unknown, with a repeated pair, an empty note or a missing WHOCC lookup date.
   - Until the key and file are loaded (before task 27), imipenem products resolve as today: `unmapped`, reason `no_ingredient_key`, shown as "cannot be checked".
3. Cilastatin SHALL NOT receive a carbapenem code, and a test SHALL show that no combination code other than the listed pairs reaches `rule_input` or the engine, for any ingredient (design P48).

## Properties to test (PBT candidates)
- *(Owner decisions 2026-11-07.)* Homeopathic units are detected exactly and a homeopathic product never contributes to a cascade finding; curated Janus keys keep their own codes and cite their source. (Req 11)
- Parsing is invariant to separator style: FNC1 form and parenthesised form of the same data yield identical results. (Req 1.1)
- Any GTIN with a corrupted check digit is rejected. (Req 1.2)
- Round trip: building a GS1 string from (GTIN, expiry, lot, serial) and parsing it returns the same GTIN and expiry. (Req 1.1, 1.3)
- NDC normalisation: all hyphenated forms of the same NDC normalise to the same canonical value. (Req 3.2)
- **Decomposition invariance:** a combination product (A+B) yields the same ingredient set as the two single-ingredient products A and B. (Req 5.1)
- Salt normalisation is idempotent (normalising twice equals normalising once). (Req 5.3)
- No resolution output passes a combination ATC code as an ingredient code. (Req 5.2)
- Resolving the same code twice against the same source version returns identical results. (Req 7.3)
- Added in refinement:
  - For any expiry YYMMDD, DD = 00 gives the last day of the month, valid dates round-trip, impossible dates are rejected, and the century follows the GS1 rule. (Req 1.3)
  - For any element string with serial and lot, neither value appears in the response, the logs or the database. (Req 1.4, 8.3)
  - For any 10-digit NDC in any layout, its NDC GTIN extracts back to the same 10 digits, and the candidate layouts contain the original. (Req 3.1)
  - For any NDC input form (10 or 11 digits, hyphenated or not, with label prefixes), the canonical 11-digit form is the same; malformed inputs are rejected. (Req 3.2)
  - For any source with duplicate product keys, a lookup returns exactly all rows with that key, in a stable order, never fewer. (Req 2.1, 3.1, 6.2)
  - A name-only row is never returned by a barcode lookup and is always found by a search for its exact product name. (Req 2.3)
  - Name search gives the same results for case, Turkish dotted/dotless i and diacritic variants of a query, and its ranking does not depend on the order of source rows. (Req 2.4, 3.3)
  - Ingredient mapping takes the most specific matching step, never chooses among several keys, and does not depend on the order of the Wikidata rows. (Req 5.3)
  - Every emitted ingredient ATC code is a well-formed 7-character code that is a code of that ingredient key; malformed published codes are never emitted. (Req 5.1)
  - Every unmapped ingredient is kept in the list with a reason and contributes no ATC code. (Req 5.4)
  - For any US product with mapped routes, every selected code is allowed for one of its routes; if none is allowed the ingredient is unmapped; with no mapped route all codes are kept and marked not route-confirmed. (Req 5.1, 5.4, owner decision DP20)
  - "Not found" is returned only when the searched sources are loaded; otherwise the API answers 503. (Req 6.2)
  - Every field in a result references a source version that belongs to the result's dataset version. (Req 7.2)
  - With no override, every enabled adapter whose parser accepts the GTIN is asked; with an override, only that adapter is asked. (Req 1.5)
  - Resolution routes leave the database and the file system unchanged and log no input value. (Req 8)
  - A failed or interrupted load leaves the previous dataset version serving unchanged; the dataset version is a function of its inputs. (Req 9.2, 9.4)
- *(Phase 2 refinement, 2026-11-08; numbered P27–P50 in design §17.)*
  - A GTIN-14 is a French CIP13 key exactly when it matches `^0(3400[0-9]{9})$` with a valid check digit, and the key is its last 13 digits. (Req 4.1)
  - For any source with duplicate or name-only French presentations, a CIP13 lookup returns exactly the rows with that code in stable order; name-only rows are never returned for a code and are found by name. (Req 4.1)
  - The ingredient list of a BDPM presentation takes `FT` names before `SA` names per link, in file order, and accounts for every composition line. (Req 5.8)
  - For any generated Nomenclátor and scan, the Spanish candidates come from the first applicable step of the order of trust only, with the matching `matched_by`; shared NTIN/GTIN values return every presentation; a table hit wins over the digits of the NTIN. (Req 4.2)
  - With the network blocked, every resolution route still answers; the request path imports no HTTP client. (Req 4.2, 7.1)
  - A German-prefix GTIN gives the `no_open_product_database` notice, never a German candidate (only exact table hits of French or Spanish data), and never a "not found" statement for Germany. (Req 4.3, 6.2)
  - Ingredient labels in de/fr/es are found by an `EU` or unscoped search under case, diacritic and Turkish-i variants, are not returned by a `TR` or `US` search, and English/INN labels are found from every region. (Req 4.4)
  - Language name functions are idempotent and never empty for every language; for `tr` and `en` and names without a Phase 2 word they equal the frozen Phase 1 functions. (Req 12.1, 5.7)
  - A name made of a known base and any salt, hydrate and connector words of its language, in the language's word order, gives the base's result; a name made only of such words is unchanged; counter-ion substances stay apart. (Req 12.2–12.4)
  - The anion-acid step lands only on existing keys, never changes a name an earlier step maps, and the table loader refuses bad rows. (Req 12.6, 12.7)
  - The biologic-suffix step maps `base-XXXX` to the base's key exactly when the suffix is a hyphen and four letters and the base maps to one key by a label step; it changes nothing else. (Req 12.8)
  - A name made of one known ingredient and salt or connector words is never an unsplit combination; two known ingredients still are. (Req 12.12)
  - A part of a combination string is never mapped without a label, synonym or table hit. (Req 12.9)
  - A BDPM product is homeopathic exactly when a substance name carries the homeopathic marker or a strength is in homeopathic units; such products never contribute to a finding or to coverage. (Req 12.10, 5.11, 11.1)
  - French route selection keeps only allowed codes per route, never falls back, and uses `all_codes` when no route is mapped. (Req 5.9)
  - The Nomenclátor's published ATC selects like a TİTCK code, and a multi-ingredient product's code is never an ingredient code. (Req 5.10, 5.2)
  - Properties P5, P7, P17, P18, P19, P20, P21 and P22 of Phase 1 hold over French and Spanish sources as well as TİTCK and openFDA ones. (Req 5, 6, 7, 10)
  - Coverage numbers equal an independent recount, leave out homeopathic products, and the before/after comparison lists every changed name by kind; a mapped name never changes key. (Req 13)
  - The dataset version changes with every Phase 2 rule file and EU source version and with nothing else. (Req 9.8)
  - Imipenem matches the carbapenem class only through its one reviewed component-code pair; cilastatin never does; for any other ingredient and any other combination code the guards still refuse. (Req 14)
  - Any element string with AI (21), in either form and any position, is rejected with 422 `gs1_serial_not_accepted` and nothing is looked up; AI (712) values of 7 digits are kept, others dropped. (Req 1.1, 1.4)
