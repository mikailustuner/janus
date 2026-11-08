# Pharmacologist review: Janus event vocabulary (collective-memory task 4)

> **Drafting-level review by an AI agent (pharmacologist role). It is not a clinical sign-off.** Every item
> below is a recommendation; the project owner decides. Nothing user-facing may use the mappings until the
> owner has accepted them and a pharmacist or physician has reviewed them. Counts are reports, never people.

- **Date:** 2026-11-08.
- **Files read:** `.kiro/specs/collective-memory/event-mapping-review.md` (sheet), `data/memory_events.csv`,
  `data/pipc.csv`, `.kiro/specs/cascade-engine/mapping-review.md` (class review, row 49 narrowing, rows 27 and 57
  not matchable), `collective-memory/requirements.md` Requirement 6, `design.md` §4.6 and §5.2,
  `.kiro/steering/medical-safety.md` (forbidden phrases).
- **Queried (read-only, FAERS counts file build `20261108T020842Z-7445632a-f55a79cf-4714`, region ALL, window
  2025Q4-2026Q3):** `faers_event_counts` (PT existence and counts), `faers_report_event` (union of reports over a
  PT list, once per report), `faers_pair_counts` (how concentrated a PT is on a few ingredients),
  `faers_report` (quarter spread). Checks that passed: all 189 sheet count rows equal the file; all PTs in the CSV
  exist and are NFC; every PIPC row 1-65 is in exactly one key; no forbidden phrase (medical-safety.md, five
  languages, whole-word scan) in any label or note. Every PT I propose below was looked up by exact string in the
  file. The numbers "union" below are reports in the file (all deduplicated reports, not only mapped ones).
- I did not use any MedDRA hierarchy (none is licensed here). Statements about what a PT contains come from its
  name, not from MedDRA.

## 1. Verdicts

| Key | Verdict | Summary |
|---|---|---|
| cough | ACCEPT | Cough only. |
| dizziness | ACCEPT (FR label) | One key is right for rows 2 and 56. FR "Vertiges" means spinning; use "Étourdissements". |
| depression | ACCEPT | Keep Depression suicidal out. |
| erectile_dysfunction | ACCEPT | |
| peripheral_oedema | ACCEPT (caveat) | Peripheral swelling is 71% of the key; unverified scope. See answers. |
| oedema | CHANGE | Add Fluid retention (the label promises it). Do not add Peripheral swelling. |
| constipation | ACCEPT | |
| gout_hyperuricaemia | CHANGE | Blood uric acid increased to core (rule 3 of the sheet itself). |
| urinary_incontinence | ACCEPT | |
| myalgia_myositis | ACCEPT | Muscle spasms, Rhabdomyolysis stay out. |
| insomnia | ACCEPT | |
| nausea | ACCEPT | Vomiting stays out. |
| hypertension | CHANGE | Add systolic and diastolic "increased" PTs. |
| rash | CHANGE | Add Rash morbilliform. Severe skin reactions stay out. |
| extrapyramidal_symptoms | ACCEPT | Bradykinesia, Dyskinesia stay out. |
| akathisia_tardive_movements | ACCEPT (label) | "Restlessness" is too general; say inner restlessness. |
| arrhythmia | CHANGE | Make the generic arrhythmia PTs consistent; add Torsade de pointes; QT and named rhythms out. |
| hyperglycaemia | ACCEPT (FR label) | Diabetes PTs stay out. |
| cognitive_impairment | ACCEPT | Dementia and Confusional state stay out. |
| gastrointestinal_upset | ACCEPT PTs, CHANGE label | Label promises bowel upset; the PTs are indigestion and belly discomfort. |
| diarrhoea | ACCEPT | |
| rhinorrhoea | ACCEPT | |
| psychosis_hallucinations | CHANGE | Delusion to core; label names delusions. Keep one key. |
| tremor | ACCEPT (TR label) | "Titreme" also means shivering. |
| joint_pain | ACCEPT | |
| genital_fungal_infection | CHANGE | Add Genital candidiasis; Balanoposthitis to borderline. One key for rows 41 and 62 is acceptable. |
| urinary_retention | ACCEPT | |
| osteoporosis_fracture | CHANGE (small) | Add two osteoporosis subtypes; fractures stay out; say so in the note. |
| vitamin_mineral_deficiency | ACCEPT (flag) | Iron PTs partly reflect blood loss, a reason for the PPI. Pharmacist question. |
| gastritis | ACCEPT | Oesophagitis stays out. |
| gastric_ulcer_bleed | CHANGE | Add Haematemesis and Melaena. Repeating the Gastritis PTs is fine. |
| heart_failure | CHANGE | Add the named heart-failure subtypes. Rows 44 and 54 stay in one key, with a caveat. |
| dry_mouth | ACCEPT | No matchable rule reaches this key (row 57). |
| seizures | CHANGE | Add three seizure types; ES label says "epileptic". Epilepsy and Status epilepticus stay out. |
| improvement_pain, improvement_sleep, improvement_mood, improvement_nausea, improvement_swelling | ACCEPT | See cross-cutting item 5. |

