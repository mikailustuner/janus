# Data pipelines

ETL jobs, one per source. Not implemented yet (Phase 1).

Planned jobs: `titck`, `us_ndc`, `eu_fr_bdpm`, `eu_es_cima`, `wikidata_ingredients`,
`onsides`, `faers`, `pipc`, `retractions`, `canon` (OpenITI).

Rules:

- Every job records source URL, license, region and snapshot date/version.
- Files with unclear redistribution terms (e.g. TİTCK lists) are fetched at runtime and
  never committed.
- External calls use timeouts, retry only when idempotent, and cache results.
