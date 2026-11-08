# Event mapping review: Janus event vocabulary (collective-memory task 4)

> **Status: PROPOSED. Nothing user-facing uses these mappings until the owner has reviewed them.**
> Every key in `data/memory_events.csv` has `status = proposed`; the FAERS key path, the finding hook
> and the donation vocabulary ignore keys that are not `active`.
> Written 2026-11-08. Counts: FAERS window 2025Q4-2026Q3, region ALL, deduplicated reports; the second
> number is reports with a mapped ingredient. Counts are reports, never people. PTs are MedDRA Preferred
> Terms as published in FAERS (MedDRA® is a registered trademark of ICH). The labels in tr, de, fr, es are
> machine-drafted and need a native check.
> The mapping was drafted by the AI assistant, reviewed by the pharmacologist agent (section 1) and
> still needs review by the project owner, and by a pharmacist or physician before any public claim.

## 0. How the proposal was made
- The 65 PIPC rows have 41 spellings of the adverse event. They were merged into **34 adverse keys**, so
  every PIPC row belongs to exactly one key (`pipc_positions`), plus **5 benefit keys** (improvement terms;
  they cover no PT, so the FAERS layer answers `not_available` for them).
- Rules used (change any of them):
  1. **Core PTs**: the same clinical event in the same words, or a direct subtype or synonym.
  2. **Borderline PTs** (not in the CSV): neighbours that the owner may want in; listed with a reason.
  3. Laboratory-value PTs are core only where the PIPC event is itself the lab condition (hyperglycaemia,
     hyperuricaemia, low magnesium or B12).
  4. **Indication-like PTs are left out** when the marker drug treats them (dementia for the cholinesterase
     inhibitor, epilepsy for the anticonvulsant): they would reflect the disease, not a side effect.
  5. Non-specific neighbours (Swelling, Surgery, Abdominal pain) are not core.
  6. A PT may sit in two keys; the key's count is always the union over its PTs, once per report.
- The union count (reports with any PT) is computed at query time (design §4.3); a PT list change needs no
  rebuild of the count file.
- **Placeholder keys kept**: `peripheral_oedema`, `cough`, `dizziness`, `constipation`, `urinary_incontinence`, `insomnia`, `improvement_pain`, `improvement_sleep`.

## 1. Reviewer verdict (pharmacologist agent, 2026-11-08): approved with changes

Full review: `event-mapping-pharmacologist-review.md` (drafting-level, AI agent, not a clinical sign-off).
**The revised proposal below and in `data/memory_events.csv` already applies the reviewer's recommendations**
(rows marked "added by review"); the owner can reject any of them. No SPLIT or MERGE was recommended.

Changes applied: PT additions for oedema (Fluid retention), gout (Blood uric acid increased), hypertension (systolic and
diastolic increased), rash (Rash morbilliform), arrhythmia (generic arrhythmia PTs and Torsade de pointes), psychosis
(Delusion), genital fungal infection (Genital candidiasis; Balanoposthitis moved to borderline), osteoporosis (two
subtypes), gastric ulcer or bleed (Haematemesis, Melaena), heart failure (five named types), seizures (three types);
label changes in FR (dizziness, hyperglycaemia), TR (tremor), ES (seizures), five languages for the psychosis, stomach
and akathisia keys, DE singular for two labels; notes added to the CSV for the keys with a known limit.

Open points the reviewer leaves to the owner (also in section 4):
1. **Torsade de pointes** inside `arrhythmia`: the PT that carries the QT concern behind rows 21 and 63, but the most
   alarming PT in the sheet. Include (applied in this revision) or leave out?
2. **Balanoposthitis** out of `genital_fungal_infection` (applied), about a fifth of that key; moderate confidence.
3. **Peripheral swelling** is 71 percent of `peripheral_oedema`; the statistician should compare drug-event figures with
   and without it before the key is accepted. Also a cluster of about 1,000 reports (Duodenal ulcer perforation with
   Peripheral swelling and one shared drug list) that may be duplicates across cases (known limit of the
   deduplication).
