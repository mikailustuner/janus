# Mapping review: PIPC rows to ATC classes

> Review sheet for the owner (cascade-engine task 4, review stop in task 5). Drafted by the
> pharmacologist agent on 2026-11-07. Files: `data/cascade_classes.csv`, `data/pipc_rules.csv`,
> `data/cascade_priority.csv`, `data/abrupt_stop_classes.csv`.
>
> **Review status.** The mapping was reviewed on 2026-11-07 by the project owner with AI
> assistance; the owner's decisions are in section 6 and have been applied to the files. It
> **still needs a review by a pharmacist or physician before any public claim** is made about it.
>
> Validator (`build_rule_base`) result after the owner's decisions: rule base version
> `590f454d7ce4dcdd6af28b97b2d767f6d808a8d0209088cca3ee0a640f9cd075`, 66 classes, 202 pattern
> rows, 2 rules not matchable (rows 27 and 57, marker role). The first draft had version
> `cd71f267…ccbd`.

## 1. How the mapping was derived

- **One class per PIPC class and role.** Each distinct Drug A or Drug B text got one class. Texts
  that PIPC repeats ("Antiemetic", "Antihypertensive", "Diuretic", "Laxative", "Sleep agent",
  "Overactive bladder medication") use one class across their rows. Where the index and marker
  meanings are the same (antihypertensive, diuretic, anticonvulsant, antipsychotic,
  benzodiazepine, cholinesterase inhibitor, laxative, alpha-1 blocker) one class serves both roles.
  Classes differ where the role changes what belongs in them: `nsaid` (index, systemic only) and
  `nsaid_marker` (adds topical NSAIDs); `beta_blocker_index_eye` (row 3, with the eye-drop
  extension), `beta_blocker_index` (row 4, no extension: owner decision) and `beta_blocker_marker` (row 17).
- **Index classes** hold the systemic forms that cause the adverse event. **Marker classes** hold
  the forms used to treat it, including topical, vaginal and over-the-counter products (laxatives,
  analgesics, antihistamines, antidiarrhoeals, antacids, cough remedies, sleep aids).
- **Codes.** Class-level groups come from pharmacological knowledge of the ATC structure
  (`basis = pharmacology`). Every single code was checked by hand on the public WHOCC ATC/DDD
  index page of its group (`whocc_lookup`; URL and date in each note; index last updated
  2026-01-20; one page per group, fetched one at a time, nothing copied). In the draft, 39 rows
  (28 codes) had been taken from the local Wikidata extract (`wikidata`); at the owner's request
  they were checked on 17 more WHOCC pages on 2026-11-07, all 28 codes were confirmed for the
  intended substance, and their basis is now `whocc_lookup`. Two codes rest on what the TİTCK list publishes (`titck_observed`, counts only). No WHO
  index text, TİTCK product name or ingredient string is in any file.
- **Longest-prefix matching** (design DP3) is used to drop sub-groups that do not belong (for
  example M01AX, which mixes NSAIDs with glucosamine and chondroitin) and add back single codes.
- **Combination codes** never appear as patterns; the loader refuses them. Where a class covers a
  combination group (C09, C07, A10, N04), the engine still only sees the decomposed ingredients.
- **Form extension** (design DP8): only ophthalmic beta-blockers (`S01ED`) on row 3, cited to
  Vander Zanden 2001. Row 4 has none (owner decision, section 6).
- **ThinkCascades**: the overlap rows (5, 8, 18, 23, 53, 56) were checked against the article's
  table of retained cascades on PMC9477172 (read only, nothing copied). All six describe the same
  cascade as the PIPC row and carry `paper:thinkcascades:drugs_aging_2022`.
- **BMJ 2026** data: the six rows the abstract names with a number (9, 25, 26, 47, 60, 65), with
  the measure and 95% CI as published. Row 32 is named only for a sex difference and has none.

## 2. Rules

| Row | Drug A (as published) | Adverse event | Drug B (as published) | Index class | Marker class | Form extension | BMJ 2026 data | Supporting id |
|---|---|---|---|---|---|---|---|---|
| 1 | Angiotensin converting enzyme inhibitor | Cough | Cough remedy | `ace_inhibitor` | `cough_remedy` |  |  |  |
| 2 | Antihypertensive | Orthostatic hypotension/dizziness | Antiemetic | `antihypertensive` | `antiemetic` |  |  |  |
| 3 | Beta-blocker (particularly lipophilic e.g., propranolol) | Depression | Antidepressant | `beta_blocker_index_eye` | `antidepressant` | S01ED |  |  |
| 4 | Beta-blocker (particularly lipophilic e.g., propranolol) | Erectile dysfunction | Phosphodiesterase-5 inhibitor, alprostadil | `beta_blocker_index` | `pde5_inhibitor_alprostadil` | none (owner decision) |  |  |
| 5 | Calcium channel blocker | Peripheral edema | Diuretic | `ccb` | `diuretic` |  |  | ThinkCascades |
| 6 | Calcium channel blocker | Constipation | Laxative | `ccb` | `laxative` |  |  |  |
| 7 | Diuretic | Gout or Hyperuricemia | Anti-gout agent | `diuretic` | `antigout` |  |  |  |
| 8 | Diuretic | Urinary incontinence | Overactive bladder medication | `diuretic` | `oab_medication` |  |  | ThinkCascades |
| 9 | Hydroxymethylglutaryl-coenzyme A (HMG Co-A) reductase inhibitor (statin) | Myalgia/myositis | Pain reliever | `statin` | `pain_reliever` |  | incidence 10.9 % (10.7-11.0) |  |
| 10 | HMG Co-A reductase inhibitor | Myalgia/myositis | Mineral supplement | `statin` | `mineral_supplement` |  |  |  |
| 11 | HMG Co-A reductase inhibitor | Myalgia/myositis | Quinine sulfate | `statin` | `quinine` |  |  |  |
| 12 | HMG Co-A reductase inhibitor | Insomnia | Sleep agent | `statin` | `sleep_agent` |  |  |  |
| 13 | Digoxin | Nausea | Antiemetic | `digoxin` | `antiemetic` |  |  |  |
| 14 | Midodrine | Hypertension | Antihypertensive | `midodrine` | `antihypertensive` |  |  |  |
| 15 | Anticonvulsant | Rash | Topical corticosteroid | `anticonvulsant` | `topical_corticosteroid` |  |  |  |
| 16 | Anticonvulsant | Nausea | Antiemetic | `anticonvulsant` | `antiemetic` |  |  |  |
| 17 | Antipsychotic | Extrapyramidal symptoms | Beta-blocker | `antipsychotic` | `beta_blocker_marker` |  |  |  |
| 18 | Antipsychotic | Extrapyramidal symptoms | Antiparkinsonian agent | `antipsychotic` | `antiparkinsonian` |  |  | ThinkCascades |
| 19 | Antipsychotic | Extrapyramidal symptoms | Anti-tremor antimuscarinic | `antipsychotic` | `antimuscarinic_antiparkinsonian` |  |  |  |
| 20 | Antipsychotic | Akathisia or tardive movements | Sedative | `antipsychotic` | `sedative` |  |  |  |
| 21 | Antipsychotic | Arrhythmia | Antiarrhythmic | `antipsychotic` | `antiarrhythmic` |  |  |  |
| 22 | Antipsychotic | Hyperglycemia | Antihyperglycemic | `antipsychotic` | `antihyperglycemic` |  |  |  |
| 23 | Benzodiazepine | Cognitive impairment | Cholinesterase Inhibitor | `benzodiazepine` | `cholinesterase_inhibitor` |  |  | ThinkCascades |
| 24 | Cholinesterase inhibitor | Urinary incontinence | Overactive bladder medication | `cholinesterase_inhibitor` | `oab_medication` |  |  |  |
| 25 | Cholinesterase inhibitor | Insomnia | Sleep agent | `cholinesterase_inhibitor` | `sleep_agent` |  | incidence 10.3 % (9.9-10.7) |  |
| 26 | Cholinesterase inhibitor | Gastrointestinal upset | Antiemetic | `cholinesterase_inhibitor` | `antiemetic` |  | adj. sequence ratio 2.24 (1.90-2.65) |  |
| 27 | Cholinesterase inhibitor | Gastrointestinal upset | Bismuth subsalicylate | `cholinesterase_inhibitor` | not matchable (no_atc_code) |  |  |  |
| 28 | Cholinesterase inhibitor | Diarrhea | Antidiarrheal | `cholinesterase_inhibitor` | `antidiarrheal` |  |  |  |
| 29 | Cholinesterase inhibitor | Rhinorrhea | Antihistamine | `cholinesterase_inhibitor` | `antihistamine` |  |  |  |
| 30 | Dopaminergic Antiparkinsonian agent | Psychotic symptoms, hallucinations | Antipsychotic | `dopaminergic_antiparkinsonian` | `antipsychotic` |  |  |  |
| 31 | Gabapentinoid | Peripheral edema | Diuretic | `gabapentinoid` | `diuretic` |  |  |  |
| 32 | Selective serotonin reuptake inhibitor/Serotonin and norepinephrine reuptake inhibitor (SSRI/SNRI) | Urinary Incontinence | Overactive bladder medication | `ssri_snri` | `oab_medication` |  |  |  |
| 33 | Tricyclic antidepressant | Cognitive Impairment | Cholinesterase Inhibitor | `tricyclic_antidepressant` | `cholinesterase_inhibitor` |  |  |  |
| 34 | Tricyclic antidepressant | Constipation | Laxative | `tricyclic_antidepressant` | `laxative` |  |  |  |
| 35 | Tricyclic antidepressant | Urinary incontinence | Overactive bladder medication | `tricyclic_antidepressant` | `oab_medication` |  |  |  |
| 36 | Flunarizine | Depression | Antidepressant | `flunarizine` | `antidepressant` |  |  |  |
| 37 | Lithium | Extrapyramidal symptoms | Antiparkinsonian agent | `lithium` | `antiparkinsonian` |  |  |  |
| 38 | Venlafaxine | Hypertension (dose-related) | Antihypertensive | `venlafaxine` | `antihypertensive` |  |  |  |
| 39 | Venlafaxine | Tremor | Benzodiazepine | `venlafaxine` | `benzodiazepine` |  |  |  |
| 40 | Dipeptidyl peptidase 4 (DPP-4) inhibitor (e.g., sitagliptin, saxagliptin) | Joint pain | Nonsteroidal anti-inflammatory drug | `dpp4_inhibitor` | `nsaid_marker` |  |  |  |
| 41 | Sodium-glucose cotransporter-2 (SGLT-2) inhibitor | Mycotic genital infections | Antifungal | `sglt2_inhibitor` | `antifungal_genital` |  |  |  |
| 42 | Metformin | Diarrhea | Antidiarrheal | `metformin` | `antidiarrheal` |  |  |  |
| 43 | Pioglitazone or Rosiglitazone | Edema | Diuretic | `pioglitazone_rosiglitazone` | `diuretic` |  |  |  |
| 44 | Rosiglitazone | Heart failure | Diuretic | `rosiglitazone` | `diuretic` |  |  |  |
| 45 | Anticholinergic antiemetic | Urinary retention | Alpha-1 receptor blocker | `anticholinergic_antiemetic` | `alpha1_blocker` |  |  |  |
| 46 | Antidopaminergic antiemetic | Extrapyramidal symptoms | Antiparkinsonian agent | `antidopaminergic_antiemetic` | `antiparkinsonian` |  |  |  |
| 47 | Laxative | Diarrhea | Antidiarrheal agent | `laxative` | `antidiarrheal` |  | adj. sequence ratio 2.53 (2.43-2.65) |  |
| 48 | Proton pump inhibitor | Osteoporosis, fractures | Vitamin supplement | `ppi` | `vitamin_supplement` |  |  |  |
| 49 | Proton pump inhibitor | Vitamin or Mineral Deficiency | Vitamin or Mineral Deficiency | `ppi` | `ppi_deficiency_supplement` |  |  |  |
| 50 | Bisphosphonate | Gastritis | Gastroprotective agent | `bisphosphonate` | `gastroprotective` |  |  |  |
| 51 | Nonsteroidal anti-inflammatory drug (NSAID) | Gastritis/gastric ulcer/gastrointestinal bleed | Gastroprotective agent | `nsaid` | `gastroprotective` |  |  |  |
| 52 | NSAID | Nausea | Antiemetic | `nsaid` | `antiemetic` |  |  |  |
| 53 | NSAID | Hypertension | Antihypertensive | `nsaid` | `antihypertensive` |  |  | ThinkCascades |
| 54 | NSAID | Worsening of heart failure | Heart failure agent | `nsaid` | `heart_failure_agent` |  |  |  |
| 55 | Opioid | Depression | Antidepressant | `opioid` | `antidepressant` |  |  |  |
| 56 | Alpha-1 receptor blocker | Orthostatic hypotension, dizziness | Vestibular suppressant | `alpha1_blocker` | `vestibular_suppressant` |  |  | ThinkCascades |
| 57 | Urinary anticholinergic | Dry mouth | Saliva substitute | `urinary_anticholinergic` | not matchable (no_atc_code) |  |  |  |
| 58 | Carbapenem (e.g., imipenem, meropenem, ertapenem) | Seizures | Anticonvulsant | `carbapenem` | `anticonvulsant` |  |  |  |
| 59 | Corticosteroid | Insomnia | Sleep agent | `corticosteroid_systemic` | `sleep_agent` |  |  |  |
| 60 | Corticosteroid | Psychosis | Antipsychotic | `corticosteroid_systemic` | `antipsychotic` |  | adj. sequence ratio 2.55 (2.47-2.64) |  |
| 61 | Corticosteroid | Hypertension | Antihypertensive | `corticosteroid_systemic` | `antihypertensive` |  |  |  |
| 62 | Acitretin | Vulvo-vaginal candidiasis | Antifungal | `acitretin` | `antifungal_genital` |  |  |  |
| 63 | Erythromycin | Arrhythmia | Antiarrhythmic | `erythromycin` | `antiarrhythmic` |  |  |  |
| 64 | Fludrocortisone | Hypertension | Antihypertensive | `fludrocortisone` | `antihypertensive` |  |  |  |
| 65 | Iron supplement | Constipation | Laxative | `iron_oral` | `laxative` |  | incidence 11.9 % (11.7-12.1) |  |

