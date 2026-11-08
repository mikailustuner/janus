# Requirements: Medication Passport (cross-border list)

> Draft seed. Refine with Kiro, then let Kiro generate `design.md` and `tasks.md`.

## Introduction
Many families live across borders (for example Turkish families in Germany), and travellers carry boxes from two countries. One person's medicine list often mixes products from Türkiye, the EU and the US under different brand names. The Passport merges them into one ingredient-level list, shows the equivalent ingredient's presence in the other regions, and lets the doctor note be written in the doctor's language. It informs; it never recommends switching products.

## Glossary
- **Ingredient key:** shared cross-region identity (Wikidata item with ATC and RxCUI) from Drug Resolution.
- **Equivalent presence:** whether a product with the same ingredient (and, where known, the same strength and dose form) exists in a region's source data.

## Requirements

### Requirement 1: Mixed-region list
**User story:** As a caregiver whose mother brings medicines from Türkiye to Germany, I want all boxes in one list so that nothing is missed.

#### Acceptance criteria
1. THE client SHALL accept items from different regions in one list and SHALL show each item's region and source.
2. WHEN two items share an ingredient key THE system SHALL flag a possible duplicate ingredient ("same active ingredient under two names") and keep both items visible.
3. Duplicate-ingredient flags SHALL be informational and SHALL NOT recommend removing an item.

### Requirement 2: Equivalents
#### Acceptance criteria
1. WHEN the user opens an item THE system SHALL show, for each other region, whether the ingredient is present in that region's source data, with the source and version date.
2. WHEN strength and dose form are known in both sources THE system SHALL show whether they match; otherwise it SHALL say they could not be compared.
3. THE system SHALL NOT present any product as interchangeable or recommend a substitute.

### Requirement 3: Language of care
#### Acceptance criteria
1. THE user SHALL choose the doctor's language (EN, TR, DE, FR, ES) independently of the interface language (see Doctor Note spec).
2. Ingredient names in the note SHALL be shown as INN plus the brand name exactly as on the patient's box.

## Properties to test (PBT candidates)
- Merging lists is order-independent and idempotent (adding the same item twice changes nothing but the count).
- Two items are flagged as duplicates if and only if they share an ingredient key.
- Equivalent-presence results never assert a strength/form match when either side is unknown.
- No Passport output contains substitution language in any supported language.

## Open items from collective-memory (2026-11-08)
- The merged list's ingredient keys (Wikidata `Q…` or Janus `J<n>`) are the keys of `POST /memory/combination` (2 to 20 keys,
  default scope `any`) and `POST /memory/regions`. The response says which level it shows (`combination`, `pairwise`,
  `single`), that the counts are lower bounds for sets, and that the comparison group includes reports naming only some of
  the medicines. It never says the medicines interact or recommends a change. Ingredient order and duplicates in the list
  change nothing.
