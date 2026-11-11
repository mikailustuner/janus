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