## 3. Classes

Notes are Janus's own words. In this sheet the WHOCC URL sentence is shortened to "WHOCC page
checked"; the CSV holds the full URL.

### `ace_inhibitor`

Used by rows: 1 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C09A` | include | pipc | pharmacology | Row 1 index. All plain ACE inhibitors (captopril, enalapril, lisinopril, perindopril, ramipril and the rest); they exist only as systemic forms. Fixed combinations (C09B) are refused by the loader; their ingredients reach the engine after decomposition. |

### `acitretin`

Used by rows: 62 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `D05BB02` | include | pipc | whocc_lookup | Row 62 index, individual drug: acitretin (oral retinoid). WHOCC page checked 2026-11-07. |

### `alpha1_blocker`

Used by rows: 45 (marker), 56 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C02CA` | include | pipc | pharmacology | Alpha-1 blockers coded as antihypertensives (doxazosin, prazosin, urapidil); doxazosin is widely used for prostate symptoms and causes the same orthostatic hypotension. |
| `G04CA` | include | pipc | pharmacology | Rows 56 (index, orthostatic hypotension) and 45 (marker, urinary retention). Tamsulosin, alfuzosin, silodosin, terazosin. One class for both roles. Combinations with dutasteride or tolterodine never reach the engine. |

### `antiarrhythmic`

Used by rows: 21, 63 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C01B` | include | pipc | pharmacology | Rows 21, 63 marker. Class I and III antiarrhythmics (amiodarone, dronedarone, flecainide, propafenone and others). Beta-blockers, verapamil, diltiazem and digoxin are left out: they are mostly started for blood pressure, angina or rate control (judgement call, listed for review). |
| `C07AA07` | include | pipc | whocc_lookup | Sotalol, a beta-blocker used almost only as a class III antiarrhythmic. WHOCC page checked 2026-11-07. |

### `anticholinergic_antiemetic`

Used by rows: 45 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A04AD01` | include | pipc | whocc_lookup | Row 45 index (urinary retention). Antiemetics with marked anticholinergic action. Scopolamine (hyoscine), including patches (the route map keeps A04 for transdermal products). Butylscopolamine (A03BB01) is an antispasmodic, not an antiemetic, and is left out. WHOCC page checked 2026-11-07. |
| `R06AA11` | include | pipc | whocc_lookup | Row 45 index (urinary retention). Antiemetics with marked anticholinergic action. Dimenhydrinate. WHOCC page checked 2026-11-07. |
| `R06AD02` | include | pipc | whocc_lookup | Row 45 index (urinary retention). Antiemetics with marked anticholinergic action. Promethazine. WHOCC page checked 2026-11-07. |
| `R06AE03` | include | pipc | whocc_lookup | Row 45 index (urinary retention). Antiemetics with marked anticholinergic action. Cyclizine. WHOCC page checked 2026-11-07. |
| `R06AE05` | include | pipc | whocc_lookup | Row 45 index (urinary retention). Antiemetics with marked anticholinergic action. Meclizine (meclozine). WHOCC page checked 2026-11-07. |

### `anticonvulsant`

Used by rows: 15, 16 (index), 58 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N03A` | include | pipc | pharmacology | Rows 15, 16 (index) and 58 (marker). All antiepileptics: rash mostly with the aromatic ones (carbamazepine, oxcarbazepine, phenytoin, lamotrigine, phenobarbital), nausea with many. One class for both roles. As marker (seizures after a carbapenem) it includes clonazepam (N03AE01) but not the benzodiazepines given acutely for a seizure (diazepam, lorazepam, midazolam), because they are in other groups and mostly given in hospital. |
| `N03AX12` | exclude | pipc | whocc_lookup | Old gabapentin code: no longer on the WHOCC page (gabapentinoids are now in N02BF), but TİTCK still publishes it (44 rows). Excluded so that a gabapentin product from Türkiye and one from the US behave the same; gabapentinoids are PIPC's own class (row 31). WHOCC page checked 2026-11-07. |
| `N03AX16` | exclude | pipc | whocc_lookup | Old pregabalin code: no longer on the WHOCC page (now N02BF02), but TİTCK still publishes it (162 rows). Excluded for the same reason as N03AX12. WHOCC page checked 2026-11-07. |

### `antidepressant`

Used by rows: 3, 36, 55 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N06A` | include | pipc | pharmacology | Rows 3, 36, 55 marker. All antidepressants: SSRIs, SNRIs, tricyclics, MAO inhibitors, mirtazapine, trazodone, bupropion (same code when used for smoking cessation), agomelatine, vortioxetine, esketamine and St John's wort (sold over the counter in Germany). Lithium is coded elsewhere (N05AN) and is not included. Combinations with antipsychotics (N06C) never reach the engine. |

### `antidiarrheal`

Used by rows: 28, 42, 47 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A07B` | include | pipc | pharmacology | Rows 28, 42 and 47 marker (row 47 writes 'Antidiarrheal agent', rows 28 and 42 'Antidiarrheal'; same class). Adsorbents: charcoal, bismuth preparations, kaolin, pectin, attapulgite, diosmectite; mostly over the counter. |
| `A07D` | include | pipc | pharmacology | Rows 28, 42 and 47 marker (row 47 writes 'Antidiarrheal agent', rows 28 and 42 'Antidiarrheal'; same class). Antipropulsives: loperamide, diphenoxylate, opium, eluxadoline. |
| `A07XA` | include | pipc | pharmacology | Rows 28, 42 and 47 marker (row 47 writes 'Antidiarrheal agent', rows 28 and 42 'Antidiarrheal'; same class). Other antidiarrhoeals: racecadotril, albumin tannate, carob, crofelemer. Probiotics (A07FA) and gut anti-infectives (nifuroxazide, rifaximin) are left out (judgement call, listed for review). |

### `antidopaminergic_antiemetic`

Used by rows: 46 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A03FA01` | include | pipc | whocc_lookup | Row 46 index (extrapyramidal symptoms). Dopamine-blocking antiemetics. Metoclopramide. Left out: promethazine (weak dopamine block; owner question), droperidol and amisulpride injections (hospital use), itopride and cinitapride (prokinetics for dyspepsia). WHOCC page checked 2026-11-07. |
| `A03FA03` | include | pipc | whocc_lookup | Row 46 index (extrapyramidal symptoms). Dopamine-blocking antiemetics. Domperidone: acts mostly outside the brain, extrapyramidal effects are uncommon but reported; kept (judgement call). WHOCC page checked 2026-11-07. |
| `A03FA04` | include | pipc | whocc_lookup | Row 46 index (extrapyramidal symptoms). Dopamine-blocking antiemetics. Bromopride. WHOCC page checked 2026-11-07. |
| `A03FA05` | include | pipc | whocc_lookup | Row 46 index (extrapyramidal symptoms). Dopamine-blocking antiemetics. Alizapride. WHOCC page checked 2026-11-07. |
| `A03FA06` | include | pipc | whocc_lookup | Row 46 index (extrapyramidal symptoms). Dopamine-blocking antiemetics. Clebopride. WHOCC page checked 2026-11-07. |
| `A04AD05` | include | pipc | whocc_lookup | Row 46 index (extrapyramidal symptoms). Dopamine-blocking antiemetics. Metopimazine. WHOCC page checked 2026-11-07. |
| `N05AB04` | include | pipc | whocc_lookup | Row 46 index (extrapyramidal symptoms). Dopamine-blocking antiemetics. Prochlorperazine, mostly used as an antiemetic in older adults; it is also in the antipsychotic class. WHOCC page checked 2026-11-07. |

