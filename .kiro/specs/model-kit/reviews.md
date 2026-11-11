# Review notes: model kit M0 (automated checks only; expert review has not yet been done)

## What the first milestone found

The second data-source pilot called six drugs simulatable with a held-out value within 2-fold. M0 rebuilt
them from confirmed evidence under stricter, written rules. The count of validated drugs falls from six to two,
and the reasons are the useful result.

| Drug | M0 status | Why |
|---|---|---|
| ertugliflozin | Validated (AUC 2 studies, ratio 0.91; Cmax 1 study, ratio 0.60) | intravenous clearance and volume from the label, bioavailability about 100 %, peak time from the label. The set does not reproduce the stated half-life (implied 5.3 h, stated 16.1 h); the page says so. |
| sunitinib | Validated, near the limit (AUC 1 study, ratio 0.81; Cmax 1 study, ratio 0.50, one of two points just outside 2-fold) | apparent oral values from the label (ranges taken as geometric midpoints, class C). The observations come from one scanned review. |
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
