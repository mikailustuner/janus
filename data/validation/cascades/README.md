# Cascade detection reference set

Reference standard for the pre-registered study in `docs/research/cascade-validation-protocol.md`
(sections 3, 5 and 7). Built on 2026-11-13 by an automated literature step that had no access to the
Janus cascade rule base, engine, tests or output (protocol 3.4). No human has reviewed the set.
**Expert review has not yet been done.**

## Files

| File | Rows | What it holds |
|---|---|---|
| `positive_pairs.csv` | 217 | Published cascades at ingredient level (A, event, B), deduplicated on (A, B) |
| `positive_candidates.csv` | 314 | Every cascade row read from the sources, with include/exclude decision, reason and the ingredient chosen |
| `positive_extraction.py` | – | The same 314 rows as data, as extracted from the source tables (input of `build_positives.py`) |
| `build_positives.py` | – | Applies the ingredient-choice and duplicate rules of protocol 3.1 |
| `negative_pairs.csv` | 434 | Two constructed negatives per positive pair (protocol 3.2) |
| `build_negatives.py` | – | Deterministic negative draw, seed 20261113 |
| `us_label_indications.json` | 1215 names | Cache of US label indication text (openFDA, CC0) used by `build_negatives.py` |
| `cascade_cases.csv` | 57 | Cascade case rows from 51 open-licence PMC case reports |
| `comparison_cases.csv` | 50 | Comparison cases (age ≥ 65, full medication list, no cascade described) |
| `sources.csv` | 106 | Every source: 5 for the positive pairs, 51 cascade case reports, 50 comparison case reports |
| `MANIFEST.sha256` | – | SHA-256 of every file above |

Only facts are recorded from the literature (drug A, event, drug B, citation, location in the source); no
article text is copied. `us_label_indications.json` holds US label indication text (public domain, CC0) as
input for the negative draw.

## 1. Positive pairs (protocol 3.1)

### Sources

Search: Europe PMC REST API, 2026-11-13, `resultType=core`:

1. `("prescribing cascade" OR "prescribing cascades") AND (PUB_TYPE:"Review" OR TITLE:"review")` – 226 hits.
2. `("prescribing cascade" OR "prescribing cascades") AND ("sequence symmetry" OR "symmetry analysis")` – screened together with 1.
3. `DOI:"10.1007/s40266-022-00964-9"` (ThinkCascades), `TITLE:"prescribing cascades" AND (TITLE:"high-throughput" OR TITLE:"sequence symmetry")` – 9 hits.

Titles were screened for systematic or scoping reviews of prescribing cascades, published cascade lists and
PSSA studies. Full text (Europe PMC `fullTextXML`) was requested for 14 documents; 10 were available and 5 were used:

| source_id | Kind | Document | Rows read | Rows included |
|---|---|---|---|---|
| DOH22 | systematic_review | Doherty et al. 2022, Pharmacol Res Perspect (PMC9485823), Tables 1–2 | 172 | 139 |
| ADR23 | systematic_review | Adrien et al. 2023, Drugs Aging (PMC10682291), Table 2 | 81 | 77 |
| CHEN23 | scoping_review | Chen et al. 2023, Front Pharmacol (PMC10350531), Table 1 | 47 | 39 |
| TC22 | list | McCarthy et al. 2022, ThinkCascades, Drugs Aging (PMC9477172), Table 2 (the nine retained cascades) | 9 | 9 |
| OMA24 | pssa | Omata et al. 2024, Drugs Real World Outcomes (PMC11365892), Tables 3–4 | 5 | 3 |

Documents retrieved and not used:

- Rochon et al. 2025 (PIPC, PMC12712104): excluded by protocol; not opened.
- Carollo et al. 2026 umbrella review (PMC13149699): cites the PIPC paper as a source for several of its rows, so it
  counts as partly derived from PIPC and was excluded as a whole.
