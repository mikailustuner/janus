# Requirements: Drug Resolution (Türkiye · European Union · United States)

> Draft seed. Refine with Kiro, then let Kiro generate `design.md` and `tasks.md`.

## Introduction
Turn what the user scans, photographs or types — in Türkiye, the EU or the US — into a precise list of **active ingredients**, each with its own ATC code (and RxCUI and Wikidata id where available), so every later component works on ingredients, not brand names or combination codes.

## Glossary
- **GS1 element string:** decoded DataMatrix content with Application Identifiers (01) GTIN, (21) serial, (17) expiry, (10) lot.
- **RegionAdapter:** the interface each region implements: `parse(code) → product key`, `lookup(product key) → product + ingredient names`, plus its source name and version date.
- **Ingredient key:** the shared cross-region identity of an active ingredient: Wikidata item id, with its ATC code(s) (P267) and RxNorm CUI (P3345).
- **Salt normalisation:** removing salt/ester words from an ingredient name ("amlodipin besilat" → "amlodipin"; "metformin hcl" → "metformin") before matching.
- **Combination ATC:** an ATC code that describes a combination product (e.g. `C09BB03`, ACE inhibitor + calcium-channel blocker).

## Requirements

### Requirement 1: Parse GS1 DataMatrix content
**User story:** As a caregiver, I want to scan the code on a medicine box so that the exact product is identified without typing.

#### Acceptance criteria
1. WHEN the client submits a GS1 element string THE system SHALL extract AI (01), (21), (17) and (10), supporting both FNC1/GS-separated and parenthesised forms.
2. WHEN AI (01) is present THE system SHALL validate the GTIN-14 check digit and reject invalid codes with a clear error.
3. WHEN AI (17) is present THE system SHALL parse it as an expiry date (YYMMDD, where DD = 00 means end of month).
4. THE system SHALL NOT require serial or lot numbers and SHALL NOT store them.
5. WHEN a GTIN is decoded THE system SHALL determine the candidate region adapter(s) from the GTIN structure and SHALL let the user override the region.

### Requirement 2: Türkiye adapter
#### Acceptance criteria
1. WHEN a GTIN-14 starts with "0" and the remaining 13 digits match a row in the current TİTCK list THE system SHALL return product name, all active ingredients and the list version date.
2. THE system SHALL refresh the TİTCK list weekly at runtime and SHALL NOT commit the list to the repository.

### Requirement 3: United States adapter
**User story:** As a caregiver in the US, I want my parent's medicines recognised even though they come in pharmacy vials.

#### Acceptance criteria
1. WHEN a GTIN encodes an NDC THE system SHALL extract the NDC and resolve it via the openFDA NDC directory.
2. WHEN the user enters or the on-device OCR reads an NDC from a pharmacy label THE system SHALL normalise 10-digit NDC formats (4-4-2, 5-3-2, 5-4-1) and resolve it.
3. WHEN only a drug name is available THE system SHALL return ranked RxNorm candidates for confirmation.

### Requirement 4: European Union adapters
#### Acceptance criteria
1. WHEN a code resolves to a French CIP13 THE system SHALL resolve it with the current BDPM files (presentations → specialty → composition) and record the BDPM update date.
2. WHEN a code resolves to a Spanish national code THE system SHALL resolve it with the AEMPS CIMA API and record the response date.
3. WHEN a code belongs to a country without an open product-code database (e.g. Germany) THE system SHALL say so and offer OCR or name search; it SHALL NOT guess a product.
4. Name search for EU users SHALL accept ingredient names in German, French and Spanish (and English/INN) through the ingredient key.

### Requirement 5: Ingredient decomposition and normalisation (all regions)
**User story:** As the cascade engine, I need every ingredient as its own ATC code so that no cascade is missed in a combination product.

#### Acceptance criteria
1. WHEN a product contains several active ingredients THE system SHALL return each ingredient separately with its own ingredient-level ATC code.
2. THE system SHALL NOT pass a combination ATC code to the cascade engine as an ingredient code.
3. WHEN mapping a name to an ingredient key THE system SHALL apply salt normalisation and multilingual synonyms from the Wikidata extract.
4. WHEN an ingredient cannot be mapped to an ATC code THE system SHALL mark it `unmapped`, show it to the user, and exclude it from rule matching with a visible notice.
5. WHEN an ingredient key is found THE system SHALL attach RxCUI (via Wikidata or RxClass) where available and record when it is not.

### Requirement 6: Confirmation and OCR
#### Acceptance criteria
1. WHEN on-device OCR produces text THE client SHALL show candidates for confirmation; unconfirmed OCR results SHALL NOT be used.
2. WHEN a scanned or typed product is not found THE system SHALL return "not found" with the region and source version searched; it SHALL NOT guess.

### Requirement 7: Reliability and provenance
#### Acceptance criteria
1. THE system SHALL apply timeouts and caching to openFDA, RxNav, CIMA and Wikidata calls and SHALL degrade gracefully when they are unavailable (cached results, clearly labelled).
2. THE resolution result SHALL include the source, region and version date used for every field.

## Properties to test (PBT candidates)
- Parsing is invariant to separator style: FNC1 form and parenthesised form of the same data yield identical results.
- Any GTIN with a corrupted check digit is rejected.
- Round trip: building a GS1 string from (GTIN, expiry, lot, serial) and parsing it returns the same GTIN and expiry.
- NDC normalisation: all hyphenated forms of the same NDC normalise to the same canonical value.
- **Decomposition invariance:** a combination product (A+B) yields the same ingredient set as the two single-ingredient products A and B.
- Salt normalisation is idempotent (normalising twice equals normalising once).
- No resolution output passes a combination ATC code as an ingredient code.
- Resolving the same code twice against the same source version returns identical results.
