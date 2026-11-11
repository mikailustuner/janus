# Implementation Plan: Drug model starter kit

## M0 (experimental vertical slice)
- [x] 1. Spec (requirements, design, properties, tasks)
- [x] 2. Evidence seed `data/modelkit/evidence_seed.csv` (six pilot drugs; verdicts of two reader passes; quotes
  and locators) and `data/modelkit/README.md`
  - _Requirements: 1.1, 1.2, 1.4, 1.5_
- [x] 3. Pipeline job `modelkit_evidence`: validation, unit normalisation, derived `confirmed`, parquet + manifest;
  sources and NOTICE; tests (M4, derived flag)
  - _Requirements: 1.3, 1.4_
- [x] 4. API store, builder (M1-M3, M5, M6, M10), validation (M8), tests
  - _Requirements: 2, 3_
- [x] 5. Exports: Janus engine JSON, mrgsolve, provenance, bib, licences; deterministic zip; mrgsolve round-trip
  test (M7) and its own workflow (`.github/workflows/modelkit-mrgsolve.yml`)
  - _Requirements: 4_
- [x] 6. API routes, public API document, `docs/open-api.md`
  - _Requirements: 5_
- [x] 7. Web: list and drug page, five languages, themes, 375 px, axe, Playwright; link from researchers page (tables scroll in their own region without breaking words; check in `e2e/model-kit.spec.ts`)
  - _Requirements: 6_
- [x] 8. MCP tools `janus_modelkit_search`, `janus_modelkit_get` (`modelkit_evidence` is open, M3)
  - _Requirements: 7_
- [x] 9. Checkpoint: all CI-equivalent checks, screenshots

## Later milestones (open)
- [x] M1 (built; the precision target was NOT met, see `reviews.md`)
  - [x] Analyte and context resolver (names and company codes from `identity_m1.csv`, metabolites, enantiomers,
    unbound, total, combination partners, prodrugs; arm context: other active drug, food, formulation, population,
    sex, species, route, regimen)
  - [x] Unit and dimension checker (per-kg kept apart, candesartan regression, mean type and dispersion separate)
  - [x] Independent reader B (structure first) beside reader A (pattern based); confirmation by code
  - [x] Derived CL/F = dose / AUC(0-inf) with a test; held-out rule adapted (DP-M14)
  - [x] Re-run of the 50-drug pilot, pre-registered; blinded sample with two automated review passes (two runs)
  - [x] Evidence seed `evidence_m1.csv`, sources, recorded answers, web texts in five languages
  - [ ] Confirmed-value precision >= 0.90 (measured 0.66 in run 1 and 0.69 in run 2). Open: a reader that is not a
    cue-sharing twin of A, a stricter arm-context reader (comparator and combination arms), population and route
    from the document structure, reader B dose fallback (xfail test), a larger sample, expert review.
- [ ] M2 ClinicalTrials.gov bulk ingestion (documented bulk download, not the API), arm-level co-administration
  filter, population-PK output filter, set builder at scale, pre-registered gate with >= 10 interpretable drugs
- [ ] M3 System report by drug class, conformal intervals once n >= 20, bootstrap intervals, full API contract
  tests, MCP `modelkit_evidence`
- [ ] M4 PK-Sim snapshot export and CI test; special populations (older adults from the audited atlas rows, renal
  and hepatic classes from labels)
- [ ] M5 FDA clinical pharmacology reviews (born-digital first, then OCR) and PMC table reader (dose only from
  table, footnote or methods, species filter)
- [ ] M6 Expert sample audit, expert review, method write-up, data package with DOI, `CITATION.cff` (owner
  decision)
- [ ] Two-compartment engine and export, per-kg handling with explicit body weight in a source, a class D
  fallback only if the owner wants it
