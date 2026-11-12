# Design: Drug model starter kit

## 1. Overview
```
data/modelkit/evidence_seed.csv (committed, small)      pipelines: job modelkit_evidence
        │                                                  validate rows, normalise units, derive `confirmed`,
        ▼                                                  write rows.parquet + manifest, `current` link
  .data/artifacts/modelkit_evidence/current ─────────────────────────────┐
                                                                         ▼
apps/api/janus/modelkit/  store.py (load/refresh)  builder.py  validate.py  export.py  router.py
        │                                                                 │
        ▼                                                                 ▼
 /modelkit/* (read-only)                                      apps/web research/model-kit, apps/mcp tools
```
The builder, the validation and the exports are pure functions of the evidence rows. They run once per release
when the store loads and the results stay in memory. No request starts a simulation.

## 2. Evidence row (`modelkit_evidence-1`)
Columns: `drug_key, analyte, analyte_class, parameter, value, value_low, value_high, statistic, unit, value_si,
dose, dose_unit, route, regimen, interval_h, population, n_subjects, formulation, coadministered, study_id,
source_id, source_locator, source_version, quote, reader_a, reader_b, confirmed, confirm_reason, note,
extracted_at, pipeline_version`. The first nine plus the quote follow the stated-value rule: `value` is what the
source states (a range is stored as its two bounds and the geometric mean in `value`, statistic `range_geomean`);
`value_si` is the canonical value (L, L/h, h, fraction, ng/mL, ng*h/mL; per-kg values keep their per-kg unit).
`reader_a`, `reader_b` are `agree` or `disagree` (relative to the extracted value); `confirmed` is derived.
Parameters: `cl, cl_f, vss, vd, v_f, t_half, tmax, f, cmax, auc_inf, auc_last, auc_tau, cl_per_kg, vd_per_kg`.
Formulations: `immediate_release, solution, modified_release, fixed_dose_combination, unspecified`.

## 3. Decisions
- **DP-M1 Two readers, agreement by code.** Reader passes return what the quoted text states for the parent
  drug (value, unit, analyte, restriction). Code compares them with the extracted value (1 % tolerance, same unit,
  restriction none). Context disagreement counts (owner decision 2026-11-11): two readers that give the same
  value but a different context (arm restriction such as a crossover test or reference arm, co-administration,
  formulation, food, population) are a disagreement and the value is not confirmed. Rows the pilot already judged by two annotation passes keep those verdicts. A value the
  readers cannot reproduce stays in the store as `confirmed = false`; it is shown on the drug page as "not used".
- **DP-M2 Held-out rule is structural.** `split_studies` classifies studies by the parameters they report for the
  parent drug (all parent rows, confirmed or not, so the split cannot depend on the outcome of confirmation; M1:
  a metabolite row does not count, a derived clearance does not count, see DP-M14): a study reporting any of
  `cl, cl_f, vss, vd, v_f, t_half, tmax, f` is a building study; a study reporting only `cmax` / `auc_*` is a test
  study; labels never test. Test studies are never read by the builder (the builder takes only the building
  rows), so the rule holds by construction; a property test checks it.
- **DP-M3 Formulation and co-administration are filters, not notes.** Modified-release rows cannot build or test
  an immediate-release model; fixed-dose combination and co-administered arms are excluded from both.