### `antiemetic`

Used by rows: 2, 13, 16, 26, 52 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A03FA` | include | pipc | whocc_lookup | Dopamine-blocking prokinetics (metoclopramide, domperidone and others), the most used antiemetics in Türkiye and much of the EU. The few dyspepsia prokinetics in the group (itopride, cinitapride) are kept: rarely prescribed, same group. WHOCC page checked 2026-11-07. |
| `A04A` | include | pipc | pharmacology | Rows 2, 13, 16, 26, 52 marker; one definition for all five. 5-HT3 and NK1 antagonists, scopolamine patches, cannabinoids and other antiemetics. |
| `N05AB04` | include | pipc | whocc_lookup | Prochlorperazine, used mainly as an antiemetic in older adults. WHOCC page checked 2026-11-07. |
| `R06AA10` | include | pipc | whocc_lookup | Trimethobenzamide, an antiemetic coded with the antihistamines (8 TİTCK rows). WHOCC page checked 2026-11-07. |
| `R06AA11` | include | pipc | whocc_lookup | Dimenhydrinate, over the counter for nausea. WHOCC page checked 2026-11-07. |
| `R06AD02` | include | pipc | whocc_lookup | Promethazine, commonly prescribed for nausea in the US. WHOCC page checked 2026-11-07. |
| `R06AE03` | include | pipc | whocc_lookup | Cyclizine, used for nausea. WHOCC page checked 2026-11-07. |
| `R06AE05` | include | pipc | whocc_lookup | Meclizine (meclozine), over the counter for nausea and motion sickness. WHOCC page checked 2026-11-07. |

### `antifungal_genital`

Used by rows: 41, 62 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `D01AC` | include | pipc | pharmacology | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Skin imidazole and triazole creams (clotrimazole, miconazole), the usual treatment of genital candidiasis in men (balanitis) on an SGLT-2 inhibitor. Also used for athlete's foot, so unrelated matches are possible (judgement call, listed for review). Systemic skin antifungals (D01B: terbinafine, griseofulvin) are left out because they do not treat Candida. |
| `G01AA01` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Vaginal polyene antifungal: nystatin. The antibacterials in the same group are not included. WHOCC page checked 2026-11-07. |
| `G01AA02` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Vaginal polyene antifungal: natamycin. The antibacterials in the same group are not included. WHOCC page checked 2026-11-07. |
| `G01AA03` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Vaginal polyene antifungal: amphotericin B. The antibacterials in the same group are not included. WHOCC page checked 2026-11-07. |
| `G01AA04` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Vaginal polyene antifungal: candicidin. The antibacterials in the same group are not included. WHOCC page checked 2026-11-07. |
| `G01AA09` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Vaginal polyene antifungal: mepartricin. The antibacterials in the same group are not included. WHOCC page checked 2026-11-07. |
| `G01AA11` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Vaginal polyene antifungal: pentamycin. The antibacterials in the same group are not included. WHOCC page checked 2026-11-07. |
| `G01AF` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Vaginal imidazoles (clotrimazole, miconazole, econazole, fenticonazole, sertaconazole and others). WHOCC page checked 2026-11-07. |
| `G01AF01` | exclude | pipc | whocc_lookup | Nitroimidazole (metronidazole) for bacterial vaginosis or trichomonas, not a fungus; excluded. WHOCC page checked 2026-11-07. |
| `G01AF06` | exclude | pipc | whocc_lookup | Nitroimidazole (ornidazole) for bacterial vaginosis or trichomonas, not a fungus; excluded. WHOCC page checked 2026-11-07. |
| `G01AF13` | exclude | pipc | whocc_lookup | Nitroimidazole (azanidazole) for bacterial vaginosis or trichomonas, not a fungus; excluded. WHOCC page checked 2026-11-07. |
| `G01AF14` | exclude | pipc | whocc_lookup | Nitroimidazole (propenidazole) for bacterial vaginosis or trichomonas, not a fungus; excluded. WHOCC page checked 2026-11-07. |
| `G01AF21` | exclude | pipc | whocc_lookup | Nitroimidazole (tinidazole) for bacterial vaginosis or trichomonas, not a fungus; excluded. WHOCC page checked 2026-11-07. |
| `G01AG02` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Vaginal terconazole. WHOCC page checked 2026-11-07. |
| `G01AX12` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Vaginal ciclopirox. WHOCC page checked 2026-11-07. |
| `J02AC01` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Oral triazole: fluconazole, the usual oral choice. Voriconazole, posaconazole and isavuconazole (invasive infections in hospital) are left out. WHOCC page checked 2026-11-07. |
| `J02AC02` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Oral triazole: itraconazole. Voriconazole, posaconazole and isavuconazole (invasive infections in hospital) are left out. WHOCC page checked 2026-11-07. |
| `J02AC06` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Oral triazole: oteseconazole, licensed for recurrent vulvovaginal candidiasis. Voriconazole, posaconazole and isavuconazole (invasive infections in hospital) are left out. WHOCC page checked 2026-11-07. |
| `J02AX07` | include | pipc | whocc_lookup | Rows 41, 62 marker (genital or vulvovaginal candidiasis). Ibrexafungerp, an oral antifungal licensed for vulvovaginal candidiasis. WHOCC page checked 2026-11-07. |

### `antigout`

Used by rows: 7 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `M04A` | include | pipc | pharmacology | Row 7 marker. Allopurinol, febuxostat, uricosurics (probenecid, benzbromarone), colchicine, pegloticase. NSAIDs and corticosteroids given for an acute attack are left out: they are started for many other reasons. |

### `antihistamine`

Used by rows: 29 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `R01AC` | include | pipc | whocc_lookup | Nasal antihistamine sprays (azelastine, levocabastine, olopatadine). Ipratropium nasal spray (R01AX03), which works best for a cholinergic runny nose, is left out because PIPC names antihistamines (owner question). WHOCC page checked 2026-11-07. |
| `R01AC01` | exclude | pipc | whocc_lookup | Cromoglicate is a mast-cell stabiliser, not an antihistamine; excluded. WHOCC page checked 2026-11-07. |
| `R01AC07` | exclude | pipc | whocc_lookup | Nedocromil is a mast-cell stabiliser, not an antihistamine; excluded. WHOCC page checked 2026-11-07. |
| `R06A` | include | pipc | pharmacology | Row 29 marker (rhinorrhoea). Systemic antihistamines, many over the counter. |
| `R06AA10` | exclude | pipc | whocc_lookup | Trimethobenzamide is an antiemetic, not used for a runny nose; excluded. WHOCC page checked 2026-11-07. |

### `antihyperglycemic`

Used by rows: 22 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A10` | include | pipc | pharmacology | Row 22 marker. Insulins and all other glucose-lowering drugs. Fixed combinations (A10BD) never reach the engine. |
| `A10X` | exclude | pipc | pharmacology | Other diabetes drugs that do not lower glucose (aldose reductase inhibitors); excluded. |

### `antihypertensive`

Used by rows: 2 (index), 14, 38, 53, 61, 64 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C02` | include | pipc | pharmacology | Rows 2 (index) and 14, 38, 53, 61, 64 (marker). One definition for both roles: the medicines that lower blood pressure are the ones started for hypertension. Chapters C02, C03, C07, C08, C09. Alpha-1 blockers licensed only for prostate symptoms (G04CA) are not in this class because PIPC names them as a class of their own (rows 45, 56). Ophthalmic beta-blockers (S01ED) are not extended here: 'Antihypertensive' is a class by indication and eye drops are never given for blood pressure (design DP8). |
| `C02KX` | exclude | pipc | whocc_lookup | Endothelin receptor antagonists, riociguat and sotatercept are given for pulmonary arterial hypertension, not for systemic blood pressure; excluded. WHOCC page checked 2026-11-07. |
| `C03` | include | pipc | pharmacology | Diuretics. Loop diuretics and mineralocorticoid antagonists used mainly for heart failure stay in: they lower blood pressure and are also prescribed for hypertension. |
| `C03X` | exclude | pipc | pharmacology | Vasopressin antagonists (tolvaptan, conivaptan) are used for hyponatraemia or kidney cysts, not for blood pressure; excluded. |
| `C07` | include | pipc | pharmacology | Systemic beta-blockers. Eye-drop beta-blockers (S01ED) are not part of this class (see the C02 row). |
| `C08` | include | pipc | pharmacology | Calcium channel blockers. |
| `C08E` | exclude | pipc | pharmacology | Non-selective calcium channel blockers (bepridil, fendiline, lidoflazine, perhexiline) are antianginal drugs, not used for hypertension; excluded. |
| `C09` | include | pipc | pharmacology | Renin-angiotensin agents: ACE inhibitors, angiotensin receptor blockers, aliskiren. Combination groups C09B and C09D never reach the engine; their ingredients do. |

### `antimuscarinic_antiparkinsonian`

Used by rows: 19 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N04A` | include | pipc | pharmacology | Row 19 marker. Anticholinergic antiparkinsonian agents (trihexyphenidyl, biperiden, benztropine, procyclidine). |

### `antiparkinsonian`

Used by rows: 18, 37, 46 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N04` | include | pipc | pharmacology | Rows 18, 37, 46 marker. All antiparkinsonian agents: anticholinergics, amantadine, levodopa, dopamine agonists, MAO-B and COMT inhibitors. Levodopa combinations (N04BA02, N04BA03) never reach the engine; levodopa does. |

### `antipsychotic`

Used by rows: 17, 18, 19, 20, 21, 22 (index), 30, 60 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N05A` | include | pipc | pharmacology | Rows 17-22 (index) and 30, 60 (marker). All antipsychotics, typical and atypical, including sulpiride, amisulpride, pimavanserin and prochlorperazine (also an antiemetic). One class for both roles. |
| `N05AN` | exclude | pipc | pharmacology | Lithium is a mood stabiliser with its own PIPC row (37); excluded. |

### `benzodiazepine`

