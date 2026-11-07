# Requirements: Data Pipelines (ETL)

> Refined 2026-11-07 for Phase 1. Requirements 1–4 apply to every pipeline. Requirements 5–9
> cover the five Phase 1 pipelines. Requirement 10 keeps the other pipelines for later phases.

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
| `eu_fr_bdpm` | BDPM files | monthly | cache allowed (licence ouverte, keep source + update date, no alteration) | 2 |
| `eu_es_cima` | AEMPS CIMA REST / nomenclátor | weekly | cache allowed with attribution | 2 |
| `wikidata_ingredients` | Wikidata (ATC P267, RxNorm P3345, multilingual labels) | monthly | cache allowed (CC0) | **1** |
| `onsides` | OnSIDES data release | per release | cache allowed (CC BY 4.0) | later |
| `faers` | FAERS quarterly ASCII files | quarterly | cache allowed (CC0) | 2 |
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
4. WHEN a barcode is not 13 digits or fails the EAN-13 check digit THE pipeline SHALL exclude the row with the reason `invalid_barcode`.
5. WHEN two or more rows share a barcode THE pipeline SHALL keep all of them and report the count; THE pipeline SHALL NOT choose one.
6. WHEN the active-ingredient text lists several ingredients THE pipeline SHALL split it into individual names and SHALL preserve every non-separator character of the original text.
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
4. THE pipeline SHALL NOT normalise NDC formats; normalisation is done in the `drug-resolution` spec.

### Requirement 9: `retractions` pipeline (Phase 1)
**User story:** As evidence integrity, I need the retraction status of every DOI Janus cites, refreshed weekly.

#### Acceptance criteria
1. WHEN run THE pipeline SHALL collect every DOI from the evidence records available (in Phase 1: the evidence records emitted by pipelines) and normalise each DOI (lower case, without `https://doi.org/` or `doi:` prefix).
2. FOR each DOI THE pipeline SHALL query the Crossref REST API and derive a status from the work's update notices (`updated-by`): `retracted`, `expression_of_concern`, `corrected` or `ok`.
3. WHEN a work has several notices THE pipeline SHALL use the most severe one (retracted > expression_of_concern > corrected), whatever their order.
4. IF a DOI is not found or the check cannot be completed THEN THE pipeline SHALL record `unknown` for that check; it SHALL NOT record `ok`.
5. IF a check cannot be completed and the last completed check of that DOI was `retracted` THEN the effective status SHALL stay `retracted`.
6. WHEN a DOI's status changes between runs THE pipeline SHALL list the change in the manifest; WHEN a status changes from `retracted` to any other status THE run SHALL end as `needs_review`.
7. THE pipeline SHALL store each raw Crossref response with its fetch time, and the notice's source (e.g. `retraction-watch`) and URL with the status.

### Requirement 10: Pipelines for later phases
#### Acceptance criteria
1. THE `eu_fr_bdpm`, `eu_es_cima`, `onsides`, `faers` and `canon` pipelines SHALL meet Requirements 1–4 and the storage rules in the sources table. Their source-specific requirements are written when their phase starts (see the Phase column).

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