4. **Fluid retention** added to `oedema` (applied); the narrow alternative is to change the label to "Swelling (oedema)".
5. **Iron PTs** in `vitamin_mineral_deficiency` partly reflect blood loss (pharmacist question).
6. Whether the depression key and severe-rash and QT findings need a support or urgent-care line on screen (experience
   spec); PT names only in a details view, never in a banner.
7. Labels in tr, de, fr, es need a native check; the ES `rhinorrhoea` label "Secreción nasal" is clinical rather than lay.

## 2. Adverse keys

### `cough` (placeholder key)
- PIPC rows: 1; phrasings: Cough
- Index classes: Angiotensin converting enzyme inhibitor
- Label (en): Cough

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Cough | 23,066 | 20,815 | |
| borderline, not in CSV | Productive cough | 5,326 | 4,960 | wet cough is a different symptom from ACE-inhibitor dry cough |
| borderline, not in CSV | Upper-airway cough syndrome | 805 | 740 | post-nasal drip syndrome, a different mechanism |

### `dizziness` (placeholder key)
- PIPC rows: 2, 56; phrasings: Orthostatic hypotension, dizziness; Orthostatic hypotension/dizziness
- Index classes: Alpha-1 receptor blocker; Antihypertensive
- Label (en): Dizziness or low blood pressure on standing

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Dizziness | 35,378 | 29,136 | |
| core | Dizziness postural | 1,060 | 841 | |
| core | Orthostatic hypotension | 1,062 | 932 | |
| borderline, not in CSV | Presyncope | 1,910 | 1,612 | near-fainting; overlaps but is a distinct PT |
| borderline, not in CSV | Orthostatic intolerance | 54 | 48 | rare, wider syndrome |
| borderline, not in CSV | Dizziness exertional | 85 | 78 | triggered by exertion, not posture |

**Question:** Placeholder key kept (donations); PIPC rows 2 and 56 name 'orthostatic hypotension/dizziness'. Is one key right?

### `depression`
- PIPC rows: 3, 36, 55; phrasings: Depression
- Index classes: Beta-blocker (particularly lipophilic e.g., propranolol); Flunarizine; Opioid
- Label (en): Depression or low mood

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Depression | 11,150 | 9,770 | |
| core | Depressed mood | 4,533 | 4,182 | |
| core | Major depression | 467 | 437 | |
| core | Depressive symptom | 315 | 287 | |
| borderline, not in CSV | Depression suicidal | 190 | 182 | carries suicidality; keep out of a general key? |
| borderline, not in CSV | Adjustment disorder with depressed mood | 491 | 484 | a diagnosis category, narrower context |

### `erectile_dysfunction`
- PIPC rows: 4; phrasings: Erectile dysfunction
- Index classes: Beta-blocker (particularly lipophilic e.g., propranolol)
- Label (en): Erectile dysfunction

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Erectile dysfunction | 1,662 | 1,578 | |
| core | Organic erectile dysfunction | 8 | 8 | |
| borderline, not in CSV | Sexual dysfunction | 913 | 771 | non-specific |
| borderline, not in CSV | Libido decreased | 575 | 516 | related but a different symptom |

### `peripheral_oedema` (placeholder key)
- PIPC rows: 5, 31; phrasings: Peripheral edema
- Index classes: Calcium channel blocker; Gabapentinoid
- Label (en): Swollen ankles or legs (peripheral oedema)

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Oedema peripheral | 6,117 | 5,471 | |
| core | Peripheral swelling | 13,304 | 11,274 | |
| borderline, not in CSV | Swelling | 7,239 | 6,316 | non-specific, any body site (7,239 reports) |

**Question:** Placeholder key kept. Is 'Peripheral swelling' (13,304 reports) close enough to peripheral oedema?