Used by rows: 23 (index), 39 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N03AE01` | include | pipc | whocc_lookup | Clonazepam, a benzodiazepine coded with the antiepileptics. WHOCC page checked 2026-11-07. |
| `N05BA` | include | pipc | pharmacology | Rows 23 (index) and 39 (marker). Benzodiazepines labelled as anxiolytics. One class for both roles. Z-drugs (N05CF) are not benzodiazepines and are left out; tetrazepam (M03BX07, withdrawn in the EU) is left out. |
| `N05CD` | include | pipc | pharmacology | Benzodiazepines labelled as hypnotics (temazepam, nitrazepam, midazolam and others). |

### `beta_blocker_index`

Used by rows: 4 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C07` | include | pipc | pharmacology | Row 4 index (erectile dysfunction). All systemic beta-blockers. PIPC says 'particularly lipophilic e.g., propranolol'; the class keeps hydrophilic ones (atenolol, sotalol) too, because PIPC names the whole class and 'particularly' is a weight, not a limit. Fixed combinations (C07B-C07F) never reach the engine. Same content as row 3 without the eye-drop extension. Owner decision 2026-11-07: no S01ED extension for row 4, because the only source found is a letter (Fraunfelder 1985), not a reviewed article; it is not added to the paper list. |

### `beta_blocker_index_eye`

Used by rows: 3 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C07` | include | pipc | pharmacology | Row 3 index (depression). All systemic beta-blockers. PIPC says 'particularly lipophilic e.g., propranolol'; the class keeps hydrophilic ones (atenolol, sotalol) too, because PIPC names the whole class and 'particularly' is a weight, not a limit. Fixed combinations (C07B-C07F) never reach the engine. |
| `S01ED` | include | form_extension (paper:vander_zanden_2001:aph_18464) | pharmacology | Form extension for row 3 only (design DP8). Eye drops drain through the nasolacrimal duct and are absorbed by the nasal mucosa without first-pass metabolism, so timolol and other ophthalmic beta-blockers can cause systemic beta-blockade; the cited review finds bronchospasm and bradycardia best supported and depression reported less often. 41 TİTCK products publish an S01ED code (design section 1). Never used in a marker role. |

### `beta_blocker_marker`

Used by rows: 17 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C07` | include | pipc | pharmacology | Row 17 marker (extrapyramidal symptoms treated with a beta-blocker; in practice propranolol for akathisia). Kept as the whole systemic class because PIPC names the class. No form extension: eye drops are not used to treat akathisia, and marker classes take no extensions (design DP8). |

### `bisphosphonate`

Used by rows: 50 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `M05BA` | include | pipc | pharmacology | Row 50 index (gastritis). Bisphosphonates taken by mouth irritate the oesophagus and stomach. Combinations with calcium or vitamin D (M05BB) never reach the engine. |
| `M05BA03` | exclude | pipc | whocc_lookup | Pamidronate is given only by infusion and does not cause gastritis; excluded. WHOCC page checked 2026-11-07. |
| `M05BA08` | exclude | pipc | whocc_lookup | Zoledronate is given only by infusion and does not cause gastritis; excluded. Ibandronate and clodronate have oral and injected forms under one code and stay in. WHOCC page checked 2026-11-07. |

### `carbapenem`

Used by rows: 58 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `J01DH` | include | pipc | pharmacology | Row 58 index. Meropenem, ertapenem, doripenem and others. Imipenem is marketed only with cilastatin and its only code (J01DH51) is a combination code, so imipenem matches only once resolution gives the imipenem ingredient an ingredient-level code (listed for review). |

### `ccb`

Used by rows: 5, 6 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C08` | include | pipc | pharmacology | Rows 5 (peripheral oedema, mainly dihydropyridines such as amlodipine) and 6 (constipation, mainly verapamil). One class for both because PIPC names the whole class in both rows. Combination group C08G never reaches the engine. |

### `cholinesterase_inhibitor`

Used by rows: 23, 33 (marker), 24, 25, 26, 27, 28, 29 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N06DA` | include | pipc | pharmacology | Rows 24-29 (index) and 23, 33 (marker). Donepezil, rivastigmine (patches included: the route map keeps N codes for transdermal products), galantamine. Memantine (N06DX01) is not a cholinesterase inhibitor and is left out, although ThinkCascades accepts it as a marker. Peripheral cholinesterase inhibitors for myasthenia (N07AA) are left out: PIPC's context is dementia. Memantine-donepezil combinations never reach the engine. |

### `corticosteroid_systemic`

Used by rows: 59, 60, 61 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `H02AB` | include | pipc | pharmacology | Rows 59-61 index. Systemic glucocorticoids by mouth or injection (joint injections included: the route map keeps H02AB for intra-articular products). Not extended (design DP8): inhaled (R03BA), nasal (R01AD), skin (D07), eye (S01BA) and gut-acting (A07EA) corticosteroids, because insomnia, psychosis and hypertension follow systemic exposure, which is small at usual doses of these forms. Fludrocortisone (H02AA02) has its own row (64) and is not in this class. |

### `cough_remedy`

Used by rows: 1 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `R05C` | include | pipc | pharmacology | Row 1 marker. Expectorants and mucolytics (acetylcysteine, ambroxol, bromhexine, guaifenesin), often over the counter and often taken for an ACE-inhibitor cough. Mixed-substance codes in the group never reach the engine. |
| `R05D` | include | pipc | pharmacology | Cough suppressants (dextromethorphan, codeine as an antitussive, butamirate, levodropropizine, benzonatate). Other cold mixtures (R05X) are left out: almost all are multi-ingredient. |

### `digoxin`

Used by rows: 13 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C01AA05` | include | pipc | whocc_lookup | Row 13 index, individual drug: digoxin only. Other cardiac glycosides (digitoxin, metildigoxin) are left out because PIPC names one substance. WHOCC page checked 2026-11-07. |

### `diuretic`

Used by rows: 5, 31, 43, 44 (marker), 7, 8 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C03` | include | pipc | pharmacology | Rows 7, 8 (index) and 5, 31, 43, 44 (marker). Thiazides, thiazide-like, loop and potassium-sparing diuretics. Potassium-sparing diuretics are kept in the index role because PIPC names the class as a whole, although gout (row 7) is mainly a thiazide and loop effect (judgement call, listed for review). Acetazolamide (S01EC01) is not included. Combination group C03E never reaches the engine. |
| `C03X` | exclude | pipc | pharmacology | Vasopressin antagonists are aquaretics used for hyponatraemia; they are not used to treat oedema or heart failure and do not raise uric acid; excluded. |

### `dopaminergic_antiparkinsonian`

Used by rows: 30 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N04B` | include | pipc | pharmacology | Row 30 index. Levodopa, amantadine, dopamine agonists, MAO-B and COMT inhibitors. Bromocriptine and cabergoline coded for prolactin disorders (G02CB) are left out because PIPC names the antiparkinsonian use. |

### `dpp4_inhibitor`

Used by rows: 40 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A10BH` | include | pipc | pharmacology | Row 40 index. All gliptins. Fixed combinations with metformin and others (A10BD) never reach the engine. |

### `erythromycin`

Used by rows: 63 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `J01FA01` | include | pipc | whocc_lookup | Row 63 index, individual drug: systemic erythromycin (oral or intravenous; also used as a prokinetic under the same code). Not extended (design DP8): skin erythromycin (D10AF02) and eye ointment (S01AA17) give no meaningful systemic exposure, so they do not prolong the QT interval. WHOCC page checked 2026-11-07. |

### `fludrocortisone`

Used by rows: 64 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `H02AA02` | include | pipc | whocc_lookup | Row 64 index, individual drug: fludrocortisone (oral). WHOCC page checked 2026-11-07. |

### `flunarizine`

Used by rows: 36 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N07CA03` | include | pipc | whocc_lookup | Row 36 index, individual drug: flunarizine (oral). WHOCC page checked 2026-11-07. |

### `gabapentinoid`

Used by rows: 31 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N02BF` | include | pipc | whocc_lookup | Row 31 index. Gabapentin, pregabalin, mirogabalin (current codes). WHOCC page checked 2026-11-07. |
| `N03AX12` | include | pipc | titck_observed | Old gabapentin code, still published on 44 TİTCK rows; kept so Turkish gabapentin products match. |
| `N03AX16` | include | pipc | titck_observed | Old pregabalin code, still published on 162 TİTCK rows; kept so Turkish pregabalin products match. |

### `gastroprotective`

Used by rows: 50, 51 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A02A` | include | pipc | pharmacology | Rows 50, 51 marker. Antacids (magnesium, aluminium and calcium salts), over the counter. Mixed antacid codes never reach the engine. |
| `A02B` | include | pipc | pharmacology | Rows 50, 51 marker. H2 blockers, PPIs, misoprostol, sucralfate, alginates, bismuth subcitrate. Eradication packs (A02BD) never reach the engine. |

### `heart_failure_agent`

Used by rows: 54 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C01AA05` | include | pipc | whocc_lookup | Row 54 marker (worsening heart failure). Digoxin. WHOCC page checked 2026-11-07. |
| `C01DX22` | include | pipc | whocc_lookup | Row 54 marker (worsening heart failure). Vericiguat. WHOCC page checked 2026-11-07. |
| `C01EB17` | include | pipc | whocc_lookup | Row 54 marker (worsening heart failure). Ivabradine. WHOCC page checked 2026-11-07. |
| `C03C` | include | pipc | pharmacology | Row 54 marker (worsening heart failure). Loop diuretics, the usual response to fluid retention. ACE inhibitors, ARBs, sacubitril-valsartan, beta-blockers and SGLT-2 inhibitors are left out: they are mostly started for blood pressure or diabetes, so a match would say little (judgement call, listed for review). |
| `C03DA` | include | pipc | pharmacology | Row 54 marker (worsening heart failure). Mineralocorticoid antagonists (spironolactone, eplerenone). |

### `iron_oral`

Used by rows: 65 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `B03AA` | include | pipc | pharmacology | Row 65 index. Oral ferrous iron salts. Parenteral iron (B03AC) does not cause constipation and is not included (it also has no substance-level code). Iron with folic acid or vitamins (B03AD, B03AE) never reaches the engine; its iron ingredient does. |
| `B03AB` | include | pipc | pharmacology | Oral ferric iron preparations (for example ferric polymaltose). |
| `B03AB02` | exclude | pipc | titck_observed | Saccharated iron oxide: the oral form is not on the TİTCK list (0 rows), and Wikidata attaches this code to intravenous iron sucrose, so an iron sucrose infusion found by name would match. Excluded. |

### `laxative`

Used by rows: 6, 34, 65 (marker), 47 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A06A` | include | pipc | pharmacology | Rows 6, 34, 65 (marker) and 47 (index). All laxatives, most of them over the counter: softeners, stimulants (bisacodyl, senna, sodium picosulfate), bulk-forming, osmotic (lactulose, macrogol, magnesium salts), enemas, peripheral opioid antagonists and prokinetic or secretagogue laxatives. One class for both roles. Magnesium oxide coded only as an antacid (A02AA02) or a supplement (A12CC10) does not match. Mixed mineral-salt code A06AD10 never reaches the engine. |

### `lithium`

Used by rows: 37 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N05AN01` | include | pipc | whocc_lookup | Row 37 index, individual drug: lithium salts. WHOCC page checked 2026-11-07. |

