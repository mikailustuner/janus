# Implementation Plan: The Time Machine

> Scope: design.md §2. Property numbers refer to design §9, decisions to §3–§8. The web screens
> are not in this plan: `experience` builds them from design §10. No health data in logs or
> fixtures. The API gains no runtime dependency: R and the model environments are used offline
> only and live under `.data/tools`.

- [x] 1. Verify every source, tool and licence before using it
  - Wikidata/LOTUS CC0 (eLife paper + Wikidata:Licensing); PubChem public domain with the
    depositor caveat; ChEMBL CC BY-SA 3.0; httk 2.7.4 MIT on CRAN; ADMET-AI 2.0.1 MIT with the
    TDC dataset caveat. Every DOI checked through Crossref with its retraction relations.
  - Record all of it in design §3 and `data/time_machine/references.csv`; add `pubchem`, `httk`
    and `admet_ai` to `pipelines/sources.toml`; regenerate `NOTICE`.
  - _Requirements: 1.1, 1.3_

- [x] 2. `faers_onset` pipeline
  - Pure date rule and exclusion reasons; Polars extraction over the raw archives of the current
    `faers` run; data-quality metrics. The `faers` artifact is unchanged.
  - Properties P18, P19; examples for every exclusion reason.
  - _Requirements: 6.1, 6.2, 6.3_

- [x] 3. Curated tables
  - `constituents.csv` (14 compounds, 4 substances, each with a reason), `comparators.csv`,
    `units.csv`, `references.csv`, `observed_pk.csv`, `compartmental_pk.csv`,
    `dose_scenarios.csv`, `potency_targets.csv`, `cascades.csv`.
  - _Requirements: 2.1, 3.2, 7.1, 7.3_

- [x] 4. `tm_molecules`, `tm_bioactivity`, `tm_labels`
  - Occurrence by InChIKey with reference ids (DP-T3, DP-T4); depositor licence filter and
    interaction pointers (DP-T5, DP-T7); label confirmation of each modern indication.
  - Property P20; parser tests with synthetic SPARQL and PubChem payloads.
  - _Requirements: 2.2, 2.3, 3.1, 3.2, 3.4, 1.2_

- [x] 5. Pure maths package
  - `units`, `pk` (closed form, superposition, seeded Monte Carlo), `onset` (log-sum-exp Weibull
    MLE, likelihood-ratio interval, shape rule), `exposure`, `twin`, `validation`.
  - Properties P1–P14.
  - _Requirements: 4.2, 4.3, 5.1, 6.4, 7.1, 7.2, 7.4_

- [x] 6. `tm_pbpk` and `tm_admet`
  - `httk_run.R` (validation doses, HTTK-Pop 65–79 vs 20–50, time to 90 % of steady state) with
    every package version captured; ADMET-AI in the pinned CPU environment with the InChIKey
    check. Both refused with exit 4 when the tool is absent, so CI never needs them.
  - _Requirements: 1.4, 1.5, 4.1, 4.2, 4.4, 2.3_

- [x] 7. Validation and the credibility rule
  - Rule fixed first (2-fold credible, 3-fold borderline); fold errors reported for all six
    validation drugs; the non-independence of rhein's AUC stated.
  - Outcome: httk 0/4 credible, compartmental 1/2 — recorded as it came out (design §8.1).
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 8. Offline build and the read-only API
  - `python -m janus.timemachine.build` assembles the artifact; `store`/`router` serve it with
    GET only, 503/404/422 behaviour, and no computation per request.
  - Properties P15, P16, P17.
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 9. Checkpoint: full checks
  - ruff, pyright strict, `HYPOTHESIS_PROFILE=ci` pytest in both projects, licence guard, log
    guard, `janus-pipelines notice --check`.
  - _Requirements: all_

- [x] 10. Three labelled review passes
  - Pharmacologist, statistician and historian, each independent, each a file under this spec.
  - _Requirements: 10.1_

- [x] 11. Hand-over to the experts
  - Every unsettled item added to `docs/pre-launch-checklist.md`; nothing marked
    expert-reviewed.
  - _Requirements: 10.2, 10.3_

- [x] 12. Web screens (owner: `experience`, built 2026-11-09 as experience Req 30, DP58–DP64)
  - Research area: substance card, exposure card with the validation table, cascade card with
    the onset curve and the population comparison. Patient-facing: the single timing sentence of
    design §10.5, in all five languages, behind the small-sample and agreement conditions.
  - _Requirements: 9.1–9.5, 3.2b, 4.2a_

- [ ] 13. Expert review (owner: the experts)
  - The items of `docs/pre-launch-checklist.md`; only an expert may set a result to reviewed.
  - _Requirements: 10.3_

- [x] 14. Fixes found while building the web screens (2026-11-09)
  - **Non-deterministic bootstrap:** two builds of the same data gave a median interval of 9 and 19 days for
    `antipsychotic_eps_antiparkinson`; the onset query's `GROUP BY` returns rows in no stable order and the seeded
    bootstrap draws by index. `summarize` now sorts the intervals first; new property
    `test_summary_does_not_depend_on_row_order`. Two rebuilds are now identical apart from `built_at`.
  - **Forbidden word in a curated note:** the medical-language hook flagged "diagnosis"/"diagnostic" in the anise
    comparator note of `data/time_machine/comparators.csv` (shown verbatim in the research area); reworded to
    "disease label"/"disease category". Artifact rebuilt.
  - _Requirements: 6.4, 9.1_