### `oedema`
- PIPC rows: 43; phrasings: Edema
- Index classes: Pioglitazone or Rosiglitazone
- Label (en): Fluid retention or swelling (oedema)

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Oedema | 4,251 | 3,870 | |
| core | Oedema peripheral | 6,117 | 5,471 | |
| core | Generalised oedema | 1,019 | 888 | |
| core (added by review) | Fluid retention | 3,145 | 2,775 | |
| borderline, not in CSV | Fluid retention | 3,145 | 2,775 | mechanism rather than the sign |

### `constipation` (placeholder key)
- PIPC rows: 6, 34, 65; phrasings: Constipation
- Index classes: Calcium channel blocker; Iron supplement; Tricyclic antidepressant
- Label (en): Constipation

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Constipation | 21,142 | 18,698 | |
| borderline, not in CSV | Faecaloma | 534 | 481 | a complication (impaction) |

### `gout_hyperuricaemia`
- PIPC rows: 7; phrasings: Gout or Hyperuricemia
- Index classes: Diuretic
- Label (en): Gout or high uric acid

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Gout | 1,243 | 1,091 | |
| core | Hyperuricaemia | 333 | 315 | |
| core | Gouty arthritis | 38 | 35 | |
| core (added by review) | Blood uric acid increased | 514 | 477 | |
| borderline, not in CSV | Blood uric acid increased | 514 | 477 | laboratory finding reported as the event |

### `urinary_incontinence` (placeholder key)
- PIPC rows: 8, 24, 32, 35; phrasings: Urinary Incontinence; Urinary incontinence
- Index classes: Cholinesterase inhibitor; Diuretic; Selective serotonin reuptake inhibitor/Serotonin and norepin; Tricyclic antidepressant
- Label (en): Urinary incontinence

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Urinary incontinence | 1,785 | 1,582 | |
| core | Urge incontinence | 64 | 61 | |
| core | Stress urinary incontinence | 33 | 29 | |
| core | Mixed incontinence | 4 | 4 | |
| borderline, not in CSV | Incontinence | 628 | 524 | unspecified: could be faecal |
| borderline, not in CSV | Micturition urgency | 1,010 | 865 | urgency without leakage |

### `myalgia_myositis`
- PIPC rows: 9, 10, 11; phrasings: Myalgia/myositis
- Index classes: HMG Co-A reductase inhibitor; Hydroxymethylglutaryl-coenzyme A (HMG Co-A) reductase inhibi
- Label (en): Muscle pain or inflammation (myalgia, myositis)

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Myalgia | 11,430 | 9,705 | |
| core | Myositis | 818 | 751 | |
| borderline, not in CSV | Muscular weakness | 7,632 | 6,580 | different symptom |
| borderline, not in CSV | Muscle spasms | 12,336 | 10,069 | cramps; quinine row 11 treats cramps |
| borderline, not in CSV | Rhabdomyolysis | 2,860 | 2,778 | severe and separate; statin safety signal in its own right |

**Question:** Row 11 (statin, then quinine) treats cramps: should 'Muscle spasms' be in?

### `insomnia` (placeholder key)
- PIPC rows: 12, 25, 59; phrasings: Insomnia
- Index classes: Cholinesterase inhibitor; Corticosteroid; HMG Co-A reductase inhibitor
- Label (en): Difficulty sleeping (insomnia)

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Insomnia | 15,753 | 13,897 | |
| core | Initial insomnia | 819 | 699 | |
| core | Middle insomnia | 1,258 | 1,131 | |
| core | Terminal insomnia | 179 | 168 | |
| core | Paradoxical insomnia | 9 | 9 | |
| borderline, not in CSV | Sleep disorder | 6,787 | 6,042 | wider, includes sleepiness and parasomnia |
| borderline, not in CSV | Poor quality sleep | 1,887 | 1,669 | unrefreshing sleep, not insomnia as such |

