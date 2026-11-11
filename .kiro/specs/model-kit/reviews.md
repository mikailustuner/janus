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

# Review notes: model kit M3 (automated checks only; expert review has not yet been done)

M3 resolved the formulation and route of each value from the study record with two independent automated resolvers
(design section 13) and re-ran the M2 pipeline on the same bulk file. Pre-registered before any result; figures below are
the pre-registered metrics. No rule of the builder, the held-out split, the status function or the confirmation changed.

| | M2 | M3 |
|---|---|---|
| Confirmed stated parent values of ClinicalTrials.gov | 2,392 | 2,565 |
| Formulation stated (not "unspecified") | 1,248 (52.2 %) | 1,944 (75.8 %) |
| Immediate release or solution (can build or test) | 809 (33.8 %) | 1,416 (55.2 %) |
| Route known | 1,842 (77.0 %) | 2,199 (85.7 %) |
| Drugs with a parameter set / complete set | 18 / 4 | 26 / 8 |
| Validated / Failed / Not validated | 0 / 1 / 403 | 0 / 1 / 403 |
| Drugs with AUC and Cmax both tested on held-out studies | 0 | 0 (one drug with an AUC point, one with a Cmax point) |
| Gate (at least 10 drugs with both) | not interpretable | not interpretable |
| Prediction intervals | not shown | not shown (1 held-out study per metric; 20 needed) |
| Precision of confirmed values (blinded, two automated review passes) | 0.73 (0.64 to 0.81), n = 97 | 0.61 (0.51 to 0.70), n = 92 |
| Precision of the formulation field, values with a stated formulation | not measured | 0.97 (0.92 to 0.99), n = 104 |

The resolvers more than halved the unspecified formulations among confirmed values but this did not produce a validated
drug or an interpretable gate: a set needs clearance and volume (labels and reviews, M5) and a test needs a study that
reports Cmax or AUC but not a half-life. The precision of confirmed values is below the target of 0.90 and, on this fresh
sample of other studies, lower than in M2; the intervals overlap, the sample is small, and the errors are the known classes
(an enantiomer or racemate read as the drug, metabolites of a prodrug, renal or creatinine clearance read as clearance,
a dose of the partner drug, another active drug in the arm), none of them new in M3. What the resolvers still get wrong:
the route kept from the readers where the resolvers found an intravenous and an oral statement together (the readers'
guess survives), a fixed-dose-combination word winning over a modified-release word, an extended-release product named in an
arm text that the resolvers left unspecified.
Limits: the resolvers were developed on the same registry; two review passes of one model family; precision, not recall; the
product table lists today's directory products.

# Review notes: model kit M4 (automated checks only; expert review has not yet been done)

M4 did three things: the route on a resolver conflict, a PK-Sim export, and special populations from US labels. Everything
was pre-registered before the first result and every reading, confirmation and review is automated.

## Route becomes unknown when the resolvers find an oral and an intravenous statement (owner decision 2026-11-11)
The M2 pipeline was re-run from the same bulk file with this rule only. Result: it changed the route of 131 confirmed
values to unknown (110 intravenous, 21 oral in M3); none of them could build or test before, because a conflict also leaves
the formulation unspecified, so the sets, the status and the gate are identical to M3.

| | M3 | M4 |
|---|---|---|
| Confirmed stated parent values (ClinicalTrials.gov) | 2,565 | 2,565 |
| Route oral / intravenous / unknown | 1,841 / 358 / 366 | 1,820 / 248 / 497 |
| Immediate release or solution, route known | 1,392 | 1,392 |
| Drugs with a set / complete set | 26 / 8 | 26 / 8 |
| Validated / Failed / Not validated | 0 / 1 / 403 | 0 / 1 / 403 |
| Drugs with AUC and Cmax both tested | 0 | 0 (gate not interpretable) |

Fresh blinded sample (studies of the M1 to M3 samples excluded; two automated review passes, kappa 0.63): (a) 100 random
confirmed values: precision 0.78 (Wilson 95 % 0.68 to 0.85), n = 81 agreed items; conservative 0.63 (0.53 to 0.72). The route
field of the values with a known route: 0.98 (0.92 to 1.00), n = 63. The formulation field of the resolved values: 0.91 (0.82 to
0.95), n = 75. Among the values whose route is "unknown" in the random sample, only 6 of 31 really state no route or both
(0.19): the resolvers leave many routes unknown that the text states. (b) The values the rule changed to unknown: only 9 could be
drawn from fresh studies (4 studies); in 8 of 9 the excerpt does not state both an oral and an intravenous route for the drug, so
the rule looks over-cautious there (n = 9: a description, not an estimate). The owner's rule is applied as decided; it costs no
set and no test, and the recorded route of these 131 values is now "unknown".
The held-out unit stays the study (owner decision (d)); two automated review passes stay the precision instrument (decision (e)).

## PK-Sim export
Feasibility (public documentation and source of the Open Systems Pharmacology Suite): PK-Sim imports a project snapshot (JSON,
`PKSim.Core.Snapshots`; project snapshot version 80 = PK-Sim 12.x). PK-Sim itself ships for Windows only (installer). The R
package ospsuite 12.4.5 (GPL-2.0; with the Suite's clarifying addendum for the Suite) bundles PK-Sim core 12.3.173 and runs on
Linux with a .NET 8 runtime: `loadProjectFromSnapshot`, `exportProjectToSnapshot` and `runSimulationsFromSnapshot` all work
there (not on macOS). It was run here in the CI image (R 4.6.1, .NET 8.0.34 from the distribution): the export loads, exports
again with name, description and small-molecule flag unchanged, and a copy completed with test-only numbers simulates.
The compound building block cannot hold what the kit has: PK-Sim derives distribution and absorption from lipophilicity, pKa,
fraction unbound, blood/plasma ratio, solubility and permeability, none of which the evidence contains, and it takes clearance
only as a process (hepatic, renal, ...) with body weight and fraction unbound; the total clearance of the evidence is not
assigned to an organ, which would be an assumption. The export therefore is a compound with name, description and the
small-molecule flag, plus `pksim-inputs.json` that lists every missing input with a status; nothing is invented and no
screening value is included. PK-Sim fills what a snapshot leaves out with its own defaults. Not simulated as exported.
Shipped: target `pksim` of the export route, the separate workflow `.github/workflows/modelkit-pksim.yml` (path filtered,
weekly and on demand, R image 4.6.1, ospsuite and rSharp pinned by release asset and sha256, cached library).