- Gilmore et al. 2026 PSSA (PMC13038655): its dyads were chosen in part from the PIPC list; excluded as derived.
- Doherty et al. 2026 (PMC13107699): applies ThinkCascades; the original ThinkCascades paper is used instead.
- Newby et al. 2026 high-throughput SSA (PMC13293265): signals are not tied to a named event per drug pair.
- Ndai et al. 2025 (two papers), Doherty et al. 2025 (Ann Fam Med) and Rochon & Gurwitz 1997 (BMJ): no full text
  available from Europe PMC.
- Adrien et al. 2025 correction (PMC12254081): correction notice; Table 2 of the original was used.

Doherty 2022, Adrien 2023 and Chen 2023 review overlapping primary studies, so `n_sources` counts documents,
not independent data sets. DOH22, ADR23, CHEN23 and TC22 were all published before the PIPC paper (2025).

### Inclusion rules applied to each table row

- Drug A, the event and drug B are named, and B is a drug (rows whose outcome mixes a drug with a diagnosis were excluded).
- For a row reporting a study result: a positive association. PSSA rows need an adjusted sequence ratio with a
  lower 95 % (or 99 %) bound above 1; other designs need a significant positive estimate. Rows with crude ratios
  only, null or inverse results, or descriptive counts only were excluded.
- Signals from hypothesis-free screening (King 2020, Wahab 2016, Hallas 2018, Hellfritzsch 2018, Tsiropoulos 2009)
  were excluded: the source reports a statistical signal, not that A causes the event.
- Fixed-dose combinations as A (C09BA, levodopa/benserazide, imipenem/cilastatin) and herbal products (no ATC code) were excluded.
- Case-derived routes in Chen 2023: only steps where a single A, an event and B are named; steps naming two or more
  possible culprits, prophylaxis, or an unclear B were excluded.
- ThinkCascades: only the nine cascades retained in the final tool.

Exclusions at row level (47 of 314): no positive association 9; lower bound not above 1 7; hypothesis-free
screening 8; crude ratio only or not adjusted 3; descriptive only 3; several drugs named as A 4; B class with no
ATC group or not named 5; fixed-dose combination 3; A not a drug or no ATC code 3; B includes a diagnosis 1;
lower bound not above 1 for a whole group 1. The per-row reason is in `positive_candidates.csv`.

### Ingredient choice (protocol 3.1) as implemented

`build_positives.py` applies the rule to each included row and each side (A and B):

1. **ingredient named in source** – the ingredient is used; its ATC code is the one within the ATC class the source
   gives or the context implies (e.g. timolol S01ED01 in glaucoma rows).
2. **class: ingredient named first** – the class is mapped to its ATC group (the mapping is in
   `positive_extraction.py`, column 7 / 11, e.g. loop diuretics `C03C`). The ingredient of that group named first is
   taken, looking first in the same table row and then in the whole article text (abstract, body, tables; not the
   reference list). The text search is mechanical: it takes the earliest position of any name or English alias of a
   group member, skips a mention inside a longer name of another ingredient ("tiotropium bromide" is not "bromide"),
   skips counter-ion words, and skips a name the source marks as excluded ("excluding edoxaban").
3. **class: lowest ATC code in class** – when no group member is named anywhere in the source.

Tallies over the 217 pairs (branch of the first source row that produced the pair):

| Side | ingredient named | class: named first (same row) | class: named first (source text) | class: lowest ATC code |
|---|---|---|---|---|
| A | 94 | 9 | 64 | 50 |
| B | 103 | 5 | 81 | 28 |

52 pairs have both sides named as ingredients in the source. Pairs by source (a pair can have several):
DOH22 121, ADR23 71, CHEN23 36, TC22 9, OMA24 3. Pairs with 1 / 2 / 3 sources: 199 / 13 / 5.

ATC codes come from the Wikidata ingredient snapshot of 2026-11-07 (CC0), single-ingredient 7-character codes,
combination codes (5th level 50–99, or labels with "/" or "and") removed. Two ingredients missing there were
looked up in the WHO ATC/DDD index on 2026-11-13: carbamazepine N03AF01, mirogabalin N02BF03 (column `atc_reference`).

