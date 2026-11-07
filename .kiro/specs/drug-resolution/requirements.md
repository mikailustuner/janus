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

## Requirements

### Requirement 1: Parse GS1 DataMatrix content
**User story:** As a caregiver, I want to scan the code on a medicine box so that the exact product is identified without typing.

#### Acceptance criteria
1. WHEN the client submits a GS1 element string THE system SHALL extract AI (01), (21), (17) and (10), supporting both FNC1/GS-separated and parenthesised forms.
   - *(Added in refinement.)* THE API SHALL accept the FNC1 form with or without the `]d2` symbology identifier, and SHALL treat the GS character and a leading FNC1 as separators only.
   - *(Added in refinement.)* IF the element string contains an Application Identifier that is not on the API's supported list THEN THE API SHALL reject it with a clear error naming the problem (not the content), and SHALL NOT guess field boundaries.
   - *(Added in refinement.)* IF an AI appears twice with different values THEN THE API SHALL reject the element string.
   - *(Added in refinement.)* WHEN the client submits only digits forming a GTIN-8, GTIN-12 (UPC-A), GTIN-13 (EAN-13) or GTIN-14 THE API SHALL treat them as AI (01) without other fields.
2. WHEN AI (01) is present THE system SHALL validate the GTIN-14 check digit and reject invalid codes with a clear error.
   - *(Added in refinement.)* IF AI (01) is missing, not 14 digits, or has a wrong check digit THEN THE API SHALL respond with HTTP 422 and SHALL NOT perform a lookup.
3. WHEN AI (17) is present THE system SHALL parse it as an expiry date (YYMMDD, where DD = 00 means end of month).
   - *(Added in refinement.)* THE API SHALL choose the century with the GS1 rule relative to the current date, and IF the month or day is impossible THEN THE API SHALL reject the expiry field while still resolving the GTIN, and say so in the result.
4. THE system SHALL NOT require serial or lot numbers and SHALL NOT store them.
   - *(Owner decision.)* The serial number identifies a single box, so it SHALL NOT leave the device: THE client SHALL send only AI (01) and, if present, AI (17) to the API. **[Client: experience spec]**
   - *(Added in refinement, defence in depth.)* IF an element string with serial (21) or lot (10) reaches the API THEN THE API SHALL drop both values inside the parser and SHALL NOT return, log or persist them; the result SHALL state only whether they were present.
5. WHEN a GTIN is decoded THE system SHALL determine the candidate region adapter(s) from the GTIN structure and SHALL let the user override the region.
   - *(Added in refinement.)* WHEN no override is given THE API SHALL ask every enabled adapter whose `parse` accepts the GTIN, order the candidates by the structural hint (GS1 prefix 868–869 → TR; NDC GTIN → US), and return the hits of all of them.
   - *(Added in refinement.)* WHEN the user gives a region override THE API SHALL use only that region's adapter.
   - *(Added in refinement.)* WHEN the structure points to a region whose adapter is not enabled in this phase (e.g. France, Spain, Germany) THE API SHALL say which region it is and that its adapter is not available yet. **[Phase 2: eu_fr, eu_es, eu_name]** for the adapters themselves.

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
2. WHEN a code resolves to a Spanish national code THE system SHALL resolve it with the AEMPS CIMA API and record the response date. **[Phase 2: eu_es]**
3. WHEN a code belongs to a country without an open product-code database (e.g. Germany) THE system SHALL say so and offer OCR or name search; it SHALL NOT guess a product. **[Phase 2: eu_name]**
4. Name search for EU users SHALL accept ingredient names in German, French and Spanish (and English/INN) through the ingredient key. **[Phase 2: eu_name]**
5. *(Added in refinement.)* Adding the EU adapters SHALL NOT change the resolution core, the result model or the cascade-engine input (Req 10).

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

### Requirement 6: Confirmation and OCR
#### Acceptance criteria
1. WHEN on-device OCR produces text THE client SHALL show candidates for confirmation; unconfirmed OCR results SHALL NOT be used. **[Client: experience spec]**
   - *(Added in refinement, server side.)* THE API SHALL return candidates and SHALL NOT mark any candidate as confirmed; confirmation is the client's.
2. WHEN a scanned or typed product is not found THE system SHALL return "not found" with the region and source version searched; it SHALL NOT guess.
   - *(Added in refinement.)* THE API SHALL return "not found" only WHEN the sources it searched are loaded; IF a needed source is not loaded THEN THE API SHALL respond with HTTP 503 `resolution_unavailable` and SHALL NOT say "not found".
   - *(Added in refinement.)* A "not found" result SHALL be HTTP 200 with an empty candidate list and the searched regions, sources and source versions.

### Requirement 7: Reliability and provenance
#### Acceptance criteria
1. THE system SHALL apply timeouts and caching to openFDA, RxNav, CIMA and Wikidata calls and SHALL degrade gracefully when they are unavailable (cached results, clearly labelled).
   - *(Added in refinement.)* In Phase 1 the request path makes no external calls: openFDA and Wikidata data come from pipeline artifacts loaded into PostgreSQL (design DP6). Any external call added later (CIMA in Phase 2; RxNav if chosen) SHALL use the `data-pipelines` HTTP policy (timeouts, retries only for idempotent requests) and a labelled cache. **[Phase 2: eu_es]** for CIMA.
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

### Requirement 10: Region adapters *(Added in refinement)*
#### Acceptance criteria
1. THE region-specific code (code parsing, product lookup, ingredient names) SHALL live behind the `RegionAdapter` interface; the resolution core, the result model and the cascade-engine input SHALL be the same for every region.
2. THE result SHALL carry, for every ingredient, its ingredient key, ingredient-level ATC codes, RxCUIs, mapping status and provenance in the same shape for every region.

## Properties to test (PBT candidates)
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
