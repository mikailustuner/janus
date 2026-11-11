# Review notes: model kit M0 (automated checks only; expert review has not yet been done)

Update 2026-11-11 (owner decision, strict rule): a drug is Validated only if every held-out point is within
2-fold. Sunitinib (one Cmax point at 0.499) is now Failed; the other statuses are unchanged. The table below
records the M0 statuses under the earlier drug-level rule and is kept for the history.

## What the first milestone found

The second data-source pilot called six drugs simulatable with a held-out value within 2-fold. M0 rebuilt
them from confirmed evidence under stricter, written rules. The count of validated drugs falls from six to one under the strict rule (two under the earlier drug-level rule),
and the reasons are the useful result.

| Drug | M0 status | Why |
|---|---|---|
| ertugliflozin | Validated (AUC 2 studies, ratio 0.91; Cmax 1 study, ratio 0.60) | intravenous clearance and volume from the label, bioavailability about 100 %, peak time from the label. The set does not reproduce the stated half-life (implied 5.3 h, stated 16.1 h); the page says so. |
| sunitinib | Failed under the strict rule (AUC 1 study, ratio 0.81; Cmax 1 study, ratio 0.50, one of two Cmax points at 0.499, just outside 2-fold; the earlier drug-level rule had called it Validated, near the limit) | apparent oral values from the label (ranges taken as geometric midpoints, class C). The observations come from one scanned review. |
| dolutegravir | Not validated: Cmax not tested (AUC 1 study, ratio 0.73) | apparent oral values from the label; no confirmed Cmax observation in a held-out study. |
| gabapentin | Not validated: no parameter set | the label's clearance is age- and dose-dependent and the readers did not confirm it; bioavailability falls with dose. |
| tramadol | Not validated: no parameter set | the per-kg label values are not converted, the sex-specific values are not used, the trial evidence is modified-release or not confirmed by both readers. |
| telmisartan | Not validated: no parameter set | the clearance is only a lower bound, bioavailability depends on dose, the trial evidence is co-administered or a fixed-dose combination. |

## Findings of the confirmation step

- The label extractor was wrong for sunitinib (the half-life of the primary active metabolite, 80 to 110 h, was read
  as the parent's), tramadol (the half-life of the M1 metabolite was read as the parent's), dolutegravir (a
  food-effect peak time) and telmisartan (a bound read as a value). Two blind readers caught all of them; none of
  these rows reached a parameter set.
- Two once-daily tramadol studies and a telmisartan fixed-dose-combination study had been counted as ordinary
  evidence. The formulation and co-administration filters remove them.
- Reader B labelled test and reference arms of a bioequivalence study as a restriction ("other"), which made
  tramadol's only immediate-release half-life and peak time unconfirmed. The rule was applied as written; reader
  instructions for arms of crossover studies are an M1 task.

## Limits

- n is very small (1 to 2 held-out studies per metric). No interval is shown. Ratios describe these drugs only.
- The held-out rule looks at which parameters a study reports. A study that reports a half-life, a clearance or a
  peak time counts as a building study even if the row is unconfirmed, so a few usable observations are not tested.
- AUC to the last sampling time is not compared (the time is not in the evidence). Steady-state Cmax is not modelled.
- One-compartment model only; the Janus engine export is a point model with no variability.
- Clearance from AUC and dose (CL/F = dose / AUC to infinity) is not derived in M0 (task M1).
- The CI job for mrgsolve could not be run on a hosted runner in this environment; the round trip was run locally
  (R 4.6.1, mrgsolve 2.0.1) with a negative control (a 2 % clearance change fails the 1 % check).

# Review notes: model kit M1 (automated checks only; expert review has not yet been done)

M1 re-read the 50 pilot drugs with the resolver, the unit checker and two independent readers (design section 9).
The exit target, a precision of at least 0.90 for confirmed values on a blinded sample, was **not met**.