### `metformin`

Used by rows: 42 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A10BA02` | include | pipc | whocc_lookup | Row 42 index, individual drug: metformin. WHOCC page checked 2026-11-07. |

### `midodrine`

Used by rows: 14 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C01CA17` | include | pipc | whocc_lookup | Row 14 index, individual drug: midodrine (oral). WHOCC page checked 2026-11-07. |

### `mineral_supplement`

Used by rows: 10 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A12AA` | include | pipc | pharmacology | Row 10 marker. PIPC writes 'Mineral supplement' without naming the mineral; read as the minerals people take for muscle pain or cramps. Potassium and sodium (electrolyte replacement for other drugs' losses) and fluoride are left out (judgement call, listed for review). Calcium salts. |
| `A12CB` | include | pipc | pharmacology | Row 10 marker. PIPC writes 'Mineral supplement' without naming the mineral; read as the minerals people take for muscle pain or cramps. Potassium and sodium (electrolyte replacement for other drugs' losses) and fluoride are left out (judgement call, listed for review). Zinc. |
| `A12CC` | include | pipc | pharmacology | Row 10 marker. PIPC writes 'Mineral supplement' without naming the mineral; read as the minerals people take for muscle pain or cramps. Potassium and sodium (electrolyte replacement for other drugs' losses) and fluoride are left out (judgement call, listed for review). Magnesium salts, the mineral most often taken for cramps. |
| `A12CE` | include | pipc | pharmacology | Row 10 marker. PIPC writes 'Mineral supplement' without naming the mineral; read as the minerals people take for muscle pain or cramps. Potassium and sodium (electrolyte replacement for other drugs' losses) and fluoride are left out (judgement call, listed for review). Selenium. |

### `nsaid`

Used by rows: 51, 52, 53, 54 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `M01A` | include | pipc | pharmacology | Rows 51-54 index (row 51 writes 'Nonsteroidal anti-inflammatory drug (NSAID)', rows 52-54 'NSAID'; same class). Systemic NSAIDs including coxibs. Not extended (design DP8): topical NSAIDs (M02AA) and eye-drop NSAIDs (S01BC), because gastric bleeding, raised blood pressure and fluid retention follow systemic exposure, which is low at usual doses of these forms. Intravenous ibuprofen and indometacin for the neonatal ductus (C01EB16, C01EB03) are not included. |
| `M01AX` | exclude | pipc | whocc_lookup | This sub-group mixes NSAIDs with substances that are not NSAIDs (glucosamine, chondroitin, diacerein, benzydamine and others); excluded, and the NSAIDs in it are included one by one below. WHOCC page checked 2026-11-07. |
| `M01AX01` | include | pipc | whocc_lookup | NSAID inside M01AX: nabumetone. WHOCC page checked 2026-11-07. |
| `M01AX02` | include | pipc | whocc_lookup | NSAID inside M01AX: niflumic acid. WHOCC page checked 2026-11-07. |
| `M01AX04` | include | pipc | whocc_lookup | NSAID inside M01AX: azapropazone. WHOCC page checked 2026-11-07. |
| `M01AX13` | include | pipc | whocc_lookup | NSAID inside M01AX: proquazone. WHOCC page checked 2026-11-07. |
| `M01AX17` | include | pipc | whocc_lookup | NSAID inside M01AX: nimesulide (widely used in Türkiye). WHOCC page checked 2026-11-07. |
| `M01AX18` | include | pipc | whocc_lookup | NSAID inside M01AX: feprazone. WHOCC page checked 2026-11-07. |
| `M01AX22` | include | pipc | whocc_lookup | NSAID inside M01AX: morniflumate. WHOCC page checked 2026-11-07. |
| `N02BA` | include | pipc | whocc_lookup | Salicylates at analgesic doses (aspirin, diflunisal, salsalate and others) are NSAIDs. Low-dose aspirin coded as an antiplatelet (B01AC06) is not included (owner question). WHOCC page checked 2026-11-07. |

### `nsaid_marker`

Used by rows: 40 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `M01A` | include | pipc | pharmacology | Row 40 marker (joint pain). Same systemic NSAIDs as the index class 'nsaid', plus topical NSAIDs (M02AA, below), because joint pain is often treated with an over-the-counter gel. Kept separate from the index class because the index class must not contain topical forms. |
| `M01AX` | exclude | pipc | whocc_lookup | This sub-group mixes NSAIDs with substances that are not NSAIDs (glucosamine, chondroitin, diacerein, benzydamine and others); excluded, and the NSAIDs in it are included one by one below. WHOCC page checked 2026-11-07. |
| `M01AX01` | include | pipc | whocc_lookup | NSAID inside M01AX: nabumetone. WHOCC page checked 2026-11-07. |
| `M01AX02` | include | pipc | whocc_lookup | NSAID inside M01AX: niflumic acid. WHOCC page checked 2026-11-07. |
| `M01AX04` | include | pipc | whocc_lookup | NSAID inside M01AX: azapropazone. WHOCC page checked 2026-11-07. |
| `M01AX13` | include | pipc | whocc_lookup | NSAID inside M01AX: proquazone. WHOCC page checked 2026-11-07. |
| `M01AX17` | include | pipc | whocc_lookup | NSAID inside M01AX: nimesulide (widely used in Türkiye). WHOCC page checked 2026-11-07. |
| `M01AX18` | include | pipc | whocc_lookup | NSAID inside M01AX: feprazone. WHOCC page checked 2026-11-07. |
| `M01AX22` | include | pipc | whocc_lookup | NSAID inside M01AX: morniflumate. WHOCC page checked 2026-11-07. |
| `M02AA` | include | pipc | pharmacology | Topical NSAIDs (gels, creams, patches), mostly over the counter; marker role only. |
| `N02BA` | include | pipc | whocc_lookup | Salicylates at analgesic doses (aspirin, diflunisal, salsalate and others) are NSAIDs. Low-dose aspirin coded as an antiplatelet (B01AC06) is not included (owner question). WHOCC page checked 2026-11-07. |

### `oab_medication`

Used by rows: 8, 24, 32, 35 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `G04BD` | include | pipc | whocc_lookup | Rows 8, 24, 32, 35 marker (row 32 writes 'Urinary Incontinence' with a capital I; same class). Bladder antimuscarinics (oral and patch) and beta-3 agonists (mirabegron, vibegron). Botulinum toxin injections and desmopressin are left out. WHOCC page checked 2026-11-07. |

### `opioid`

Used by rows: 55 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N02A` | include | pipc | pharmacology | Row 55 index (depression). Opioid analgesics including tramadol, tapentadol and patches (route map keeps N for transdermal products). Codeine and dextromethorphan coded as cough suppressants (R05DA) and loperamide are left out: antitussive doses are short and loperamide does not reach the brain. Opioid-paracetamol combinations (N02AJ) never reach the engine; their opioid ingredient does. |
| `N07BC` | include | pipc | whocc_lookup | Opioids used for opioid dependence (buprenorphine, methadone and others). WHOCC page checked 2026-11-07. |
| `N07BC04` | exclude | pipc | whocc_lookup | Lofexidine is an alpha-2 agonist, not an opioid; excluded. WHOCC page checked 2026-11-07. |

### `pain_reliever`

Used by rows: 9 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `M01A` | include | pipc | pharmacology | Row 9 marker (myalgia). Systemic NSAIDs, many over the counter. |
| `M01AX` | exclude | pipc | whocc_lookup | Sub-group mixing NSAIDs with non-analgesic substances (glucosamine, chondroitin, diacerein); excluded, its NSAIDs are included one by one. WHOCC page checked 2026-11-07. |
| `M01AX01` | include | pipc | whocc_lookup | NSAID inside M01AX: nabumetone. WHOCC page checked 2026-11-07. |
| `M01AX02` | include | pipc | whocc_lookup | NSAID inside M01AX: niflumic acid. WHOCC page checked 2026-11-07. |
| `M01AX04` | include | pipc | whocc_lookup | NSAID inside M01AX: azapropazone. WHOCC page checked 2026-11-07. |
| `M01AX13` | include | pipc | whocc_lookup | NSAID inside M01AX: proquazone. WHOCC page checked 2026-11-07. |
| `M01AX17` | include | pipc | whocc_lookup | NSAID inside M01AX: nimesulide (widely used in Türkiye). WHOCC page checked 2026-11-07. |
| `M01AX18` | include | pipc | whocc_lookup | NSAID inside M01AX: feprazone. WHOCC page checked 2026-11-07. |
| `M01AX22` | include | pipc | whocc_lookup | NSAID inside M01AX: morniflumate. WHOCC page checked 2026-11-07. |
| `M02AA` | include | pipc | pharmacology | Row 9 marker (myalgia). Topical NSAIDs, over the counter and often used for muscle pain. |
| `N02A` | include | pipc | pharmacology | Row 9 marker (myalgia). Opioid analgesics. |
| `N02B` | include | pipc | pharmacology | Row 9 marker (myalgia). Paracetamol, metamizole, salicylates and other non-opioid analgesics, mostly over the counter. Muscle relaxants (thiocolchicoside, cyclobenzaprine; M03B) are left out (owner question). |
| `N02BF` | exclude | pipc | whocc_lookup | Gabapentinoids are used for nerve pain, not muscle pain, and are PIPC's own class (row 31); excluded. WHOCC page checked 2026-11-07. |

### `pde5_inhibitor_alprostadil`

Used by rows: 4 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `G04BE01` | include | pipc | whocc_lookup | Row 4 marker. PIPC names PDE-5 inhibitors and alprostadil. Alprostadil (injection or urethral). Its ductus code C01EA01 is left out. Other erectile-dysfunction drugs in G04BE (papaverine, yohimbine, moxisylyte, apomorphine) are left out because PIPC does not name them. WHOCC page checked 2026-11-07. |
| `G04BE03` | include | pipc | whocc_lookup | Row 4 marker. PIPC names PDE-5 inhibitors and alprostadil. Sildenafil. The pulmonary hypertension product shares this code. WHOCC page checked 2026-11-07. |
| `G04BE08` | include | pipc | whocc_lookup | Row 4 marker. PIPC names PDE-5 inhibitors and alprostadil. Tadalafil. The pulmonary hypertension and prostate uses share this code. WHOCC page checked 2026-11-07. |
| `G04BE09` | include | pipc | whocc_lookup | Row 4 marker. PIPC names PDE-5 inhibitors and alprostadil. Vardenafil. WHOCC page checked 2026-11-07. |
| `G04BE10` | include | pipc | whocc_lookup | Row 4 marker. PIPC names PDE-5 inhibitors and alprostadil. Avanafil. WHOCC page checked 2026-11-07. |
| `G04BE11` | include | pipc | whocc_lookup | Row 4 marker. PIPC names PDE-5 inhibitors and alprostadil. Udenafil. WHOCC page checked 2026-11-07. |

