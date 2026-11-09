# Do HTTK-Pop age-group simulations predict how drug exposure changes in older adults? A comparison against measured ratios in FDA drug labels

**Status:** draft research note, not peer reviewed. **Expert review has not yet been done.** Prepared in the Janus project (open-source research prototype, not a
medical device). Analysis date 2026-11-09. Nothing here is guidance for any person or a dose recommendation.

**Plain summary.** HTTK-Pop, a widely used open tool for simulating population variability in toxicokinetics, gives
almost the same older-vs-younger exposure ratio for every drug (1.38–1.76). Measured older-vs-younger ratios reported
in FDA labels vary between drugs, and HTTK-Pop does not track that variation (Spearman ρ = 0.21, 95% CI −0.13 to 0.53).
A single drug-independent constant of 1.37 (from Stader et al. 2020) predicts the label ratios better than HTTK-Pop
(geometric mean fold error 1.16 vs 1.21; difference +0.047, 95% CI +0.002 to +0.088). Simple corrections learned on
half of the drugs did not beat the training-half median on the other half. To make the comparison we built a
deterministic, accuracy-measured atlas of older-vs-younger exposure ratios from FDA labels: 163 drugs, 134 of them
with a numeric ratio, median 1.35.

---

## 1. Background

- Ageing changes pharmacokinetics (PK) mainly through lower hepatic and renal blood flow, lower glomerular filtration
  and changes in body composition (Mangoni & Jackson 2004, doi:10.1046/j.1365-2125.2003.02007.x). A physiologically
  based analysis of 10 drugs found AUC rising by about 0.9% per year of age from 20 years on, largely independent of
  the drug (Stader et al. 2020, *Clin Pharmacokinet*, doi:10.1007/s40262-019-00822-9). Over the ~35 years between the
  age groups used here (20–50 vs 65–79), this implies a constant ratio of about 1.009^35 ≈ 1.37.
- HTTK and HTTK-Pop (US EPA; Pearce et al. 2017, doi:10.18637/jss.v079.i04; Ring et al. 2017,
  doi:10.1016/j.envint.2017.06.004) simulate steady-state plasma concentrations with Monte Carlo physiology based on
  NHANES and are used to identify potentially sensitive subpopulations (e.g. Breen et al. 2022,
  doi:10.1038/s41370-022-00491-0).
- We found no study that validates HTTK-Pop's **age-group ratios** against measured clinical older-vs-younger PK ratios
  across many drugs (literature search: PubMed E-utilities, ~35 queries, abstracts only; absence is not proven).
