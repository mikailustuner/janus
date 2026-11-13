# Model kit gate, round B4: pre-registered protocol

**Status:** pre-registration, written 2026-11-13 (UTC). The cross-study plausibility rule in section 3 was written before
it was implemented or run on any data. The time of the git push of this file is the timestamp. Research use only. Not for
clinical decisions. **Expert review has not yet been done.** Every reading and check in this protocol is automated. No
language model reads values for the product.

## 1. The gate and why it is not yet interpretable

The model kit builds a one-compartment parameter set (clearance, volume, absorption rate) for a drug from published
values. It then tests the set against held-out studies of the same drug: one study at a time is left out, the set is
rebuilt from the other studies, and the left-out study's oral AUC and Cmax are predicted. A point passes if the prediction
is within 2-fold of the observed value.

The pre-registered gate rule (product rule DP-M20): the gate is **interpretable only when at least 10 drugs have both AUC
and Cmax tested** against held-out studies. Below that, no statement about the model kit's accuracy as a whole is made.
On the current release, 0 drugs have both metrics tested.

## 2. Gate bound (B4.1)

The bound is a count over the current release, not a test. It was computed before this protocol was written, with the
product's own filters, and is reported in [`modelkit-gate.md`](modelkit-gate.md). It counts, per drug, nested upper
bounds:

- **T0:** usable oral AUC and Cmax observations (confirmed, parent drug, immediate release or solution, dose stated, not a
  special population, not co-administered, not a label study, not linked to another study) exist at all.
- **T1:** for a study with such an observation, another study of the same drug has a usable clearance.
- **T1b:** as T1, and for Cmax another study also has a usable peak time (the set needs it for the absorption rate).
- **Gate:** the product gate itself (leave one study out).

T1b ignores the volume, the half-life and the population rule, so it is an upper bound of the gate.

## 3. Cross-study plausibility rule (B4.3)

### 3.1 Why

The model kit's dasatinib set showed a known error type that the two readers and the strict record check do not catch. In
study NCT00529763 the posted results give apparent clearance (CL/F) as 211.09 and 221.84 "mL/h". Both readers read the
posted unit correctly, so both values were confirmed. They are about 1,000-fold below the CL/F values that both readers
agree on in the other dasatinib study, NCT00339144 (135 to 549 L/h). The posted unit is almost certainly wrong, and a set
built from these values predicts exposures about 1,000-fold too high.

No rule that looks at one study alone can see this: the record is internally consistent. Only a comparison across studies
can. This rule is **new and pre-registered**. It is written before it is run on any data, and it is not a post-hoc fix.
The dasatinib case motivated it, and its expected effect on dasatinib is stated below before the run.

### 3.2 The rule

For every value that is confirmed after the strict record check (a **candidate**):

1. **Comparison key.** Drug, parameter, route (oral, intravenous or unknown). For the dose-dependent parameters (Cmax,
   AUC to infinity, AUC to the last time, AUC over a dosing interval) also the regimen (single, multiple or unknown).
   A per-kg clearance or volume is its own parameter and is never compared with an absolute one.
2. **Normalisation.** Each value is converted to the parameter's canonical unit (L/h, L, h, ng/mL, ng·h/mL) by the same
   unit code the readers use. A dose-dependent value is divided by its dose in mg; a dose-dependent value without a dose
   takes no part in the rule.
3. **Reference values.** Values of the same key that **both readers agree on** (before the strict record check, so values
   the strict check withheld count as reference too), of the parent drug, not co-administered, not in a special
   population, with formulation immediate release, solution or unspecified. Reference values are only used to withhold a
   value. The rule never confirms a value.
4. **Study summary.** Each study is summarised by the median of its normalised values for the key. A study's own values are
   never compared with each other (dose groups, arms and periods of one study vary for their own reasons).
5. **Reference.** For a candidate in study S, the reference is the median of the summaries of all **other** studies of the
   key. The candidate itself never enters its own reference.
6. **Minimum.** The rule applies only when at least **one** other study has a reference value for the key. With only the
   candidate's own study, nothing is checked.
7. **Factor.** A candidate is withheld when it differs from the reference by **more than 10-fold** in either direction
   (value / reference > 10 or < 1/10).