| | Run 1 | Run 2 (after the failure classes of run 1) |
|---|---|---|
| Confirmed stated values in the pool | 450 | 346 (run 1 sample removed) |
| Blinded sample (at most 3 per document) | 100 | 100 |
| Two automated review passes agree (correct or incorrect) | 94 | 85 |
| Primary precision (both passes correct / both passes agree) | 0.66 (Wilson 95 % 0.56 to 0.75) | 0.69 (0.59 to 0.78) |
| Conservative (anything not called correct by both counts as wrong) | 0.62 (0.52 to 0.71) | 0.59 (0.49 to 0.68) |
| By source, run 2 | | ClinicalTrials.gov 48 of 59 (0.81), label text 11 of 26 (0.42) |

Reader agreement (share of reader A's parent-drug values that reader B confirms): ClinicalTrials.gov 0.46
(458 of 987, Wilson 0.43 to 0.50), label text 0.61 (98 of 161, 0.53 to 0.68). Almost all remaining errors were shared
by both readers (a cue that both use), not caught by the second reader.

What the review found, and what was fixed for run 2: regimen read as "multiple dose" from the word "daily"; an
injection read as intravenous; a second active drug in the same arm not recognised; a dose taken from the neighbour in a
combination; the value of a comparator or antidote in the same record; a fed/fasted column taken from a caption.
What is left (open items): arm context of combination and comparator groups (dabrafenib with trametinib, a combination
product), analyte of closely named drugs (cisatracurium for atracurium), special populations and phases in label
sentences (paediatric, renal impairment, a beta phase), route from the label sentence, and a reader B that is not a twin
of reader A.

Sets and gate (strict rule): of the 50 drugs, 42 have any evidence row for the parent drug; 4 have a parameter set
(2 complete); 0 are Validated, 1 Failed (a single Cmax point), 41 Not validated; the system gate is not interpretable
(fewer than 10 drugs with AUC and Cmax tested). The six M0 drugs are all Not validated under M1 (ertugliflozin was
Validated and sunitinib Failed in M0): the M0 rows had been judged by annotation passes that are not a product
pipeline, and the deterministic readers confirm fewer rows. 7 clearances were derived (dose / AUC); 2 remain after run 2.
Values refused by the unit checker (ClinicalTrials.gov, reader A): dimension mismatch 1,411, unknown unit 316, molar
unit 162. Seeds hold 916 rows (all parent rows, at most 3 non-parent rows per drug as examples of separate analytes).

Limits: the readers were developed on the same 50 drugs and documents; the two review passes are runs of one model
family and may share blind spots; the sample measures precision, not recall; run 2 changes were made after seeing run 1.

# Review notes: model kit M2 (automated checks only; expert review has not yet been done)

M2 read the official ClinicalTrials.gov bulk file for the 609-drug pool (design section 11). Pre-registered before any
result; the figures below are the pre-registered metrics.

| | Result |
|---|---|
| Study records in the bulk file / with posted results / with a PK outcome / naming a pool drug | 611,234 / 80,976 / 7,070 / 2,966 |
| Candidate values (reader A) / rows stored / confirmed parent rows | 67,771 / 36,376 / 2,458 (183 drugs) |
| Drugs in the store (any row) | 404 |
| Drugs with a parameter set / complete set | 18 / 4 |
| Status: Validated / Failed / Not validated | 0 / 1 / 403 |
| Drugs with AUC and Cmax both tested on held-out studies | 0 (needed: 10) |
| **Gate** | **Not interpretable.** One held-out Cmax point (enzalutamide, ratio 0.35); no AUC point |
| Precision of confirmed values (blinded sample, two automated review passes, 166 drugs that are not development drugs) | 0.73 (Wilson 95 % 0.64 to 0.81), n = 97; conservative 0.71 (0.61 to 0.79); below the 0.90 target |

What limits the number of sets: of 2,489 confirmed stated rows (200 drugs), 47 % have an unspecified formulation (an arm
that does not say tablet or solution) and cannot build or test (design DP-M3); only 612 rows of 72 drugs pass the
formulation and co-administration filters. A set needs a clearance and a volume (or a half-life), most
ClinicalTrials.gov records report only Cmax, AUC or Tmax, and the held-out rule makes a study that also reports a
half-life a building study. Clearances are derived only for a single-dose AUC to infinity with a known route.