`positive_pairs.csv` columns: `class_a_label` / `class_b_label` hold the class as named in the source with its ATC
group when the side was class-named, otherwise the ingredient's 4th-level ATC code. `adverse_event` joins the
distinct events of all source rows with " / ". `locators` give `source: Table N, row R (label)`; row numbers count
the table's body rows, including section-heading rows.

### Judgement calls and doubts (positive pairs)

- The mechanical "named first" search can pick an ingredient mentioned in another context. Known cases:
  timolol (mentioned for glaucoma) became the first-named beta blocker in DOH22, giving timolol C07AA06 for
  systemic beta-blocker cascades (timolol → furosemide, prochlorperazine, paroxetine, sildenafil);
  rofecoxib became the first-named NSAID in DOH22; paroxetine the first-named antidepressant in DOH22.
- The lowest-ATC branch yields old or rarely used drugs: alprenolol, phenylbutazone, quinethazone, pentobarbital,
  rescinnamine, methylthiouracil, ethylmorphine, dyphylline, epinephrine (inhalant), zimelidine (withdrawn),
  insulin (human), liquid paraffin, etidronic acid, amphotericin B. They are kept because the rule is fixed.
- Class-to-ATC mappings that needed a choice: "antifungal" for genital infection → J02A, G01AF, D01A; "LAMA or LABA"
  → R03BB, R03AC (Adrien gives R03BB only, used as given for ADR23); "medications for LUTS" → G04BD, G04CA;
  "antihypertensives" → C02 (as coded by Adrien) or C02, C03, C07, C08, C09 (ThinkCascades); "sleep agents" → N05C;
  "vestibular sedatives" → N07CA, R06A, N05BA; "PDE5 inhibitors" → G04BE03/08/09/10/11; "gabapentinoids" → N02BF.
- Diphenhydramine keeps the code Adrien gives (D04AA32, topical) for the constipation cascade and R06AA02 for the
  Chen route; pairs are deduplicated on names, so each pair carries one code.
- Several Chen 2023 steps come from single case reports; they meet the inclusion rule but rest on weaker evidence
  than the PSSA rows.

## 2. Negative pairs (protocol 3.2)

`build_negatives.py`, seed 20261113, two negatives per positive pair, 434 rows. For each positive pair in
`pair_id` order, B′ is drawn uniformly (one `random.Random(20261113)` stream) from the single-ingredient
7-character ATC codes of the Wikidata snapshot that share B's first ATC level and differ from B at the third
level (first four characters). B′ is drawn again when:

- (a) an adverse event listed for A in OnSIDES v3.1.1 appears in the indications text of a US label of B′
  (`a_event_is_indication(<event>)`): A's events are the MedDRA terms of all single-ingredient OnSIDES labels of A
  (US, EU, UK, JP), matched case-insensitively as whole words in the `indications_and_usage` text;
- (b) (A, B′) is a positive pair (`positive_pair`, by name or by ATC code pair).

Recorded judgement calls, also redraws: B′ equal to A or to B (`same_as_a`, `same_as_b`); (A, B′) already drawn
(`duplicate_negative`); no single-ingredient US label of B′ found (`no_us_label`), because rule (a) cannot be
checked without one. Drawing stops at the first valid B′ or after 200 draws.

US labels: openFDA drug label API (CC0), searched by `openfda.generic_name`, keeping up to five
single-ingredient labels per name (sorted by set_id). The repository's local openFDA artifact holds labels for
11 drugs only, so it was not used. Every lookup is kept in `us_label_indications.json` (1215 names, 468 with
indications text, retrieved 2026-11-13). OnSIDES and Wikidata were read from the Janus open-data artifact
snapshots (OnSIDES v3.1.1 release 2026-04-22; Wikidata ingredients retrieved 2026-11-07). Neither is part of the
cascade rule base.

Result: 434 negatives, none without a valid draw; draws per negative 1–62 (median 3). Redraw reasons over all
negatives: no US label 1216, A event is an indication of B′ 378, duplicate 9, positive pair 3, same as A 1,
same as B 1. B′ first ATC level: N 122, A 90, G 90, C 46, R 28, H 20, P 16, J 10, M 6, B 4, D 2.