### `nausea`
- PIPC rows: 13, 16, 52; phrasings: Nausea
- Index classes: Anticonvulsant; Digoxin; NSAID
- Label (en): Nausea

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Nausea | 60,514 | 51,952 | |
| borderline, not in CSV | Vomiting | 37,047 | 32,730 | the antiemetic is also given for vomiting |
| borderline, not in CSV | Retching | 1,568 | 1,361 |  |

**Question:** Should 'Vomiting' (37,047 reports) be in, since an antiemetic treats it too?

### `hypertension`
- PIPC rows: 14, 38, 53, 61, 64; phrasings: Hypertension; Hypertension (dose-related)
- Index classes: Corticosteroid; Fludrocortisone; Midodrine; NSAID; Venlafaxine
- Label (en): High blood pressure

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Hypertension | 14,871 | 13,207 | |
| core | Blood pressure increased | 10,421 | 8,977 | |
| core (added by review) | Blood pressure systolic increased | 1,533 | 1,433 | |
| core (added by review) | Blood pressure diastolic increased | 415 | 389 | |
| borderline, not in CSV | Hypertensive crisis | 639 | 566 | an emergency, narrower |
| borderline, not in CSV | Blood pressure inadequately controlled | 219 | 209 | worsening of known hypertension |
| borderline, not in CSV | Blood pressure abnormal | 1,807 | 1,528 | direction unknown |
| borderline, not in CSV | Blood pressure fluctuation | 1,574 | 1,409 | direction unknown |

### `rash`
- PIPC rows: 15; phrasings: Rash
- Index classes: Anticonvulsant
- Label (en): Skin rash

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Rash | 37,437 | 32,361 | |
| core | Rash erythematous | 6,426 | 5,956 | |
| core | Rash pruritic | 4,719 | 4,177 | |
| core | Rash macular | 2,992 | 2,624 | |
| core | Rash maculo-papular | 1,738 | 1,686 | |
| core | Rash papular | 1,240 | 894 | |
| core (added by review) | Rash morbilliform | 180 | 160 | |
| borderline, not in CSV | Dermatitis | 2,505 | 2,316 | other skin conditions; topical steroid is also given for them |
| borderline, not in CSV | Urticaria | 14,673 | 12,961 | hives, different |
| borderline, not in CSV | Eczema | 12,452 | 11,556 | different |
| borderline, not in CSV | Erythema | 14,312 | 12,496 | redness, non-specific |

**Question:** Anticonvulsant rash can be severe (SJS/TEN). Keep severe cutaneous reactions out of this key?

### `extrapyramidal_symptoms`
- PIPC rows: 17, 18, 19, 37, 46; phrasings: Extrapyramidal symptoms
- Index classes: Antidopaminergic antiemetic; Antipsychotic; Lithium
- Label (en): Stiffness, slowed or abnormal movements (extrapyramidal symptoms)

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Extrapyramidal disorder | 554 | 540 | |
| core | Parkinsonism | 753 | 534 | |
| core | Dystonia | 863 | 792 | |
| core | Cogwheel rigidity | 56 | 53 | |
| borderline, not in CSV | Bradykinesia | 659 | 579 | a parkinsonian sign; include? |
| borderline, not in CSV | Dyskinesia | 2,721 | 2,276 | belongs to the akathisia/tardive key |
| borderline, not in CSV | Parkinsonism hyperpyrexia syndrome | 7 | 7 | rare, severe |

### `akathisia_tardive_movements`
- PIPC rows: 20; phrasings: Akathisia or tardive movements
- Index classes: Antipsychotic
- Label (en): Inner restlessness or involuntary movements (akathisia, tardive dyskinesia)

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Akathisia | 756 | 676 | |
| core | Tardive dyskinesia | 638 | 507 | |
| core | Tardive akathisia | 21 | 21 | |
| borderline, not in CSV | Dyskinesia | 2,721 | 2,276 | 2,721 reports, many not drug-induced tardive |

