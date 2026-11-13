# FAERS signal calibration: pre-registered protocol

Status: registered before any count for the reference pairs was computed. The git commit that adds this
file, pushed to the public repository, is its timestamp. Changes after registration are listed in the
results file (`docs/research/faers-calibration.md`) as deviations.

## 1. Question

How well does the disproportionality statistic Janus shows next to a medicine and an event (reporting
odds ratio from FAERS, `apps/api/janus/memory/stats.py`) separate drug–event pairs that are known to be
causal from pairs known not to be? How far are its intervals off for pairs with no effect?

## 2. Reference sets

- OMOP 2013 reference set: 399 drug–outcome pairs (165 positive, 234 negative controls) for acute liver
  injury, acute kidney injury, acute myocardial infarction and upper gastrointestinal bleeding.
  Ryan PB et al., Drug Saf 2013;36(Suppl 1):S33–S47. doi:10.1007/s40264-013-0097-8.
- EU-ADR reference set: 93 pairs (43 positive, 50 negative controls) for ten events. Coloma PM et al., Drug Saf 2013;36(1):13–23.
  doi:10.1007/s40264-012-0002-x.
- Both as distributed in the OHDSI MethodEvaluation R package (Apache License 2.0), file
  `data/*ReferenceSet.rda` at commit `d7305910f6c6`; converted to CSV without change and stored under
  `data/validation/faers/` with the citation in `pipelines/sources.toml` and `NOTICE`.
- A pair present in both sets with the same label counts once; a pair with conflicting labels is dropped
  and reported.

## 3. Index test (frozen)

- FAERS artifact `20261108T004801Z-b4dfb36a-b253` (2025Q4–2026Q3, 1,510,804 reports after removal of
  superseded versions and deleted cases).
- Drug names in FAERS are mapped to ingredient keys exactly as Janus does (`janus.memory.faers_build`);
  reference drug names are resolved to ingredient keys with the same name index. Reports are counted with
  the same drug roles as Janus.
- The 2×2 table, PRR, ROR, Woolf interval, Yates chi-squared, Haldane correction and Evans criteria are
  computed by `janus.memory.stats` unchanged. No threshold is tuned.

### Outcome definitions (MedDRA preferred terms, fixed now, before any count)

| Outcome | Preferred terms (any of) |
| --- | --- |
| Acute liver injury | Acute hepatic failure; Hepatic failure; Liver injury; Drug-induced liver injury; Hepatitis acute; Hepatitis fulminant; Hepatotoxicity; Hepatocellular injury; Cholestatic liver injury; Mixed liver injury; Hepatic necrosis |
| Acute kidney injury | Acute kidney injury; Renal failure; Renal failure acute; Renal injury; Nephropathy toxic; Renal tubular necrosis; Tubulointerstitial nephritis; Anuria |
| Acute myocardial infarction | Acute myocardial infarction; Myocardial infarction; Silent myocardial infarction |
| Upper gastrointestinal bleeding | Upper gastrointestinal haemorrhage; Gastric haemorrhage; Duodenal ulcer haemorrhage; Gastric ulcer haemorrhage; Peptic ulcer haemorrhage; Haematemesis; Melaena; Oesophageal haemorrhage; Gastritis haemorrhagic |
| Anaphylaxis | Anaphylactic reaction; Anaphylactic shock; Anaphylactoid reaction; Anaphylactoid shock |
| Aplastic anaemia | Aplastic anaemia; Bone marrow failure; Pancytopenia |
| Cardiac valve fibrosis | Cardiac valve fibrosis; Cardiac valve disease; Mitral valve incompetence; Aortic valve incompetence; Tricuspid valve incompetence |
| Leukopenia, neutropenia, agranulocytosis | Leukopenia; Neutropenia; Agranulocytosis; Febrile neutropenia; White blood cell count decreased; Neutrophil count decreased |
| Rhabdomyolysis | Rhabdomyolysis; Myoglobinuria; Necrotising myositis |
| Stevens–Johnson syndrome | Stevens-Johnson syndrome; Toxic epidermal necrolysis; SJS-TEN overlap |

Term matching ignores case. A report counts for an outcome when at least one of its terms is listed.

## 4. Outcomes

Primary: area under the ROC curve of ln ROR for positive versus negative controls, with a 95 % DeLong
interval, over all estimable pairs. Hypothesis: the lower bound is above 0.5.

Estimable: the drug resolves to an ingredient key and appears in at least one report. Pairs that are not
estimable are counted by reason and left out of the primary analysis; a secondary analysis includes them
with the lowest score.

Secondary:

- AUC per reference set and per outcome (descriptive, no hypothesis).
- Sensitivity and specificity of the Evans decision Janus uses (PRR ≥ 2, chi-squared ≥ 4, at least 3
  reports), with Wilson intervals.
- Empirical calibration (Schuemie MJ et al., Stat Med 2014;33(2):209–218): a normal systematic-error
  distribution is fitted by maximum likelihood to ln ROR of the negative controls, taking each estimate's
  standard error into account. Reported: the fitted mean and spread; the share of negative controls
  whose nominal 95 % interval excludes 1, before and after calibration (leave-one-out for the
  negatives); calibrated p-values for the positive controls.
- A calibration plot (estimate against standard error, with the fitted null).

## 5. Analysis

One script (`pipelines/tools/faers_calibration.py`) computes every number from the frozen inputs and
writes them with the plot. Results are reported whether or not the hypothesis is met.

## 6. Limits stated in advance

- FAERS is a spontaneous-reporting system: counts are reports, not patients; disproportionality is not
  a rate and does not show cause. Reporting is affected by publicity, litigation and stimulated reporting.
- One year of reports; rare drugs have few reports and wide intervals.
- The reference sets were built for observational health-care data; some of their negative controls may
  carry reporting artefacts in FAERS (for example indication bias).
- The outcome definitions are lists of preferred terms chosen in advance, not validated case definitions.