### `pioglitazone_rosiglitazone`

Used by rows: 43 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A10BG02` | include | pipc | whocc_lookup | Row 43 index: rosiglitazone. WHOCC page checked 2026-11-07. |
| `A10BG03` | include | pipc | whocc_lookup | Row 43 index: pioglitazone. Other glitazones (troglitazone, lobeglitazone) are left out because PIPC names two substances. WHOCC page checked 2026-11-07. |

### `ppi`

Used by rows: 48, 49 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A02BC` | include | pipc | pharmacology | Rows 48, 49 index. All proton pump inhibitors. Eradication packs (A02BD) never reach the engine. |

### `ppi_deficiency_supplement`

Used by rows: 49 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A12CC` | include | pipc | pharmacology | Row 49 marker. PIPC publishes Drug B as 'Vitamin or Mineral Deficiency', the same words as the adverse event; the text is kept as published. Owner decision 2026-11-07: read as supplements for the deficiencies best linked to long-term PPI use, vitamin B12, magnesium and oral iron; calcium and vitamin D belong to the fracture cascade (row 48). This row: magnesium. |
| `B03AA` | include | pipc | pharmacology | Row 49 marker. PIPC publishes Drug B as 'Vitamin or Mineral Deficiency', the same words as the adverse event; the text is kept as published. Owner decision 2026-11-07: read as supplements for the deficiencies best linked to long-term PPI use, vitamin B12, magnesium and oral iron; calcium and vitamin D belong to the fracture cascade (row 48). This row: oral iron (ferrous). |
| `B03AB` | include | pipc | pharmacology | Row 49 marker. PIPC publishes Drug B as 'Vitamin or Mineral Deficiency', the same words as the adverse event; the text is kept as published. Owner decision 2026-11-07: read as supplements for the deficiencies best linked to long-term PPI use, vitamin B12, magnesium and oral iron; calcium and vitamin D belong to the fracture cascade (row 48). This row: oral iron (ferric). |
| `B03BA` | include | pipc | pharmacology | Row 49 marker. PIPC publishes Drug B as 'Vitamin or Mineral Deficiency', the same words as the adverse event; the text is kept as published. Owner decision 2026-11-07: read as supplements for the deficiencies best linked to long-term PPI use, vitamin B12, magnesium and oral iron; calcium and vitamin D belong to the fracture cascade (row 48). This row: vitamin B12. |

### `quinine`

Used by rows: 11 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `P01BC01` | include | pipc | whocc_lookup | Row 11 marker: quinine (PIPC writes quinine sulfate; the salt shares the substance code). Hydroquinine (M09AA01), a different substance used for cramps in some EU countries, is left out. WHOCC page checked 2026-11-07. |

### `rosiglitazone`

Used by rows: 44 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A10BG02` | include | pipc | whocc_lookup | Row 44 index, individual drug: rosiglitazone. WHOCC page checked 2026-11-07. |

### `sedative`

Used by rows: 20 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N03AE01` | include | pipc | whocc_lookup | Row 20 marker (akathisia or tardive movements). Clonazepam, the benzodiazepine most used for akathisia. Mirtazapine is left out (antidepressant). WHOCC page checked 2026-11-07. |
| `N05B` | include | pipc | pharmacology | Row 20 marker (akathisia or tardive movements). Anxiolytics: benzodiazepines, hydroxyzine and others. |
| `N05BE` | exclude | pipc | pharmacology | Buspirone is not sedating; excluded. |
| `N05C` | include | pipc | pharmacology | Row 20 marker (akathisia or tardive movements). Hypnotics and sedatives. |
| `N05CH` | exclude | pipc | pharmacology | Melatonin and its agonists are not used to sedate; excluded. |
| `N05CJ` | exclude | pipc | whocc_lookup | Orexin antagonists are sleep drugs, not sedatives for movement disorders; excluded. WHOCC page checked 2026-11-07. |

### `sglt2_inhibitor`

Used by rows: 41 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A10BK` | include | pipc | pharmacology | Row 41 index. All gliflozins. |

### `sleep_agent`

Used by rows: 12, 25, 59 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N05BA` | include | pipc | pharmacology | Rows 12, 25, 59 marker; one definition for all three. Benzodiazepines labelled as anxiolytics but often prescribed for sleep (lorazepam, alprazolam, diazepam). |
| `N05C` | include | pipc | pharmacology | Rows 12, 25, 59 marker; one definition for all three. All hypnotics and sedatives: benzodiazepine hypnotics, Z-drugs, melatonin and its agonists, orexin antagonists, barbiturates and others. Melatonin is often bought without prescription. |
| `N06AX05` | include | pipc | whocc_lookup | Rows 12, 25, 59 marker; one definition for all three. Trazodone, the antidepressant most prescribed for sleep in older adults. Mirtazapine, low-dose doxepin and quetiapine are left out (judgement call). WHOCC page checked 2026-11-07. |
| `R06AA02` | include | pipc | whocc_lookup | Rows 12, 25, 59 marker; one definition for all three. Diphenhydramine, an over-the-counter sleep aid. WHOCC page checked 2026-11-07. |
| `R06AA09` | include | pipc | whocc_lookup | Rows 12, 25, 59 marker; one definition for all three. Doxylamine, an over-the-counter sleep aid. WHOCC page checked 2026-11-07. |

### `ssri_snri`

Used by rows: 32 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N06AB` | include | pipc | pharmacology | Row 32 index. All SSRIs. |
| `N06AX16` | include | pipc | whocc_lookup | SNRI: venlafaxine. WHOCC page checked 2026-11-07. |
| `N06AX17` | include | pipc | whocc_lookup | SNRI: milnacipran. WHOCC page checked 2026-11-07. |
| `N06AX21` | include | pipc | whocc_lookup | SNRI: duloxetine. WHOCC page checked 2026-11-07. |
| `N06AX23` | include | pipc | whocc_lookup | SNRI: desvenlafaxine. WHOCC page checked 2026-11-07. |
| `N06AX28` | include | pipc | whocc_lookup | SNRI: levomilnacipran. WHOCC page checked 2026-11-07. |

### `statin`

Used by rows: 9, 10, 11, 12 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `C10AA` | include | pipc | pharmacology | Rows 9-12 index. Row 9 writes the class with '(statin)', rows 10-12 without it; same class. All HMG-CoA reductase inhibitors. Lipid combinations (C10B) never reach the engine. |

### `topical_corticosteroid`

Used by rows: 15 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `D07A` | include | pipc | pharmacology | Row 15 marker (rash). Plain skin corticosteroids of all potencies. Skin corticosteroids combined with antiseptics, antibiotics or others (D07B, D07C, D07X) are combination groups and are refused as patterns; the corticosteroid ingredient of such a product reaches the engine after decomposition. |

### `tricyclic_antidepressant`

Used by rows: 33, 34, 35 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N06AA` | include | pipc | pharmacology | Rows 33-35 index. Amitriptyline, nortriptyline, imipramine, clomipramine, doxepin, dosulepin and the rest of the group, including the tetracyclic maprotiline and opipramol, which share the anticholinergic profile. Fixed combinations with antipsychotics (N06C) never reach the engine. |

### `urinary_anticholinergic`

Used by rows: 57 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `G04BD` | include | pipc | whocc_lookup | Row 57 index (dry mouth). Bladder antimuscarinics: oxybutynin (patch included), tolterodine, solifenacin, darifenacin, trospium, fesoterodine, propiverine, flavoxate and others. WHOCC page checked 2026-11-07. |
| `G04BD12` | exclude | pipc | whocc_lookup | Mirabegron is a beta-3 agonist without anticholinergic action; excluded. WHOCC page checked 2026-11-07. |
| `G04BD15` | exclude | pipc | whocc_lookup | Vibegron is a beta-3 agonist without anticholinergic action; excluded. WHOCC page checked 2026-11-07. |

### `venlafaxine`

Used by rows: 38, 39 (index).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `N06AX16` | include | pipc | whocc_lookup | Rows 38, 39 index, individual drug: venlafaxine. Desvenlafaxine (N06AX23) is a different substance and is left out. WHOCC page checked 2026-11-07. |

### `vestibular_suppressant`

Used by rows: 56 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A04AD01` | include | pipc | whocc_lookup | Row 56 marker (orthostatic hypotension, dizziness). Scopolamine. Benzodiazepines, also used as vestibular suppressants, are left out because they are started for many other reasons (owner question). WHOCC page checked 2026-11-07. |
| `N07CA` | include | pipc | whocc_lookup | Row 56 marker (orthostatic hypotension, dizziness). Antivertigo drugs (betahistine, cinnarizine, flunarizine, acetylleucine). Betahistine is not a vestibular suppressant in the strict sense but is the drug most prescribed for dizziness in Türkiye and the EU, and ThinkCascades gives it as an example for this cascade. WHOCC page checked 2026-11-07. |
| `R06AA11` | include | pipc | whocc_lookup | Row 56 marker (orthostatic hypotension, dizziness). Dimenhydrinate. WHOCC page checked 2026-11-07. |
| `R06AD02` | include | pipc | whocc_lookup | Row 56 marker (orthostatic hypotension, dizziness). Promethazine. WHOCC page checked 2026-11-07. |
| `R06AE03` | include | pipc | whocc_lookup | Row 56 marker (orthostatic hypotension, dizziness). Cyclizine. WHOCC page checked 2026-11-07. |
| `R06AE05` | include | pipc | whocc_lookup | Row 56 marker (orthostatic hypotension, dizziness). Meclizine (meclozine). WHOCC page checked 2026-11-07. |

### `vitamin_supplement`

Used by rows: 48 (marker).

| Pattern | Match | Scope | Basis | Note |
|---|---|---|---|---|
| `A11CC` | include | pipc | pharmacology | Row 48 marker (osteoporosis, fractures). Vitamin D and its analogues (cholecalciferol, calcitriol, alfacalcidol). Calcium is a mineral and is left out because PIPC writes 'Vitamin supplement' (owner question). Vitamin A plus D (A11CB) never reaches the engine. |

## 4. Abrupt-stop list

The six groups of `medical-safety.md` rule 4 are covered on systemic forms only (no eye drops,
skin, inhaled or nasal forms). The groups beyond rule 4 were confirmed by the owner on
2026-11-07 (a wrong "do not stop suddenly" warning is low-harm, so over-inclusion is the safe
side). Gut-acting corticosteroids (A07EA) are not on the list (owner decision: low systemic
exposure).