### `arrhythmia`
- PIPC rows: 21, 63; phrasings: Arrhythmia
- Index classes: Antipsychotic; Erythromycin
- Label (en): Irregular heartbeat (arrhythmia)

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Arrhythmia | 2,432 | 2,187 | |
| core | Arrhythmia supraventricular | 27 | 26 | |
| core | Ventricular tachyarrhythmia | 17 | 17 | |
| core (added by review) | Ventricular arrhythmia | 199 | 192 | |
| core (added by review) | Tachyarrhythmia | 111 | 108 | |
| core (added by review) | Supraventricular tachyarrhythmia | 10 | 10 | |
| core (added by review) | Torsade de pointes | 495 | 494 | |
| borderline, not in CSV | Electrocardiogram QT prolonged | 2,549 | 2,477 | the usual form of the antipsychotic/erythromycin concern |
| borderline, not in CSV | Torsade de pointes | 495 | 494 | the arrhythmia of QT prolongation |
| borderline, not in CSV | Long QT syndrome | 115 | 114 |  |
| borderline, not in CSV | Ventricular tachycardia | 1,045 | 992 |  |
| borderline, not in CSV | Ventricular fibrillation | 689 | 665 |  |
| borderline, not in CSV | Supraventricular tachycardia | 556 | 499 |  |
| borderline, not in CSV | Atrial fibrillation | 6,155 | 5,319 | very common, mostly unrelated |

**Question:** Rows 21 and 63 are about QT-related arrhythmia. Which of the QT/torsade/tachycardia PTs belong?

### `hyperglycaemia`
- PIPC rows: 22; phrasings: Hyperglycemia
- Index classes: Antipsychotic
- Label (en): High blood sugar

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Hyperglycaemia | 2,393 | 2,184 | |
| core | Blood glucose increased | 8,891 | 8,164 | |
| borderline, not in CSV | Diabetes mellitus inadequate control | 1,147 | 1,095 | worsening of known diabetes |
| borderline, not in CSV | Hyperglycaemic hyperosmolar nonketotic syndrome | 100 | 95 | emergency, narrower |

### `cognitive_impairment`
- PIPC rows: 23, 33; phrasings: Cognitive Impairment; Cognitive impairment
- Index classes: Benzodiazepine; Tricyclic antidepressant
- Label (en): Memory or thinking problems

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Cognitive disorder | 3,461 | 3,071 | |
| core | Memory impairment | 8,566 | 7,331 | |
| core | Amnesia | 3,455 | 3,157 | |
| borderline, not in CSV | Confusional state | 9,480 | 8,620 | acute confusion (delirium-like), 9,480 reports; include? |
| borderline, not in CSV | Dementia | 2,492 | 2,178 | the indication of the cholinesterase inhibitor in rows 23 and 33: confounding by indication |
| borderline, not in CSV | Dementia Alzheimer's type | 744 | 617 | same |

**Question:** Dementia PTs are left out because the marker drug (cholinesterase inhibitor) treats dementia. Agree?

### `gastrointestinal_upset`
- PIPC rows: 26, 27; phrasings: Gastrointestinal upset
- Index classes: Cholinesterase inhibitor
- Label (en): Indigestion or stomach discomfort

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Gastrointestinal disorder | 10,798 | 9,222 | |
| core | Dyspepsia | 8,216 | 7,291 | |
| core | Abdominal discomfort | 13,699 | 11,605 | |
| borderline, not in CSV | Abdominal pain | 18,588 | 16,168 | 18,588 reports; broad |
| borderline, not in CSV | Abdominal pain upper | 16,497 | 14,146 | 16,497 reports; broad |
| borderline, not in CSV | Gastrointestinal pain | 1,009 | 877 |  |

