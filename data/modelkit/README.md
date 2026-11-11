# Model kit evidence seed (experimental)

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
