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