### `diarrhoea`
- PIPC rows: 28, 42, 47; phrasings: Diarrhea
- Index classes: Cholinesterase inhibitor; Laxative; Metformin
- Label (en): Diarrhoea

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Diarrhoea | 54,376 | 45,809 | |
| borderline, not in CSV | Frequent bowel movements | 3,210 | 2,731 | close |
| borderline, not in CSV | Diarrhoea haemorrhagic | 577 | 484 | severe form |

### `rhinorrhoea`
- PIPC rows: 29; phrasings: Rhinorrhea
- Index classes: Cholinesterase inhibitor
- Label (en): Runny nose

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Rhinorrhoea | 5,760 | 5,148 | |
| borderline, not in CSV | Nasal congestion | 5,566 | 5,059 | blocked nose, opposite symptom |

### `psychosis_hallucinations`
- PIPC rows: 30, 60; phrasings: Psychosis; Psychotic symptoms, hallucinations
- Index classes: Corticosteroid; Dopaminergic Antiparkinsonian agent
- Label (en): Hallucinations, delusions or other psychotic symptoms

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Hallucination | 6,308 | 5,876 | |
| core | Hallucination, visual | 1,843 | 1,735 | |
| core | Hallucination, auditory | 1,006 | 954 | |
| core | Hallucinations, mixed | 260 | 247 | |
| core | Hallucination, tactile | 62 | 60 | |
| core | Hallucination, olfactory | 39 | 36 | |
| core | Psychotic disorder | 1,708 | 1,590 | |
| core | Psychotic symptom | 202 | 198 | |
| core | Psychotic behaviour | 42 | 40 | |
| core (added by review) | Delusion | 1,137 | 1,074 | |
| borderline, not in CSV | Delusion | 1,137 | 1,074 | a psychotic symptom, 1,137 reports |
| borderline, not in CSV | Delusional disorder, unspecified type | 40 | 34 | a diagnosis |

**Question:** Rows 30 and 60 are 'psychotic symptoms, hallucinations' and 'psychosis'. Keep one key?

### `tremor`
- PIPC rows: 39; phrasings: Tremor
- Index classes: Venlafaxine
- Label (en): Tremor

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Tremor | 9,605 | 8,405 | |
| borderline, not in CSV | Essential tremor | 92 | 79 | a disease, not a drug effect |

