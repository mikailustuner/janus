# Model kit gate: what was tested and what it shows (round B4)

**Status:** research log of the Janus project (open-source research prototype, not a medical device), November 2026.
Research use only. Not for clinical decisions. **Expert review has not yet been done.** Every reading, check and review
pass below is automated.

Pre-registered protocol: [`modelkit-gate-protocol.md`](modelkit-gate-protocol.md), pushed before the cross-study rule was
implemented or run. The numbers are in [`data/validation/modelkit/gate.json`](../../data/validation/modelkit/gate.json).
They are computed by `pipelines/tools/modelkit_gate_report.py` from the current model kit release (evidence run
`20261112T170053Z-00e7d273-177c`).

## 1. In short

- **The gate is not interpretable.** It needs at least 10 drugs with both AUC and Cmax tested against held-out studies.
  The current release has **0**. With the current data, at most **0** drugs could reach it.
- **The limit is the data, not the method.** Too few drugs have a second, independent study with a clearance and a time
  of peak concentration.
- **Narrowed claim:** AUC was within 2-fold of held-out studies in the **3 drugs** where it could be tested (11 of 11
  points, Wilson 95 % 0.74–1.00). **Cmax could not be tested for any drug.** No statement is made about the model kit as a
  whole.
- **Cross-study plausibility check.** It is pre-registered and implemented, and it withholds the known dasatinib unit
  error. But it did not meet its own decision rule, so it stays **switched off**.

## 2. What was tested

For each drug, the model kit builds a one-compartment parameter set (clearance, volume, absorption rate) from confirmed
published values. Two independent rule-based readers must agree on a value. ClinicalTrials.gov values must also pass a
strict record check.

The set is tested **leave one study out**: each study with an oral AUC or Cmax is held out in turn, the set is rebuilt from
the drug's other studies, and the held-out values are predicted. A point passes when the prediction is within 2-fold of
the observed value. A drug is *validated* only when AUC and Cmax are both tested and every point passes. It *fails* when
any point is outside 2-fold.

## 3. Gate result (current release)

| | Value |
|---|---|
| Drugs in the release | 404 |
| Drugs with a parameter set / complete set | 8 / 2 |
| Drugs with AUC tested / Cmax tested / both | 3 / 0 / **0** |
| Validated / Failed / Not validated | 0 / 0 / 404 |
| Gate interpretable (≥ 10 drugs with both) | **no** |

AUC points (each predicted by a set built without its own study):

| Drug | Points | Predicted / observed | Studies |
|---|---|---|---|
| apremilast | 8 | 0.83–1.36 | 4 |
| repaglinide | 2 | 0.73, 0.75 | 2 |
| talazoparib | 1 | 1.61 | 1 |
| **All** | **11 of 11 within 2-fold** | geometric mean fold error 1.22 (drug bootstrap 1.15–1.61) | 7 |

- Point level: 11 of 11, Wilson 95 % 0.74–1.00. The points are clustered in 3 drugs, so this interval is optimistic.
- Drug level: 3 of 3, Wilson 95 % 0.44–1.00.
- Cmax: no point.

## 4. Gate bound (B4.1)

The bound counts nested upper limits per drug, with the product's own filters: confirmed, parent drug, immediate release
or solution, oral, dose stated, not a special population, not co-administered, not a label study, not linked to another
study.

| Tier | AUC | Cmax | Both |
|---|---|---|---|
| T0: usable oral AUC and Cmax observations exist | 10 | 16 | 10 |
| T1: and another study of the drug has a usable clearance | 5 | 6 | 5 |
| T1b: and, for Cmax, another study has a time of peak concentration | 5 | **0** | **0** |
| Product gate (leave one study out) | 3 | 0 | 0 |

T1b ignores the volume, half-life and population rules, so it is an upper bound. **At most 0 drugs** can have both
metrics tested with the current data. The pre-registered threshold is 10.

**Limiting numbers.**
- Drugs with any confirmed value: 73 of 404. Only 23 have confirmed values in two or more studies.
- Drugs with a testable oral observation: 16. Only 3 have them in two or more studies.
- Drugs with a usable clearance: 20.
- Drugs with a usable time of peak concentration: 14.
- Drugs with both a usable clearance and a usable peak time: 4.

To test Cmax, the set needs an absorption rate. The set gets it from a time of peak concentration in a study **other**
than the held-out one. No drug with a held-out Cmax has that.

**The earlier figure of "1 drug".** The earlier gate study reported an upper bound of 1 drug. Re-checked on the release it
used (`20261112T142707Z-8ac5398b-8b3e`, before the strict record check, when every value both readers agree on was
used): T1b = 1 and the gate tested 1 drug with both metrics. That drug was **dasatinib**, and it was tested only because
of the unit error described below. It failed, with points 133- to 1,022-fold off. After the strict record check, the
bound is 0.

**What would change it.** More data, not another method. The gate needs about ten drugs that each have:
- one study with an oral, dose-stated AUC and Cmax; and
- another independent study with a clearance and a time of peak concentration;

all at the precision the publication rule requires. The two new document sources measured in round B3a did not pass that
rule (see [`modelkit-precision.md`](modelkit-precision.md)): PubMed Central tables 0.36 (lower bound 0.09), Drugs@FDA
reviews 0.77 (lower bound 0.48). So they add no held-out study. Even when the held-back document sources were included in
an earlier exploratory run, only 1 drug had both metrics tested.

## 5. Cross-study plausibility check (B4.3)

