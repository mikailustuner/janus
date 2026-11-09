# Pharmacologist review pass — Time Machine

> **AI review pass**, not a human review. Performed by the `pharmacologist` agent profile
> (`.kiro/agents/pharmacologist.md`) on 2026-11-09 against the built artifact
> (`tm_molecules` 20261109T001156Z, `tm_bioactivity` 20261109T000811Z, `tm_pbpk`
> 20261109T003250Z, `tm_admet` 20261109T003234Z). Verdicts: **accept**, **correct**, **reject**.
> Nothing here sets a result to expert-reviewed.

## Scope reviewed
Constituent selection (L1), target and comparator choices (L2), the PBPK and compartmental
parameter sets, the validation outcome, the dose conversion, and every statement that could read
as a dose or a treatment.

## Verdicts

### 1. Constituent selection — accept
Each of the 14 compounds is a recognised constituent of its substance and each has a referenced
occurrence statement. Hyperforin, hypericin and pseudohypericin are the right markers for
*Hypericum perforatum*; rhein, emodin, aloe-emodin, chrysophanol and sennoside A are the right
hydroxyanthracene set for *Rheum*; trans-anethole dominates anise oil. Acetic acid for vinegar
is correct and correctly handled as a preparation, not a taxon.

### 2. Rhein as the modelled species for rhubarb — **correct**
The dose scenario converts the Canon's two dirhams to 168–792 mg of "total hydroxyanthracene
derivatives expressed as rhein" and then models that as rhein. EMA/HMPC/113701/2019 states
60–80 % are mono- and diglycosides with "only small amounts of the respective aglycones", plus
10–25 % sennosides. Free rhein at ingestion is therefore a small fraction of that mass; the
glycosides are cleaved by colonic bacteria hours later, which a one-compartment oral model does
not represent at all.
**Correction applied in the design and the artifact note:** the scenario is labelled an
overestimate of immediate free rhein exposure. **Still outstanding for the experts:** the model
has no colonic activation step, so its Tmax is wrong for a glycoside prodrug even if its Cmax
magnitude is plausible. Listed in the pre-launch checklist.

### 3. Rhein PK parameters from diacerein — accept with a caveat
Taking rhein's apparent CL/F and t½ from oral diacerein is sound: Nicolas 1998 states diacerein
is entirely converted to rhein pre-systemically, and expressing the dose in rhein equivalents
(38.58 mg from 50 mg diacerein) is the correct molar correction. The ka of 1.5 /h is an
assumption and is labelled one. The 99 % protein binding (Nicolas 1998) is recorded but **not
used** — the model uses an ADMET-AI prediction instead (see 7).

### 4. httk validation outcome — accept
The direction of the failures is what a pharmacologist would predict: httk's IVIVE from in-vitro
intrinsic clearance under-predicts hepatic clearance for drugs with substantial first-pass and
high extraction, so AUC is over-predicted (midazolam 11.9×, haloperidol 32×). Haloperidol is
the extreme because its true oral bioavailability (~0.65) and large first-pass are not captured
by the default parameterisation. Keeping the package default rather than choosing
`restrictive.clearance` per drug (DP-T9) is the correct methodological call.
**Accept the consequence:** no httk drug may carry an exposure statement, and the PBPK layer is
published only as a relative older-versus-younger comparison.

### 5. Risperidone observed value — **correct**
The observed Cmax is parent risperidone only. The clinically relevant moiety is risperidone plus
9-hydroxyrisperidone ("active moiety"), and CYP2D6 phenotype shifts the parent/metabolite split
several-fold. Comparing a model that has no metabolite compartment against parent-only data in a
non-genotyped cohort is a weak test in both directions.
**Correction:** the artifact note must say the comparison is parent-drug only. Added to the
checklist as an expert item; the verdict (`failed`) does not change.

### 6. The metoclopramide cascade — accept as labelled
PIPC row 18 is written for antipsychotics. Metoclopramide is a dopamine D2 antagonist that
causes drug-induced parkinsonism by the same mechanism, so the extension is pharmacologically
reasonable, but it is an extension of the rule base and is correctly labelled interpretive.
Note the cascade has **zero** usable FAERS onset pairs, so it currently carries no result at all.

### 7. ADMET-AI `PPBR_AZ` as the unbound fraction — **reject**
Using a machine-learning prediction of percent-bound to convert a total concentration to an
unbound one is not acceptable for a potency comparison. The review found the prediction exceeds
100 % for hyperforin (112.6 %), chrysophanol (101.9 %) and emodin (101.6 %) — physically
impossible, and it would have produced a negative unbound fraction.
**Fixed during this pass (DP-T15):** an out-of-range prediction is now rejected and the
comparison falls back to the total concentration with an explicit `total_only` basis.
**Still rejected for any published verdict:** where a measured unbound fraction exists in the
literature (rhein ~99 %, Nicolas 1998), that measured value should be used instead of a
prediction. No verdict is currently published, so nothing is wrong in the output today; this
must be settled before any verdict is.

### 8. Potency target gating — accept, strongly
Restricting verdicts to curated condition-relevant targets is the right rule. The review
confirms the concrete danger it prevents: rhein's most sensitive public-domain assay is an
inhibitor screen against apurinic/apyrimidinic endonuclease at 0.32 µM. A verdict built on that
would have read "the concentration reaches the active level" and meant nothing about bruises.

### 9. Interaction flags — accept
One established pair (hyperforin–PXR, cited to Moore 2000) and 32 screening-panel records
correctly separated. Flagging acetic acid on CYP1A2 from a broad qHTS panel is noise, but it is
labelled a screening record and not an interaction, which is honest. The pharmacologically
important induction direction is worth noting for the write-up: hyperforin's PXR binding causes
**induction** of CYP3A4, whereas the CYP3A4 record carried alongside it is an **inhibition**
IC50 — opposite directions, and the product copy must not conflate them. Added to the checklist.

### 10. Safety language — accept
No output states a dose a person could take, no output recommends a substance, and the only
patient-facing sentence carries no concentration, dose or molecule. The dose scenarios are
clearly historical-text conversions in a research area. No forbidden phrase appears.

## Summary
Accept 6, correct 3, reject 1 (resolved in the pipeline during the pass, with a residual item
for the experts). Nothing in the current output is a treatment or dosing claim. The most
important thing this pass changed: out-of-range predicted protein binding can no longer reach a
comparison.
