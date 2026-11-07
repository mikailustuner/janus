# Requirements: Data Pipelines (ETL)

> Draft seed. Refine with Kiro, then let Kiro generate `design.md` and `tasks.md`.

## Introduction
Every external source enters Janus through a pipeline that records its version, license and update cadence, validates its shape, and produces read-only artifacts for the API. Pipelines are the place where licensing rules are enforced (what may be committed, cached or only fetched at runtime).

## Sources and cadence
| Pipeline | Source | Cadence | Storage rule |
|---|---|---|---|
| `titck` | TİTCK licensed products list | weekly | fetch at runtime, never commit |
| `us_ndc` | openFDA NDC directory | weekly | cache allowed (CC0) |
| `eu_fr_bdpm` | BDPM files | monthly | cache allowed (licence ouverte, keep source + update date, no alteration) |
| `eu_es_cima` | AEMPS CIMA REST / nomenclátor | weekly | cache allowed with attribution |
| `wikidata_ingredients` | Wikidata (ATC P267, RxNorm P3345, multilingual labels) | monthly | cache allowed (CC0) |
| `onsides` | OnSIDES data release | per release | cache allowed (CC BY 4.0) |
| `faers` | FAERS quarterly ASCII files | quarterly | cache allowed (CC0) |
| `pipc` | PIPC Table 1 (Europe PMC XML) | per release | commit allowed (CC BY 4.0) |
| `retractions` | Crossref update notices for every DOI in `evidence` | weekly | cache allowed |
| `canon` | OpenITI Canon Book 2 | per release | separate CC BY-NC-SA data package |

## Requirements

### Requirement 1: Provenance
#### Acceptance criteria
1. Every pipeline run SHALL record source URL, license, snapshot/version date, row counts and a content hash.
2. Every artifact SHALL be traceable to the run that produced it.

### Requirement 2: Validation
#### Acceptance criteria
1. WHEN a source file's columns or schema differ from the expected shape THE pipeline SHALL fail loudly and keep the previous artifact.
2. WHEN row counts change by more than a configured percentage between runs THE pipeline SHALL flag the run for review.
3. THE `titck` pipeline SHALL report the share of rows with an ATC code and the number of multi-ingredient products.

### Requirement 3: Licensing enforcement
#### Acceptance criteria
1. THE pipeline SHALL refuse to write a source marked "fetch at runtime, never commit" into the repository's `data/` directory.
2. THE NOTICE file SHALL be generated from the pipelines' license records.

### Requirement 4: Reliability
#### Acceptance criteria
1. External downloads SHALL use timeouts and idempotent retries.
2. A failed pipeline SHALL never leave the API without a usable artifact.

## Properties to test (PBT candidates)
- Re-running a pipeline on the same input produces the same content hash.
- A schema-mismatched input never replaces the previous artifact.
- The generated NOTICE contains an entry for every source used by any artifact.