### `joint_pain`
- PIPC rows: 40; phrasings: Joint pain
- Index classes: Dipeptidyl peptidase 4 (DPP-4) inhibitor (e.g., sitagliptin,
- Label (en): Joint pain

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Arthralgia | 35,469 | 29,889 | |
| borderline, not in CSV | Joint swelling | 9,459 | 8,420 | different |
| borderline, not in CSV | Joint stiffness | 1,881 | 1,598 | different |

### `genital_fungal_infection`
- PIPC rows: 41, 62; phrasings: Mycotic genital infections; Vulvo-vaginal candidiasis
- Index classes: Acitretin; Sodium-glucose cotransporter-2 (SGLT-2) inhibitor
- Label (en): Genital yeast infection (thrush)

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Vulvovaginal candidiasis | 136 | 102 | |
| core | Vulvovaginal mycotic infection | 217 | 158 | |
| core | Genital infection fungal | 40 | 35 | |
| core | Balanitis candida | 22 | 21 | |
| core (added by review) | Genital candidiasis | 35 | 32 | |
| borderline, not in CSV | Candida infection | 1,925 | 1,507 | site not given |
| borderline, not in CSV | Vulvovaginal pruritus | 444 | 393 | a symptom |
| borderline, not in CSV | Vulvovaginal burning sensation | 571 | 549 | a symptom |
| borderline, not in CSV | Vulvovaginal discomfort | 333 | 292 | a symptom |
| borderline, not in CSV | Balanoposthitis | 104 | 94 | moved from core by the review: does not say fungal; usual male presentation on an SGLT-2 inhibitor, about a fifth of the key (owner decides) |

**Question:** Rows 41 (SGLT-2 'mycotic genital infections') and 62 (acitretin 'vulvo-vaginal candidiasis') share one key. OK?

### `urinary_retention`
- PIPC rows: 45; phrasings: Urinary retention
- Index classes: Anticholinergic antiemetic
- Label (en): Difficulty passing urine (urinary retention)

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Urinary retention | 2,355 | 2,054 | |
| borderline, not in CSV | Urinary hesitation | 113 | 100 | milder form |
| borderline, not in CSV | Urinary retention postoperative | 9 | 8 | procedure-related |

### `osteoporosis_fracture`
- PIPC rows: 48; phrasings: Osteoporosis, fractures
- Index classes: Proton pump inhibitor
- Label (en): Weaker bones (osteoporosis)

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Osteoporosis | 2,485 | 2,281 | |
| core | Osteopenia | 689 | 651 | |
| core | Bone density decreased | 1,043 | 941 | |
| core | Osteoporotic fracture | 150 | 141 | |
| core (added by review) | Osteoporosis postmenopausal | 20 | 17 | |
| core (added by review) | Senile osteoporosis | 9 | 7 | |
| borderline, not in CSV | Hip fracture | 2,340 | 1,768 | 2,340 reports; fractures of every site are mostly traumatic |
| borderline, not in CSV | Fracture | 1,187 | 922 |  |
| borderline, not in CSV | Femur fracture | 1,587 | 1,231 |  |
| borderline, not in CSV | Spinal fracture | 1,739 | 1,378 |  |
| borderline, not in CSV | Compression fracture | 1,005 | 852 | often osteoporotic |

**Question:** PIPC row 48 reads 'Osteoporosis, fractures'. Are site-specific fracture PTs in or out? (They are mostly trauma.)

### `vitamin_mineral_deficiency`
- PIPC rows: 49; phrasings: Vitamin or Mineral Deficiency
- Index classes: Proton pump inhibitor
- Label (en): Low vitamin B12, magnesium or iron

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Vitamin B12 deficiency | 395 | 374 | |
| core | Vitamin B12 decreased | 295 | 272 | |
| core | Hypomagnesaemia | 1,129 | 1,103 | |
| core | Magnesium deficiency | 63 | 62 | |
| core | Blood magnesium decreased | 675 | 573 | |
| core | Iron deficiency | 547 | 494 | |
| core | Iron deficiency anaemia | 767 | 691 | |
| borderline, not in CSV | Vitamin D deficiency | 718 | 679 | outside the narrowing of row 49 (cascade-engine review: B12, magnesium, oral iron) |
| borderline, not in CSV | Folate deficiency | 128 | 124 | same |

**Question:** The cascade-engine review narrowed row 49 to B12, magnesium and iron; the PT list follows that.

### `gastritis`
- PIPC rows: 50; phrasings: Gastritis
- Index classes: Bisphosphonate
- Label (en): Stomach lining inflammation (gastritis)

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Gastritis | 1,738 | 1,582 | |
| core | Gastritis erosive | 249 | 239 | |
| core | Gastritis haemorrhagic | 63 | 62 | |
| borderline, not in CSV | Oesophagitis | 776 | 716 | the usual bisphosphonate problem, but PIPC says gastritis |

### `gastric_ulcer_bleed`
- PIPC rows: 51; phrasings: Gastritis/gastric ulcer/gastrointestinal bleed
- Index classes: Nonsteroidal anti-inflammatory drug (NSAID)
- Label (en): Stomach ulcer or bleeding in the stomach or bowel

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Gastritis | 1,738 | 1,582 | |
| core | Gastritis erosive | 249 | 239 | |
| core | Gastritis haemorrhagic | 63 | 62 | |
| core | Gastric ulcer | 1,024 | 911 | |
| core | Gastric ulcer haemorrhage | 187 | 172 | |
| core | Gastric haemorrhage | 421 | 337 | |
| core | Gastrointestinal haemorrhage | 3,149 | 2,739 | |
| core | Upper gastrointestinal haemorrhage | 738 | 709 | |
| core | Peptic ulcer | 181 | 166 | |
| core | Peptic ulcer haemorrhage | 39 | 39 | |
| core | Duodenal ulcer | 473 | 455 | |
| core | Duodenal ulcer haemorrhage | 151 | 146 | |
| core (added by review) | Haematemesis | 1,323 | 1,197 | |
| core (added by review) | Melaena | 1,052 | 974 | |
| borderline, not in CSV | Melaena | 1,052 | 974 | a sign of upper GI bleeding |
| borderline, not in CSV | Lower gastrointestinal haemorrhage | 273 | 259 | not gastric |
| borderline, not in CSV | Duodenal ulcer perforation | 1,383 | 1,378 | 1,383 reports; perforation not bleeding |

**Question:** Row 51 names 'gastritis/gastric ulcer/gastrointestinal bleed', so the Gastritis PTs are repeated here (a PT may sit in two keys).

### `heart_failure`
- PIPC rows: 44, 54; phrasings: Heart failure; Worsening of heart failure
- Index classes: NSAID; Rosiglitazone
- Label (en): Heart failure

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Cardiac failure | 5,082 | 4,482 | |
| core | Cardiac failure congestive | 1,885 | 1,635 | |
| core | Cardiac failure acute | 504 | 476 | |
| core | Cardiac failure chronic | 280 | 256 | |
| core (added by review) | Heart failure with reduced ejection fraction | 253 | 240 | |
| core (added by review) | Heart failure with preserved ejection fraction | 129 | 123 | |
| core (added by review) | Heart failure with midrange ejection fraction | 13 | 13 | |
| core (added by review) | Left ventricular failure | 212 | 204 | |
| core (added by review) | Right ventricular failure | 271 | 266 | |
| borderline, not in CSV | Pulmonary oedema | 2,689 | 2,371 | a consequence; also common in other conditions |

### `dry_mouth`
- PIPC rows: 57; phrasings: Dry mouth
- Index classes: Urinary anticholinergic
- Label (en): Dry mouth

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Dry mouth | 6,200 | 5,398 | |
| borderline, not in CSV | Dry throat | 749 | 677 |  |

### `seizures`
- PIPC rows: 58; phrasings: Seizures
- Index classes: Carbapenem (e.g., imipenem, meropenem, ertapenem)
- Label (en): Seizures (fits)

| Proposed | PT | Reports | Mapped | Note |
|---|---|---:|---:|---|
| core | Seizure | 11,674 | 10,079 | |
| core | Seizure cluster | 210 | 195 | |
| core | Generalised tonic-clonic seizure | 1,683 | 1,619 | |
| core | Convulsions local | 12 | 11 | |
| core (added by review) | Partial seizures | 510 | 479 | |
| core (added by review) | Tonic convulsion | 141 | 134 | |
| core (added by review) | Clonic convulsion | 45 | 45 | |
| borderline, not in CSV | Epilepsy | 2,582 | 2,390 | a disease; the marker drug treats it |
| borderline, not in CSV | Status epilepticus | 814 | 780 | emergency, narrower |

**Question:** Epilepsy PTs left out: the marker drug (anticonvulsant) treats epilepsy. Agree?

## 3. Benefit keys

| Key | Label (en) | Placeholder? |
|---|---|---|
| `improvement_pain` | Less pain | yes |
| `improvement_sleep` | Better sleep | yes |
| `improvement_mood` | Better mood | new proposal |
| `improvement_nausea` | Less nausea | new proposal |
| `improvement_swelling` | Less swelling | new proposal |

## 4. Owner decisions

*(To be filled in at the review stop: per key accept / change PT list / drop; the seven open points of section 1; labels; benefit keys; then switch `status` to `active`.)*
