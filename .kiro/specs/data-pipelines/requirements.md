# Requirements: Data Pipelines (ETL)

> Refined 2026-11-07 for Phase 1. Requirements 1–4 apply to every pipeline. Requirements 5–9
> cover the five Phase 1 pipelines. Requirement 10 keeps the other pipelines for later phases.
>
> **Refined 2026-11-08 for Phase 2.** Requirements 11–13 cover the `eu_fr_bdpm`, `eu_es_cima` and
> `faers` pipelines. Requirement 14 adds what the core needs for FAERS-sized output. Requirement 15
> covers the step that turns the FAERS artifact into the DuckDB count tables that
> `collective-memory` reads (it maps through `drug-resolution` ingredient keys, so its code is in
> `apps/api`, not in `pipelines/`). No original criterion or property was dropped; additions are
> marked *(Added in Phase 2 refinement)*. Facts behind the requirements were checked against the
> live sources on 2026-11-08 (design §10).

## Introduction
Every external source enters Janus through a pipeline that records its version, license and update cadence, validates its shape, and produces read-only artifacts for the API. Pipelines are the place where licensing rules are enforced (what may be committed, cached or only fetched at runtime).

## Glossary
- **Pipeline:** one ETL job for one source (e.g. `titck`). Runs from the command line.
- **Run:** one execution of a pipeline. Has a run id and ends as `succeeded`, `needs_review` or `failed`.
- **Artifact:** the normalised output of a run (rows plus manifest), read-only after it is written.
- **Manifest:** the provenance record stored with an artifact (see Requirement 1).
- **Current artifact:** the artifact the API reads for a source. Only a promoted run becomes current.
- **Promote:** make a run's artifact the current artifact in one atomic step.
- **Storage rule:** per source, one of `runtime_only` (fetch at runtime, never commit), `cache` (may be stored outside the repository), `commit` (may be committed under `data/`), `separate_package` (own license package).
- **Source registry:** one machine-readable list of all sources Janus uses or cites, with license, terms, storage rule and cadence.
- **Source hash:** SHA-256 of the downloaded bytes.
- **Content hash:** SHA-256 of the artifact's rows in a canonical serialisation, independent of file format and input row order.
- **Expected schema:** the required columns or fields, with types, that a pipeline needs from its source.
- **Data directory:** the directory for runtime and cached artifacts, set by `JANUS_DATA_DIR`. It is outside version control.

## Sources and cadence
| Pipeline | Source | Cadence | Storage rule | Phase |
|---|---|---|---|---|
| `titck` | TİTCK licensed products list | weekly | fetch at runtime, never commit (`runtime_only`) | **1** |
| `us_ndc` | openFDA NDC directory | weekly | cache allowed (CC0) | **1** |
| `eu_fr_bdpm` | BDPM files (`CIS_bdpm`, `CIS_CIP_bdpm`, `CIS_COMPO_bdpm`) | monthly | cache allowed (licence ouverte, keep source + update date, no alteration) | 2 — Req 11 |
| `eu_es_cima` | AEMPS CIMA REST / nomenclátor (bulk: Nomenclátor de prescripción, updated daily) | weekly | cache allowed with attribution | 2 — Req 12 |
| `wikidata_ingredients` | Wikidata (ATC P267, RxNorm P3345, multilingual labels) | monthly | cache allowed (CC0) | **1** |
| `onsides` | OnSIDES data release | per release | cache allowed (CC BY 4.0) | later |
| `faers` | FAERS quarterly ASCII files (FDA now publishes them as "AEMS", formerly FAERS) | quarterly | cache allowed (CC0) | 2 — Req 13, 15 |
| `pipc` | PIPC Table 1 (Europe PMC XML) | per release | commit allowed (CC BY 4.0) | **1** |
| `retractions` | Crossref update notices for every DOI in `evidence` | weekly | cache allowed | **1** |
| `canon` | OpenITI Canon Book 2 | per release | separate CC BY-NC-SA data package | 4 |

## Requirements

### Requirement 1: Provenance
**User story:** As a reviewer of a Janus finding, I want every data row traceable to the source file and run it came from, so that I can check where it came from and how old it is.

#### Acceptance criteria
1. Every pipeline run SHALL record source URL, license, snapshot/version date, row counts and a content hash.
   - WHEN a run finishes, with any outcome, THE pipeline SHALL write a manifest with: run id, pipeline name, source id, source URL(s), license, region (TR, EU, US or none), snapshot/version date as published by the source, retrieval time (UTC), source hash, content hash, row counts (input rows, output rows, excluded rows by reason), expected-schema version, code version (git commit) and outcome.
   - WHEN a source publishes no version date (e.g. Wikidata) THE pipeline SHALL use the retrieval time as the snapshot date and SHALL record that it did so.
