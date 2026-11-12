# Model kit evidence seeds (experimental)

`evidence_seed.csv` is the small committed input of the `modelkit_evidence` pipeline job (spec:
`.kiro/specs/model-kit/`). One row per fact for six drugs (dolutegravir, ertugliflozin, gabapentin, sunitinib,
tramadol, telmisartan): the value as the source states it, its locator, the quoted text, and the verdicts of two
automated reader passes. Nothing here is a recommendation. Research use only. Not for clinical decisions. Expert
review has not yet been done.

How the rows were made (all automated):
- ClinicalTrials.gov, Europe PMC (CC BY articles only) and one scanned FDA review: values were extracted by rule-based
  readers, then judged against the source by two separate annotation passes; a row is confirmed only if both agree.
- US labels (DailyMed): label sentences were extracted by rule, then re-read blind by two separate passes that saw
  only the sentence and the quantity asked for; code compared their answers with the extracted value. Where they
  disagreed the row is kept with `confirmed = false` and is never used.
- Rows judged wrong by both passes (another analyte or another drug) are not in the file.

Source terms: ClinicalTrials.gov data is shown with attribution, the date the record was processed, and the
statement that units were converted and values re-typed (see `pipelines/sources.toml`, `NOTICE`). FDA labels and
reviews are public domain. PMC rows come from articles under CC BY with per-article attribution. The file holds
short quotes only; no raw downloads.

## Milestone M1 files
- `evidence_m1.csv`: values read from ClinicalTrials.gov outcome measures and DailyMed label section 12.3 for the 50
  pilot drugs by two independent automated readers (reader A pattern based, reader B structure first); a value is
  confirmed only if both give the same value, unit, analyte, dose and context (code decides). All rows of the parent
  drug, confirmed or not, and at most three rows per drug of other analytes (metabolite, partner drug, unknown code) as
  examples of what is stored apart. Derived clearances (dose / AUC to infinity of one arm) carry `origin = derived`.
  Made by `python -m janus_pipelines.modelkit.pilot` from private pilot inputs; the readers are in
  `pipelines/janus_pipelines/modelkit/`.
- `identity_m1.csv`: names of the 50 drugs: Wikidata labels and aliases (CC0) and a short curated list of named
  metabolites and prodrugs; the resolver uses it for analyte classes.
- `sources_m1.json`: title, link and terms of every record behind a row.
- Measured precision of confirmed values on a blinded sample (two automated review passes): 0.69, n = 85, below the
  0.90 target (`.kiro/specs/model-kit/reviews.md`). Read every value as unverified. Research use only. Not for clinical
  decisions. Expert review has not yet been done.

## Milestone M2 files
- `identity_m2.csv`: names of the 609-drug pool (pool names, Wikidata labels and aliases, CC0; the M1 codes,
  metabolites and prodrugs for the 50 M1 drugs; very short, generic and slang names left out). Made by
  `pipelines/tools/build_modelkit_identity.py`. The ClinicalTrials.gov intake (`modelkit_ctgov`) uses it.
- ClinicalTrials.gov rows of the whole pool are not committed: the job `modelkit_ctgov` reads the official bulk file of
  all study records, keeps the studies with posted results that name a pool drug and report a PK outcome, and reads
  them with the two readers. `modelkit_evidence` merges its current run and replaces the ClinicalTrials.gov rows of the
  seed files for the drugs it covers. Source, terms, processing date and the statement of modification are in
  `pipelines/sources.toml` and `NOTICE`.

## Milestone M3 files
- `product_forms.csv`: dosage form class (immediate release, solution, modified release, fixed-dose combination, other
  route) and route of marketed products (brand names) of the 609-drug pool, from the public US product directory
  (openFDA NDC, CC0; human prescription products only; a brand is kept only if all its directory products fall in one
  class). Made by `pipelines/tools/build_modelkit_product_forms.py`. The formulation resolvers
  (`pipelines/janus_pipelines/modelkit/formulation_a.py` and `formulation_b.py`) use it when a study names a marketed
  product. The directory lists today's products, not necessarily the product used in a study.
- `precision.json`: the measured precision of confirmed values on the fresh blinded sample of milestone M3 (two automated
  review passes, evaluation only): counts only; the evidence job copies it into the release manifest and the API computes
  the Wilson intervals. Read every value as unverified. Expert review has not yet been done.

## Milestone M4 files
- `special_populations.csv`: the exposure statements about older adults, renal impairment and hepatic impairment that two
  independent automated readers of the openFDA label text (CC0) agree on, one row per drug, population class, grade,
  measure and ratio (population / reference population; "30 % higher" = 1.30, "2-fold lower" = 0.5, a range gives its
  geometric mean), with the population definition as written, the reference population if the sentence names one, the quote,
  the label's set id, version and effective date, and the number of labels that state the same ratio. Written by the job
  `modelkit_special_populations` (it reads the 14 label files once, about 1.8 GB, one at a time). Quoted evidence only: not
  extrapolated to a model, not dose advice, not checked by a person.