No SPLIT or MERGE is recommended. I considered and rejected: merging `oedema` into `peripheral_oedema` (placeholder
key must keep its meaning, row 43 says generic edema); splitting `heart_failure` for rows 44 and 54; splitting
`vitamin_mineral_deficiency` into three keys (a PIPC row can only point to one key); splitting
`psychosis_hallucinations`.

## 2. Keys that are not a plain ACCEPT

PT lists below are the complete core list after my changes. Union = reports with any core PT, once per report.

### oedema (CHANGE)
Core: `Oedema | Oedema peripheral | Generalised oedema | Fluid retention`. Union 10,757 -> 13,482 reports.
- Add Fluid retention (3,145 reports): the label is "Fluid retention or swelling", and fluid retention is how
  the thiazolidinedione effect is reported. Alternative if the owner wants it narrow: keep the list and change the
  label to "Swelling (oedema)".
- Do not add Peripheral swelling here: it would raise the union to 22,759 (limb swelling of any cause would
  outweigh the rest). The two keys then differ on that PT; I accept that because the PIPC wording differs too
  ("Peripheral edema" rows 5 and 31, "Edema" row 43).

### gout_hyperuricaemia (CHANGE)
Core: `Gout | Hyperuricaemia | Gouty arthritis | Blood uric acid increased`. Union 1,600 -> 2,019.
- The sheet's rule 3 says a lab-value PT is core when the PIPC event is itself the lab condition. "Gout or
  Hyperuricemia" is. Blood glucose increased (hyperglycaemia) and Blood pressure increased (hypertension) are core
  under the same rule, so Blood uric acid increased (514 reports) should be too.