- FDA labels for prescription drugs often report measured older-vs-younger differences ("AUC was 40% higher in
  subjects ≥65 years") in the pharmacokinetics or geriatric-use sections (21 CFR 201.57(c)(9)(v)). Manual comparisons
  exist for narrow drug groups (Boyce et al. 2012, doi:10.1016/j.amjopharm.2012.01.001: labels gave quantitative
  age-related clearance information for 4 of the 13 antidepressants where the literature reported a change) and
  for newly approved drugs (Lisi 2021, doi:10.4140/TCP.n.2021.455).

## 2. Questions and pre-registered decision rules

Written before any result was computed.

- **D-a (atlas usable):** at least one extracted field reaches precision ≥ 0.90 on a blind-checked sample, covering
  ≥ 30 drugs.
- **D-b (HTTK-Pop useful):** the lower 95% bound of Spearman ρ (log HTTK-Pop ratio vs log label ratio) is > 0 **and**
  HTTK-Pop's geometric mean fold error (GMFE) is lower than that of the constant 1.37, with a 95% CI of the difference
  excluding 0.
- **D-c (correction useful):** on held-out drugs, a corrected HTTK-Pop beats both raw HTTK-Pop and the training-half
  median, with CIs of the differences excluding 0.

## 3. Data

| Source | Version | Licence | Use |
|---|---|---|---|
| openFDA drug label bulk files | export 2026-11-06; 262,909 records, 14 parts | CC0 1.0 | Older-vs-younger ratios |
| httk R package | 2.7.4 on R 4.6.1 | MIT | HTTK-Pop simulations |
| Wikidata | 2026-11 | CC0 | Ingredient keys, CAS (P231) |

Only `HUMAN PRESCRIPTION DRUG` labels with a single substance were used (29,314 of 32,749 prescription labels with
PK or geriatric text). Sections read: `pharmacokinetics`, `clinical_pharmacology`, `geriatric_use`,
`use_in_specific_populations`.

## 4. Methods

### 4.1 Label atlas (deterministic extraction)

- **Split:** labels split by parity of `md5(set_id)`: even half for writing rules, odd half for validation only.
- **Candidate sentences:** sentences containing an older-adult term (elderly, geriatric, older subjects/patients,
  ≥65, 65 years and older, …) **and** a PK term (AUC, Cmax, half-life, clearance, exposure, plasma concentration);
  paediatric-only sentences excluded.
- **Extracted fields:** parameter ∈ {AUC, Cmax, concentration/exposure, CL, t½}; older/younger ratio on the
  parameter's own scale; kind ∈ {percent, fold, two values, "similar" (ratio 1)}; number of older subjects when
  stated.
- **Drug-level exposure ratio:** priority AUC > CL (as 1/ratio) > concentration > Cmax; t½ never used as exposure.
  Several labels of one ingredient (generic copies) → median per parameter.
- **Accuracy before use:** a stratified blind sample of 100 sentences from the validation half (60 where the extractor
  found something, 40 where it did not), annotated from the sentence text alone without seeing the extractor output.
  Precision per field; recall weighted by the sampling strata. A ratio counts as correct within ±2%.

### 4.2 HTTK-Pop simulation

For each ingredient with both an atlas ratio and human `pbtk` parameters in httk:

```r
calc_mc_css(chem.cas = cas, which.quantile = 0.5, samples = 1000, model = "pbtk",
            output.units = "mg/L", daily.dose = 1,
            httkpop.generate.arg.list = list(method = "virtual individuals",
                                             agelim_years = c(65, 79)))   # and c(20, 50)
```

`set.seed(20261109)` per group and chemical; other options at package defaults (`restrictive.clearance = TRUE`).
Prediction = ratio of median Css (65–79 / 20–50). HTTK-Pop does not sample above 79 years. Mean body weight was
83.5 kg (65–79) and 85.8 kg (20–50); a body-weight-adjusted sensitivity analysis is reported.

### 4.3 Comparators and metrics

- Baselines: B0 constant 1.0; **B1 constant 1.37** (Stader et al. 2020); B2 median label ratio of the training half.
- Metrics on the log scale: Spearman and Pearson correlation; GMFE = 10^mean|log10(pred/obs)|; share within 1.25-fold
  and 2-fold; direction agreement (> 1.1, < 0.91, in between). 95% CIs by bootstrap over drugs (2,000 resamples).
- Held-out correction: ingredients split by parity of `md5(ingredient_key)` (training 14, test 25 drugs). C1 linear
  log(label) = a + b·log(httk); C2 C1 plus a renal term (exploratory only, see §5.1); C3 class-wise (ATC level 1)
  median residual.

## 5. Results

### 5.1 Atlas accuracy

| Round | Field | Precision (Wilson 95% CI) | n |
|---|---|---|---|
| 1 (pre-registered extractor) | parameter + ratio | 0.833 (0.735–0.90) | 78 |
| 2 (corrected extractor, new unseen sample) | parameter + ratio | **0.965 (0.902–0.988)** | 86 |
| 2 | renal-impairment ratio | 0.80 (0.68–0.88) — excluded | 55 |

Weighted recall in round 2: 0.77. Round 1 failed the gate; the extractor's systematic errors (ranges like "40 to 60%",
section numbers splitting sentences, older-vs-older comparisons, formulation comparisons) were fixed by general rules
and validated on a **new** blind sample drawn with a new seed, excluding round-1 sentences. This second round was
not pre-registered and is reported as a deviation (§7).

**Atlas:** 347 substance names → 301 mapped → 254 ingredients; 163 with an exposure ratio, 134 numeric (29 "similar").
Median numeric ratio **1.35** (deciles 1.14–1.99).