2. Every artifact SHALL be traceable to the run that produced it.
   - THE pipeline SHALL store every artifact under its run id, and every artifact file SHALL carry that run id in its manifest.
   - THE pipeline SHALL never modify an artifact after its run has finished.
3. THE pipeline SHALL compute the content hash so that the same normalised rows give the same hash regardless of input row order or output file format.
4. WHEN a run succeeds THE pipeline SHALL emit a source-level evidence record (source URL, license, region, snapshot date, run id) in the form the `evidence` table loader consumes.
5. THE pipeline SHALL account for every input row: input rows SHALL equal output rows plus excluded rows, and every excluded row SHALL have a recorded reason.

### Requirement 2: Validation
#### Acceptance criteria
1. WHEN a source file's columns or schema differ from the expected shape THE pipeline SHALL fail loudly and keep the previous artifact.
   - IF a required column or field is missing, renamed or of the wrong type THEN THE pipeline SHALL end the run as `failed`, exit with a non-zero status, name the mismatched columns or fields in its error output, and leave the current artifact unchanged.
   - Extra columns not in the expected schema SHALL NOT fail the run; THE pipeline SHALL list them in the manifest.
2. WHEN row counts change by more than a configured percentage between runs THE pipeline SHALL flag the run for review.
   - WHEN a run's output row count differs from the current artifact's output row count by more than the pipeline's threshold (default 10%) THE pipeline SHALL end the run as `needs_review` and SHALL NOT promote it.
   - WHEN a maintainer promotes a `needs_review` run explicitly THE pipeline SHALL record who promoted it and when, in a promotion record next to the manifest (the manifest itself is not modified, Req 1.2).
   - WHEN no current artifact exists THE pipeline SHALL skip the row-count check.
3. THE `titck` pipeline SHALL report the share of rows with an ATC code and the number of multi-ingredient products.
   - THE `titck` manifest SHALL also report the number of duplicate barcodes and the number of rows excluded for an invalid barcode.

### Requirement 3: Licensing enforcement
#### Acceptance criteria
1. THE pipeline SHALL refuse to write a source marked "fetch at runtime, never commit" into the repository's `data/` directory.
   - IF the output path of a `runtime_only` source resolves (after resolving `..` and symbolic links) to a location inside the repository's `data/` directory, or anywhere inside the repository that is not ignored by git, THEN THE pipeline SHALL refuse to write, fail the run, and write nothing.
   - THE pipeline SHALL refuse to start a run for a source that is missing from the source registry.
2. THE NOTICE file SHALL be generated from the pipelines' license records.
   - THE NOTICE generator SHALL build `NOTICE` from the source registry, including sources that are cited only and not ingested.
   - IF an artifact manifest names a source that is not in the source registry THEN THE NOTICE generator SHALL fail.
   - THE NOTICE generator SHALL produce byte-identical output for the same registry, and CI SHALL fail WHEN the committed `NOTICE` differs from the generated one.

### Requirement 4: Reliability
#### Acceptance criteria
1. External downloads SHALL use timeouts and idempotent retries.
   - THE pipeline SHALL set a connect timeout and a read timeout on every external request.
   - WHEN a request fails with a connection error, a timeout, HTTP 429 or HTTP 5xx THE pipeline SHALL retry only idempotent requests (GET, HEAD), at most 3 times, with increasing delay, and SHALL honour a `Retry-After` header.
   - THE pipeline SHALL NOT retry HTTP 4xx responses other than 429.
   - THE pipeline SHALL keep within each source's published rate limit (openFDA 240 requests/minute; RxNav 20 requests/second; Crossref public pool 5 single-record requests/second, 1 concurrent request).
   - THE pipeline SHALL identify itself with a User-Agent that includes the contact from `JANUS_CONTACT`, which is either an http(s) URL or an email address. No contact is assumed or derived when it is unset.
   - WHEN a source's usage policy requires contact information (Wikidata, Wikimedia User-Agent policy) and `JANUS_CONTACT` is unset THE pipeline SHALL refuse to start the run.
   - THE pipeline SHALL send Crossref's `mailto` parameter only WHEN `JANUS_CONTACT` is an email address; otherwise it SHALL use Crossref's public pool without `mailto`.
2. A failed pipeline SHALL never leave the API without a usable artifact.
   - THE pipeline SHALL write a new artifact to a staging location and promote it only after validation passes, by an atomic switch of the current-artifact pointer.
   - IF a run fails or is interrupted at any step THEN the current artifact SHALL be the one that was current before the run.
   - WHEN no artifact has ever been promoted for a source THE pipeline SHALL report the source as unavailable rather than produce an empty artifact.

### Requirement 5: `pipc` pipeline (Phase 1)
**User story:** As the cascade engine, I need the 65 PIPC cascades as structured rows with a locator for each, so that every rule cites its row in the source table.