8. **Ties and boundaries.**
   - Medians of an even number of values are the geometric mean of the two middle values (all medians are taken on the log
     scale).
   - Exactly 10-fold is kept ("more than"). A relative tolerance of 1e-9 absorbs floating-point noise at the boundary.
   - With exactly two studies that differ by more than 10-fold, the candidates of **both** are withheld. The rule cannot
     tell which study is right, so neither is confirmed.
9. **Effect.** A withheld value keeps its row with `confirmed = false` and the reason "both readers agree, but the value
   differs more than 10-fold from the drug's other studies (cross-study check)". No schema change. Derived clearances are
   made only from confirmed AUC values, so a derived value of a withheld AUC disappears with it.
10. **Scope.** The ClinicalTrials.gov intake, where the strict record check runs. It runs after the strict record check,
    on all studies of the intake together. Label values, the M0 annotations and the held-back document sources are not
    checked and are not used as reference.

### 3.3 Why these numbers

- **Factor 10.** The errors the rule targets are unit errors: mL vs L and ng vs µg (1,000-fold), minutes vs hours
  (60-fold), hours vs days (24-fold). The smallest common one is 24-fold. The gate's own accuracy band is 2-fold.
  Real differences between studies of the same drug, route and regimen (different populations, doses, assays) are mostly
  well within 10-fold, so 10 sits between real variation and the smallest unit error. A smaller factor would remove real
  values. A larger one would miss 24-fold errors.
- **One other study is enough.** The motivating case has exactly two studies. Requiring two or more other studies would
  leave it untouched. The cost is that two disagreeing studies are both withheld.
- **Reference includes values the strict check withheld.** Confirmed values are few (a candidate rarely has a confirmed
  value from another study). The wider pool of values both readers agree on is about 85 % correct without the strict rule
  (risk–coverage curve, level 0), and it is only used to withhold. Values from co-administration arms, special
  populations and modified-release or other-route products are left out of the reference because they differ for real
  reasons.
- **Median of study summaries.** One study with many arms must not outvote the others. The median is robust to one wrong
  study when three or more studies exist.

### 3.4 What is known before the run

- Seen before writing: the dasatinib values above (from the earlier gate study), the number of confirmed values per
  parameter in the current release (Cmax 133, half-life 99, CL/F 65, AUC to infinity 43, tmax 43, ...), and the gate
  bound of section 2. No cross-study ratio of any other drug was computed.
- Expected: the two confirmed dasatinib CL/F values of NCT00529763 are withheld (about 1,000-fold below the reference
  from NCT00339144). Expected effect on the gate: none. The gate is empty on the current release, and the rule only
  withholds values.

## 4. Evaluation (fixed now)

On the current release (evidence run `20261112T170053Z-00e7d273-177c`), with the rule applied to the confirmed
ClinicalTrials.gov values of the readers (derived rows of withheld AUC values removed with them):

1. The number of candidates, the number with at least one other study (checkable), and the number withheld, by
   parameter. Each withheld value is listed with its study, value, reference and ratio.
2. Whether the dasatinib values of NCT00529763 are withheld.
3. For withheld values that an earlier automated review sample already judged, the earlier verdicts. This re-uses verdicts
   given before this rule existed. It is **not** a fresh precision measurement, and it is labelled so.
4. The gate recomputed with the product code: sets, complete sets, drugs with AUC, Cmax and both tested, statuses.
5. Secondary: the same on the earlier release without the strict check (`20261112T142707Z-8ac5398b-8b3e`), where dasatinib
   was the only drug with both metrics tested and was Failed.

**Decision rule.** The rule is switched on in the intake if (a) its property tests pass (a single study is never
checked; values within a 10-fold band are never withheld; a value scaled 1,000-fold away from at least one consistent
other study is always withheld; the result does not depend on row order or on the unit scale; the rule only withholds), and
(b) of the withheld values with earlier agreed verdicts, no more than half were judged correct by both passes. If (b)
fails, the rule stays in the code switched off, and its effect is reported as a proposal. Whatever the outcome, the effect
is reported. The rule cannot raise the share of correct values that was measured. It removes values, and its own precision
would need a fresh sample, which the exhausted registry cannot give.

## 5. Not in this round

No new source, reader or sample. No change to the 2-fold criterion, the status rule, the leave-one-study-out design or the
threshold of 10 drugs. Production artifacts are not rebuilt here. The re-run of the intake with the rule on is a separate
step.