| Pattern | Group | Status | Note |
|---|---|---|---|
| `C07` | beta_blocker | rule 4 | Systemic beta-blockers; stopping suddenly can cause rebound angina, tachycardia or infarction. Eye drops (S01ED) are not on the list. |
| `N03A` | antiepileptic | rule 4 | Antiepileptics; stopping suddenly can trigger seizures or status epilepticus. The old gabapentinoid codes in this group (N03AX12, N03AX16) are listed separately under gabapentinoid. |
| `H02A` | corticosteroid | rule 4 | Systemic corticosteroids (glucocorticoids and fludrocortisone); stopping suddenly after long use can cause adrenal crisis. Skin (D07), inhaled (R03BA), nasal (R01AD), eye (S01BA) and gut-acting (A07EA) forms are not on the list. Gut-acting corticosteroids (A07EA) are not added (owner decision 2026-11-07: low systemic exposure). |
| `N05BA` | benzodiazepine | rule 4 | Benzodiazepines (anxiolytic); stopping suddenly can cause withdrawal seizures and delirium. |
| `N05CD` | benzodiazepine | rule 4 | Benzodiazepines (hypnotic); same withdrawal risk. |
| `N03AE01` | benzodiazepine | rule 4 | Clonazepam; same withdrawal risk (also covered by the antiepileptic group). |
| `M03BX07` | benzodiazepine | rule 4 | Tetrazepam, a benzodiazepine coded as a muscle relaxant (withdrawn in the EU); same withdrawal risk. |
| `N06A` | antidepressant | rule 4 | Antidepressants; stopping suddenly can cause discontinuation syndrome, and with MAO inhibitors and tricyclics severe rebound effects. |
| `C02AC01` | clonidine | rule 4 | Clonidine (tablets and patches); stopping suddenly can cause rebound hypertensive crisis. |
| `N02CX02` | clonidine | rule 4 | Clonidine coded for migraine prevention; same rebound risk. |
| `C02AC` | central_alpha_agonist | beyond rule 4, confirmed | Other centrally acting alpha-2 agonists (guanfacine, moxonidine, rilmenidine); rebound hypertension after a sudden stop is described, less often than with clonidine. |
| `N07BC04` | central_alpha_agonist | beyond rule 4, confirmed | Lofexidine; its label advises gradual reduction because blood pressure rebounds after a sudden stop. |
| `N02BF` | gabapentinoid | beyond rule 4, confirmed | Gabapentin, pregabalin, mirogabalin; sudden withdrawal can cause seizures (in people with epilepsy) and withdrawal symptoms; labels advise tapering over at least a week. |
| `N03AX12` | gabapentinoid | beyond rule 4, confirmed | Old gabapentin code still published by TİTCK. |
| `N03AX16` | gabapentinoid | beyond rule 4, confirmed | Old pregabalin code still published by TİTCK. |
| `M03BX01` | baclofen | beyond rule 4, confirmed | Baclofen; sudden withdrawal can cause hallucinations, seizures and, after intrathecal use, a life-threatening syndrome. |
| `M03BX02` | tizanidine | beyond rule 4, confirmed | Tizanidine; sudden withdrawal can cause rebound hypertension and tachycardia. |
| `N02A` | opioid | beyond rule 4, confirmed | Opioid analgesics; sudden stop in a physically dependent person causes withdrawal; the FDA warned in 2019 of serious harm after sudden opioid stops in dependent patients. |
| `N07BC` | opioid | beyond rule 4, confirmed | Opioids for opioid dependence (methadone, buprenorphine); same risk. |
| `N04B` | dopaminergic_antiparkinsonian | beyond rule 4, confirmed | Levodopa and other dopaminergic drugs; sudden withdrawal can cause a neuroleptic-malignant-like syndrome and severe worsening of parkinsonism. |
| `N05A` | antipsychotic | beyond rule 4, confirmed | Antipsychotics; sudden withdrawal can cause rebound psychosis, withdrawal dyskinesia and, with clozapine, cholinergic rebound. |
| `N05AN01` | lithium | beyond rule 4, confirmed | Lithium; sudden stop raises the risk of early relapse of mania. |
| `N05CF` | z_drug | beyond rule 4, confirmed | Z-drugs (zolpidem, zopiclone); rebound insomnia, and withdrawal seizures after high doses. |
| `N05CA` | barbiturate | beyond rule 4, confirmed | Barbiturate hypnotics; sudden withdrawal can cause seizures and delirium. |

## 5. Rows where I am uncertain

The judgement calls below were confirmed by the owner on 2026-11-07 (section 6) unless a
decision there changed them.

- **Rows 2, 14, 38, 53, 61, 64 (`antihypertensive`).** Chapters C02, C03, C07, C08, C09. Left out:
  pulmonary-hypertension drugs (C02KX), vasopressin antagonists (C03X), antianginal non-selective
  calcium channel blockers (C08E), and prostate-only alpha-1 blockers (G04CA). Loop diuretics and
  MRAs used for heart failure stay in. The same class serves as row 2's index.
- **Rows 3, 4 (beta-blocker index).** PIPC says "particularly lipophilic e.g., propranolol"; I kept
  all systemic beta-blockers rather than only lipophilic ones.
- **Row 4.** No eye-drop extension (owner decision: the only source is a letter).
- **Row 7 (`diuretic` as index).** Potassium-sparing diuretics are included although gout is mainly
  a thiazide and loop effect.
- **Row 9 (`pain_reliever`).** Muscle relaxants (thiocolchicoside, cyclobenzaprine), common for
  muscle pain in Türkiye, are left out. Gabapentinoids are left out.
- **Row 10 (`mineral_supplement`).** PIPC does not name the mineral. I read it as calcium,
  magnesium, zinc and selenium; potassium, sodium and fluoride are left out.
- **Row 11 (`quinine`).** Hydroquinine (M09AA01), used for cramps in some EU countries, is left out.
- **Rows 12, 25, 59 (`sleep_agent`).** Includes benzodiazepine anxiolytics, trazodone and the OTC
  sleep aids diphenhydramine and doxylamine. Mirtazapine, low-dose doxepin and quetiapine are left
  out.
- **Rows 15, 16, 58 (`anticonvulsant`).** The old gabapentinoid codes N03AX12 and N03AX16 are
  excluded so Turkish and US gabapentinoid products behave the same; WHOCC no longer lists them
  under N03AX, but TİTCK still publishes them (44 and 162 rows). As marker (row 58), benzodiazepines
  given acutely for a seizure are not included, apart from clonazepam.
- **Row 20 (`sedative`).** Anxiolytics and hypnotics plus clonazepam; buspirone, melatonin agonists
  and orexin antagonists excluded. Mirtazapine left out.
- **Rows 21, 63 (`antiarrhythmic`).** Class I and III antiarrhythmics plus sotalol. Other
  beta-blockers, verapamil, diltiazem and digoxin are left out because they are mostly started for
  other reasons.
- **Rows 23, 33 (`cholinesterase_inhibitor` as marker).** Memantine is left out (PIPC names
  cholinesterase inhibitors; ThinkCascades also accepts memantine).
- **Row 27.** Bismuth subsalicylate has no ingredient-level code; not matchable.
- **Rows 28, 42, 47 (`antidiarrheal`).** Probiotics (A07FA) and gut anti-infectives (nifuroxazide,
  common in Türkiye) are left out.
- **Row 29 (`antihistamine`).** Ipratropium nasal spray is left out because PIPC names
  antihistamines. Trimethobenzamide is excluded (it is an antiemetic coded with antihistamines).
- **Rows 41, 62 (`antifungal_genital`).** Skin antifungal creams (D01AC) are included for male
  genital candidiasis; they are also used for athlete's foot, so unrelated matches are possible.
  Terbinafine and griseofulvin are left out.
- **Row 45 (`anticholinergic_antiemetic`).** Scopolamine, dimenhydrinate, promethazine, cyclizine,
  meclizine; my selection.
- **Row 46 (`antidopaminergic_antiemetic`).** Domperidone is kept although extrapyramidal effects
  are uncommon; promethazine is left out.
- **Row 48 (`vitamin_supplement`).** Vitamin D only; calcium left out because PIPC writes "vitamin".
- **Row 49.** Drug B text reading: decided by the owner (vitamin B12, magnesium, oral iron).
- **Row 50 (`bisphosphonate`).** Infusion-only pamidronate and zoledronate excluded. Ibandronate
  and clodronate have oral and injected forms under one code, so an injected product still matches.
- **Rows 51-54 (`nsaid`).** Analgesic salicylates (N02BA) are included; low-dose aspirin coded as an
  antiplatelet (B01AC06) is not, although it causes gastric bleeding (row 51).
- **Row 54 (`heart_failure_agent`).** Limited to loop diuretics, MRAs, digoxin, ivabradine and
  vericiguat. ACE inhibitors, ARBs, sacubitril-valsartan, beta-blockers and SGLT-2 inhibitors are
  left out.
- **Row 56 (`vestibular_suppressant`).** Betahistine and cinnarizine are included (common for
  dizziness, and ThinkCascades gives betahistine as an example); benzodiazepines are left out.
- **Row 57.** Saliva substitutes have no ingredient-level code; not matchable.
- **Row 58 (`carbapenem`).** Imipenem's only code is the combination code J01DH51, so imipenem will
  not match until resolution gives the imipenem ingredient its own code. PIPC names imipenem.
- **Row 65 (`iron_oral`).** B03AB02 is excluded because Wikidata puts it on intravenous iron
  sucrose; the oral form has 0 TİTCK rows.
- **Codes verified on WHOCC but absent from the local artifacts** (no TİTCK row, no Wikidata item
  in the extract): oteseconazole J02AC06, ibrexafungerp J02AX07, levomilnacipran N06AX28. They are
  correct codes but match nothing today.
- **Codes first taken from Wikidata** (39 rows, 28 codes) were checked on their WHOCC group pages on
  2026-11-07 at the owner's request; all match the intended substance and now have basis
  `whocc_lookup`.

## 6. Owner decisions (2026-11-07)

The questions of the draft and the owner's answers. All are applied to the files.

1. **Row 49 reading.** Drug B is published as "Vitamin or Mineral Deficiency". *Decision:* narrow
   it to the deficiencies best linked to long-term PPI use: vitamin B12 (`B03BA`), magnesium
   (`A12CC`) and oral iron (`B03AA`, `B03AB`). Calcium and vitamin D belong to the fracture
   cascade (row 48). `A11CC` and `A12AA` were removed from `ppi_deficiency_supplement`.
2. **Abrupt-stop proposals.** *Decision:* all proposed groups confirmed: `central_alpha_agonist`
   (incl. lofexidine), `gabapentinoid` (with the old TİTCK codes `N03AX12`/`N03AX16`),
   `baclofen`, `tizanidine`, `opioid`, `dopaminergic_antiparkinsonian`, `antipsychotic`,
   `lithium`, `z_drug`, `barbiturate`. A wrong "do not stop suddenly" warning is low-harm, so
   over-inclusion is the safe side. Gut-acting corticosteroids (`A07EA`) are not added (low
   systemic exposure).