- `special_populations_atlas.csv`: one row per drug from the older-adult exposure atlas: an earlier automated extraction
  that the two-reader rule did NOT confirm and that no person has checked; the API and the pages show it only as evidence
  with its quote and that status, never as a verdict. `quote_checked` is true where the quote was found word for word in the
  cited label version.
- `special_populations.meta.json`: coverage counts of the label job and the measured precision of the confirmed statements on
  a blinded sample (two automated review passes, evaluation only; counts only, the API computes the intervals).
- PK-Sim export (`target=pksim`): a PK-Sim project snapshot with one compound (name, description, small molecule) and
  `pksim-inputs.json`. The evidence does not hold lipophilicity, pKa, fraction unbound, blood/plasma ratio, solubility,
  permeability, molecular weight or the clearance process; they are marked missing and nothing is invented. The file loads
  in PK-Sim 12.x and exports again (checked in `.github/workflows/modelkit-pksim.yml` with ospsuite 12.4.5, which bundles
  PK-Sim core 12.3.173, GPL-2.0 with the Suite's clarifying addendum, on Linux); it is not simulated as exported.

## Milestone M5 files
- `ctgov_study_ids.csv`: the organisation study id and secondary ids of every ClinicalTrials.gov record in the evidence
  (normalised: upper case letters and digits), read from the official bulk file by
  `pipelines/tools/build_modelkit_ctgov_ids.py`. Used only by the study identity rule: a study that may be the same study
  in another source (shared trial number, shared study code, identical results) never tests a parameter set.
- `precision_documents.json`: the measured precision of the confirmed values of the two document sources of milestone
  M5 (Drugs@FDA review tables, PMC article tables; blinded samples of 100 values, two automated review passes) and whether
  their values are published. Rule fixed before the measurement: published only if the precision is at least 0.70 and the
  upper Wilson bound at least 0.75. Both measured 0.48 on 2026-11-12: neither is published.

## Milestone M6 files
- No new committed file. `expert_audit.json` is **absent** until a person has audited the pre-registered sample of the
  published confirmed values. When the project owner adds it (written by `pipelines/tools/score_modelkit_audit.py`
  with `--record`), the job `modelkit_evidence` checks it strictly (exact fields, counts that recompute, reviewer roles
  only, never a name) and copies it into the manifest; the API, the web pages and the MCP text then show "Expert audit:
  precision X (n = N, date)." instead of "Expert review has not yet been done."


## Precision work (strict publication check)
- ClinicalTrials.gov values: after the two readers agree, a third, separate check
  (`pipelines/janus_pipelines/modelkit/strict_ctgov.py`) reads only the record's structure (interventions, arms, the
  result group, the outcome measure and the cell titles) and abstains unless the context is plain: no other agent in the
  arm or record, no metabolite, matrix, clearance-type, transformed, modelled or pharmacodynamic read-out, no special
  population, no release-modifying or non-oral non-intravenous product, no body-size dose, no regimen contradiction, a
  known oral or intravenous route. Values below level 3 are kept in the run with `confirmed = false` and the reason
  "the strict publication check abstained (codes)". This trades coverage for precision: about one in eight of the values
  the two readers agree on stays confirmed.
- `precision.json` now holds the measurement of that check: every not-yet-reviewed confirmed value of non-development drugs
  at level 3 (126 values, 14 studies), two automated review passes, evaluation only. Values within a study are correlated,
  so read the interval as optimistic. Read every value as unverified. Expert review has not yet been done.
- US-label special-population statements and the document sources (FDA reviews, PMC articles) are unchanged: their
  strict checks (`strict_sp.py` with the list-aligning reader `sp_c.py`, `strict_pmc.py`) did not reach the pre-registered
  precision on fresh samples and are not used for publishing.
- Round 3 reference tables, used only by the strict check (made by `pipelines/tools/build_modelkit_reference.py`):
  `analytes.csv` (drug, name, relation, source): metabolite names read from the pharmacokinetics and clinical
  pharmacology sections of single-substance openFDA drug labels (CC0; only metabolite-shaped names are kept), prodrug
  esters from the public US product directory (openFDA NDC, CC0; dabigatran etexilate, tenofovir alafenamide ...),
  and reversal agents from label indications (andexanet alfa, idarucizumab). `combination_products.csv` (brand,
  components, source): products with two or more active ingredients, at least one a pool drug, from the same
  directory (prescription and OTC) and from multi-ingredient labels. A value whose outcome or group names one of
  these, or whose intervention names such a product, is not kept. Automated, not checked by a person.