#### Acceptance criteria
1. WHEN run THE `pipc` pipeline SHALL fetch the full-text XML of PMC12712104 from Europe PMC and parse Table 1.
2. THE pipeline SHALL output one row per cascade with: physiological system, kind (drug class or individual drug), Drug A, adverse event, Drug B, and its row position in Table 1.
3. IF the parsed table does not contain exactly 65 cascades THEN THE pipeline SHALL fail the run.
4. WHEN a cascade's cells are split across more than one table row in the XML THE pipeline SHALL merge them into one cascade.
5. THE pipeline SHALL keep the cell text as published, changing only whitespace.
6. WHEN the run succeeds THE pipeline SHALL write `data/pipc.csv` and, next to it, a metadata file with source URL, DOI (10.1007/s41999-025-01215-x), PMCID, license (CC BY 4.0), attribution text, retrieval date and content hash.
7. THE pipeline SHALL NOT map Drug A or Drug B to ATC codes; that mapping is curated in the `cascade-engine` spec.

### Requirement 6: `titck` pipeline (Phase 1)
**User story:** As the Türkiye adapter, I need barcode → product → ingredients → ATC from the current TİTCK list, so that a scanned box resolves without OCR.

#### Acceptance criteria
1. WHEN run THE `titck` pipeline SHALL fetch the newest weekly "Ruhsatlı Beşeri Tıbbi Ürünler Listesi" file at runtime, or read a local file given on the command line, and record its publication date.
2. THE pipeline SHALL read the sheet "RUHSATLI ÜRÜNLER LİSTESİ", locate the header row by its column names, and require the columns BARKOD, ÜRÜN ADI, ETKİN MADDE and ATC KODU.
3. THE pipeline SHALL output for each product row: barcode (13 digits), product name, the active-ingredient text as published, the list of individual ingredient names split from it, the ATC code as published, and the suspension status.
4. ~~WHEN a barcode is not 13 digits or fails the EAN-13 check digit THE pipeline SHALL exclude the row with the reason `invalid_barcode`.~~ *(Changed 2026-11-07 by owner decision, `drug-resolution` DP9.)* WHEN a barcode is not 13 digits or fails the EAN-13 check digit THE pipeline SHALL output the row as a name-only row (barcode null, `name_only` true), SHALL NOT repair or keep the invalid value, and SHALL report the number of name-only rows. Such rows are reachable by name search only.
5. WHEN two or more rows share a barcode THE pipeline SHALL keep all of them and report the count; THE pipeline SHALL NOT choose one.
6. WHEN the active-ingredient text lists several ingredients THE pipeline SHALL split it into individual names and SHALL preserve every non-separator character of the original text.
   - *(Added 2026-11-07, owner decision `drug-resolution` DP10.)* A separator inside parentheses SHALL NOT split the text (e.g. `inaktif çocuk felci (tip 1, 2, 3)` is one name).
7. THE pipeline SHALL store its artifacts only in the data directory and SHALL NOT commit any part of the list (Requirement 3.1).
8. THE pipeline SHALL NOT decide which ATC codes are combination codes; that is done in the `drug-resolution` spec.

### Requirement 7: `wikidata_ingredients` pipeline (Phase 1)
**User story:** As drug resolution in every region, I need one shared ingredient key with ATC codes, RxNorm CUIs and names in five languages.

#### Acceptance criteria
1. WHEN run THE pipeline SHALL query the Wikidata Query Service for every item with an ATC code (P267) and output: QID, all ATC codes, all RxNorm CUIs (P3345), and labels and aliases in en, tr, de, fr and es.
2. THE pipeline SHALL record the query text's hash and the retrieval time as the snapshot date.
3. WHEN a query would exceed the service's time limit THE pipeline SHALL split it into smaller queries and merge the results.
4. THE pipeline SHALL output each QID once, with at least one ATC code.

### Requirement 8: `us_ndc` pipeline (Phase 1)
**User story:** As the United States adapter, I need the openFDA NDC directory locally, so that NDC lookups do not depend on the API being reachable.

#### Acceptance criteria
1. WHEN run THE pipeline SHALL read the openFDA download index, download the NDC directory bulk file it lists, and record the index's export date as the snapshot date.
2. IF the number of parsed records differs from the record count in the download index THEN THE pipeline SHALL fail the run.
3. THE pipeline SHALL output for each product: product NDC, package NDCs, product type, brand and generic name, active ingredients with strength, RxCUIs, and marketing end date, as published.
   - *(Added 2026-11-07, owner decision `drug-resolution` DP20.)* THE pipeline SHALL also output the route(s) of administration and the dosage form, as published.
4. THE pipeline SHALL NOT normalise NDC formats; normalisation is done in the `drug-resolution` spec.