3. **Row 4 extension source.** The candidate was Fraunfelder FT (Europe PMC: Fraunfelder FT, Meyer
   SM), "Sexual Dysfunction Secondary to Topical Ophthalmic Timolol", JAMA 1985;253(21):3092,
   doi:10.1001/jama.1985.03350450064016 (verified in Crossref; Europe PMC types it as a letter).
   *Decision:* no eye-drop extension for row 4, because the only source is a letter, not a
   reviewed article; the letter is not added to the paper list.
4. **ThinkCascades overlap.** Rows 5, 8, 18, 23, 53, 56 confirmed against the paper; row 23 (where
   ThinkCascades also accepts memantine) and row 56 ("vestibular sedatives") treated as the same
   cascade. *Decision:* agreed.
5. **Not-matchable roles.** *Decision:* row 57 (saliva substitute) gets no proxy (pilocarpine as a
   stand-in would be a guess); it stays not matchable and is shown as "cannot be checked". Row 27
   (bismuth subsalicylate) likewise. Imipenem (row 58): a `drug-resolution` follow-up is
   recorded so the imipenem ingredient gets an ingredient-level carbapenem code.
6. **Broad marker choices.** *Decision:* all confirmed as drafted: sleep agents including
   benzodiazepine anxiolytics, trazodone and OTC antihistamines (rows 12, 25, 59); heart-failure
   agents limited to diuretics and a few others (row 54); antiarrhythmics limited to class I/III
   plus sotalol (rows 21, 63); skin antifungal creams for rows 41 and 62; vitamin D without
   calcium (row 48); low-dose aspirin outside the NSAID class (rows 51-54; otherwise every
   intentional aspirin-plus-PPI prophylaxis would be flagged as a cascade); muscle relaxants
   outside pain relievers (row 9); benzodiazepines outside vestibular suppressants (row 56).
7. **Wikidata-based codes.** *Decision:* verify each against the public WHOCC index pages like the
   others. Done (section 1).

## 7. Synonym proposals from the coverage report (pending owner review)

Task 12, drafted by the pharmacologist agent on 2026-11-07 from the coverage report for rule base
`590f454d…` and dataset `e6798def…`. `data/ingredient_synonyms.csv` is **not changed**. The full
list, with the TİTCK names, evidence per row and draft CSV rows, is in the git-ignored file
`.data/cascades/synonym-proposals.md`; this section gives counts, QIDs and codes only.

**102 proposed rows: 30 US (20 Wikidata items), 72 TİTCK (41 items).** Each was simulated through
code selection (drug-resolution §5.5) and the class patterns. A row is proposed only where the
name is the same active substance as the item: a salt, ester, hydrate, solvate, grade, misspelling
or glued spelling. Step 0 matches the exact folded name, so each spelling needs its own row.
"Products" counts listings per name (TR; US Rx / OTC). "Homeopathic" means openFDA strengths in
homeopathic units.

| # | Name(s) | QID | label_en | Code → class | Products | Confidence |
|---|---|---|---|---|---|---|
| 1 | lithium carbonate, lithium citrate (US) | Q152763 | lithium | N05AN01 → `lithium` (row 37; abrupt-stop) | Rx 78 / OTC 71 (70 homeopathic) | high |
| 2 | methylprednisolone acetate, sodium succinate, hemisuccinate (US; ambiguous today with the aceponate item) | Q417222 | methylprednisolone | H02AB04 → `corticosteroid_systemic` | Rx 91 | high |
| 3 | atorvastatin calcium propylene glycol solvate (US) | Q668093 | atorvastatin | C10AA05 → `statin` | Rx 67 | high |
| 4 | sodium phosphate monobasic, 4 spellings (US) | Q3249706 | sodium phosphates | A06AG01 → `laxative`; IV products get B05XA09, no class | Rx 61 / OTC 6 (laxative: Rx 15, OTC 6) | high |
| 5 | sodium phosphate dibasic, 4 spellings (US) | Q3249706 | sodium phosphates | as row 4 | Rx 30 / OTC 143 (137 homeopathic) | conditional on a homeopathic exclusion |
| 6 | alendronate sodium (US) | Q420057 | alendronic acid | M05BA04 → `bisphosphonate` | Rx 38 | high |
| 7 | psyllium husk (US) | Q430675 | Psyllium | A06AC01 → `laxative` | OTC 39 | high |
| 8 | sennosides a and b (US) | Q502327 | senna glycoside | A06AB06 → `laxative` | OTC 28 | high |
| 9 | dapagliflozin propanediol (US) | Q409898 | dapagliflozin | A10BK01 → `sglt2_inhibitor`, `antihyperglycemic` | Rx 19 | high |
| 10 | prochlorperazine edisylate (US) | Q2359690 | prochlorperazine | N05AB04 → `antiemetic`, `antipsychotic`, `antidopaminergic_antiemetic` | Rx 18 | high |
| 11 | methylcellulose 4000 mpa s (US) | Q416312 | methyl cellulose | A06AC06 → `laxative` | OTC 18 | high |
| 12 | diclofenac epolamine (US, topical patch) | Q244408 | Diclofenac | M02AA15 → `nsaid_marker`, `pain_reliever` (not the index `nsaid`) | Rx 15 | high |
| 13 | ertugliflozin pidolate (US; flagged as unsplit today) | Q27077223 | ertugliflozin | A10BK04 → `sglt2_inhibitor` | Rx 8 | high |
| 14 | risedronate sodium hemi pentahydrate (US) | Q408724 | risedronic acid | M05BA07 → `bisphosphonate` | Rx 6 | high |
| 15 | aliskiren hemifumarate (US) | Q414904 | aliskiren | C09XA02 → `antihypertensive` | Rx 6 | high |
| 16 | valproate sodium (US) | Q240642 | valproic acid | N03AG01 → `anticonvulsant` | Rx 5 / OTC 16 (all homeopathic) | medium |
| 17 | 6 TİTCK names | Q3249706 | sodium phosphates | A06AG01 → `laxative` (34); B05XA09 for electrolyte products | TR 56 | high |
| 18 | 2 TİTCK names | Q422092 | alginic acid | A02BX13 (the code every product publishes) → `gastroprotective` | TR 43 | high |
| 19 | 9 TİTCK names | Q3492616 | Insulin Lispro | A10AD04 (published) → `antihyperglycemic` | TR 14 | medium |
| 20 | 3 TİTCK names | Q502327 | senna glycoside | A06AB06 (published) → `laxative` | TR 13 | high |
| 21 | 5 TİTCK names | Q252251 | cyanocobalamin | B03BA01 → `ppi_deficiency_supplement` | TR 8 | high |
| 22 | 2 TİTCK names | Q411347 | amlodipine | C08CA01 → `ccb`, `antihypertensive` | TR 7 | high |
| 23 | 3 TİTCK names | Q139347 | cholecalciferol | A11CC05 → `vitamin_supplement` | TR 7 | high |
| 24 | 1 TİTCK name | Q4737384 | Aluminium glycinate | A02AB07 → `gastroprotective` | TR 6 | high |
| 25 | 1 TİTCK name | Q388801 | furosemide | C03CA01 → `diuretic`, `heart_failure_agent`, `antihypertensive` | TR 6 | high |

The other 39 TİTCK rows (misspellings of ARBs, NSAIDs, antihistamines, paracetamol,
guaifenesin and others; 1 to 5 products each) and 5 US rows (diazoxide choline, ibuprofen lysine,
three corticosteroid esters) are in the data-directory file.

**Most important finding.** In the US the `lithium` class has 0 Rx products; its 14 OTC products
are all homeopathic. Row 37 is therefore not on the cannot-fire list but fires in the US only on
homeopathic products. Row 1 of the table fixes it. The report's trigram hints missed this name
and the atorvastatin solvate (follow-up for `coverage.py`: also hint when a member's name is a
whole word of the unmapped name).

**Rules that cannot fire in a region.** None is fixed by a synonym.

| Rule | Region | Reason |
|---|---|---|
| pipc:11 statin → quinine | TR | No quinine product in the TİTCK list (no string, no code P01BC01). In the US, 48 of the 49 OTC quinine products are homeopathic |
| pipc:14 midodrine → antihypertensive | TR | No midodrine product in the TİTCK list (US: 109 Rx) |
| pipc:27 cholinesterase inhibitor → bismuth subsalicylate | TR, US | Not matchable by design (no ingredient-level code; decision 5), although products exist (US 247 OTC, TİTCK 5). Only matching by ingredient identity, a design change, would make it checkable |
| pipc:36 flunarizine → antidepressant | US | Only one bulk-ingredient listing in openFDA; no finished product |
| pipc:44 rosiglitazone → diuretic | TR, US | No TİTCK product; openFDA has only two bulk-ingredient listings (row 43 still covers pioglitazone) |
| pipc:57 urinary anticholinergic → saliva substitute | TR, US | Not matchable by design (no ATC code; no proxy, decision 5) |

**Owner decisions needed (not proposed).** Dimenhydrinate (US 40 listings, TİTCK 4) has no
Wikidata item; mapping it to diphenhydramine (R06AA02) would put it in `sleep_agent` and miss the
vestibular and antiemetic classes, which list R06AA11, so it needs its own ingredient key. US
"colchiceine" (Rx 6) sits on products named colchicine, probably a data error. Prodrugs
(fosaprepitant Rx 27, gabapentin enacarbil, aripiprazole lauroxil) and the elemental names iron,
zinc and selenium are not mapped. No item exists for vericiguat, finerenone (both already listed in
`heart_failure_agent`), human insulin, activated charcoal, iron protein succinylate, butalbital or
oxymorphone. Five TİTCK names on local products (mouth gels, throat sprays, an antiseptic, a cream without a code) are not proposed: their
group-level product codes would fall back to all of the item's codes and place them in systemic
classes. Follow-ups: homeopathic strengths are counted as the substance today (2,991 US OTC
products with a mapped ingredient). `ppi_deficiency_supplement` lacks the B03AB02 exclusion that
`iron_oral` has. Codeine's item carries only R05DA04, so codeine never gets the opioid
abrupt-stop warning.

**Rejected as noise.** Of 493 hints, the rest were other substances that share trigrams (methyl,
trolamine and ethylhexyl salicylate, thymol, aspartame, quinine → quinidine,
butabarbital → butethal), homeopathic listings (bromides, phosphates, creosote, Polygala), ATC text or
combination fragments, or names already keyed whose code the route map excludes (glycerin and
polyethylene glycol 400 eye drops, mineral oil, ophthalmic zinc sulfate). Counts per class are in the
data-directory file.