- **DP-M4 No per-kg conversion.** The evidence has no body weight; per-kg values stay per-kg.
- **DP-M5 Pooling.** One value per study (geometric mean over the study's arms); across studies the weighted
  geometric mean with weights n (1 when n is missing); between-study spread reported as the geometric CV.
- **DP-M6 Absorption rate from Tmax.** ka solves tmax = ln(ka/k)/(ka-k); no solution (tmax at or above 1/k)
  leaves ka unset and the set incomplete. Class C.
- **DP-M7 Status function (strict, owner decision 2026-11-11).** Every held-out point has a ratio predicted /
  observed. Validated iff AUC and Cmax are both tested and every point is in [0.5, 2]; Failed iff any tested point
  is outside; else Not validated with reasons. The geometric mean over studies and the GMFE are reported per
  metric for information only. A failed drug lists the points outside 2-fold. Suspect parameter: an AUC point off,
  then clearance (or bioavailability); a Cmax point off, then absorption rate and volume.
- **DP-M8 No invented precision.** The existing conformal code (`simulation/calibration.py`) is calibrated for
  one quantity (screening-model half-lives) and does not apply to evidence-built sets; the same split-conformal
  quantile rule is implemented for log fold errors and returns nothing below 20 independent held-out studies.
  Wilson intervals are given for shares; GMFE is shown with n.
- **DP-M9 Compute at load.** Plan decision (validation at pipeline time) relaxed for M0: the six-drug computation
  is milliseconds; results are cached per run id. Revisit when the store is large (M2).
- **DP-M10 Janus engine export is a point model.** `Params` of `simulation/compartmental.py` with all spreads 1.0
  and bioavailability fixed (`f_fixed`), because no variability is evidenced; the same engine code produces the
  reference curve of the round-trip test.
- **DP-M11 mrgsolve round trip.** R with a pinned mrgsolve in a separate CI job (see section 6).

## 4. API
Medical-policy routes (no-store). Errors as codes. Models: drug summary, drug detail (parameters, validation,
exclusions), evidence rows, system validation. Export returns a deterministic zip (fixed timestamps).

## 5. Web
Server components read the API through the existing server fetch helper; client component only for the chart and
the evidence popover. Keys in `messages/*.json` under `modelKit`. Design tokens of `design.md`.

## 6. mrgsolve in CI
A separate workflow (`.github/workflows/modelkit-mrgsolve.yml`) runs in the `rocker/r-ver:4.6.1` image (the R of the
simulator image, CRAN pinned to a dated snapshot), installs mrgsolve 2.0.1 once (cached) and checks the version,
builds the export for every drug with a complete set and compares the mrgsolve curve with the Janus engine curve
(tolerance 1 % where the curve is at least 0.1 % of its peak, 0.1 % of the peak elsewhere; one dose and three
doses). It runs on pushes and pull requests that touch the model kit, nightly and on demand; the main jobs do
not wait for it and skip the `mrgsolve` tests when R is missing. Locally: `pytest -m mrgsolve`; set
`JANUS_REQUIRE_MRGSOLVE=1` to turn a missing R into a failure.

## 7. Correctness properties
- **M1** The test studies of a drug share no study id with the rows the builder used.
- **M2** An unconfirmed row never appears in a set's evidence list.
- **M3** Every parameter of a set lists at least one evidence row, and the value is reproducible from the listed
  rows by the stated rule.
- **M4** Unit conversion is reversible: `from_si(to_si(v, u), u) = v` within 1e-9 relative.
- **M5** Builder output does not depend on row order.
- **M6** Modified-release, co-administered and fixed-dose-combination rows never appear in a set or a test.
- **M7** The exported mrgsolve model reproduces the Janus engine curve within 1 % on a fixed grid.
- **M8** Status is Failed iff a tested point is outside [0.5, 2]; Validated iff both tested and every point inside (Validated implies all points within [0.5, 2]).
- **M9** No export or page text contains a forbidden phrase (`medical-safety.md`) or "AI"; every export carries
  the two statements.
- **M10** No per-kg row is converted.

## 8. M0 evidence and findings
Six drugs from the second data-source pilot (dolutegravir, ertugliflozin, gabapentin, sunitinib, tramadol,
telmisartan). The pilot called all six simulatable; the stricter M0 rules change that, see `reviews.md`.

## 9. Milestone M1 decisions
- **DP-M12 Evidence schema 2.** `modelkit_evidence-2` adds `arm_id, origin (m0_annotation | reader_pair | derived),
  derivation, evidence_kind (pk | interaction), food, dispersion_type, dispersion_low, dispersion_high`; analyte
  classes `parent, parent_unbound, metabolite, enantiomer, total, prodrug, combination_partner, unconfirmed,
  unspecified`; formulation `other_route` (intramuscular, topical, patch and similar). The job reads
  `evidence_seed.csv` (M0) and `evidence_m1.csv` (M1); M0 rows of ClinicalTrials.gov and DailyMed are replaced by the
  M1 rows of the same drug, M0 rows of PMC and the scanned review are kept with their M0 annotation verdicts.
- **DP-M13 Build-time reading in `pipelines/janus_pipelines/modelkit/`.** `resolver.py` (names from
  `data/modelkit/identity_m1.csv`: Wikidata labels and aliases, CC0, plus a short curated list of metabolites and
  prodrugs; analyte class; study-arm context), `units.py` (unit table, dimension analysis, per-kg handling, mean type
  and dispersion), `reader_a.py` (pattern based: sentences, titles, flattened table lines, the resolver),
  `reader_b.py` (structure first: the unit's dimension, arm-to-intervention links, eligibility flags, the table grid,
  token rules; shares only reference data), `confirm.py` and `pairing.py` (the only place the two meet),
  `derive.py`, `pilot.py` (the 50-drug re-run). Disagreement rule: DP-M1.
- **DP-M14 Derived clearance and the split.** Derived rows never make their study a building study; with no stated
  clearance one study builds (first in sorted order) and never tests. A set built from derived clearance has class C
  and says "Derived: CL/F = dose / AUC to infinity of one study arm".
- **DP-M15 Label formulation and route.** When a label sentence is silent on formulation and route, they are taken
  from the label's own dosage forms and routes (structured data of the same label) only if every form is a plain oral
  form and the only route is oral. This is a separate step after confirmation and is noted on the row.
- **DP-M16 Measured precision is shown.** The system report carries the caveat `confirmed_precision_below_target`
  (blinded sample, two automated review passes) for as long as the target of 0.90 is not met.

## 10. Milestone M1 properties
- **M11** Only a row of the parent drug that both readers confirm reaches the builder; a non-parent analyte, an
  interaction arm, an `other_route` formulation and a per-kg value never do (tests: builder properties, readers).
- **M12** Unit conversion goes through the dimension check; a per-kg unit is never converted (tests: units).
- **M13** Reader B's module imports nothing from reader A, the resolver's classification or the pairing code (test).
- **M14** A derived clearance equals dose / AUC(0-inf) of its own arm and is labelled derived (test).

## 10. Owner decision 2026-11-11: M1 ships as experimental

M1 is merged and shown as **experimental**, with the measured confirmed-value precision (0.69, below the 0.90 exit
target) stated on every page and the instruction to read every value as unverified. M1 is not complete: its exit
criterion is reopened after the later milestones (M2–M6) and must be met before any production label. The status
text stays "Expert review has not yet been done".

## 11. Milestone M2 decisions
- **DP-M17 ClinicalTrials.gov through the official bulk file.** The job `modelkit_ctgov` downloads the one file
  `ctg-studies.json.zip` (all study records; one request, timeouts, generic user agent, no contact data) to its scratch
  directory, reads it and removes it; the raw file is never committed. The data API is not crawled (robots.txt disallows
  `/api/` for crawlers). Source, terms, processing date and the statement of modification are in `sources.toml` and
  `NOTICE`. The job writes rows of the evidence schema (`modelkit_evidence-2`, no change); `modelkit_evidence` merges the
  current run of `modelkit_ctgov` and drops the seed files' ClinicalTrials.gov rows of every drug the new run covers.
  Run order: `modelkit_ctgov`, then `modelkit_evidence`, then `deploy/sync-data.sh` from the developer machine (the
  server needs neither job).
- **DP-M18 Pool.** The 609 drugs of the atlas pilots; names in `data/modelkit/identity_m2.csv` (pool names, Wikidata
  labels and aliases of the drug's item, CC0; the curated codes, metabolites and prodrugs of M1 for its 50 drugs; very
  short, generic and slang names left out). The matcher is a prefix-tree regular expression (same matches as the sorted
  alternation of M1, tested), because thousands of names make a plain alternation slow.
- **DP-M19 Study to drug.** A study record is read for every pool drug named by its interventions (name, other names),
  arm groups or titles, if it has posted results and an outcome measure whose title names a PK parameter. Both readers
  read the same (study, drug) pair; confirmation is as in DP-M1. No reader or confirmation rule changed in M2.
- **DP-M20 Gate rule.** The system gate is interpretable iff at least 10 drugs have both AUC and Cmax tested on
  held-out studies (M1 counted drugs with AUC tested only). The system report also gives the point-level counts per
  metric (held-out points, points within 2-fold, GMFE of the points). Bootstrap intervals are computed in the
  milestone's research analysis, not in the product (M3).
- **DP-M21 List at scale.** `GET /modelkit/drugs` takes `q`, `status`, `has_set`, `limit` (1 to 200, default 50) and
  `offset`, answers sorted by name with `total` and release-wide `counts`; the summaries are computed once per release.
  The web list searches and pages (25 per page); the recorded demo answer holds every drug's summary and the drug pages
  of the drugs with a parameter set.

## 12. Milestone M2 properties
- **M15** The intake keeps a study only if it has posted results, a PK outcome measure and names a pool drug (test on a
  synthetic bulk file).
- **M16** The evidence job's merge replaces the seed's ClinicalTrials.gov rows of exactly the drugs the intake covers.
- **M17** The gate is interpretable iff at least 10 drugs have both metrics tested (test).
- **M18** The list route's page, search and filter agree with the full list; `counts` ignore the filters (test).

## 13. Milestone M3 decisions
- **DP-M22 Formulation and route are resolved from the study record, not assumed.** Two resolvers read, per (study,
  drug, results group), the evidence in four layers, most specific first: the results group, the outcome measure, the
  matching protocol arm (with the interventions of that arm that name the drug), and every intervention of the study that
  names the drug. Only text about the drug counts (clauses that name it, or every clause where the arm gives no other
  active drug; placebo clauses never). Resolver A (`formulation_a.py`) is pattern based; resolver B (`formulation_b.py`)
  works on token sequences and the record structure; they share only the result type, the decision rule and the product
  table (`formref.py`). Rule (`formref.decide`): nothing stated stays `unspecified`; fixed-dose-combination, then non-oral
  route, then modified-release words win; a bare tablet or capsule word is the weakest evidence for immediate release and
  loses against everything else; intravenous administration is a solution; oral and intravenous words in one layer, or an
  explicit immediate-release word against solution evidence, are a conflict and stay unresolved. `formulation.py` is the
  only place the two meet: the same formulation goes on both candidates if they agree, `unspecified` if not, and the
  confirmation is decided again by code. The route is filled the same way where the readers had none.
  The builder's immediate-release filter (DP-M3), the held-out rule and the status function are unchanged.
- **DP-M23 Marketed products.** `data/modelkit/product_forms.csv` maps a brand name to the dosage form class of its
  products in the public US product directory (openFDA NDC, CC0, human prescription products); a brand is kept only if all
  its products fall in one class and its name contains no name of a pool drug. A study that names the brand resolves to that
  class (a plain tablet or capsule counts as the weak immediate-release evidence).
- **DP-M24 Intervals.** For each metric (AUC, Cmax) one score per (drug, held-out study) is the geometric mean of its
  predicted / observed ratios; split-conformal width over all scores of the release (coverage 0.8); shown only from 20
  independent held-out studies (unchanged minimum), and per drug only for a complete set that can predict the metric. Below
  that the API and the interface give the reason code `interval_n_too_small` with n and the minimum.
- **DP-M25 System report page.** `GET /modelkit/validation` carries counts of drugs, sets and rows, the formulation and
  route counts of the confirmed values, the intervals, the reasons for Not validated and for no set, the measured precision
  (read from the evidence manifest, made from `data/modelkit/precision.json`; Wilson intervals computed by the API) and the
  list of what is missing. The web has its own page `/research/model-kit/report`; the list links to it.
- **MCP `janus_modelkit_evidence`** returns the evidence rows of one drug (optional `parameter` and `role` filter), read-only.

## 14. Milestone M3 properties
- **M19** Unspecified never becomes immediate release without evidence in the record; a modified-release word always wins
  over a generic tablet or capsule word (Hypothesis, both resolvers and the shared rule).
- **M20** Resolver B imports nothing from resolver A, the readers or the pairing code (test).
- **M21** No interval is given below 20 independent held-out studies; a study counts once per drug and metric (test).
- **M22** Every `/modelkit` route answers with exactly the documented fields, no-store headers and the documented error codes
  (contract tests).

## 15. Milestone M4 decisions
- **DP-M26 Route on conflict.** `formulation.resolve_pairs`: if either resolver reports `conflict:iv_and_oral` (oral and
  intravenous words in one evidence layer) the route of the pair is `unknown` and the readers' own route is not used.
  Nothing else changed (owner decision 2026-11-11 (c)); the held-out unit stays the study (decision (d)).
- **DP-M27 PK-Sim export.** The target `pksim` is a zip with `pksim-compound.snapshot.json` (a PK-Sim project snapshot,
  version 80 = PK-Sim 12.x: `Version`, `Name`, `Description`, `Compounds` with one compound that has a name, a description
  and `IsSmallMolecule`), `pksim-inputs.json` (what is missing, with a status, and what the evidence says that PK-Sim has no
  input for), and the common files. No physico-chemical value, no alternative and no process is written: the evidence has none,
  PK-Sim fills what a snapshot leaves out with its own defaults (they are PK-Sim's, not ours), and the total clearance of the
  evidence is not assigned to the hepatic or renal clearance process because that would be an assumption (PK-Sim then also needs
  body weight, fraction unbound and the blood/plasma ratio). The format is the open source snapshot schema of PK-Sim
  (`PKSim.Core.Snapshots`, GPL-2.0 with the Suite's clarifying addendum; ospsuite and rSharp are GPL-2.0 too); the keys used are tested against the property names of the classes.
- **DP-M28 PK-Sim check in CI.** Workflow `modelkit-pksim.yml` (path filtered, weekly and on demand, R image 4.6.1, .NET 8
  runtime from the distribution, ospsuite 12.4.5 and rSharp 1.2.3 from the project's GitHub release with sha256, cached): the export is
  loaded (`loadProjectFromSnapshot`), written back (`exportProjectToSnapshot`) and the compound's name, description and
  small-molecule flag must survive; a copy completed with test-only numbers (not drug data) plus an individual, a protocol and a
  simulation is run (`runSimulationsFromSnapshot`) and must give a positive, non-negative concentration profile. The export itself
  is not simulated: it lacks the inputs. ospsuite 12.4.5 bundles PK-Sim core 12.3.173; macOS is not supported by the run function.
- **DP-M29 Special populations.** Reader A (`sp_a`, sentence level patterns) and reader B (`sp_b`, headings first, then clauses and
  token windows) read the sections 8.5, 8, 12.3 and the clinical pharmacology text of the openFDA label files and their tables;
  they share only `sp_model` (result type, vocabulary). Convention: "X % higher" = 1 + X/100, "X % lower" = 1 - X/100, "X-fold
  or X times higher" = X, "X-fold lower" = 1/X, a range gives its geometric mean, a ratio outside (0, 50] is refused. A sub-section
  heading gives its class to at most 5 following sentences and only to a sentence that compares with a reference group. A
  confidence level ("90 % CI") is not a magnitude; a dialysis session is not a population; an absolute concentration column is not
  a ratio. `sp_confirm` pairs the candidates (class, grade, measure, ratio within 1 %, no context flag, same sentence).
- **DP-M30 Special populations in the product.** The job `modelkit_special_populations` writes the confirmed statements to
  `data/modelkit/special_populations.csv` (one row per drug, class, grade, measure and ratio; the label with the latest effective
  date is quoted; `n_labels` counts the labels with the same ratio). The older-adult atlas rows are in
  `special_populations_atlas.csv`; `special_populations.meta.json` holds coverage and the measured precision. The drug answer has
  `special_populations` (statements, atlas rows, reason codes), the system report has the counts, coverage and precision. The web
  drug page has a section "Special populations" (statements as quoted evidence; atlas rows in a collapsed block with their status).

## 16. Milestone M4 properties
- **M23** On an oral and intravenous conflict the route is unknown; the readers' own route never survives it (test, Hypothesis).
- **M24** The PK-Sim export invents nothing: only schema keys, no physico-chemical value, no process; every missing input has the
  status `missing` or `not_assigned` and no value (tests).
- **M25** The PK-Sim export loads in PK-Sim, exports again with name, description and small-molecule flag intact, and a completed
  copy simulates (CI workflow, `pytest -m pksim`).
- **M26** Reader B imports nothing from reader A or the pairing; both readers give the same ratio for the same sentence by the
  fixed convention (Hypothesis, shared table of sentences).
- **M27** A confirmed pair always agrees within 1 %, on class, grade and measure, without context flags (Hypothesis).

## 17. Milestone M5 decisions
- **DP-M31 Documents job.** `modelkit_documents` reads Drugs@FDA review PDFs and PMC Open Access articles. Reviews are located with the
  Drugs@FDA data file (single-ingredient NDAs of a pool drug, review documents of the original submission, the table-of-contents page
  for the PDF links; at most three PDFs per drug, clinical pharmacology or biopharmaceutics first, then multidiscipline or integrated);
  articles with the Europe PMC search (title names the drug and a PK word, open access, CC BY or CC0; one request every 10 s as robots.txt
  asks) and read from the PMC Article Datasets of NLM. Three licence checks (search result, bucket metadata, the XML licence element);
  retracted articles and author manuscripts are not used. The NCBI E-utilities are not used (robots.txt disallows them).
- **DP-M32 Tables only, two readers.** Born-digital PDFs (at least half of the pages have a text layer) are read through
  `pdftotext -layout`; scanned PDFs are counted, not read. Reader A (`doc_a`, line patterns) and reader B (`doc_b`, column intervals of
  the layout or the JATS grid, token rules) share only reference data (identity table, unit table, value types, the formulation evidence
  functions of the M3 resolvers and `formref.decide`); `documents.py` is the only meeting point: pairing on the shared locator (review:
  PDF, page, line, column of the number; article: PMCID, table id, row and column), confirmation by code (DP-M1), and the same study
  for both readers. Never read: summary, recommendation, conclusion, overview and labeling sections; dispersion, bound, count and test
  columns; ratio, least-squares, model, simulation, toxicokinetic, radioactivity, animal and special-population tables; dose-normalised
  quantities. Dose only from the column header, the title or caption, the footnotes, or the study's design text (review section of that
  study code; article methods with a dosing verb). Where a review table is silent on formulation and route and every product of the
  application is a plain oral tablet or capsule, the products give immediate release and oral (the label rule DP-M15 for reviews).
- **DP-M33 Human only.** An article is dropped if its title, journal, keywords or abstract name another species or a veterinary context,
  a table if its caption, footnotes or header name one; an article needs a human cue in its abstract or methods (`species.py`; the pilot's
  horse case is a test).
- **DP-M34 Study identity (leakage guard).** Two studies of one drug are the same study if they share an NCT number, a sponsor study code
  (ClinicalTrials.gov: organisation and secondary ids, `data/modelkit/ctgov_study_ids.csv`), duplicate a result (same parameter other
  than Tmax, doses equal within 1 %, values within 1 %, n equal or missing), or are a review's document-level study and a coded study
  of the same PDF; links close transitively (`study_identity.py`; columns `study_keys`, `study_group`, schema `modelkit_evidence-3`).
  `split_studies` puts a study whose group has more than one study on the training side: it never tests.
- **DP-M35 Publishing rule.** A document source's values enter the evidence store only if its measured precision (blinded sample, two
  automated review passes) is at least 0.70 and the upper Wilson bound at least 0.75; `data/modelkit/precision_documents.json` records the
  measurement and the decision; held-back rows are counted in the manifest. PMC rows carry the article's authors, title, journal, year,
  DOI and licence in `source_version`, shown with every value.

## 18. Milestone M5 properties
- **M28** Reader B (`doc_b`) imports nothing from reader A, the pairing or the meeting module (test).
- **M29** The pilot's horse case and every non-human article reach no reader (test).
- **M30** A study linked to another study never tests; without links the split is unchanged (tests).
- **M31** Dispersion, count and test columns never give a value; a dose is never taken from an abstract (tests).

## 19. Milestone M6 decisions
- **DP-M36 Special populations are evidence, not set inputs (plan section 7 rule 3).** `population_class` reads the row's
  population: `special` (the readers' class: children, older adults, renal or hepatic impairment), `healthy`, `patients`,
  `unspecified`. A special row never builds and never tests (`exclusion_reason`: `special_population`). A row of patients
  builds only if the drug has no healthy-adult row the builder can read (parameter and route in `builder.READS`, building
  study, no exclusion). The reference of a set is the class of the rows it uses (healthy, else patients, else unspecified);
  a held-out observation is tested only if its class is the reference or unspecified (every class but special for an
  unspecified reference). Other rows get `not_reference_population`; a set that uses a patients row carries the warning
  `reference_population_patients`. The study split is unchanged (every row of every population still decides it), so
  nothing is loosened. Pre-registered with three dated addenda (private).

## 20. Milestone M6 properties
- **M32** No used row and no tested point is of a special population; used rows are of the drug's building classes and
  tested points of the classes compatible with the set's reference (Hypothesis, builder properties).
- **DP-M37 Expert sample audit record.** `pipelines/janus_pipelines/modelkit/audit.py` scores filled answer sheets
  (precision = correct / (correct + incorrect), Wilson 95 %, per stratum, margin and overall; strict consensus of several
  reviewers; Cohen's kappa) and checks the record `modelkit_expert_audit-1` (date, release audited, n, correct, cannot
  judge, precision, Wilson bounds, criterion of plan 12.3 met, reviewer roles; exactly these fields, no name). The tool
  `pipelines/tools/score_modelkit_audit.py` writes it; `modelkit_evidence` reads `data/modelkit/expert_audit.json` when it
  exists (absent: input hash unchanged). The API puts it in `statements.expert_audit` and the line "Expert audit: precision X
  (n = N, date)." in `statements.expert_review`; the system report replaces the caveat `expert_review_pending` with
  `expert_audit_sample_only` and lists `expert_audit_below_target` while the criterion is not met. Web and MCP rebuild the
  line from the numbers. Exports keep "Expert review has not yet been done." (the audit does not review a model file).
- **DP-M38 Data package.** `janus.modelkit.package` writes the package of a release (evidence, special populations, sets,
  validation, licences, README, `datapackage.json`, `.zenodo.json` without DOI or creators); a row of an unpublished source
  or a PMC row without CC BY or CC0 stops the build. Not committed, not uploaded (owner decision).
- **DP-M39 Strict publication check (selective prediction).** After the two readers agree, `strict_ctgov.check` reads only
  the record's structure (interventions, arms, result group, outcome measure, cell titles) and the row's formulation, route,
  regimen, dose and co-administration flags, and returns rule codes; `level` maps them to nested levels 1-5. The
  ClinicalTrials.gov intake keeps a value confirmed only at level >= 3 (`PUBLISH_LEVEL`); below it the row stays in the run
  with `confirmed = false` and reason `strict_check` plus the codes. It shares no code with readers A and B (test). Measured
  on fresh blinded samples with two automated passes (private pre-registration); the measured precision is in
  `data/modelkit/precision.json`. The same kind of check exists for label statements (`strict_sp`, with the list-aligning
  third reader `sp_c`) and PMC tables (`strict_pmc`); neither reached its pre-registered precision and neither is used.
- **M33** The scoring recomputes from the counts; a record with any other field (a name) or numbers that do not recompute
  is refused by the job and not shown by the API (tests).
- **M34** The package holds only publishable rows and every file's hash; the same release gives the same bytes (tests).