### Requirement 9: `retractions` pipeline (Phase 1)
**User story:** As evidence integrity, I need the retraction status of every DOI Janus cites, refreshed weekly.

#### Acceptance criteria
1. WHEN run THE pipeline SHALL collect every DOI from the evidence records available (in Phase 1: the evidence records emitted by pipelines, and the DOIs of the curated paper list `data/evidence_papers.csv`; *added 2026-11-07, `evidence-integrity` DP13*) and normalise each DOI (lower case, without `https://doi.org/` or `doi:` prefix); a DOI present in both is checked once.
2. FOR each DOI THE pipeline SHALL query the Crossref REST API and derive a status from the work's update notices (`updated-by`): `retracted`, `expression_of_concern`, `corrected` or `ok`.
3. WHEN a work has several notices THE pipeline SHALL use the most severe one (retracted > expression_of_concern > corrected), whatever their order.
4. IF a DOI is not found or the check cannot be completed THEN THE pipeline SHALL record `unknown` for that check; it SHALL NOT record `ok`.
5. IF a check cannot be completed and the last completed check of that DOI was `retracted` THEN the effective status SHALL stay `retracted`.
6. WHEN a DOI's status changes between runs THE pipeline SHALL list the change in the manifest; WHEN a status changes from `retracted` to any other status THE run SHALL end as `needs_review`.
7. THE pipeline SHALL store each raw Crossref response with its fetch time, and the notice's source (e.g. `retraction-watch`) and URL with the status.

### Requirement 10: Pipelines for later phases
#### Acceptance criteria
1. THE `eu_fr_bdpm`, `eu_es_cima`, `onsides`, `faers` and `canon` pipelines SHALL meet Requirements 1–4 and the storage rules in the sources table. Their source-specific requirements are written when their phase starts (see the Phase column).
   - *(Added in Phase 2 refinement.)* The source-specific requirements of `eu_fr_bdpm`, `eu_es_cima` and `faers` are Requirements 11, 12 and 13. `onsides` and `canon` stay open until their phase.

### Requirement 11: `eu_fr_bdpm` pipeline (Phase 2) *(Added in Phase 2 refinement)*
**User story:** As the France adapter, I need each CIP13 presentation with its product and composition exactly as the BDPM publishes them, so that a scanned French box resolves to ingredient names, with the BDPM named as source and its update date shown.

#### Acceptance criteria
1. WHEN run THE pipeline SHALL fetch `CIS_bdpm.txt`, `CIS_CIP_bdpm.txt` and `CIS_COMPO_bdpm.txt` from the BDPM download service, or read local copies given on the command line, and SHALL read each file's update date from the BDPM download page.
   - IF the update date of any of the three files cannot be read THEN THE pipeline SHALL fail the run.
   - THE snapshot date SHALL be the oldest of the three file dates (the files are updated on different days), and THE manifest SHALL list all three in `metrics.file_dates`.
2. THE pipeline SHALL read each file as tab-separated text without a header, with the published column counts (`CIS_bdpm` 12, `CIS_CIP_bdpm` 13, `CIS_COMPO_bdpm` 8), SHALL accept CRLF and LF line ends, and SHALL decode each file strictly with its own encoding: `CIS_bdpm` and `CIS_COMPO` as Windows-1252, `CIS_CIP` as UTF-8 (observed 2026-11-08).
   - IF a file cannot be decoded with its encoding, or the most common column count of a file differs from the published one, THEN THE pipeline SHALL end the run as `failed` and name the file (schema mismatch, Req 2.1). It SHALL NOT guess another encoding or replace undecodable bytes.
   - WHEN a single line has a different column count than the file's published one THE pipeline SHALL exclude it with the reason `malformed_row`.
3. THE pipeline SHALL output one row per line of `CIS_CIP_bdpm` with: CIP13, CIP7, CIS code, presentation label, presentation status, commercialisation status of the presentation and its declaration date; from `CIS_bdpm` for the same CIS: denomination, pharmaceutical form, routes, authorisation status, authorisation procedure, commercialisation status, authorisation date and holder; and the list of `CIS_COMPO` lines of that CIS in file order (pharmaceutical form, substance code, substance name, dosage, reference dosage, nature `SA` or `FT`, link number).
   - THE pipeline SHALL NOT keep price, reimbursement or other columns that Janus does not use.
4. THE pipeline SHALL keep every text value exactly as published after decoding: no trimming, case change, Unicode normalisation or correction (licence ouverte: the data must not be altered; the holder column starts with a space in the source).
5. WHEN the CIP13 is not 13 digits, does not start with `3400`, or fails the EAN-13 check digit THE pipeline SHALL output the row as a name-only row (CIP13 null, `name_only` true), SHALL NOT repair or keep the invalid value, and SHALL report the number of name-only rows (same convention as Req 6.4).
   - WHEN two or more rows share a CIP13 THE pipeline SHALL keep all of them and report the count.
