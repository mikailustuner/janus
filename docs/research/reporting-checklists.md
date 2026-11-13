# Reporting checklists

Where each item of the relevant reporting guideline is answered for the two validation studies. Items that do
not apply say why. Open items are marked **open**.

- CV = [cascade-validation.md](cascade-validation.md), CVP = [cascade-validation-protocol.md](cascade-validation-protocol.md),
  RS = `data/validation/cascades/README.md` (reference set).
- FC = [faers-calibration.md](faers-calibration.md), FCP = [faers-calibration-protocol.md](faers-calibration-protocol.md).

## Cascade detection validation: STARD 2015

Bossuyt PM et al. STARD 2015: an updated list of essential items for reporting diagnostic accuracy studies.
BMJ 2015;351:h5527. The "participants" of this study are drug pairs and published case reports, not patients.

| #   | Item                                                                            | Where                                                                                                                       |
| --- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| 1   | Identified as a study of diagnostic accuracy, with a measure of accuracy        | CV title and summary (sensitivity, specificity)                                                                             |
| 2   | Structured summary                                                              | CV "Summary"                                                                                                                |
| 3   | Scientific background, intended use of the index test                           | CVP §1; CV "What follows for the product"                                                                                   |
| 4   | Objectives and hypotheses                                                       | CVP §1, §4 (H1, H2)                                                                                                         |
| 5   | Prospective or retrospective data collection                                    | CVP §3 (published literature, collected after registration)                                                                 |
| 6   | Eligibility criteria                                                            | CVP §3.1–3.3; RS inclusion and exclusion                                                                                    |
| 7   | How potentially eligible units were identified                                  | RS search strategy (databases, queries, dates)                                                                              |
| 8   | Where and when units were identified                                            | RS (sources and search dates)                                                                                               |
| 9   | Consecutive, random or convenience series                                       | RS (all eligible rows of the included reviews; case reports in relevance order); negatives by seeded random draw (CVP §3.2) |
| 10a | Index test in enough detail to replicate                                        | CVP §2; CV "Index test" (release, dataset, rule-base hashes)                                                                |
| 10b | Reference standard in enough detail to replicate                                | CVP §3; RS; `build_negatives.py`, `build_positives.py`                                                                      |
| 11  | Rationale for the reference standard                                            | CVP §3.1 (sources independent of the rule base)                                                                             |
| 12a | Definition and rationale of positivity for the index test, pre-specified or not | CVP §2 (pre-specified)                                                                                                      |
| 12b | Definition of the categories of the reference standard                          | CVP §3.1–3.2 (pre-specified)                                                                                                |
| 13a | Whether the index test's assessors knew the reference standard                  | Not applicable: the index test is automated and answered the public API                                                     |
| 13b | Whether the reference standard's assessors knew the index test                  | CVP §3.4; RS (built blind to the rule base, engine and output)                                                              |
| 14  | Methods for estimating and comparing diagnostic accuracy                        | CVP §4, §6 (Wilson intervals)                                                                                               |
| 15  | Handling of indeterminate results                                               | CVP amendment 1 (unresolved names)                                                                                          |
| 16  | Handling of missing data                                                        | CVP amendment 1; CV (unresolved counts)                                                                                     |
| 17  | Analyses of variability, pre-specified or exploratory                           | CVP §6 (one pair per cascade); CV (within-scope sensitivity, labelled exploratory)                                          |
| 18  | Intended sample size and how it was determined                                  | CVP §5                                                                                                                      |
| 19  | Flow of units                                                                   | RS flow (found, screened, included, reasons); CV pair and case counts                                                       |
| 20  | Baseline characteristics                                                        | RS (sources, ingredient rule tallies, case ages); CV "Limits"                                                               |
| 21a | Distribution of the target condition's severity                                 | Not applicable to drug pairs; case characteristics in RS                                                                    |
| 21b | Distribution of alternative diagnoses in those without the target condition     | CV "Flagged negative pairs"                                                                                                 |
| 22  | Time between index test and reference standard                                  | CV (reference set pushed `38ef35c` before the run on 2026-11-13)                                                            |
| 23  | Cross tabulation of index test by reference standard                            | CV primary table (79/217, 421/432) and `results/`                                                                           |
| 24  | Estimates of accuracy with precision                                            | CV primary and secondary tables                                                                                             |
| 25  | Adverse events from the tests                                                   | Not applicable (no participants)                                                                                            |
| 26  | Limitations                                                                     | CV "Limits"; CVP §7                                                                                                         |
| 27  | Implications for practice                                                       | CV "What follows for the product"                                                                                           |
| 28  | Registration                                                                    | Pre-registered in the public repository (commit `d7a0b1f`); not in an external registry                                     |
| 29  | Where the full protocol can be accessed                                         | CVP                                                                                                                         |
| 30  | Sources of funding and role of funders                                          | **open** (to be stated by the owner)                                                                                        |