For 12 drugs A no OnSIDES events were found (no single-ingredient OnSIDES label): alprenolol, amezinium
metilsulfate, bendroflumethiazide, dyphylline, fesoterodine, isosorbide mononitrate, levosulpiride, mirogabalin,
phenylbutazone, quinethazone, rofecoxib, zimelidine. Their negatives were checked by rule (b) only
(`a_onsides_events` = 0). OnSIDES salt names are matched to the ingredient (lithium → lithium carbonate,
lithium citrate); valproic acid → valproate and insulin (human) → "insulin, regular, human" are set explicitly.

Reproduce (offline, from the committed cache; gives an identical `negative_pairs.csv`):

```
uv run --no-project --with pyarrow python data/validation/cascades/build_negatives.py \
  --positives data/validation/cascades/positive_pairs.csv \
  --wikidata <janus>/.data/artifacts/wikidata_ingredients/current \
  --onsides <janus>/.data/artifacts/onsides/current \
  --label-cache data/validation/cascades/us_label_indications.json \
  --out data/validation/cascades/negative_pairs.csv
```

Add `--fetch` to look up names missing from the cache (the first run used it). An offline rerun was checked to
give a byte-identical file.

Positive pairs, reproduce: export the Wikidata snapshot to JSON
(`[{qid, label: label_en, aliases: aliases_en, atc: sorted(atc_codes), rxcui: rxcuis}]`), download the five
sources from `https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML` into one folder, then
`python3 data/validation/cascades/build_positives.py <wd.json> <xml folder> <out folder>`.

## 3. Cascade cases (protocol 3.3)

Search: Europe PMC REST API, all queries run 2026-11-13 (`resultType=core`, cursor paging); full text from
`fullTextXML`. The queries combine generic cascade terms with drug-event-drug combinations taken from the
cascade literature; the 50 logged queries are listed in the appendix below with their hit counts.

Flow:

- Records retrieved, de-duplicated by PMCID: 7417.
- Excluded because the Europe PMC licence field was not an open Creative Commons licence: 158.
- Screened on title and abstract: 7259. Automated filter: title or abstract must name the A term, the B term and
  the event of the query; for the generic queries, case-report publication type or a single-patient abstract.
  Survivors were shortlisted by an automated reading of title and abstract.
- Full text assessed: 114. Included: 51 reports, 57 rows. Excluded: 63 –
  not an A → event → B sequence (event handled only by stopping or switching A, no new drug, or culprit not stated) 29;
  short rescue treatment while A was being withdrawn 14; no usable medication list 11;
  authors judged the event not drug-induced 2; not a case report 2; B not a new drug 1;
  B not named as an ingredient 1; retrieved but not assessed once the target was reached 3.

