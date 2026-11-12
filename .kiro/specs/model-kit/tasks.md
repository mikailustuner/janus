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
- [~] M2 ClinicalTrials.gov bulk ingestion, set builder at scale, pre-registered gate (see `reviews.md` for the numbers)
  - [x] Official bulk download (not the API), job `modelkit_ctgov`, sources and NOTICE, resumable shards, merge into
    `modelkit_evidence`, pool identity table (609 drugs)
  - [x] Pre-registration written before any result (private); gate counts drugs with both metrics tested
  - [x] List route paging and search, summaries per release, web list search and pages, recorded release
  - [x] Precision measured again on a blinded sample (two automated review passes); texts in five languages
  - [ ] Arm-level co-administration and population-PK filters at scale beyond the M1 fixes (no reader change in M2)
- [~] M3 Formulation resolver, system report, intervals, API contract tests, MCP `modelkit_evidence`
  - [x] Pre-registration written before any result (private)
  - [x] Two independent formulation and route resolvers, product forms table, Hypothesis properties (DP-M22, DP-M23)
  - [x] M2 pipeline re-run with the resolver (same bulk file), sets and strict gate recomputed (see `reviews.md`)
  - [x] Intervals only from 20 independent held-out studies, otherwise the reason is shown (DP-M24)
  - [x] System report page, drug page (status explanation, failed points and suspect parameter, formulation per evidence
    row), API contract tests for all routes, MCP `janus_modelkit_evidence`, five languages
  - [x] Precision measured again on a fresh blinded sample including the formulation field (two automated review passes)
  - [ ] System report by drug class and bootstrap intervals in the product (not meaningful before 10 drugs have both
    metrics tested)
- [~] M4 Route on conflict, PK-Sim export and CI check, special populations (see `reviews.md` for the numbers)
  - [x] Pre-registration written before any result (private), with three addenda (code freezes, a run that failed in its
    accounting and its display rule)
  - [x] Route becomes unknown when the resolvers find an oral and an intravenous statement (owner decision 2026-11-11);
    pipeline re-run from the same bulk file, sets and gate recomputed, fresh blinded sample (two automated review passes)
  - [x] PK-Sim feasibility checked against the open source suite: snapshot (JSON) format, PK-Sim 12.x (project snapshot
    version 80), ospsuite 12.4.5 (bundles PK-Sim core 12.3.173, GPL-2.0) loads and runs it on Linux with a .NET 8 runtime
  - [x] PK-Sim compound export (only what the evidence has; the rest marked missing, nothing invented), load and round-trip
    check in its own workflow `modelkit-pksim.yml`, a completed test copy simulates
  - [x] Special populations: two independent readers (`sp_a`, `sp_b`), confirmation, job `modelkit_special_populations`,
    committed statements, older-adult atlas rows as unconfirmed evidence, API fields, system report, web section and
    report card, five languages, MCP text
  - [x] Precision of the confirmed statements measured on a blinded sample (two automated review passes)
  - [ ] Confirmed-value precision >= 0.90 for the ClinicalTrials.gov values and for the special-population statements (not
    met, see `reviews.md`); expert audit (M6)
  - [ ] PK-Sim: a mechanistic compound needs lipophilicity, pKa, fraction unbound, blood/plasma ratio and a clearance process;
    no open evidence source of them is read yet
- [~] M5 FDA clinical pharmacology reviews (born-digital first, then OCR) and PMC table reader (dose only from
  table, footnote or methods, species filter) (see `reviews.md` for the numbers)
  - [x] Pre-registration written before any download (private), with six addenda (access routes after robots.txt, two
    reader rules, born-digital threshold, code freezes, the FDA result, a second reader iteration)
  - [x] Drugs@FDA review location and download (data file, table-of-contents pages, at most three PDFs per drug), job
    `modelkit_documents`, born-digital text layer, two independent table readers, confirmation by code, same study
  - [x] PMC Open Access articles: Europe PMC search, PMC Article Datasets, three licence checks, human-only filter (the
    pilot's horse case is a test), dose only from table, caption, footnotes or methods with a dosing verb
  - [x] Study identity across sources (NCT number, sponsor code, numerical duplicate, review document); a linked study
    never tests; schema `modelkit_evidence-3`
  - [x] Precision measured on fresh blinded samples (two automated review passes): review tables 0.48, PMC tables 0.48;
    both held back by the pre-registered rule; system report, five languages, MCP text, public API document
  - [ ] Precision at least 0.70 for either document source (not met); OCR of scanned reviews (not run: it was to follow a
    measured born-digital reader)
  - [ ] Coverage 150 sets and 40 Validated (not approached: 26 sets, 0 Validated; see `reviews.md`)
- [~] M6 Expert sample audit, expert review, method write-up, data package with DOI, `CITATION.cff` (owner
  decision) (see `reviews.md`)
  - [x] Special populations neither build nor test a set; patients only without a healthy-adult value; tests in the
    population of the set (DP-M36, M32); pre-registered (private), evidence re-run, sets and gate recomputed
  - [x] Expert sample audit pre-registered and drawn (366 items, 48 strata; 20-drug method review), bilingual packet and
    answer sheet (private), scoring tool tested on synthetic fills (DP-M37)
  - [x] `expert_audit` record read by the evidence job; API, system report, web pages (five languages) and MCP show the
    audit line only with a record; shipped without one
  - [x] Method write-up draft (private); data package builder with the publishable-rows test (DP-M38)
  - [ ] Expert audit done and its record committed; pharmacometrician and clinical pharmacologist method review; opinions
    published (owner, plan 12.5)
  - [ ] DOI and `CITATION.cff` (owner decision); package upload
- [ ] Two-compartment engine and export, per-kg handling with explicit body weight in a source, a class D
  fallback only if the owner wants it

## Reopened after M2–M6 (owner decision 2026-11-11)

- [ ] M1 exit criterion: confirmed-value precision ≥ 0.90 on a blinded sample (measured 0.69, n = 85). Shared error
      classes to fix first: regimen, route, combination arms, comparator drugs, population words in label sentences.
      Precision work (2026-11-12): met for ClinicalTrials.gov values by abstention only (DP-M39): two automated passes
      found 125 of 126 kept values correct; about 13 % of the values the readers agree on stay confirmed. Expert review
      has not yet been done.