6. WHEN the CIS of a presentation is missing from `CIS_bdpm` THE pipeline SHALL keep the row with empty product fields and `specialty_missing` true; WHEN a CIS has no `CIS_COMPO` line THE composition list SHALL be empty. Both SHALL be counted in the manifest.
7. THE pipeline SHALL NOT choose between the `SA` and `FT` lines of a composition, split or normalise substance names, or assign ATC codes; those decisions belong to `drug-resolution`.
8. THE manifest and the evidence source record SHALL carry the source name (base de données publique des médicaments), its URL, the snapshot date, and the licence "Licence Ouverte (Etalab)"; the downloaded files SHALL be stored under `raw/` with the run (storage rule `cache`) and SHALL NOT be committed.
9. THE manifest SHALL report: presentations, name-only rows, duplicate CIP13, rows with `specialty_missing`, CIS without composition, `FT` lines, and the share of presentations with status "Présentation active".

### Requirement 12: `eu_es_cima` pipeline (Phase 2) *(Added in Phase 2 refinement)*
**User story:** As the Spain adapter, I need every Spanish presentation with its national code, active ingredients, ATC code and GS1 product codes (NTIN and GTIN), so that a scanned Spanish box resolves from a local copy without a live call.

#### Acceptance criteria
1. WHEN run THE pipeline SHALL fetch the AEMPS Nomenclátor de prescripción archive, or read a local copy given on the command line, and SHALL require `Prescripcion.xml` and `DICCIONARIO_PRINCIPIOS_ACTIVOS.xml` in it.
   - THE snapshot date SHALL be the `listprescriptiondate` in the header of `Prescripcion.xml`; IF it is missing THEN THE pipeline SHALL fail the run.
   - THE pipeline SHALL read the XML as a stream (the file is about 190 MB), parse it with a parser that rejects external entities, and keep memory independent of the file size.
2. THE pipeline SHALL output one row per `prescription` element with: national code (`cod_nacion`, 6 digits, as published), registration number, medicine name, presentation name, the ATC code as published (display only), the active ingredients in `orden_colacion` order with dictionary name, dose and dose unit, the NTIN list, the GTIN list, route codes, commercialisation flag, registration status codes and dates, and the serialisation flag.
   - WHEN an ingredient code is missing from the ingredient dictionary THE pipeline SHALL keep the code and set the name to null.
   - WHEN a presentation has no ingredient code (512 of 30,900 on 2026-11-08) THE ingredient list SHALL be empty.
3. THE pipeline SHALL keep an NTIN or GTIN only WHEN its digits form a valid GS1 code (8, 12, 13 or 14 digits, correct check digit); other values SHALL be left out and counted as `invalid_gtin_values`.
   - WHEN an NTIN does not have the form `0847000` + 6 digits + check digit, or its embedded 6 digits differ from the row's national code, THE pipeline SHALL keep it as published and count it (`ntin_nonstandard`, `ntin_cn_mismatch`). It SHALL NOT correct it.
   - WHEN the same NTIN or GTIN is published on more than one presentation THE pipeline SHALL keep it on all of them and count the shared codes.
