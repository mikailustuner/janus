# Requirements: National products, Canada (DPD) and Italy (AIFA)

> Owner request 2026-11-10. Two new product sources for the medication passport: the Health Canada Drug Product
> Database (DPD, Open Government Licence - Canada) and the AIFA open data on packs and active ingredients (Italy,
> CC BY 4.0). Scope: two pipeline jobs, the resolution tables, the passport target list, the texts in five languages.
> No cascade, memory or privacy logic changes. Expert review has not yet been done.

## Introduction
Janus resolves a scanned or typed product to ingredient codes and, in the medication passport, lists the products of
a target country that contain the same ingredients. This work adds two target countries: Canada (DIN) and Italy (AIC).
Neither is guessed: a product is listed only when every ingredient of it was mapped to a Janus ingredient code by the
existing resolution machinery; strength is called "same" only when two normalised strengths are equal; everything
else is shown as published or as "unknown".

## Glossary
- **DIN:** Drug Identification Number, eight digits, one per marketed Canadian product (`ca_din`).
- **AIC:** Italian pack code, nine digits (`it_aic`).
- **Unmapped ingredient:** an ingredient line whose published name was not mapped to exactly one Janus key.
- **Listable product:** a product with at least one ingredient line, all of them mapped.

## Requirements

### 1. Source and licence
1.1 THE SYSTEM SHALL record each source in `pipelines/sources.toml` (id `dpd`, `aifa`), in `NOTICE` (generated) and in
`.kiro/steering/data-sources.md`, with licence, publisher, attribution text, the date the licence was checked and the
official page it was checked on.
1.2 IF the official page does not state the licence recorded here, THEN that country SHALL not be loaded.
1.3 THE SYSTEM SHALL state that Janus is not endorsed by Health Canada or AIFA.

### 2. Pipelines
2.1 WHEN `ca_dpd` runs, THE job SHALL download the marketed extract `allfiles.zip` with timeouts and a generic user
agent, and read the eight tables (drug, ingred, form, route, package, ther, status, schedule).
2.2 THE job SHALL read UTF-8 strictly, keep cells as published (not trimmed) and count malformed lines.
2.3 THE job SHALL refuse a table whose column count differs from the documented one, a missing or oversized archive
member, and a `DRUG_CODE` listed twice.
2.4 A DIN is valid only when it is eight ASCII digits; otherwise the row is kept as name-only with no DIN.
2.5 THE job SHALL join tables on `DRUG_CODE`, take the status from the single current status line (else unknown).
2.6 THE job SHALL measure how many package lines carry a UPC and publish the share as a metric; no feature relies on
the UPC.
2.7 WHEN `eu_it_aifa` runs, THE job SHALL read `confezioni.csv` and `PA_confezioni.csv` (semicolon separated, header
checked, no quoting) with the same download rules.
2.8 A line with another number of cells than the header is counted as malformed and not guessed.
2.9 An AIC is valid only when it is nine ASCII digits; otherwise the pack is name-only.
2.10 THE snapshot date SHALL be the HTTP `Last-Modified` date (oldest of the files); a missing date fails by name.
2.11 Raw downloads SHALL never be committed. Both jobs write the usual hashed run and `current` pointer.

### 3. Ingredient mapping
3.1 THE SYSTEM SHALL map each ingredient name with the existing ladder (labels, spelling, salt-normalised,
anion-acid, curated synonyms) and never choose between two keys.
3.2 A name that maps to no key or to two keys SHALL stay unmapped or ambiguous, and its product SHALL stay out of
every passport listing.
3.3 Canadian names of the form `A (B)` SHALL map when `A` maps to one key and `B` maps to the same key or to none.
3.4 A single-ingredient product's own published ATC code MAY bridge a name that the ladder cannot map, per source,
only when exactly one eligible item carries that code; a combination code never feeds the bridge.
3.5 THE SYSTEM SHALL report, per source, products, products fully mapped, names mapped, and the reasons for the rest.
3.6 No Italian word list SHALL be used.
3.7 Veterinary, disinfectant and radiopharmaceutical DPD rows, homeopathic registrations and suspended AIFA packs
SHALL be left out and counted.

### 4. Products and identifiers
4.1 One prepared product per human DPD row (DIN) and per authorised, non-homeopathic AIFA pack (AIC).
4.2 Product ids SHALL not depend on file row order.
4.3 Ingredients are kept in file order with the strength as published.
4.4 THE resolution tables SHALL accept the code kinds `ca_din` and `it_aic` and the product region `CA`; Italian
products are region `EU`.
4.5 THE migration SHALL be forward-only in the repository's sense and reversible.
4.6 `ca_dpd` and `eu_it_aifa` artifacts SHALL be optional inputs of the loader: a dataset without them still loads.
4.7 Identifier coverage SHALL be reported (products with a code over products).

### 5. Strength and form
5.1 THE text shown SHALL be the published cells, trimmed and joined.
5.2 A normalised strength SHALL exist only when the source states a mass or international unit with a reference
that the existing representation can express (per unit for tablets and capsules, per mL, per g).
5.3 `UNIT` (DPD) SHALL not be read as an international unit; `%`, vial, sachet, actuation and similar SHALL give none.
5.4 No code where the source states no mass per unit, mL or g.
5.5 AIFA unit names SHALL be read from a closed table; other units give none.
5.6 THE dose-form table is owner-reviewed; no row SHALL be added for the new sources without that review. Until then
their form group is unknown.

### 6. Passport
6.1 Canada and Italy SHALL be selectable target countries; each listed product shows name, identifier, source, the
data date of the source and the attribution.
6.2 Presence SHALL be `present`, `not_available` or `unknown` as for the other sources; absence of a product is never
stated as absence of a medicine.
6.3 No product SHALL be listed with an unmapped ingredient (Property N5).
6.4 Strength is "same" only when both normalised strengths are equal (Property N1).
6.5 Status text SHALL be only what the source states.

### 7. Name search and scan
7.1 Italian products SHALL be found by name; AIFA has no GTIN, so a scan never resolves to an Italian product.
7.2 Canadian products SHALL be a passport target only: not candidates of name search, not scan results (UPC unused).
7.3 A candidate id of the Canadian source SHALL be refused with 422.
7.4 The cascade coverage report SHALL not read Canadian products.
7.5 Region `CA` is outside the three rule regions.

### 8. Deployment data path
8.1 `deploy/sync-data.sh` and `load-data.sh` SHALL need no change: they copy every artifact except TITCK and the
loader reads optional artifacts when present.
8.2 THE weekly job `deploy/titck-refresh.sh` SHALL run `ca_dpd` and `eu_it_aifa` before the reload; a failed refresh
keeps the previous run and does not stop the job.

### 9. Texts and wording
9.1 Every new string in en, tr, de, fr, es; messages are only added, never reordered.
9.2 Wording says "automated", never "AI"; nothing implies human review; the status text is "Expert review has not
yet been done".
9.3 Source and data date are shown wherever products are listed.

### 10. Tests and review
10.1 Unit and Hypothesis properties N1-N7, API tests, web unit tests, Playwright for the passport with a new target.
10.2 Automated read-only passes of the data, safety and localization reviewers; findings fixed or recorded.