Licences of the 51 reports (from each article's own licence statement): CC BY 4.0 19, CC BY 3.0 3, CC BY 2.5 1,
CC BY without version 7, CC BY-NC 4.0 5, CC BY-NC 3.0 7, CC BY-NC-SA 3.0 1, CC BY-NC-ND 4.0 8.

Rules and judgement calls:

- A qualifies when the authors attribute an event to drug A and a new drug B is started for that event. This
  includes events misread as a new condition (CC002, CC005, CC025, CC027, CC028, CC029) and recognised adverse
  effects treated with B (e.g. extrapyramidal symptoms → anticholinergic, tardive dyskinesia → valbenazine,
  lithium-induced nephrogenic diabetes insipidus → thiazide, amiloride or desmopressin).
- Rescue treatment of one dose or a few days given while A was stopped was excluded. B continued as ongoing
  therapy was kept even when A had been stopped first (CC006, CC007, CC033, CC036–CC039, CC046, CC047, CC056);
  a detector reading the medication list at that time may not see A as current.
- Several drugs for one event: `expected_b` is the first or main one named by the authors; alternatives are in
  `locator`. Several possible culprits: `expected_a` is the one the authors name; co-suspects are in `locator`.
- Age given only as a decade or "middle-aged" is recorded as `unknown` (CC010, CC044, CC049).
- Four reports give a second cascade in the same patient (CC009, CC012, CC014, CC043) and two give a second
  patient (CC051, CC055).

Doubts: partial medication lists (CC023, CC031, CC036, CC044, CC047, CC049, CC054, CC055); weak or suggested
causality (CC005, CC029, CC041, CC043, CC052); A chosen among several antipsychotics (CC018, CC019, CC020, CC042);
B a supplement, topical or bone-protection drug (CC010, CC012, CC032, CC033, CC052, CC053); CC026 age taken from
the title; CC002 start year of A differs between table and text (both before B). The set leans towards
psychiatric drugs; only 10 of the 57 rows are patients aged 65 or over (44 younger, 3 unknown). Protocol 3.3
sets no age limit for cascade cases, but the set is not an older-adult sample.

## 4. Comparison cases (protocol 3.3)

Search: Europe PMC REST API, 2026-11-13, one query (hit count 2900; the first 600 records in Europe PMC
relevance order were taken):

```
PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y AND (LICENSE:"cc by" OR LICENSE:"cc0" OR LICENSE:"cc by-nc"
OR LICENSE:"cc by-nc-nd" OR LICENSE:"cc by-sa" OR LICENSE:"cc by-nc-sa") AND ("65-year-old" OR "66-year-old"
OR ... OR "99-year-old") AND ("his medications included" OR "her medications included" OR
"home medications included" OR "medications included" OR "medication list" OR "current medications"
OR "home medications") AND PUB_YEAR:[2015 TO 2026]
```

Flow: 600 records → 188 removed on title (drug-related topic words such as induced, toxic, adverse, overdose,
interaction, or no PMCID) → 412 full texts downloaded → the first 170 in relevance order screened (screening
stopped once enough cases were eligible) → 4 not parseable, 3 aged under 65, 13 without an adult age in the
case section → 150 assessed: 50 included; 16 eligible but not used (kept as reserves, to cap at 50 and reduce
cardiology); 32 excluded because the topic was a drug adverse event or an adverse effect was treated with
another drug (one of them, PMC13022825, was found at a final check and replaced by PMC12718630);
1 excluded for an ambiguous licence statement; about 51 excluded for no full medication list (fewer than three
named medicines, classes only) or ambiguity – this last figure is the remainder, not an item-by-item count.

Inclusion: age ≥ 65 from the case text; at least three named medicines in the list at presentation (a
combination product counts once); the report describes no drug adverse effect treated with another drug; an
open CC licence as stated in the article. Licences: CC BY 4.0 34, CC BY-NC 4.0 8, CC BY-NC-ND 4.0 7,
CC BY-NC 3.0 1. Topics: oncology 8, surgery and gastroenterology 8, cardiology 6, infection 5, nephrology 5,
endocrinology and bone 5, orthopaedics and falls 4, dermatology 3, neurology 2, pulmonary 2, psychiatry 1,
vascular surgery 1.

Doubts: CM027 licence differs between the article (CC BY-NC-ND 4.0, recorded) and Europe PMC metadata
(CC BY-NC-SA); CM039 adrenal insufficiency after a short prednisolone course, attributed by the authors to a
pituitary cyst; CM049 lithium stopped for no indication and alprazolam switched to a diazepam taper (medicine
changes, not a cascade); CM043 later skin treatments stopped for intolerance, no new drug for it; CM031 list
includes medicines given at dialysis; CM022 one entry is a class ("nonsteroidal anti-inflammatory drugs");
CM011 age and list from the first presentation (2017); CM046 only case 1 of a two-case report. Almost all
reports are from 2025–2026 because of the relevance ordering. A report that does not describe a cascade does not
prove there is none (protocol 4): several lists contain pairs that a detector may flag.

## 5. Targets (protocol 5)

| Item | Target | Achieved |
|---|---|---|
| Positive pairs | ≥ 80 | 217 |
| Negative pairs | 2 per positive | 434 |
| Cascade cases | ≥ 40 | 57 rows from 51 reports |
| Comparison cases | ≥ 40 | 50 |

No shortfall.

## 6. Known limits

- All steps (search, screening, extraction, rule application) were automated. No clinician or pharmacist has
  checked any row. Expert review has not yet been done.
- Published cascades over-represent well-known ones (protocol 7). Three of the five positive sources review
  overlapping primary studies.
- The ingredient rule turns many class-level cascades into one ingredient each; with the mechanical "named
  first" search and the lowest-ATC fallback, some chosen ingredients are rarely used or withdrawn, or were
  named in the source in another context (section 1).
- ATC codes come from Wikidata, not from the WHO ATC index itself (two codes were checked in the WHO index).
  Wikidata may lack or mislabel codes; ingredients without a Wikidata ATC code cannot be drawn as B′.
- Negative pairs are constructed (protocol 7). Rule (a) depends on OnSIDES, which is extracted from labels by a
  language model and misses or mislabels some effects, and on whole-word matching of MedDRA terms in label
  indication text; synonyms that differ in wording are missed. Twelve drugs A had no OnSIDES events.
  Requiring a US label for B′ means B′ is always a drug marketed in the US.
- Cascade cases lean towards psychiatric drugs and younger patients; some medication lists are partial.
  Comparison cases are almost all from 2025–2026.
- Europe PMC licence metadata and the article's own licence statement differ for at least one report; the
  article statement was recorded.

## Appendix: cascade case queries (Europe PMC, 2026-11-13, `resultType=core`)

| id | hits | query |
|---|---|---|
| q1 | 621 | ("prescribing cascade" OR "prescription cascade" OR "prescribing cascades" OR "medication cascade" OR "drug cascade") AND OPEN_ACCESS:y |
| q2 | 34 | (amlodipine OR nifedipine OR felodipine OR "calcium channel blocker") AND (edema OR oedema) AND (furosemide OR diuretic) AND "prescribing" AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| q3 | 35 | metoclopramide AND (parkinsonism OR "extrapyramidal") AND (levodopa OR "carbidopa") AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| q4 | 13 | (donepezil OR rivastigmine OR galantamine OR "cholinesterase inhibitor") AND (incontinence OR "overactive bladder") AND (oxybutynin OR tolterodine OR solifenacin OR antimuscarinic OR anticholinergic) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| q5 | 45 | lithium AND tremor AND (propranolol OR primidone) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| q6 | 124 | (gabapentin OR pregabalin) AND (edema OR oedema) AND (furosemide OR diuretic) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| q7 | 23 | cascade AND ("adverse drug reaction" OR "adverse drug event" OR "side effect") AND (deprescribing OR polypharmacy) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| q8 | 23 | (antipsychotic OR haloperidol OR risperidone OR olanzapine) AND (parkinsonism OR "drug-induced parkinsonism") AND (levodopa OR "carbidopa") AND "misdiagnosed" AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| q9 | 22 | ("ACE inhibitor" OR lisinopril OR enalapril OR ramipril OR perindopril) AND cough AND (codeine OR dextromethorphan OR antitussive OR "cough syrup" OR benzonatate) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| q10 | 27 | (thiazide OR hydrochlorothiazide OR chlorthalidone OR furosemide) AND gout AND (allopurinol OR colchicine OR febuxostat) AND "drug-induced" AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| q11 | 9 | (flunarizine OR cinnarizine OR prochlorperazine) AND parkinsonism AND (levodopa OR "anti-parkinson") AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| q12 | 82 | cascade AND (polypharmacy OR "older adult" OR elderly) AND ("drug-induced" OR "medication-induced") AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r1 | 54 | ("drug-induced parkinsonism" OR "drug induced parkinsonism") AND (levodopa OR carbidopa OR "dopamine agonist") AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r2 | 230 | ("ACE inhibitor" OR "angiotensin-converting enzyme inhibitor" OR lisinopril OR enalapril OR ramipril OR perindopril OR captopril) AND cough AND (inhaler OR asthma OR salbutamol OR albuterol OR budesonide OR fluticasone OR montelukast OR antitussive OR codeine) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r3 | 222 | amiodarone AND hypothyroidism AND (levothyroxine OR "thyroxine") AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r4 | 208 | lithium AND hypothyroidism AND (levothyroxine OR thyroxine) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r5 | 401 | (antipsychotic OR haloperidol OR risperidone OR olanzapine OR aripiprazole) AND (extrapyramidal OR dystonia OR parkinsonism) AND (benztropine OR trihexyphenidyl OR biperiden OR procyclidine) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r6 | 33 | clozapine AND (sialorrhea OR sialorrhoea OR hypersalivation) AND (glycopyrrolate OR glycopyrronium OR hyoscine OR scopolamine OR atropine OR amisulpride OR clonidine) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r7 | 29 | (antipsychotic OR risperidone OR haloperidol OR amisulpride OR paliperidone) AND hyperprolactinemia AND (cabergoline OR bromocriptine) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r8 | 85 | (antidepressant OR SSRI OR mirtazapine OR escitalopram OR sertraline OR venlafaxine) AND ("restless legs" OR "restless leg") AND (pramipexole OR ropinirole OR rotigotine OR gabapentin OR pregabalin OR levodopa) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r9 | 29 | (pramipexole OR ropinirole OR "dopamine agonist") AND (edema OR oedema) AND (furosemide OR diuretic OR torsemide OR hydrochlorothiazide) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r10 | 510 | (levodopa OR pramipexole OR ropinirole OR "dopaminergic") AND (hallucinations OR psychosis) AND (quetiapine OR clozapine OR pimavanserin OR risperidone OR haloperidol) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r11 | 27 | (SSRI OR fluoxetine OR sertraline OR escitalopram OR paroxetine OR venlafaxine) AND bruxism AND (buspirone OR clonazepam OR "botulinum") AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r12 | 227 | (antipsychotic OR aripiprazole OR haloperidol OR metoclopramide OR SSRI) AND akathisia AND (propranolol OR benzodiazepine OR clonazepam OR mirtazapine OR benztropine) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r13 | 68 | (metoclopramide OR antipsychotic OR haloperidol OR risperidone) AND "tardive dyskinesia" AND (valbenazine OR deutetrabenazine OR tetrabenazine) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r14 | 1 | (venlafaxine OR NSAID OR ibuprofen OR naproxen OR methylphenidate OR "pseudoephedrine") AND hypertension AND ("antihypertensive" OR amlodipine OR lisinopril) AND "drug-induced hypertension" AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r15 | 7 | (diuretic OR furosemide OR "cholinesterase inhibitor" OR donepezil) AND ("urinary incontinence" OR "urinary urgency") AND (oxybutynin OR tolterodine OR solifenacin OR mirabegron OR trospium) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r16 | 108 | (valproate OR "valproic acid" OR amiodarone OR flunarizine OR cinnarizine OR levosulpiride OR sulpiride OR lithium) AND parkinsonism AND (levodopa OR carbidopa) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r17 | 25 | (anticholinergic OR oxybutynin OR amitriptyline OR antihistamine OR diphenhydramine) AND ("urinary retention") AND (tamsulosin OR "alpha-blocker" OR alfuzosin OR doxazosin) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r18 | 72 | (antihypertensive OR doxazosin OR tamsulosin OR prazosin OR levodopa OR quetiapine) AND "orthostatic hypotension" AND (midodrine OR fludrocortisone OR droxidopa) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r19 | 155 | (donepezil OR rivastigmine OR galantamine) AND (anticholinergic OR oxybutynin OR "urinary") AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r20 | 765 | ("calcium channel blocker" OR amlodipine OR nifedipine OR lercanidipine OR felodipine) AND ("peripheral edema" OR "pedal edema" OR "ankle edema" OR "leg edema" OR "lower extremity edema" OR "ankle swelling") AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r21 | 1358 | (gabapentin OR pregabalin) AND (edema OR oedema OR "leg swelling") AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| r22 | 194 | ("misinterpreted as a new" OR "mistaken for a new" OR "misdiagnosed as") AND ("adverse drug reaction" OR "side effect" OR "drug-induced") AND ("was started on" OR "was prescribed" OR "was initiated") AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y AND (polypharmacy OR elderly OR "older") |
| t1 | 76 | lithium AND ("nephrogenic diabetes insipidus" OR polyuria) AND (amiloride OR hydrochlorothiazide OR thiazide OR desmopressin) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t2 | 88 | clozapine AND (enuresis OR "urinary incontinence" OR constipation OR tachycardia) AND (desmopressin OR oxybutynin OR laxative OR macrogol OR docusate OR senna OR propranolol OR ivabradine OR metoprolol) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t3 | 149 | ("proton pump inhibitor" OR omeprazole OR pantoprazole OR esomeprazole OR lansoprazole) AND hypomagnesemia AND (magnesium) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t4 | 59 | (anticholinergic OR oxybutynin OR amitriptyline OR "anticholinergic burden") AND ("cognitive impairment" OR dementia OR delirium) AND (donepezil OR rivastigmine OR galantamine OR memantine) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t5 | 343 | (antipsychotic OR risperidone OR olanzapine OR clozapine) AND ("weight gain" OR hyperglycemia OR diabetes) AND (metformin OR insulin OR topiramate) AND "induced" AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t6 | 43 | (SSRI OR antidepressant OR sertraline OR paroxetine OR fluoxetine OR escitalopram) AND ("sexual dysfunction" OR "erectile dysfunction") AND (sildenafil OR tadalafil OR bupropion) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t7 | 436 | (NSAID OR ibuprofen OR naproxen OR diclofenac OR celecoxib OR etoricoxib) AND (hypertension OR "blood pressure" OR "heart failure" OR edema) AND (amlodipine OR lisinopril OR furosemide OR antihypertensive OR diuretic) AND "induced" AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t8 | 305 | ("calcium channel blocker" OR amlodipine OR nifedipine OR lercanidipine) AND (edema OR oedema) AND (furosemide OR diuretic OR hydrochlorothiazide OR spironolactone) AND (polypharmacy OR elderly OR "older") AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t9 | 51 | (corticosteroid OR prednisone OR prednisolone OR dexamethasone) AND (psychosis OR mania OR delirium) AND (olanzapine OR quetiapine OR haloperidol OR risperidone) AND "steroid-induced" AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t10 | 136 | (antipsychotic OR risperidone OR amisulpride OR paliperidone OR haloperidol) AND (hyperprolactinemia OR galactorrhea OR gynecomastia) AND (aripiprazole OR cabergoline OR bromocriptine) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t11 | 54 | (opioid OR morphine OR oxycodone OR tramadol OR codeine) AND ("opioid-induced constipation" OR constipation OR nausea) AND (naloxegol OR methylnaltrexone OR lactulose OR laxative OR metoclopramide OR ondansetron OR haloperidol) AND (polypharmacy OR cascade) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t12 | 769 | ("drug-induced" OR "medication-induced" OR iatrogenic) AND ("was prescribed" OR "was started on" OR "was treated with") AND (misattributed OR misinterpreted OR "not recognized" OR unrecognized OR overlooked) AND (polypharmacy OR elderly OR "older adult") AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t13 | 723 | (valproate OR "valproic acid" OR levetiracetam OR topiramate OR carbamazepine) AND (tremor OR parkinsonism OR depression OR psychosis OR hyponatremia) AND (propranolol OR levodopa OR antidepressant OR sertraline OR quetiapine OR "sodium chloride" OR tolvaptan) AND "induced" AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t14 | 73 | (SGLT2 OR dapagliflozin OR empagliflozin OR canagliflozin) AND ("genital" OR "urinary tract infection" OR candid) AND (fluconazole OR antifungal OR antibiotic) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t15 | 208 | (beta-blocker OR propranolol OR metoprolol OR atenolol OR timolol OR flunarizine OR isotretinoin OR montelukast) AND depression AND (antidepressant OR sertraline OR escitalopram OR fluoxetine) AND "induced" AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
| t16 | 142 | (metoclopramide OR domperidone OR levosulpiride OR prochlorperazine OR cinnarizine OR flunarizine) AND (parkinsonism OR "tardive dyskinesia" OR dystonia) AND (levodopa OR tetrabenazine OR trihexyphenidyl OR benztropine OR biperiden OR clonazepam OR propranolol) AND PUB_TYPE:"Case Reports" AND OPEN_ACCESS:y |
