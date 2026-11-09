# Implementation Plan: CDS Hooks service

- [x] 1. Request model and extraction: `janus/cds/fhir.py` (strict top level and context, lenient FHIR, limits,
  focus, patient and status filters). P7. _Requirements: 2, 3.1, 3.5, 3.6_
- [x] 2. Mapping: `janus/cds/mapping.py` (systems, shapes, order, signatures), repository queries
  `refs_by_product_rxcui`, `qids_by_rxcui`, `qids_by_atc`, migration `0013` (GIN index). P6. _Requirements: 3_
- [x] 3. Cards: `janus/cds/cards.py` (focus filter, summary, detail, source, link). P2–P5. _Requirements: 4_
- [x] 4. Service and routes: `janus/cds/service.py`, `router.py` (discovery, service, 412/413/422/503), body limit
  table, `JANUS_CDS_CORS_ORIGINS` and `cors.py`; discovery in the public OpenAPI document. P1, P8.
  _Requirements: 1, 2, 5_
- [x] 5. Tests on the synthetic dataset: examples, statelessness, CORS. _Requirements: 6.2_
- [x] 6. Docs: `docs/cds-hooks.md` (sandbox demo), `docs/open-api.md`, pre-launch checklist items.
  _Requirements: 6.1, 5.4_
- [x] 7. Reviews: safety-auditor and pharmacologist passes on the card wording and the mapping; fixes; sheets in this
  folder. _Requirements: 3, 4_
- [x] 8. Checkpoint: ruff, ruff format, pyright, pytest (database tests included); commit. _Requirements: all_