### 5.2 Does HTTK-Pop predict the label ratios? (39 drugs with both)

| Metric | Value (95% CI) |
|---|---|
| HTTK-Pop ratio range / median | 1.38–1.76 / 1.54 |
| Label ratio median (same 39 drugs) | 1.35 |
| Spearman ρ (log scale) | **0.21 (−0.13 to 0.53)** |
| Pearson r (log scale) | 0.22 (−0.14 to 0.55) |
| GMFE, HTTK-Pop | 1.21 (69% within 1.25-fold, 100% within 2-fold) |
| GMFE, constant 1.0 | 1.37 |
| **GMFE, constant 1.37** | **1.16** (72% within 1.25-fold) |
| GMFE(HTTK-Pop) − GMFE(1.37) | **+0.047 (+0.002 to +0.088)** |
| Direction agreement | 0.85 — fully explained by the base rate (85% of labels > 1.1; 100% of HTTK-Pop) |

Sensitivity: body-weight adjustment makes HTTK-Pop worse (GMFE 1.23); excluding "similar" drugs (n = 34) gives
ρ = 0.04 (−0.33 to 0.42).

**Held-out correction (test 25 drugs):** raw HTTK-Pop 1.215; C1 1.183; C2 1.193 (exploratory); C3 1.158;
**constant 1.37: 1.140**; training median: 1.171. C1 and C3 improve raw HTTK-Pop, but neither beats the training
median (C1 − B2: −0.027 to +0.053; C3 − B2: −0.033 to +0.007). The corrections learn the average shift, not
drug-specific information.

### 5.3 Decisions

- D-a: **met** (0.965 ≥ 0.90; 163 drugs).
- D-b: **not met** (ρ CI includes 0; HTTK-Pop significantly worse than the constant 1.37).
- D-c: **not met**.

## 6. Interpretation

HTTK-Pop lowers cardiac output, glomerular filtration and hepatocellularity (liver cells per gram) with age; the
in-vitro intrinsic clearance and fraction unbound of each chemical do not change with age, so whole-liver intrinsic
clearance falls by about the same proportion for every drug (about 38% lower at 72 than at 35; see §10). It therefore
produces an almost drug-independent shift of about 1.4–1.6 (coefficient of variation 0.048 across the 39 drugs vs
0.204 for the label ratios), with little information on how drugs differ. This agrees with Stader et al. 2020, who found the age effect
on exposure largely drug-independent and driven by blood flow and filtration. Much of the between-drug variation in
label ratios (CYP phenotype, small-study noise, single dose vs steady state) has no counterpart in HTTK-Pop.

**Practical implication:** for an older-vs-younger exposure ratio of a medicine, HTTK-Pop's age-group output should
not be read as drug-specific. A constant around 1.35–1.37 is at least as good, and the measured label ratio, where one
exists, is better evidence than either.

## 7. Limitations and deviations

1. **Annotation:** automated annotation, blind to extractor output; not checked by a domain expert. Inter-annotator
   agreement with a second, independent automated annotator is reported in §10.1. Expert review has not yet been done.
2. **Second extraction round** was not pre-registered (round-1 result is reported above).
3. **Label studies are small** (n = 6–24 older subjects where stated), often single-dose, mostly in healthy adults
   aged 65–75; they do not represent frail people over 80. HTTK-Pop does not sample above 79 either.
4. **Few drugs** with both a label ratio and httk human parameters (39), limited by the CAS–Wikidata mapping.
5. **Renal field excluded** (precision 0.80); the renal correction is exploratory only (8 drugs).
6. One known atlas error found outside validation (olanzapine, a smoker/non-smoker sentence read as an age ratio of
   3.0) was left in by rule and removed in a sensitivity analysis.
7. Bootstrap counts reduced in sensitivity runs (1,000) and power simulations (2,000).

## 8. Before publication