**Why.** In ClinicalTrials.gov study NCT00529763, dasatinib's apparent clearance is posted as 211.09 and 221.84 "mL/h".
Both readers read that unit faithfully, so both values are confirmed. They are about 1,000-fold below the values of
dasatinib's other study (NCT00339144, 135–549 L/h). A check that looks at one study alone cannot see this. The new rule
was pre-registered before it was run. It is a new rule, not a post-hoc fix.

**Rule (as pre-registered).**
- **Compare.** Each confirmed value is compared with the median of the drug's other studies, for the same parameter and
  route (and regimen for Cmax and AUC).
- **Normalise.** Values are in canonical units, and exposure values are divided by the dose.
- **Withhold.** A value is withheld when it differs from that median by more than **10-fold**.
- **Reference values.** Values that both readers agree on, including values that the strict check withheld. Values from
  co-administration arms, special populations, and modified-release or other-route products are left out.
- **Minimum.** At least one other study is needed. With two studies that disagree, both are withheld.
- **Effect.** The check only withholds values; it never confirms one.

Implemented as `plausibility.cross_study_outliers` (a pure function) with property tests. The tests cover:
- a single study is never checked;
- values inside a 10-fold band are never withheld;
- unit errors of 24-, 60- and 1,000-fold are always withheld;
- the result is independent of row order and of the unit scale;
- the check only withholds values.

It is wired into the ClinicalTrials.gov intake after the strict record check (`read_bulk(cross_study=True)`).

**Effect on the current release** (336 confirmed ClinicalTrials.gov values; 149 have another study to compare with):

| Drug | Parameter | Study | Value | Reference (other studies) | Ratio | Earlier automated verdicts |
|---|---|---|---|---|---|---|
| dasatinib | CL/F | NCT00529763 | 211.09 mL/h | 245.5 L/h | 0.00086 | correct / correct |
| dasatinib | CL/F | NCT00529763 | 221.84 mL/h | 245.5 L/h | 0.00090 | correct / correct |
| acalabrutinib | V/F | NCT02029443 | 2,100 L | 171.3 L | 12.3 | correct / correct |

- The known dasatinib error **is caught**.
- No gate number changes. The gate stays at 0 drugs with both metrics, and AUC stays at 11 of 11 points in 3 drugs.
- Secondary, on the earlier release without the strict check: 16 of 2,565 values withheld. Dasatinib is no longer tested,
  and it moves from Failed to Not validated. The withheld values include:
  - a lomitapide Cmax that earlier review passes had already found to be a metabolite's value;
  - two rosuvastatin half-lives 12- to 14-fold below the other study.

  As pre-registered for two disagreeing studies, the values of dasatinib's other study (NCT00339144) are withheld too.

**Decision (pre-registered rule, applied as written).** The rule was to be switched on only if no more than half of the
withheld values with earlier automated verdicts had been judged correct by both review passes. All 3 had been judged
correct. **The rule is not met, so the check stays in the code switched off.**

The earlier verdicts are re-used, not a fresh measurement. The item list names study, drug and parameter, and every item
matching these three values carries the same verdict pair.

Observation (post hoc, not a measurement):
- The review passes check whether a value matches its source. A unit error *in the source* is "correct" by that standard,
  so this decision criterion could not reward the check for the error it was built for. This was not foreseen when the
  rule was written.
- Whether the acalabrutinib volume of 2,100 L is a real value or an error is not known.

A fair test of the check needs a reference that knows the true value, such as an expert or an independent compilation,
and a fresh pre-registration.

## 6. What is shown and what is not

| What | Status | Numbers |
|---|---|---|
| ClinicalTrials.gov values that pass the strict check are read correctly | **shown** (automated review, not experts) | 125 of 126 (0.992; Wilson 0.956–0.999; cluster-aware lower bound 0.934), 14 studies; covers 336 of 2,565 agreed values |
| AUC is predicted within 2-fold for held-out studies | **shown for 3 drugs only** | 11 of 11 points (Wilson 0.74–1.00); 3 of 3 drugs (0.44–1.00) |
| Cmax is predicted within 2-fold for held-out studies | not tested | 0 drugs |
| The model kit is accurate across drugs (the gate) | not tested | 0 of the 10 drugs needed; upper bound 0 |
| A drug's parameter set is validated | not tested | 0 of 404 (no drug has both metrics tested) |
| Article tables and FDA review tables are precise enough to publish | **not shown** | 0.36 (lower 0.09) and 0.77 (lower 0.48); rule ≥ 0.90 |
| A value posted with a wrong unit is withheld | **not shown** | Check exists and catches dasatinib, but did not meet its decision rule; switched off |
| The readers find every value a source reports (recall) | not tested | needs expert annotation |
| Predictions for children, older adults, kidney or liver impairment | not tested | excluded from building and testing |
| Expert review | not tested | Expert review has not yet been done. |

## 7. Reproduce

```
cd apps/api && PYTHONPATH=../../pipelines uv run python ../../pipelines/tools/modelkit_gate_report.py \
    --run ../../.data/artifacts/modelkit_evidence/current \
    --secondary ../../.data/artifacts/modelkit_evidence/runs/20261112T142707Z-8ac5398b-8b3e \
    --out ../../data/validation/modelkit/gate.json --date 2026-11-13
```

The evidence runs are build artifacts and are not committed. The cross-study check is tested in
`pipelines/tests/test_modelkit_plausibility.py`.
