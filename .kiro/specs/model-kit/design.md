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
  restriction none). Rows the pilot already judged by two annotation passes keep those verdicts. A value the
  readers cannot reproduce stays in the store as `confirmed = false`; it is shown on the drug page as "not used".
- **DP-M2 Held-out rule is structural.** `split_studies` classifies studies by the parameters they report (all
  rows, confirmed or not, so the split cannot depend on the outcome of confirmation): a study reporting any of
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
- **DP-M7 Status function.** Per metric, the drug-level ratio is the geometric mean over studies of the study's
  geometric mean of predicted/observed. Validated iff AUC and Cmax tested and both ratios in [0.5, 2]; Failed iff
  a tested ratio is outside; else Not validated with reasons. A ratio within 10 % of a band edge is flagged "near
  the limit". Suspect parameter: AUC off, then clearance (or bioavailability); Cmax off with AUC fine, then
  absorption rate and volume.
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
- **M8** Status is Failed iff a tested ratio is outside [0.5, 2]; Validated iff both tested and inside.
- **M9** No export or page text contains a forbidden phrase (`medical-safety.md`) or "AI"; every export carries
  the two statements.
- **M10** No per-kg row is converted.

## 8. M0 evidence and findings
Six drugs from the second data-source pilot (dolutegravir, ertugliflozin, gabapentin, sunitinib, tramadol,
telmisartan). The pilot called all six simulatable; the stricter M0 rules change that, see `reviews.md`.