## FAERS signal calibration: READUS-PV

Fusaroli M et al. The REporting of A Disproportionality analysis for drUg Safety signal detection using individual
case safety reports in PharmacoVigilance (READUS-PV): explanation and elaboration. Drug Saf 2024;47(6):585–599.
Checklist: <https://readus-statement.org>.

| #   | Item                                                                    | Where                                                                                                     |
| --- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| 1a  | Identified as a disproportionality analysis; data type and database     | FC/FCP title and §2–3 (FAERS)                                                                             |
| 1b  | Events and drugs under study                                            | FCP §2–3 (reference sets and outcome definitions)                                                         |
| 2a  | Drugs, events and existing knowledge                                    | FCP §2 (reference sets with known answers)                                                                |
| 2b  | Rationale                                                               | FCP §1 (how well the statistic the site shows separates known pairs)                                      |
| 2c  | Why case-report databases and disproportionality fit                    | FCP §1, §6                                                                                                |
| 3   | Objectives, pre-specified hypothesis                                    | FCP §1, §4                                                                                                |
| 4a  | Study identified, data type                                             | FCP §3                                                                                                    |
| 4b  | Whole design incl. sensitivity analyses                                 | FCP §4–5                                                                                                  |
| 5a  | Database, custodian, coverage, coding of drugs and events               | FCP §3 (FDA FAERS, MedDRA preferred terms, ingredient keys)                                               |
| 5b  | Extraction dates and pre-processing                                     | FCP §3 (artifact run, quarters, removal of superseded versions and deleted cases)                         |
| 6a  | Study population and restrictions                                       | FCP §3 (all reports of the four quarters)                                                                 |
| 6b  | Key variables                                                           | FCP §3–4                                                                                                  |
| 6c  | Grouping of drugs and events; ingredients, salts, roles                 | FCP §3 (ingredient keys; suspect roles; outcome term lists)                                               |
| 6d  | Additional data sources                                                 | FCP §2 (reference sets)                                                                                   |
| 7a  | Descriptive analyses                                                    | FC "Pairs"                                                                                                |
| 7b  | Disproportionality measures and thresholds                              | FCP §3 (ROR, PRR, Evans criteria)                                                                         |
| 7c  | Sensitivity analyses, control of confounding                            | FCP §4 (non-estimable pairs at lowest score, per set, per outcome, empirical calibration)                 |
| 7d  | Case-by-case analysis                                                   | Not performed (not the study's aim)                                                                       |
| 7e  | Methods for other data sources                                          | FCP §4 (DeLong, Schuemie empirical calibration)                                                           |
| 8a  | Number of reports at each stage                                         | FCP §3 (1,626,375 input, 1,510,804 after removals); FC "Pairs"                                            |
| 8b  | Characteristics of cases                                                | Not applicable (method evaluation over reference pairs, not a case series)                                |
| 9   | All results with confidence intervals, incl. sensitivity analyses       | FC primary and secondary tables, `results/pairs.csv`                                                      |
| 10  | Case-by-case results                                                    | Not performed                                                                                             |
| 11  | Key results in context                                                  | FC "Summary"                                                                                              |
| 12a | External validity                                                       | FC "Limits"                                                                                               |
| 12b | Relevance for practice                                                  | FC "Summary" (a ratio is a reason to look closer)                                                         |
| 12c | Further designs                                                         | [limitations.md](limitations.md)                                                                          |
| 13  | Limitations: no causation, no incidence; confounding and reporting bias | FC "Limits"; FCP §6                                                                                       |
| 14a | Funding                                                                 | **open** (to be stated by the owner)                                                                      |
| 14b | Conflicts of interest                                                   | **open** (to be stated by the owner)                                                                      |
| 14c | Institutional approval                                                  | No participants were recruited; only public, de-identified reports and published reference sets were used |
| 14d | Data, code and protocol availability                                    | FC (script, outputs, protocol commit `d505bd2`); [reproduce.md](reproduce.md)                             |