- Expert review of the validation sample, starting with the disagreement sentences in §10.1 (report Cohen's κ).
- External validation of the atlas against PK-DB (Grzegorzewski et al. 2021, doi:10.1093/nar/gkaa990) or published
  older-adult PK studies, and against the 52-drug clinical data compiled by Stader et al.
- Raise the renal field to ≥ 0.90 precision or leave it out.
- Release the atlas (CSV with set_id, label version and the quoted sentence), the extractor and the analysis scripts
  with a DOI (e.g. Zenodo).

## 9. Reproducibility

Scripts (not yet in the public repository): label streaming (`extract_labels.py`, ijson 3.3.0), deterministic
extractor (`extract.py`, round-2 sha256 `f4665c52…`), blind sampling and evaluation (`sample_val2.py`,
`evaluate2.py`), atlas (`atlas.py`), HTTK-Pop runs (`httk_list.R`, `httkpop.R`, 1,000 virtual individuals per group,
~21 s per chemical), analysis (`ideaD.py`). Seeds: 20261109 (extraction sample round 1, simulations), 20261110
(round-2 sample). Label zip SHA-256 values recorded.

---

## 10. Internal validation (no external sources)

Added 2026-11-09 after the analysis above was finished. Only files already on disk were used (no new downloads, no
PK-DB, no supplements). Scripts: `agreement.py`, `consistency.py`,
`agreement.json`, `consistency.json`, `consistency.csv`, `inconsistent.json`, `ann2/`, `httksrc/`. **The Plain
summary is unchanged:** no conclusion in it changes. One mechanistic statement in §6 is corrected below (10.3), and
the atlas precision is shown to depend on one annotation convention (10.1).

### 10.1 Independent second annotator (round-2 blind sample)

- **Design.** The same 100 round-2 age sentences (A000–A099; the 40 renal sentences were not
  re-annotated) were given to a second, independent automated annotator, with only the sentence
  text, the substance name and the written rules of §4.1 (parameter ∈ {AUC, Cmax, conc, CL,
  t½}; older/younger ratio on the parameter's own scale; "similar" = 1; one value per parameter). It never saw the
  extractor output or annotator 1's gold. Neither annotator is a domain expert.
- **Agreement (annotator 1 = existing gold vs annotator 2).**

| Measure | Value |
|---|---|
| Cohen's κ, parameter presence (100 sentences × 5 parameters = 500 decisions) | **0.961** (raw agreement 0.988) |
| Cohen's κ, sentence contains any older-vs-younger statement (100) | 0.934 (0.970) |
| Ratio within ±2%, (sentence, parameter) pairs annotated by both | 87/92 = **0.946** (A2 value matches one of A1's listed values) |
| Same, counting a pair as agreeing only if A1 gave a single value | 83/92 = 0.902 |
| Sentences with full agreement (same parameters and ratios) | 93/100 |

- **Extractor re-scored** (same rules as `evaluate2.py`; precision = parameter + ratio within ±2%, Wilson 95% CI;
  recall weighted by the sampling strata):

| Gold | Precision | Weighted recall |
|---|---|---|
| Annotator 1 (as reported in §5.1) | 0.965 (0.902–0.988), 83/86 | 0.774 |
| **Annotator 2** | **0.895 (0.813–0.944), 77/86** | 0.684 |
| **Consensus** (93 fully agreeing sentences; only values both annotators gave) | **0.949 (0.877–0.980), 75/79** | 0.785 |

  Parameter-only precision is 0.977 against both annotators. The drop against annotator 2 comes almost entirely
  from one convention: sentences that report **two values for the same parameter** (two studies, two age
  subgroups or two sexes). Annotator 1 listed both values and accepted either; the extractor picks one; annotator 2
  gave one averaged or chosen value (citalopram 23%/30% → 27%; armodafinil −21%/−9% → −15%; mirtazapine men −40% /
  women −10% → −40%). Six of the nine extractor items counted wrong against annotator 2 are of this kind; the other
  three (ketoprofen AUC 1.4 instead of 1.7 from a "respectively" list, nabumetone "<1%" read as a CL change,
  acamprosate "likely to be higher" read as "similar") are the same three errors already found by annotator 1.
  **Consequence:** with annotator 2 alone the D-a gate (precision ≥ 0.90) would be narrowly missed (0.895); with
  the consensus it is met (0.949, lower CI bound 0.877). D-a therefore holds only under the stated convention that
  either reported value of a multi-value sentence is correct; the atlas should flag multi-value sentences or store
  both values.
- **Disagreements for expert adjudication (7 sentences):**

| ID | Substance | Annotator 1 | Annotator 2 | Extractor | Sentence (abridged) |
|---|---|---|---|---|---|
| A053 | armodafinil | CL 0.79 or 0.91 | CL 0.85 | CL 0.79 | "elderly subjects ≥75 and 65 to 74 years of age had approximately 21% and 9% lower oral clearance, respectively, compared to young subjects." |
| A060 | tadalafil | AUC 1.0, Cmax 1.0, conc 1.0 | AUC 1.0, Cmax 1.0 | AUC 1.0, Cmax 1.0 | "no statistically significant differences in exposure (AUC and Cmax) were observed between elderly (70 to 85 years) and younger … subjects." |
| A066 | citalopram | AUC 1.23 or 1.30; t½ 1.30 or 1.50 | AUC 1.27; t½ 1.40 | AUC 1.23; t½ 1.30 | "In two pharmacokinetic studies, citalopram AUC was increased by 23% and 30%, respectively, in subjects ≥ 60 years … and its half-life was increased by 30% and 50%, respectively" |
| A068 | citalopram | AUC 1.30 or 1.23; t½ 1.50 or 1.30 | AUC 1.27; t½ 1.40 | AUC 1.30; t½ 1.30 | "In a single-dose study, citalopram AUC and half-life were increased in the subjects ≥ 60 years old by 30% and 50%, respectively, whereas in a multiple-dose study they were increased by 23% and 30%, respectively" |
| A082 | bupropion | conc 1.0 | — | — | "These data suggest that there is no prominent effect of age on bupropion concentration; however, another … study suggested that the elderly are at increased risk for accumulation of bupropion and its metabolites" |
| A084 | theophylline | — | CL 0.63, t½ 1.13 | — | Flattened table of clearance and half-life by age group (neonates … adults 16–60 … elderly); values not in one sentence. |
| A094 | etodolac | — | CL 0.93, t½ 1.02 | — | Flattened table "Pharmacokinetic Parameters of Etodolac in Normal Healthy Adults (18-65) … Elderly (>65)"; CL/F 49.1 vs 45.7 mL/h/kg. |

  Four further sentences agree under the "either value" rule but not on a single value (A038 sildenafil: parent
  84% vs metabolite 107%; A073/A090 ketorolac, identical text: Cmax 2.52 vs 2.99 "little difference"; A083
  mirtazapine: men −40%, women −10%). An expert would need to look at 7 sentences (11 including these).
  Note that the extractor's choice in A068 (AUC 1.30, t½ 1.30) mixes the two studies, which neither annotator did.

### 10.2 Within-drug consistency across labels (generic copies)

- Label-level exposure ratio recomputed per label (set_id) with the atlas rule (median per parameter in the label;
  AUC > CL (1/r) > conc > Cmax; "similar" only as fallback), then compared with the ingredient's median over labels.
- **163 ingredients** have a label ratio; **135 have ≥ 2 labels** (6,206 labels in total).

| Measure | Value |
|---|---|
| Labels within ±10% of their ingredient's median | **0.982** |
| Ingredients with all labels within ±10% | 126/135 = **0.933** |
| Spread (max/min label ratio) per ingredient: median / 75th / 90th percentile / max | 1.00 / 1.00 / 1.06 / 1.64 |
| Ingredients with identical values in every label | 87% |
| Spread > 1.25 / > 2 | 6 / 0 ingredients |

  The high agreement mostly reflects generic labels copying the reference label verbatim; it shows that the
  extractor is stable on repeated or reformatted text, not that the underlying studies replicate.
- **Inconsistent ingredients (9) and causes:**

| Ingredient | Labels | Values (parameter) | Cause | Atlas value affected? |
|---|---|---|---|---|
| metformin | 4 | 0.95 (AUC) vs 1.54 (CL 0.65) | **Extraction error**: a flattened PK table (not an age comparison) read as AUC/Cmax 0.95; the true sentence gives CL −35%, Cmax +76% | **Yes**: atlas 0.95, should be ≈ 1.54 (not among the 39 HTTK drugs) |
| zolpidem | 109 | 1.64 / 1.5 (AUC); 1.3 (AUC, sublingual); 1.0 (CL "similar") | Mixed: 1.5 = "respectively" list mis-aligned after subscripts were lost; 1.0 = sex comparison within the elderly ("clearance similar in men and women"); 1.3 = genuinely different study (sublingual 3.5 mg, AUC0–4h) | No (median 1.64 correct) |
| pantoprazole | 129 | 1.43 (oral, repeated) vs 1.0 (IV, "similar") | **Genuinely different statements** (route) | Value 1.43 kept (AUC priority); IV labels say similar |
| theophylline | 26 | CL 0.70 vs CL 1.5 | **Extraction error**: smokers vs non-smokers read as age ratio (same pattern as olanzapine) | No (median 1.43 correct) |
| levetiracetam | 158 | CL 0.62 vs "fold" 0.5 | **Extraction error**: "twice‑daily" (non-breaking hyphen) read as a two-fold change | No |
| doxazosin | 63 | CL/t½ "similar" (IR) vs AUC 1.34 (XL) | **Genuinely different statements** (formulation) | Atlas uses XL 1.34 by AUC priority |
| ropinirole | 55 | CL −15% vs CL −30% | **Genuinely different statements** (different labels/studies) | No (median) |
| cyclobenzaprine | 175 | AUC 1.7-fold (IR, steady state) vs AUC +40% (ER) | **Genuinely different statements** (formulation/study) | No (median 1.7) |
| atorvastatin | 237 | AUC 1.3 vs AUC 0.9 | **Extraction error**: female-vs-male sentence read as age ratio | No (median 1.3) |

  Five of nine are extraction errors (error types not among the blind-sample errors: **sex comparisons**,
  **smoker comparisons**, a table row and a hyphen artefact); four are genuinely different statements (route,
  formulation, study). Only metformin changes the ingredient-level atlas value, because medians absorb minority
  errors.
- **HTTK-Pop comparison restricted** (same code path and bootstrap as `ideaD.py`: seed 20261109, 2,000 resamples;
  the unrestricted run reproduces §5.2 exactly). Of the 39 drugs, 3 have a single label, 32 have consistent labels
  and 4 are inconsistent (doxazosin, pantoprazole, theophylline, zolpidem).

| Set | n | Spearman ρ (95% CI) | GMFE HTTK-Pop | GMFE 1.37 | Difference (95% CI) |
|---|---|---|---|---|---|
| All (as §5.2) | 39 | 0.21 (−0.13 to 0.53) | 1.210 | 1.164 | +0.047 (+0.002 to +0.088) |
| Inconsistent excluded | 35 | 0.18 (−0.19 to 0.50) | 1.225 | 1.174 | +0.050 (+0.002 to +0.093) |
| Multi-label consistent only | 32 | 0.20 (−0.20 to 0.54) | 1.232 | 1.170 | +0.062 (+0.014 to +0.107) |

  **The conclusion does not change:** in every subset the ρ interval includes 0 and HTTK-Pop is worse than the
  constant 1.37 with an interval excluding 0.

### 10.3 Model-side check: what HTTK-Pop varies with age (httk 2.7.4 source)

Function bodies were deparsed from the installed namespace (`.data/tools/R-library/httk`, version 2.7.4 confirmed)
Path: `calc_mc_css` → `create_mc_samples` → `httkpop_mc` → `httkpop_generate` →
`httkpop_virtual_indiv` → `tissue_masses_flows`, `gen_serum_creatinine` + `estimate_gfr`, `estimate_hematocrit`
→ `httkpop_biotophys_default`.

Age-dependent in HTTK-Pop:
- **Cardiac output and hence all organ flows, including liver flow** (`tissue_masses_flows`):
  `flow_mean = tissue_scale(...1.05 * flow_ref) * (1 - pmax(0, 0.005 * (age_years - 25)))`, i.e. −0.5%/year after
  25; organ flows are fixed fractions of it. Ratio ≈ 0.81 at 72 vs 35 years.
- **GFR** (`estimate_gfr` → `ckd_epi_eq`): `141 * … * 0.993^age_years`, with serum creatinine drawn by age from
  NHANES (`gen_serum_creatinine`), then `Qgfrc` in `httkpop_biotophys_default`.
- **Hepatocellularity** (`tissue_masses_flows`):
  `mu <- log(10^(-0.66 * log10(tmf_dt[, age_years]) + 3.1))`;
  `million.cells.per.gliver <- exp(rnorm(n, mean = mu, sd = sigma))`. Median ≈ 121 × 10⁶ cells/g at 35 years vs
  ≈ 75 at 72 years (ratio ≈ 0.62).
- Brain, bone, skeletal-muscle mass (`brain_mass`, `bone_mass_age`, `skeletal_muscle_mass`), BSA and hematocrit
  (`estimate_hematocrit`, which feeds `Rblood2plasma`). Adult **liver mass has no age term** (age enters only for
  `age_years <= 18`; otherwise `tissue_scale` by height).

Not age-dependent:
- **In-vitro Clint (per 10⁶ hepatocytes) and fraction unbound (fup):** drawn in `invitro_mc` with
  `clint.pop.cv = 0.3`, `fup.pop.cv = 0.3` (plus measurement CVs) and adjusted by `apply_clint_adjustment` /
  `calc_fup_correction`; none of these functions takes age or any HTTK-Pop variable (0 occurrences of `age_years`
  or `httkpop`).
- **But scaled hepatic intrinsic clearance does decline with age**: `calc_hep_clearance` computes
  `Clint <- Clint * million.cells.per.gliver; Clint <- Clint * (Vliverc * 1000 * liver.density)`, so the age
  decline in hepatocellularity lowers whole-liver Clint by roughly 38% between the group mid-ages.

**Correction to §6.** The sentence "intrinsic clearance does not change with age in the model" is wrong as
written. Correct statement: in HTTK-Pop the in-vitro Clint and fup do not vary with age, but whole-liver intrinsic
clearance falls with age through a single drug-independent hepatocellularity curve, together with lower cardiac
output (liver blood flow) and lower GFR. Because each of these factors multiplies every drug's parameters by the
same age function, drugs differ only in how their clearance splits between flow-limited hepatic, capacity-limited
hepatic and renal routes, which explains the narrow, nearly drug-independent range. The conclusion of §6 stands;
only the mechanism description changes.

**Spread of predictions (re-read from the simulation output):** 81 chemicals simulated; the 39 compared drugs and all
81 both span **1.379–1.764** (confirmed). Coefficient of variation:

| Ratios | n | CV (SD/mean) | SD of ln ratio |
|---|---|---|---|
| HTTK-Pop | 39 | **0.048** | 0.048 |
| Label, same 39 drugs | 39 | **0.204** | 0.201 |
| Label, 34 numeric of these | 34 | 0.179 | 0.174 |
| Label, whole atlas (numeric) | 134 | 0.243 | 0.217 |

HTTK-Pop's between-drug variation is about one quarter (CV 0.048 vs 0.204) of the label ratios'; even if every
label ratio were exact, HTTK-Pop could explain little of their spread.

### 10.4 What remains for expert review

- Adjudicate the 7 disagreement sentences in 10.1 (11 with the multi-value cases), and decide the convention for
  multi-value sentences (store both / average / exclude).
- Fix or exclude metformin in the atlas (0.95 → ≈ 1.54) and add rules for sex and smoker comparisons, flattened
  tables and the non-breaking-hyphen "twice-daily" artefact; none of these error types was among the extractor
  errors found in the blind samples, so the blind precision does not capture them.
- Expert review is still required before publication (§8): both annotations here are automated and come from
  closely related systems, so their agreement may be inflated.
