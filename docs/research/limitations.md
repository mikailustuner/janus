# Known limitations

Everything Janus is known not to do well, in one place, with the measurement behind each point where one exists.
Janus is a research prototype, not a medical device. Expert review has not yet been done.

## Prescribing cascades

- **A fixed list.** The engine checks the 65 cascades of the PIPC list (Rochon et al. 2025). Published cascades are
  much broader: on 217 cascades from sources independent of that list, Janus flagged 36 % (95 % CI 30–43 %); all 77
  whose drug classes the list links were flagged. "No notice" never means "no cascade".
  ([cascade-validation.md](cascade-validation.md))
- **Notices are frequent in polypharmacy.** Half of older patients' full medication lists from case reports that
  describe no cascade (26 / 50) received at least one notice, mostly statin → pain reliever and NSAID →
  antihypertensive. A notice is a pattern to discuss with a doctor, not a finding that something is wrong.
- **Classes are drawn by ATC code.** A drug outside the mapped classes is never checked; 59 of the 138 missed
  published cascades involved such a drug.
- The reference set for these numbers was assembled by automated literature steps; no clinician has checked it.

## FAERS reporting ratios

- **Not causation, and the intervals are too narrow.** For drug–event pairs known to have no effect, the nominal
  95 % interval of the reporting odds ratio excludes 1 in 26 % of pairs (expected 5 %); typical ratios of up to
  about 13 arise from reporting artefacts alone. The ratio separates known causal from non-causal pairs with an AUC
  of 0.74 (0.69–0.78). ([faers-calibration.md](faers-calibration.md))
- Counts are reports, not people; there is no denominator of patients. One year of reports (2025Q4–2026Q3); rare
  drugs have few reports. Reporting follows publicity, litigation and stimulated reporting.
- The Evans criteria Janus uses to call a pair "disproportionate" flag 55 % of known causal pairs and stay silent for
  88 % of known non-causal pairs.

## Medicine names and products

- Some ingredient names do not resolve (for example thyroxine, niacin and epoetin alfa as spelled in the FAERS
  reference sets). An unresolved medicine is not checked; the screen says so.
- National product lists differ in coverage and update cadence; a product missing from a list cannot be scanned.
- Label photos are read on the device with OCR; recognition errors are possible and every result is confirmed by
  the person before it is used.

## Drug model starter kit (experimental)

- Values are read from documents by automated readers. The measured precision (0.99) covers ClinicalTrials.gov
  values that pass a strict check, about 13 % of the values both readers agree on; other sources are held back until
  they meet the same bar. How many true values are missed (recall) has not been measured.
- The model kit's validation gate has too few drugs with held-out data to be interpreted.
  ([modelkit-precision.md](modelkit-precision.md))
- It is not a dose calculator and gives no dose advice.

## Simulations

- The in-browser explorer and the queued simulations are in silico and exploratory; a concentration or dose in
  them is never a dose a person could take.

## Translations

- Interface and notice texts in Turkish, German, French, Spanish and Portuguese were drafted by automated tools and
  have not been reviewed by native speakers.

## Operations

- One server; a failure means downtime until restore from backup. The CDS Hooks service has no client
  authentication yet and is for sandboxes only. ([security.md](../security.md))

## How to report an error

Open an issue at <https://github.com/mikailustuner/janus/issues> (no personal or patient data), or for a
vulnerability use the repository's private vulnerability reporting.