4. WHEN `cod_nacion` is not 6 digits THE pipeline SHALL output a name-only row (national code null) and count it.
5. THE pipeline SHALL NOT ingest the Nomenclátor's duplicate-therapy, interaction, geriatric-advice, teratogenicity, safety-note, excipient or image elements. They are AEMPS advice text that Janus has not reviewed against its medical-safety rules.
6. THE pipeline SHALL NOT call the CIMA REST API. The REST API is for the Spain adapter's request path (`drug-resolution` Phase 2, under the HTTP policy of Req 4.1).
7. WHEN the server answers HTTP 403 THE pipeline SHALL fail with a message that names the User-Agent policy (the AEMPS host rejected a generic command-line User-Agent on 2026-11-08 and accepted the pipelines' own).
8. THE manifest and the evidence source record SHALL name AEMPS (CIMA / Nomenclátor de prescripción) as source, give the snapshot date and the licence "Reutilización con cita de la fuente y de la fecha de actualización (AEMPS aviso legal; Ley 37/2007)"; the archive SHALL be stored under `raw/` (storage rule `cache`).
9. THE manifest SHALL report: presentations, name-only rows, rows with no ingredient, rows with NTIN, rows with GTIN, rows with neither, `invalid_gtin_values`, `ntin_nonstandard`, `ntin_cn_mismatch`, and the number of NTIN and GTIN values shared by several presentations.

### Requirement 13: `faers` pipeline (Phase 2) *(Added in Phase 2 refinement)*
**User story:** As Collective Memory, I need the latest public adverse-event reports as one clean row per case, with the reporting region, so that I can count reports per medicine and event.

#### Acceptance criteria
1. WHEN run THE pipeline SHALL read the FDA quarterly data extract page, take the four most recent quarters that have an ASCII file, download those ASCII archives, and record each quarter label and posting date.
   - Quarter labels SHALL be matched case-insensitively (the page links both `2025Q4` and `2026q3`).
   - IF fewer than four quarters are listed, or the four most recent are not consecutive, THEN THE pipeline SHALL fail the run. A command-line option MAY name the quarters explicitly (tests, back-fill).
   - THE snapshot date SHALL be the posting date of the newest quarter; IF the page gives none, THE pipeline SHALL use the archive's `Last-Modified` header and record that it did so.
2. THE pipeline SHALL read `DEMO`, `DRUG`, `REAC` and the `DELETE` file of each archive as `$`-delimited text with a header line, decode them strictly as UTF-8, treat `quote` characters as ordinary text, and accept CRLF and LF line ends (`DRUG` uses CRLF).
   - Required columns: `primaryid, caseid, caseversion, fda_dt, occr_country, reporter_country` in `DEMO`; `primaryid, caseid, drug_seq, role_cod, prod_ai` in `DRUG`; `primaryid, caseid, pt` in `REAC`. A missing, renamed or retyped column SHALL fail the run (Req 2.1); extra columns SHALL be listed in the manifest.
   - WHEN a line has a different field count than its header THE pipeline SHALL exclude the line with the reason `malformed_row`.
3. THE pipeline SHALL deduplicate by case: of all versions of one `caseid` in the window it SHALL keep the version with the highest `caseversion`, breaking a tie by the latest `fda_dt`, then by the highest `primaryid`.
   - THE pipeline SHALL remove every version of a `caseid` that appears in a `DELETE` file of any quarter in the window.
   - THE pipeline SHALL account for every removed report: superseded versions with the reason `superseded_version`, deleted cases with `deleted_case`; and SHALL write the removed reports (primaryid, caseid, caseversion, quarter, reason, kept primaryid where it applies) to a side table next to the artifact (Req 14.3).
   - THE pipeline SHALL NOT try to merge different cases that may describe the same event (FDA does not deduplicate them either); the manifest SHALL state that the reports are not deduplicated across cases.
4. THE pipeline SHALL output one row per kept report with: `primaryid`, `caseid`, `caseversion`, quarter, `fda_dt` as published, the raw `occr_country` and `reporter_country`, the derived `region` and `region_basis`, the drugs (`drug_seq`, `role_cod`, the active-ingredient text `prod_ai` split into its ingredient names at the `\` separator, as published) and the events (`pt`, as published, in file order).
   - THE pipeline SHALL NOT keep demographics (age, sex, weight), reporter occupation, manufacturer, literature, lot and free-text dose fields, outcomes, therapy dates or indications. Adding one needs a change to this requirement.
   - THE event terms are MedDRA Preferred Terms kept as published in FAERS; THE pipeline SHALL NOT add MedDRA hierarchy levels (SOC, HLT, LLT) or any other MedDRA table. *(Owner decision 2026-11-08.)*
   - WHEN `prod_ai` is empty THE drug SHALL be kept with an empty ingredient list and counted (127,674 of about 5.9 million drug lines in the window of 2026-11-08).
5. WHEN a `DRUG` or `REAC` line refers to a `primaryid` that is not in `DEMO` of the same archive THE pipeline SHALL exclude that line and count it as `orphan_line`.
6. THE pipeline SHALL derive the region of a report with one pure function:
   - the occurrence country is used when it is present; otherwise the reporter country; a value that is empty or `COUNTRY NOT SPECIFIED` counts as not present;
   - `TR` gives `TR`; `US` and the US territories `PR`, `GU`, `VI`, `AS`, `MP`, `UM` give `US` (FDA treats them as US; owner decision 2026-11-08); the FAERS pseudo-code `EU` and the ISO codes of the 27 EU member states give `EU` (EU-27 only: `GB`, `CH`, `NO`, `IS`, `LI` give `OTHER`); any other present value gives `OTHER`; no present value gives `UNKNOWN`;
   - `region_basis` records `occr_country`, `reporter_country` or `none`.
7. THE manifest SHALL record the region rule it applied (`metrics.region_rule`: basis order, territories mapped to US, EU-27 list, version) and SHALL report: reports per quarter and per region, kept and removed counts by reason, the share of reports with region `UNKNOWN`, reports with no drug and with no event, and the share of kept reports whose `caseversion` is greater than 1.
8. THE manifest and the evidence source record SHALL describe the data as spontaneous reports that are not deduplicated across cases, and the licence as CC0 / public domain as stated by FDA; the archives SHALL be stored under `raw/` with the run (storage rule `cache`).
9. WHEN the number of output reports differs from the current artifact's by more than 15 % THE run SHALL end as `needs_review` (the window moves by one quarter per run; Req 2.2 with a job-specific threshold).

### Requirement 14: Large outputs in the core *(Added in Phase 2 refinement)*
**User story:** As a maintainer, I want the FAERS run to finish on an ordinary laptop, without changing the hash rules every other pipeline relies on.

#### Acceptance criteria
1. WHEN a job produces its rows as a stream THE core SHALL compute the content hash without holding all rows or all canonical lines in memory, and SHALL give exactly the hash that Req 1.3 gives for the same rows held in memory.
2. WHEN a job produces its rows as a stream THE core SHALL write `rows.parquet` in batches and SHALL still stage, validate, hash and promote the run the same way (Req 2, 4.2).
3. THE core SHALL let a job add named side tables (for example the removed reports of Req 13.3). THE core SHALL write them next to `rows.parquet` in the same staging step, record their file name, row count and SHA-256 in the manifest, and never change them after the run (Req 1.2). Side tables SHALL NOT be part of the content hash.
4. THE FAERS run over four quarters (about 1.5 million reports) SHALL stay within 4 GiB of peak memory; the checkpoint task SHALL measure and report the peak.

### Requirement 15: FAERS counts for Collective Memory *(Added in Phase 2 refinement)*
**User story:** As Collective Memory, I need report counts per ingredient, event and region in a read-only DuckDB file, so that the statistics can be computed without reading 1.5 million reports at request time.

#### Acceptance criteria
1. WHEN run THE builder SHALL read the current `faers` artifact, SHALL refuse it IF its outcome is not `succeeded` (or a promoted `needs_review`) or its rows do not hash to the manifest's content hash, and SHALL leave the current counts file unchanged in that case.
2. THE builder SHALL map each distinct ingredient name of the artifact to an ingredient key with the `drug-resolution` name ladder in its non-Turkish mode (same salt and spelling rules, same synonym and curated files, same Wikidata artifact), and SHALL record the resolution dataset version and the rules version it used.
   - *(Phase 2, 2026-11-08.)* "Non-Turkish mode" is the `en` language of the `drug-resolution` name functions (Phase 2 Req 12.1), which includes the reviewed salt and ester words, the anion-acid table and the biologic-suffix step once the owner has accepted them; the builder passes the language explicitly.
   - ONLY names with status `mapped` SHALL contribute to counts. `ambiguous`, `unsplit` and unmapped names SHALL NOT be counted; they SHALL be listed with the number of reports they occur in, and the builder SHALL write a coverage report (share of ingredient occurrences mapped per exposure scope, steps used, top 50 unmapped names).
3. THE builder SHALL use two exposure scopes: `suspect` (roles `PS`, `SS`, `I`) and `any` (the suspect roles and `C`). Role `DN` and any other role code SHALL be excluded from both and counted.
4. THE builder SHALL count distinct reports: an ingredient counts once per report however many drug lines or combination strings name it, and an event counts once per report.
5. THE builder SHALL write a DuckDB file with: report facts (report id, case id, quarter, region), report–ingredient and report–event facts, and these count tables: total reports per region; reports per (ingredient key, region, scope); reports per (event, region); reports per (ingredient key, event, region, scope) for every pair with at least one report. From them the 2×2 table of `collective-memory` follows: a = pair count, b = ingredient count − a, c = event count − a, d = N − ingredient count − event count + a, with N, the ingredient counts and the event counts all taken over reports with a mapped ingredient (`reports_mapped`).
   - THE regions SHALL be `TR`, `EU`, `US`, `OTHER`, `UNKNOWN` and `ALL`; for every table the five regional counts SHALL add up to the `ALL` count.
   - Column names SHALL say `reports`, never `people` or `patients`.
   - THE metadata SHALL carry the notice "MedDRA® the Medical Dictionary for Regulatory Activities terminology is the international medical terminology developed under the auspices of ICH. MedDRA® trademark is registered by IFPMA on behalf of ICH." and the statement that event terms are Preferred Terms as published in FAERS; no MedDRA hierarchy table SHALL be written. *(Owner decision 2026-11-08.)*
   - *(Owner decision 2026-11-08.)* The primary denominator N of the 2×2 table is the number of deduplicated reports with at least one mapped ingredient (a report whose drugs did not map could hide the drug of interest and fall into the "other drugs" cells). Therefore the primary ingredient, event and pair counts count only those reports. THE file SHALL also store, as a sensitivity figure, the number of all deduplicated reports and the event counts over all reports (`reports_all`), so that the 2×2 table can be recomputed with N = all reports.
6. THE file SHALL carry a metadata table with: build id, `faers` run id, snapshot date and quarters, resolution dataset version, rules version, code version, row counts and the SHA-256 of each table's rows exported in sorted order (independent of row order).
7. THE builder SHALL give the same tables, and the same table hashes, for the same inputs, whatever the order of the reports in the artifact.
8. THE builder SHALL write the file to a staging location and switch a `current` pointer in one atomic step; the API SHALL open the file read-only. A failed or interrupted build SHALL leave the previous file current (Req 4.2).
9. THE builder SHALL log run id, step, counts and outcome only; no medicine or event names (privacy rule: no health data in logs; FAERS names are public but the log rule is uniform).

## Properties to test (PBT candidates)
- Re-running a pipeline on the same input produces the same content hash. (Req 1.1, 1.3)
- A schema-mismatched input never replaces the previous artifact. (Req 2.1)
- The generated NOTICE contains an entry for every source used by any artifact. (Req 3.2)
- Added in refinement:
  - Permuting input rows does not change the content hash. (Req 1.3)
  - Every input row is either in the output or excluded with a reason. (Req 1.5)
  - A run is flagged for review exactly when the row-count change exceeds the threshold. (Req 2.2)
  - The `titck` metrics equal a direct recount of the artifact. (Req 2.3)
  - A `runtime_only` source is never written inside the repository's `data/` directory, however the path is written. (Req 3.1)
  - Only idempotent requests are retried, and never more than the limit. (Req 4.1)
  - After any sequence of runs with failures at any step, the current artifact is complete and valid. (Req 4.2)
  - `pipc` parsing returns exactly the generated cascades, in order, with split rows merged. (Req 5.2–5.4)
  - Splitting TİTCK ingredient text keeps every non-separator character. (Req 6.6)
  - Wikidata merging does not depend on result order and outputs each QID once. (Req 7.3, 7.4)
  - The retraction status is the most severe notice, whatever their order. (Req 9.3)
  - A failed check never turns a `retracted` DOI into anything else. (Req 9.4, 9.5)
  - DOI normalisation is idempotent and case-insensitive. (Req 9.1)
- Added in Phase 2 refinement:
  - Hashing a stream of rows in chunks gives the same hash as hashing them in memory, for any chunk size; side tables never change the content hash. (Req 14.1, 14.3)
  - BDPM: re-rendering the parsed cells reproduces the input cells exactly, including leading and trailing spaces and accents. (Req 11.4)
  - BDPM: each file decodes with its own encoding; undecodable bytes always fail the run and are never replaced. (Req 11.2)
  - BDPM: a CIP13 is accepted exactly when it has 13 digits, starts with `3400` and has a correct check digit; every other value gives a name-only row and is never repaired. (Req 11.5)
  - BDPM: the output has one row per presentation line, the composition list is the CIS's lines in file order, and every input line is output or excluded with a reason. (Req 11.3, 11.6, 1.5)
  - CIMA: a GS1 code is kept exactly when its length is 8, 12, 13 or 14 and its check digit is correct; an NTIN built from a national code embeds that code. (Req 12.3)
  - CIMA: parsing a generated Nomenclátor reproduces the generated presentations, independent of their order and of unknown extra elements; advice elements never reach the output. (Req 12.2, 12.5)
  - FAERS: for any set of reports over several quarters with deletions, the output has exactly one report per non-deleted case, with the highest version; no deleted case remains; the removed list explains every difference; the result does not depend on report or quarter order. (Req 13.3, 1.5)
  - FAERS: every input line is output or excluded with a reason, and malformed lines are excluded. (Req 13.2, 13.5, 1.5)
  - FAERS: a region is exactly one of TR, EU, US, OTHER, UNKNOWN; the occurrence country wins over the reporter country; `EU` and the 27 member-state codes give EU; missing values give UNKNOWN. (Req 13.6)
  - FAERS: the quarter window is the four latest consecutive quarters whatever the listing order and letter case; a gap fails. (Req 13.1)
  - FAERS: CRLF and LF files give the same rows; quote characters in values are kept. (Req 13.2)
  - FAERS: no output row has a field outside the allowed list. (Req 13.4)
  - Counts: every 2×2 table built from the count tables equals a direct recount from the report facts, with a ≤ min(drug, event) and b, c, d ≥ 0. (Req 15.5)
  - Counts: the regional counts add up to the `ALL` count in every table; `suspect` counts never exceed `any` counts. (Req 15.3, 15.5)
  - Counts: repeating a drug line or an event inside a report does not change any count. (Req 15.4)
  - Counts: only `mapped` names contribute; mapped plus listed unmapped occurrences equal all ingredient occurrences. (Req 15.2)
  - Counts: the tables and their hashes do not depend on report order; a changed artifact row is refused. (Req 15.1, 15.7)
  - Counts: a failed build never changes the current counts file. (Req 15.8)