### hypertension (CHANGE)
Core: `Hypertension | Blood pressure increased | Blood pressure systolic increased | Blood pressure diastolic increased`.
Union 24,869 -> 26,039.
- The two added PTs are direct subtypes of "Blood pressure increased" (1,533 and 415 reports) and are omitted by
  accident. Keep out: Hypertensive crisis (alarming), Essential hypertension (211, the patient's own disease),
  Blood pressure inadequately controlled (known hypertension), Hypotension.
- Borderline note: Supine hypertension (9 reports) is the midodrine-specific form (row 14); too small to matter.

### rash (CHANGE)
Core: `Rash | Rash erythematous | Rash pruritic | Rash macular | Rash maculo-papular | Rash papular | Rash morbilliform`.
Union 50,729 -> 50,863.
- Rash morbilliform (180) is the measles-like eruption classic for aromatic anticonvulsants. Keep out: Exfoliative
  rash, Drug eruption (1,480, non-specific), Stevens-Johnson syndrome (1,118), Toxic epidermal necrolysis (1,217),
  DRESS (2,207); also Rash vesicular and Rash pustular (borderline).

### arrhythmia (CHANGE)
Core: `Arrhythmia | Arrhythmia supraventricular | Ventricular arrhythmia | Tachyarrhythmia | Ventricular tachyarrhythmia | Supraventricular tachyarrhythmia | Torsade de pointes`.
Union 2,475 -> 3,231 (generic-only version without Torsade: 2,781).
- The proposed core is uneven: two rare subtypes (27 and 17 reports) are in, while Ventricular arrhythmia (199) and
  Tachyarrhythmia (111) are not. The rule I apply: PTs that name a general class of rhythm disturbance are core.
- Torsade de pointes (495): the arrhythmia that defines the QT mechanism behind rows 21 and 63. Reporters code it
  as Torsade, not "Arrhythmia", so leaving it out hides the most on-point reports. It is also the most alarming
  PT in the sheet (see item 3); this is the owner's call.
- Borderline (not core): Electrocardiogram QT prolonged (2,477 mapped; an ECG reading, not a heartbeat
  symptom), Long QT syndrome, Ventricular tachycardia, Ventricular fibrillation, Supraventricular tachycardia,
  Atrial fibrillation, Bradyarrhythmia, Heart rate irregular. Named rhythms follow cardiac disease, and atrial
  fibrillation is the main reason antiarrhythmics (the marker class) are prescribed. Adding them would raise the
  key to about 10,400 reports; adding the two QT PTs alone, to about 5,000.

### psychosis_hallucinations (CHANGE)
Core: the sheet's nine PTs + `Delusion`. Union 10,678 -> 11,138. One key for rows 30 and 60 is right (see answers).
- Delusion (1,137) is the other defining psychotic symptom; row 30 says "psychotic symptoms". Paranoia (875) stays
  borderline (can be personality or mood). Substance-induced psychotic disorder stays out.
- Label: "Hallucinations, delusions or other psychotic symptoms" (see item 6 for the translations).

### genital_fungal_infection (CHANGE)
Core: `Vulvovaginal candidiasis | Vulvovaginal mycotic infection | Genital infection fungal | Genital candidiasis | Balanitis candida`.
Union 511 -> 441.
- Add Genital candidiasis (35, a direct match). Move Balanoposthitis (104) to borderline: the PT does not say
  fungal and the key is about fungal infection. This is a moderate-confidence call: balanoposthitis is the usual male
  presentation on an SGLT-2 inhibitor, and the owner may prefer to keep it (it is about a fifth of the key).
- Not core: Candida infection (site not given), Vaginal infection (436, includes bacterial), the vulvovaginal
  symptom PTs, Fournier's gangrene (a separate serious event).

### osteoporosis_fracture (CHANGE, small)
Core: `Osteoporosis | Osteopenia | Bone density decreased | Osteoporotic fracture | Osteoporosis postmenopausal | Senile osteoporosis`.
Union 3,956 -> 3,981.
- Add the two subtypes (20 and 9 reports). Fractures stay out. The key name says "fracture" but the label does not;
  put in the `note` column: "Fractures are counted only where coded osteoporotic; site fractures are mostly trauma."

### gastric_ulcer_bleed (CHANGE)
Core: the sheet's twelve PTs + `Haematemesis | Melaena`. Union 7,749 -> 9,444.
- Vomiting blood and black stool (1,323 and 1,052 reports) are the way upper GI bleeding is usually coded, and the
  marker (gastroprotective agent) acts on the upper tract. Omitting them hides real reports.
- Keep out: Lower gastrointestinal haemorrhage (273; the label says "bowel", so the owner may add it), and the
  ulcer perforation PTs (Duodenal ulcer perforation 1,383 is an outlier; see "Not verified").

### heart_failure (CHANGE)
Core: `Cardiac failure | Cardiac failure congestive | Cardiac failure acute | Cardiac failure chronic | Heart failure with reduced ejection fraction | Heart failure with preserved ejection fraction | Heart failure with midrange ejection fraction | Left ventricular failure | Right ventricular failure`.
Union 7,620 -> 8,364.
- The five added PTs are named types of heart failure (253, 129, 13, 212, 271). Cardiopulmonary failure (173) stays
  out (unclear), as does Pulmonary oedema.
- Row 54 is "worsening of heart failure" in people who already have it. No PT carries "worsening", so reports from
  people with existing heart failure are counted. This is confounding by the disease the marker drug treats. Rows 44
  and 54 can share a key, but the experience spec should word the row 54 FAERS line carefully (it counts reports of
  heart failure with the NSAID, not reports of worsening).

### seizures (CHANGE)
Core: `Seizure | Seizure cluster | Generalised tonic-clonic seizure | Convulsions local | Partial seizures | Tonic convulsion | Clonic convulsion`.
Union 13,120 -> 13,546.
- Partial seizures (510) is the second most common seizure type in the file and was missing, while the rare
  "Convulsions local" (12) was in. Keep out: Epilepsy and the epilepsy syndromes (the marker drug's indication),
  Status epilepticus (see answers), Febrile convulsion, Psychogenic seizure, Drug withdrawal convulsions,
  Seizure like phenomena.
- ES label: "crisis epilépticas" reads as an epilepsy diagnosis, which the key deliberately excludes (item 6).

### gastrointestinal_upset (PTs accepted, label CHANGE)
Core unchanged: `Gastrointestinal disorder | Dyspepsia | Abdominal discomfort`.
- The real cholinesterase-inhibitor effects (nausea, vomiting, diarrhoea) have their own keys and are not in this one.
  The label "Stomach or bowel upset" suggests diarrhoea and nausea are counted. New label: "Indigestion or stomach
  discomfort" (item 6). Row 26's antiemetic marker points at nausea and vomiting, which this key does not count;
  the experience spec could show the nausea key as a second, separate line for row 26 (never summed).
- "Gastrointestinal disorder" (10,798) is a non-specific PT, against the sheet's rule 5. I keep it because the PIPC
  event itself is non-specific. Whether it is what reporters use for "stomach upset" is unverified.
- Row 27 (bismuth) is not matchable, so only row 26 reaches this key through a finding.

### dizziness, akathisia_tardive_movements, hyperglycaemia, tremor (ACCEPT with a label change)
PT lists unchanged. Label changes in item 6.

### peripheral_oedema, vitamin_mineral_deficiency (ACCEPT with a flag)
PT lists unchanged. See answers and item 2.

## 3. Answers to the sheet questions

1. **dizziness: is one key right for rows 2 and 56?** Yes. Both are orthostatic hypotension and dizziness, and the
   markers (antiemetic, vestibular suppressant) both treat the dizziness. Keep Presyncope and Vertigo out
   (different symptoms), and Hypotension (13,315) out: for antihypertensives low pressure is the intended effect.
2. **peripheral_oedema: is Peripheral swelling close enough?** Acceptable, with a caveat. The key's lay label is
   "swollen ankles or legs", and Peripheral swelling is how most such reports are coded. But it is 13,304 of the key's
   18,608 reports (71%), and limb swelling from injury, clot, or infection is also coded there. I could not check
   what the PT contains. Before the owner accepts it, the statistician should compare the drug-event figures with
   and without it. Label nit: it also covers hands; DE "periphere Ödeme" should be singular "peripheres Ödem".
3. **myalgia_myositis: should Muscle spasms be in for row 11?** No. It would raise the union from 12,168 to 23,468
   (12,336 reports of spasms from any cause, such as muscle disease, spasticity, and exercise). PIPC names the
   event as myalgia/myositis for rows 9 to 11. Row 11 is a statin followed by quinine for cramps, so the FAERS line
   next to it will under-count cramps; say that in the finding text. Rhabdomyolysis (2,860) stays out: severe,
   a separate event.
4. **nausea: should Vomiting be in?** No. The union with Vomiting is 78,703 against 60,514, and PIPC says nausea.
   Vomiting may be shown as a separate line.
5. **rash: keep severe cutaneous reactions out?** Yes. Stevens-Johnson, TEN, DRESS, Exfoliative rash and the
   non-specific Drug eruption are different events with different urgency. A rash count must not be read as
   covering them. Recommendation for the experience spec: show urgent-care wording for a severe skin reaction
   on every finding with this key, whatever the counts say.
6. **arrhythmia: which QT, torsade and tachycardia PTs belong?** Torsade de pointes yes. Electrocardiogram QT
   prolonged and Long QT syndrome no (ECG findings). Ventricular tachycardia, Ventricular fibrillation,
   Supraventricular tachycardia and Atrial fibrillation no (named rhythms of cardiac disease; AF is the marker
   class's main indication). Generic arrhythmia and tachyarrhythmia PTs yes. Details in section 2.
7. **cognitive_impairment: agree to leave dementia out?** Agree. Dementia and Dementia Alzheimer's type (3,188
   reports together) are the disease the marker drug treats. Confusional state (9,480) also stays out: acute
   confusion is delirium-like and would raise the union from 14,268 to 22,032. Mental impairment (1,413) and
   Disturbance in attention (2,654) are plausible borderline PTs. Note that Memory impairment is still confounded
   by dementia among benzodiazepine and tricyclic users; no PT choice removes that.
8. **psychosis_hallucinations: keep one key?** Yes. Rows 30 and 60 are the same cascade (psychotic symptoms, then an
   antipsychotic); the key covers "psychosis" and "psychotic symptoms, hallucinations" alike. Note for row 30:
   hallucinations are also a feature of the disease the dopaminergic drug treats (Parkinson's disease), so the
   FAERS line is confounded by indication.
9. **genital_fungal_infection: OK to share between rows 41 and 62?** Yes. The cascade is the same (genital
   candidiasis, then an antifungal). Row 62 names vulvovaginal candidiasis only; the shared key also counts male
   balanitis, which for acitretin is a slight over-count. The key is small (441 to 511 reports).
10. **osteoporosis_fracture: are site fractures in?** Out. Hip, femur, spinal and unspecified fracture PTs together
    would raise the union from 3,956 to 10,936, mostly falls and trauma. Compression fracture (1,005) stays
    borderline. Channelling also applies: people with osteoporosis on a bisphosphonate are often given a PPI.
11. **vitamin_mineral_deficiency: follows the row 49 narrowing?** Yes, B12, magnesium and iron. One flag: iron
    deficiency (anaemia) is often blood loss, which is also a reason to start a PPI; the iron PTs are 1,294 of
    the 3,773 reports. I did not change it because the owner chose iron; it is a pharmacist question.
12. **gastric_ulcer_bleed: repeating the Gastritis PTs?** Fine. A PT may sit in two keys; no PIPC row group is
    affected (requirement 6.6). Row 50 is a bisphosphonate with a gastroprotective agent; row 51 is an NSAID.
13. **seizures: leave Epilepsy PTs out?** Agree. Status epilepticus (814) also stays out: it is a prolonged seizure,
    so a report usually carries Seizure too, and the PT is alarming without adding much (item 3).

## 4. Cross-cutting findings

### 4.1 Row attachment and fit to the drug pair (item 1)
- All 65 rows are in exactly one key. Fits checked against the drug pair:
  - Rows 21 and 63 (antipsychotic, erythromycin): QT-related arrhythmia; handled under `arrhythmia`.
  - Row 11 (statin, quinine for cramps): fits `myalgia_myositis` as PIPC words it; the cramps limit is in answer 3.
  - Row 51 repeats the Gastritis PTs: acceptable (answer 12).
  - Row 17 (antipsychotic, beta-blocker marker): the beta-blocker treats tremor and akathisia, so the line next to
    it is the extrapyramidal key as PIPC words it. Fine.
  - Row 47 (laxative then diarrhoea): the index drug causes it by its action; fine.
  - Rows 27 and 57 are not matchable: `dry_mouth` is reached by no finding at all; `gastrointestinal_upset` only
    through row 26. Both keys are still valid for donations and for lookups by key.
  - Row 54 ("worsening"): see heart_failure.
  - Rows 41 and 62: see answer 9.
- Documentation: `design.md` §4.6 shows `cough` with `Cough|Productive cough`; the proposal has `Cough` only.
  Update the example when the vocabulary is accepted.

### 4.2 Confounding by indication or by the disease (item 2)
PT choice can remove only the two named cases and the ones below. The rest is a limit that belongs in the
statistics wording ("reports of the drug and the event together; the disease may explain them").
- **Antipsychotic and hyperglycaemia:** Diabetes PTs (Diabetes mellitus 3,944, Type 2 diabetes mellitus 2,301,
  Diabetes mellitus inadequate control) are already out; keep them out. Diabetic ketoacidosis out (serious). But
  Hyperglycaemia and Blood glucose increased are also reported for people who already have diabetes; no PT fixes it.
- **Diuretic and urinary PTs (rows 8, 7):** Not an indication problem. Pollakiuria (3,098), Polyuria (497) and
  Micturition urgency are the expected diuretic action, not a side effect; keep them out. Gout in diuretic users
  follows heart failure and kidney disease.
- **Beta-blocker and mood (row 3):** Depression is common after a heart attack, when beta-blockers are started.
  Disease confounding, not fixable by PT.
- **Antihypertensive and hypertension:** correct that the index drugs of rows 14, 38, 53, 61, 64 are not
  antihypertensives. Patients on them often have hypertension, so Essential hypertension is kept out.
- **Urinary retention (row 45):** older men with benign prostate enlargement; the marker drug treats it.
- **Dopaminergic drug and hallucinations/dyskinesia (rows 30, 20):** Parkinson's disease causes hallucinations.
  Dyskinesia (2,721) is concentrated: one ingredient accounts for 589 of 2,276 mapped reports (I did not look up
  which). Keep Dyskinesia out of both movement keys.
- **PPI (rows 48, 49):** bisphosphonate users get PPIs (osteoporosis); bleeding patients get PPIs (iron).
- **Seizures (row 58) and cardiac failure (row 54):** the patient may already have epilepsy or heart failure.
- No further PT should be removed for this reason.

### 4.3 Alarming or misleading PTs (item 3)
- **Out of every key (keep it that way):** Depression suicidal, Rhabdomyolysis, Status epilepticus, Hypertensive
  crisis, Diarrhoea haemorrhagic, Parkinsonism hyperpyrexia syndrome, Hyperglycaemic hyperosmolar nonketotic
  syndrome, Stevens-Johnson syndrome, Neuroleptic malignant syndrome, Duodenal ulcer perforation.
- **In a key by design:** Torsade de pointes (proposed by me; owner's decision), Gastrointestinal haemorrhage,
  Cardiac failure acute, Ventricular tachyarrhythmia, Generalised tonic-clonic seizure, Major depression, Psychotic
  disorder. They are the event the key names.
- Recommendation for the experience spec: show the key label by default, and the PT names only in a details view,
  never in a banner. `PairOut.event.pts` returns them (design §5.2), so this is a display rule, not an API change.
- Depression key: a reader with low mood may see it. Ask a clinician whether the screen needs a support line.

### 4.4 PT strings (item 4)
- All 189 sheet rows and all CSV PTs exist by exact string. Every PT I propose exists. PTs I looked for that do not
  exist, so nobody should propose them: Fragility fracture, Hyposalivation, Tardive dystonia, Xerostomia.

### 4.5 Benefit keys (item 5)
- All five are sensible and have no forbidden phrase in any language. They cover no PT, so the FAERS layer answers
  `not_available`.
- Semantic partners: `improvement_sleep` with insomnia, `improvement_nausea` with nausea, `improvement_swelling` with
  the two oedema keys. `improvement_pain` and `improvement_mood` stand alone, which is fine.
- Wording: the labels describe what a donor noticed, not what a medicine does. The donation screen must not read
  as an efficacy claim ("this medicine reduces pain") and must not prompt "after you stopped" (Janus never advises
  stopping). DE "Weniger Schwellungen" could be singular "Weniger Schwellung". No other issue.

### 4.6 Labels (item 6)
No label contains a forbidden phrase (scan above). Clinical accuracy and lay wording; the tr, de, fr, es drafts need a
native check in any case. Suggested changes (my recommendation, to be checked by a native speaker):

| Key | Current | Suggested |
|---|---|---|
| dizziness FR | Vertiges ou baisse de tension en se levant | Étourdissements ou baisse de tension en se levant |
| tremor TR | Titreme (tremor) | Ellerde veya vücutta titreme (tremor) ("titreme" alone also means shivering) |
| hyperglycaemia FR | Hyperglycémie (sucre sanguin élevé) | Hyperglycémie (taux de sucre élevé dans le sang) |
| seizures ES | Convulsiones (crisis epilépticas) | Convulsiones (crisis convulsivas) |
| psychosis en | Hallucinations or psychotic symptoms | Hallucinations, delusions or other psychotic symptoms |
| psychosis tr / de | ... | Halüsinasyon, sanrı veya psikotik belirtiler / Halluzinationen, Wahnvorstellungen oder psychotische Symptome |
| psychosis fr / es | ... | Hallucinations, idées délirantes ou symptômes psychotiques / Alucinaciones, ideas delirantes o síntomas psicóticos |
| gastrointestinal_upset en | Stomach or bowel upset | Indigestion or stomach discomfort |
| gastrointestinal_upset tr / de | ... | Hazımsızlık veya mide rahatsızlığı / Verdauungsbeschwerden oder Magenbeschwerden |
| gastrointestinal_upset fr / es | ... | Troubles digestifs ou gêne à l'estomac / Indigestión o molestias de estómago |
| akathisia en | Restlessness or involuntary movements | Inner restlessness or involuntary movements (akathisia, tardive dyskinesia) |
| akathisia tr / de | ... | Yerinde duramama veya istemsiz hareketler / Innere Unruhe oder unwillkürliche Bewegungen |
| akathisia fr / es | ... | Impatiences ou mouvements involontaires / Inquietud interna o movimientos involuntarios |
| peripheral_oedema DE | periphere Ödeme | peripheres Ödem |
| improvement_swelling DE | Weniger Schwellungen | Weniger Schwellung |

Other labels are accurate. "Depression" and "Seizures" are the PIPC event words, not diagnoses of the reader. Two
remarks: the ES `rhinorrhoea` label "Secreción nasal" is clinical rather than lay ("Moqueo"), and the EN
`urinary_retention` label "Difficulty passing urine" reads milder than the PT (complete retention).

## 5. Not verified or needs a pharmacist or physician

- Everything here is a drafting-level opinion of an AI agent. A pharmacist or physician must review the final PT
  lists before any public claim, as requirement 6.3 says.
- What MedDRA puts inside Peripheral swelling, Gastrointestinal disorder and Balanoposthitis. I judged from names.
- No disproportionality figure was computed (statistician's work). The statistician should check, for the keys I
  changed or flagged (peripheral_oedema, oedema, arrhythmia, vitamin_mineral_deficiency), whether the result is
  driven by one PT.
- A recurring report cluster: Duodenal ulcer perforation has 1,383 reports, five ingredients each appear in
  936 to 1,041 of them, they are spread evenly over the four quarters, and 578 of them also carry Peripheral
  swelling. About 1,000 reports seem to share one drug list. I did not identify the source or whether
  they are duplicates across cases (known limit: dedup is by case version only). It may add about 1,000 reports to
  `peripheral_oedema` (of 18,608) and `oedema` is not affected. The builder or statistician should look at it.
- Whether the support-line and urgent-care wording (depression, severe rash, QT) is needed.
- Whether iron belongs in row 49's event key (blood-loss confounding).
- Torsade de pointes inside `arrhythmia` (alarm versus coverage), and Balanoposthitis out of the genital key.
- Translation quality in tr, de, fr, es. Whether Status epilepticus belongs in `seizures` for a neurologist.
- Mapped-ingredient names for the Wikidata ids I mention were not resolved.

VERDICT: approved with changes
