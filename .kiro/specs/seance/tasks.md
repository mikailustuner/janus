# Implementation Plan: The Séance, Phase 4

> Scope: design.md §2. Property numbers refer to design §8, decisions to §9. Owner decisions of
> 2026-11-08 applied (DP9, DP10). The web screen is not in this plan: `experience` builds it from
> design §7. No health data in logs or fixtures; no OpenITI text in test fixtures beyond short
> synthetic phrases. No new runtime dependency in the API.

- [x] 1. Verify the sources
  - OpenITI repository, version, commit and blob (GitHub contents and commits API); licence on the
    Zenodo record of release 2025.1.9; PMC3941892 article, DOI and licence (PMC OAI record);
    Hamdard 1998 kept cite-only. Update `pipelines/sources.toml` and regenerate `NOTICE`.
  - _Requirements: 1.1, 1.4, 3.1, 3.2_

- [x] 2. Book 2 text module (`canon_text.py`, pure)
  - Split at headings with locators and printed pages; sections from inline labels; normalised
    theme matching with prefix/suffix forms; spans; rule tags.
  - Properties P1–P3; examples for `لل`, `حرقة`, sections, missing book.
  - _Requirements: 1.2, 1.3, 1.3a, 1.3b_

- [x] 3. `canon` job and the data package
  - Pinned fetch with blob check, `needs_review` when headings ≠ 844, stable span ids (P4);
    `datasets/canon/` with `LICENSE` (full CC BY-NC-SA 4.0 legal code), `README.md`, `entries.csv`,
    `theme_spans.csv`, `source.json`. Run on the pinned file: 844 entries, 534 spans.
  - _Requirements: 1.1, 1.2, 1.3d, 3.1_

- [x] 4. `canon_gold` job
  - Name columns of Tables 1–2 → `data/canon_gold_pmc3941892.csv` + meta (P5). 29 rows.
  - _Requirements: 1.4, 3.2_

- [x] 5. Reader step
  - `canon_reader.py`: `Reader` protocol, `AnthropicReader` (SDK client passed in, structured
    output, timeout, refusal fallbacks), validation (P8); tests with fakes only.
  - No API key configured: the 43-clause sample read offline by the reader agent →
    `reader_ai.csv` with provenance in the README (DP6).
  - _Requirements: 1.3, 1.3c_

- [x] 6. Identifications
  - 31 substances: gold row, Hamdard entry and page (facts only), status rule (design §3.5).
  - _Requirements: 1.4, 1.4a, 1.4b_

- [x] 7. Two labelled AI review passes
  - Historian and pharmacologist agents, run separately on the same 43 clauses →
    `review_historian.csv`, `review_pharmacologist.csv`, `review_pharmacologist_identifications.csv`.
  - _Requirements: 5.1_

- [x] 8. Assembly and quality report (`canon_package.py`, pure)
  - Claims (P6, P7), substances, `quality.json`; `expert_review` always `pending`; hazards never
    headline. Result: 76 claims, 0 expert-reviewed.
  - _Requirements: 1.5, 4.1, 4.2, 5.2, 5.3_

- [x] 9. Séance data tables
  - `data/seance_conditions.csv`, `data/seance_present.csv`, `data/seance_science.csv`; four
    papers in `data/evidence_papers.csv` (source `seance_science`); `data/README.md`.
  - _Requirements: 2.1b, 2.1c, 4.3_

- [x] 10. Witnesses and synthesis (`model.py`, `witnesses.py`, pure)
  - Invariants, count and missing (P9–P11); past (P12), present via the memory reader's cells and
    `memory.stats` (P13), science via `integrity.citability` (P14, P15).
  - _Requirements: 2.1–2.3, 4.3_

- [x] 11. Catalogue, service and routes
  - Startup validation (P16); `POST /seance/pair`, `GET /seance/catalogue` as medical routes;
    503 without the package; witnesses degrade to missing when counts or integrity are absent.
  - HTTP properties P17–P20 without a database; P21 and the two-witness examples on `janus_test`.
  - _Requirements: 2, 6_

- [x] 12. Contract and checklist
  - Design §7 for `experience`; pre-launch checklist items for the expert review, the science
    findings, the NC licence and the Ottoman samples.
  - _Requirements: 4.4, 7_

- [x] 13. Checkpoint
  - pyright strict, ruff, pytest (`HYPOTHESIS_PROFILE=ci`, DB tests after `alembic upgrade head`),
    license-guard, log-guard. Gate 4: not met (two of three witnesses at best; design §4.5).

- [ ] 14. After the experts (not in Phase 4)
  - Apply the expert review (`expert_review = reviewed`), re-run assembly, re-check headline pairs.
  - Run the `retractions` pipeline so the four séance DOIs are checked; reload integrity.
  - Open items of design §10.
