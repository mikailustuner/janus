# Light face: pharmacologist review of goals, mapping and validation cases

**Pharmacologist pass (agent), 2026-11-08 — AI-reviewed, pending expert review**

Scope: `data/light/goals.csv`, `data/light/effect_goal_map.csv`, `data/light/validation_cases.csv` and the citations they
use from `data/evidence_papers.csv`. Checked against the build `ca2bb569c5216716` (top 15 candidates per goal) and the
draft validation report. Statistics (ranking key, Wilson bound, hit definition, top-K, inverse rule) are out of scope:
they belong to the statistician pass. MedDRA term names suggested below are from memory and must be checked against a
MedDRA browser (Janus holds no MedDRA licence, DP4); terms suggested for the mapping must also pass the loader's OnSIDES
vocabulary check.

## Summary verdict

**ACCEPT WITH CHANGES.** The goal list and most mapping directions are sound and the rationales mostly describe effects,
not treatments. Before this goes in front of an expert:
- two ambiguous hair terms and `Priapism` should be `excluded` (direction not supported);
- a route/site rule is needed for local effects (topical corticosteroids rank 2–8 for alopecia);
- the "toxicity-sign" terms (weight loss, appetite, hypotension, somnolence, diarrhoea) need a flag, and obesity a
  narrowing rule, because cytotoxic medicines fill the top of those lists;
- one citation does not support its rationale (Goldstein 1998 on the angina trials);
- several Yang-only rows need a specific citation;
- the validation report must say which years are first reports and which are approvals, and must say that the sildenafil
  labels left in the primary run were written after the erectile effect was known.

## Findings

### F1. Goals (`goals.csv`)
| Row | Verdict | Note |
|---|---|---|
| alopecia | CHANGE | Names fine. PT set: add `Alopecia totalis`, `Alopecia universalis` (both are hair-loss conditions in the goal's scope). Do not add scarring alopecia (not the goal). |
| eyelash_hypotrichosis | ACCEPT | `Madarosis` is the right PT (loss of eyelashes/eyebrows). |
| erectile_dysfunction | ACCEPT / Q | Names fine. Confirm `Organic erectile dysfunction` is a current PT (Q5). |
| obesity | CHANGE | Add `Overweight` (verify PT). Names fine. |
| insomnia | ACCEPT | Four insomnia PTs correct; benefit key right. |
| premature_ejaculation | ACCEPT | |
| hyperhidrosis | ACCEPT | Do not add `Night sweats` (different condition). |
| hypertension | CHANGE | Add `Essential hypertension` (verify PT). `Blood pressure increased` is a measurement PT; acceptable in the union. |
| diarrhoea, constipation, nausea | ACCEPT | |
| low_mood | CHANGE | `Depression` alone is narrow for "low mood": add `Depressed mood` (and `Major depression` if the expert agrees; verify PTs). Label "Low mood" is acceptable as a condition name. |
| swelling | CHANGE | Add `Peripheral swelling` (verify PT); it is how many reporters code ankle swelling. |
| pain | ACCEPT | No PT set is the right call; the note is accurate. |
| pulmonary_arterial_hypertension | Q | `Pulmonary arterial hypertension` is correct; many reports are coded `Pulmonary hypertension` (broader, includes non-group-1). Expert to decide (Q8). |
| multiple_myeloma | CHANGE | `Plasma cell myeloma` is the MedDRA name. Add `Plasma cell myeloma recurrent`, `Plasma cell myeloma refractory` if present as PTs (verify). |
| erythema_nodosum_leprosum | ACCEPT | `Type 2 lepra reaction` is the MedDRA name; note correct. |
| parkinsons_disease | ACCEPT | Keep `Parkinson's disease` only; `Parkinsonism` would pull in drug-induced parkinsonism (antipsychotics), the opposite signal. |

Benefit keys: the five keys used are all the `improvement_*` keys in `memory_events.csv`; assignments are correct. No
condition name is clinically wrong.

### F2. Mapping rows (`effect_goal_map.csv`; row = term)
**Alopecia**
- `Hypertrichosis`, `Hairiness` — ACCEPT. Direction sound (minoxidil principle); Zappacosta 1980 is the right specific citation.
- `Abnormal hair growth`, `Hair growth abnormal` — **CHANGE → excluded.** The term does not state a direction (excess,
  loss, texture or colour change). Dantrolene enters the top 10 (rank 9) on this term alone. Proposed rationale:
  "Direction not stated (excess growth, loss or a change of texture); on its own it does not point to the goal."
- `Application site hypertrichosis` — ACCEPT active, under the local-effect rule (F3). Rationale CHANGE (table).
- `Hirsutism` — ACCEPT excluded. Reason is defensible; note that minoxidil and ciclosporin also list hirsutism without
  an androgenic mechanism, so exclusion is conservative, not wrong.

**Eyelash hypotrichosis**
- `Growth of eyelashes`, `Eyelash thickening`, `Eyelash changes` — ACCEPT. Erlotinib at rank 2 is pharmacologically
  real (EGFR inhibitors cause eyelash trichomegaly), not noise. Smith 2012 is a post-approval trial; the original
  observation is the latanoprost hypertrichosis report (Johnstone, Am J Ophthalmol 1997) — **needs a specific citation**;
  add it only after a Crossref check.
- `Madarosis` excluded — ACCEPT.

**Erectile dysfunction**
- `Erection increased` — ACCEPT direction; **CHANGE rationale/citation.** Goldstein 1998 is the ED trial; it does not
  report the angina trials, so the current rationale is not supported by its citation. Either reword to what Goldstein
  supports (table) or add a source for the angina-trial observation (the review Ghofrani, Osterloh, Grimminger, Nat Rev
  Drug Discov 2006, "Sildenafil: from angina to erectile dysfunction to pulmonary hypertension and beyond" — verify in
  Crossref before adding).
- `Spontaneous penile erection` — ACCEPT.
- `Priapism` — **CHANGE → excluded.** In labels, priapism is mostly a rare idiosyncratic reaction of alpha-1 blockade or
  serotonergic drugs (tamsulosin, trazodone, SSRIs, atomoxetine, antipsychotics: 9 of the top 15), and several of these
  more often *impair* erection (SSRIs, antipsychotics via prolactin). As a direction marker for the goal it is mostly
  wrong. PDE5 inhibitors keep their place through `Erection increased`. Caveat: this change was decided after seeing the
  results and alters the sildenafil case; record it as a non-blind change (DP10) and let the expert confirm (Q1).
- `Painful erection` excluded — ACCEPT.

**Obesity** — see F4. Terms are correctly placed in MedDRA (`Anorexia` is the LLT for loss of appetite; the note is right).

**Insomnia** — `Somnolence`, `Sedation`, `Hypersomnolence`: ACCEPT direction (H1-antihistamine / low-dose doxepin
principle); **needs a specific citation**; flag as nonspecific (F4 rule) — top 11 are opioids and cytotoxics. Rationale
wording CHANGE (F6).

**Premature ejaculation** — `Ejaculation delayed`: ACCEPT; this is the SSRI/dapoxetine principle and the top candidates
(duloxetine, paroxetine) fit. **Needs a specific citation.**

**Hyperhidrosis** — `Anhidrosis`: ACCEPT direction (anticholinergic principle: glycopyrronium); **needs a specific
citation.** Two cautions for the expert (Q7): levobupivacaine (rank 1) shows anhidrosis from a regional nerve block,
a local procedure effect (F3 rule removes it); topiramate/zonisamide oligohidrosis is a carbonic-anhydrase effect linked
to hyperthermia in children — a harm signal, not a useful action. Consider adding `Hypohidrosis` (and LLT
`Oligohidrosis`) as active rows if they are in the OnSIDES vocabulary.

**Bowel** — `Constipation` → diarrhoea: ACCEPT (opioid principle; loperamide is the classic case); `Diarrhoea` →
constipation: ACCEPT with flag. Both **need a specific citation**. `Diarrhoea` is one of the most frequently labelled
effects (antibiotics, cytotoxics, interferons fill the top 15): flag as nonspecific (F4 rule).

**Hypertension** — `Hypotension`, `Blood pressure decreased`: ACCEPT direction; **needs a specific citation**; flag as
nonspecific. The top 15 are almost all IV cytotoxics or proteasome inhibitors, where hypotension is an infusion or
hypersensitivity reaction, not a vasodilator action.

### F3. Local / application-site effects — recommended rule
Topical corticosteroids (amcinonide, fluocinonide, diflorasone, betamethasone, clobetasol, cortisol, mometasone) reach
alopecia ranks 2–8 through plain `Hypertrichosis`/`Hairiness` from their local-reactions list, not through the
`Application site …` term, so a term-only rule will not catch them. Recommended rule (deterministic, in `labels.py`):
1. Each goal gets a scope: `local:skin` (alopecia, hyperhidrosis), `local:eye` (eyelash_hypotrichosis), else `systemic`.
2. Each label gets a route class from its product's RxNorm dose form (RxCUI is already used for keys, DP3): `systemic`
   (oral, IV, IM, SC, transdermal patch, rectal for systemic use), `local:skin` (cutaneous), `local:eye` (ophthalmic),
   `local:other` (otic, nasal, inhaled, intra-articular, intralesional, local/regional anaesthetic injection).
   Unknown dose form → treat as `systemic` and mark the card "route unknown".
3. A systemic goal counts only systemic-route labels. An `Application site …` term may never map to a systemic goal
   (loader refuses the row).
4. A local goal counts systemic-route labels and site-matched local labels only (`local:skin` for alopecia and
   hyperhidrosis, `local:eye` for eyelashes). Local-route candidates are listed as a separate "effect where the product
   is applied" group, not interleaved with systemic ones (the statistician decides how ranks are shown).
5. Card text for a local candidate: "Seen where the product is applied; this does not show an effect elsewhere."

Effect on the cases: minoxidil's OnSIDES labels are oral (hypertrichosis), bimatoprost's are ophthalmic (site-matched),
so no validation case changes. Topical corticosteroids stay visible for alopecia but separated; note for the expert that
corticosteroids are already used in alopecia areata through immunosuppression (Q2), so these are not new hypotheses.
Levobupivacaine drops out of hyperhidrosis (`local:other`).

### F4. Obesity and other "toxicity-sign" terms — recommendation: keep, narrow, flag
`Weight decreased`, `Weight loss`, `Decreased appetite` and its LLTs are the right terms for the mechanism of the real
cases (topiramate, GLP-1 agonists suppress appetite), so keep them. But capecitabine, everolimus, bortezomib,
lenalidomide, imatinib, temozolomide sit in the top 15 because weight loss there is cachexia, mucositis or nausea.
1. **Narrow** (obesity only): leave out candidates whose ingredient ATC code is in L01 (antineoplastic agents). ATC from
   the shared ingredient key (Wikidata/RxClass), ingredient level only. This is a pharmacological class rule, not a
   case-tuned one; it does not touch topiramate or liraglutide. Whether to extend to L04AX (lenalidomide, pirfenidone)
   is Q3.
2. **Flag** (all goals): add a `nonspecific` marker to the rows `Weight decreased`, `Weight loss`, `Decreased appetite`,
   `Anorexia`, `Appetite decreased NOS`, `Appetite lost`, `Somnolence`, `Sedation`, `Hypersomnolence`, `Diarrhoea`,
   `Constipation`, `Hypotension`, `Blood pressure decreased`. Cards matched only by such terms carry: "This effect is
   also a common sign of illness or of a medicine's toxicity; on its own it is weak support." (A schema change to the
   mapping file; owner/designer to choose the column name.)
3. Rationales already state the toxicity caveat for weight and appetite — keep that text.

### F5. Validation cases (`validation_cases.csv`)
| Case | Original use | Later use | Year | `indication_terms` | Verdict |
|---|---|---|---|---|---|
| amantadine_parkinson | right (influenza A) | right | 1969 = first report (Schwab); US approval for parkinsonism came later (1973 — verify) | complete; `parkinsonism` correctly catches all amantadine labels | CHANGE note (year kind) |
| bimatoprost_eyelash | right (glaucoma / ocular hypertension) | right | 2008 approval, right | complete, not over-broad | ACCEPT |
| liraglutide_obesity | right | right | 2014 approval, right | complete (`weight management` catches Saxenda) | ACCEPT; build Q: 0 US labels used *and* 0 removed means no US liraglutide label was keyed at all (Victoza and Saxenda are single-ingredient US labels) — a key-mapping gap, not a pharmacology result |
| minoxidil_alopecia | right | right | 1988 topical approval, right | complete; OTC topical labels are not in OnSIDES, so the 22 oral labels used are a fair primary test | ACCEPT |
| sildenafil_ed | right ("angina (clinical trials)") | right | 1998, right | complete | CHANGE note: the 63 US labels left are PAH labels written after the erectile effect was known, so the primary run is contaminated for this case |
| sildenafil_pah | right (prior marketed use) | right | 2005, right | complete; `pah` as whole word is safe | ACCEPT |
| thalidomide_enl | right (sedative) | right | 1965 = first report; US approval for ENL 1998 | complete (`lepra` catches "lepra reactions") | CHANGE note (year kind) |
| thalidomide_mm | right | right | 1999 = first report; US approval with dexamethasone 2006 | complete | CHANGE note (year kind) |
| topiramate_obesity | right (epilepsy) | right | 2012 approval of the combination, right; note accurate | complete; single-ingredient topiramate labels carry no weight indication, so 0 removed is correct | ACCEPT |

The effect predates the later-use label for minoxidil (oral label), bimatoprost (eyelash growth known from latanoprost
before 2001) and topiramate (weight loss in the original label); only sildenafil's remaining labels postdate the
observation.

**Missing classic side-effect-derived repurposings** (names only; decide before re-running, or the set becomes less
blind): within existing goals — semaglutide → obesity; low-dose doxepin → insomnia; topical glycopyrronium →
hyperhidrosis; dapoxetine / SSRIs → premature ejaculation (no US approval, so US-only primary run cannot evaluate it);
finasteride → androgenetic alopecia (mechanism-derived, a fair "unreachable" case). Outside current goals — bupropion →
smoking cessation; propranolol → infantile haemangioma; spironolactone → hirsutism/acne; iproniazid → depression;
aspirin → antiplatelet use.

### F6. Wording (medical-safety rules 2 and 7)
No row uses a forbidden phrase. Borderline: "points to a possible use for …" (Somnolence, Ejaculation delayed,
Anhidrosis, Constipation, Diarrhoea) reads close to "treatment for". Use one template: "*X* as an unwanted effect
suggests an action that may be worth investigating for *goal*." Historical approval facts in validation notes
("approved for weight management in 2014") describe the past, not a candidate — ACCEPT. Cited titles contain
"in the Treatment of" (Goldstein, Schwab, Sheskin): verbatim titles are citations; the forbidden-phrase test should
exempt the title field explicitly rather than silently.

## Requested changes

| File | Row | Current | Proposed |
|---|---|---|---|
| goals.csv | alopecia `faers_pts` | Alopecia\|Alopecia areata\|Androgenetic alopecia\|Diffuse alopecia | + `Alopecia totalis`\|`Alopecia universalis` (verify PTs) |
| goals.csv | obesity `faers_pts` | Central obesity\|Obesity | + `Overweight` (verify PT) |
| goals.csv | hypertension `faers_pts` | Blood pressure increased\|Hypertension | + `Essential hypertension` (verify PT) |
| goals.csv | low_mood `faers_pts` | Depression | + `Depressed mood` (verify PT); `Major depression` per Q |
| goals.csv | swelling `faers_pts` | Oedema\|Oedema peripheral | + `Peripheral swelling` (verify PT) |
| goals.csv | multiple_myeloma `faers_pts` | Plasma cell myeloma | + `Plasma cell myeloma recurrent`\|`Plasma cell myeloma refractory` (verify PTs) |
| effect_goal_map.csv | Abnormal hair growth | active | excluded; "Direction not stated (excess growth, loss or a change of texture); on its own it does not point to the goal." |
| effect_goal_map.csv | Hair growth abnormal | active | excluded; same rationale |
| effect_goal_map.csv | Application site hypertrichosis | "Local excess hair growth where a product is applied." | "Local excess hair growth where a product is applied; counts only for labels applied to the skin (local-effect rule)." |
| effect_goal_map.csv | Erection increased | "Erections were reported during the angina trials of sildenafil." | "A pro-erectile effect; sildenafil was later studied for erectile dysfunction (Goldstein 1998)." — or keep the angina sentence and add a verified source for it |
| effect_goal_map.csv | Priapism | active | excluded; "Mostly a rare reaction of alpha-1 blocking or serotonergic medicines, several of which more often impair erection; on its own it does not point to the goal." (non-blind change, DP10) |
| effect_goal_map.csv | Somnolence, Sedation, Hypersomnolence, Ejaculation delayed, Anhidrosis, Constipation, Diarrhoea | "… points to a possible use for …" | "… as an unwanted effect suggests an action that may be worth investigating for …"; specific citation needed |
| effect_goal_map.csv | Hypotension, Blood pressure decreased | Yang only | specific citation needed; rationale add "In infusion and allergic reactions it is not a blood-pressure-lowering action." |
| effect_goal_map.csv | Growth of eyelashes, Eyelash thickening, Eyelash changes | Smith 2012 | add the original latanoprost observation (Johnstone 1997) after Crossref check |
| effect_goal_map.csv (schema) | 13 toxicity-sign rows (F4.2) | — | `nonspecific` marker + card sentence |
| labels.py / design §5.2 | label signals | all routes count | local-effect rule F3 (goal scope, label route from RxNorm dose form) |
| candidates / design §6 | obesity goal | all ingredients | leave out ATC L01 ingredients (F4.1) |
| validation_cases.csv | amantadine_parkinson note | … | append "1969 is the first report; US approval for parkinsonism came later." (year to verify) |
| validation_cases.csv | thalidomide_enl note | … | append "1965 is the first report; US approval for this use came in 1998." |
| validation_cases.csv | thalidomide_mm note | … | append "1999 is the first report; US approval (with dexamethasone) came in 2006." |
| validation_cases.csv | sildenafil_ed note | … | append "The US labels left in the primary run are pulmonary arterial hypertension labels written after the erectile effect was known." |
| validation report (generator) | column "Later use (year)" | bare year | "Later use (year of first report or approval)" |
| light build (keys) | liraglutide | 0 US labels keyed | investigate key mapping for Victoza/Saxenda before the gate is read |

## Questions for the human expert (pharmacist / physician)
1. Should `Priapism` be excluded for erectile dysfunction (alpha-1 / serotonergic priapism vs pro-erectile action)? It
   changes the sildenafil case, and the change is non-blind.
2. Local-effect rule (F3): agree that site-matched topical effects count for skin/eye goals but are shown separately?
   Should topical corticosteroids be marked as an existing use for alopecia areata?
3. Obesity narrowing: leave out ATC L01 only, or also L04AX and other classes whose weight loss is toxicity?
4. Are diarrhoea → constipation and hypotension → hypertension useful enough to keep, given how nonspecific they are?
5. Please verify the MedDRA PT names proposed in F1 (and `Organic erectile dysfunction`) in a current MedDRA version.
6. Specific citations for the Yang-only rows (sedation, delayed ejaculation, anhidrosis, bowel, hypotension), and
   confirmation of the Johnstone 1997 and Ghofrani 2006 references.
7. Hyperhidrosis: should carbonic-anhydrase oligohidrosis (topiramate, zonisamide) be kept, given its hyperthermia risk?
8. PAH goal: add `Pulmonary hypertension` to the PT set or keep group-1 only?
9. Should top candidates that are already approved for the goal (vardenafil, tadalafil, alprostadil for ED; tirzepatide
   for obesity) be marked as known uses, despite DP16?
10. Which missing cases (F5) should be added to the fixed set before the next run?

AI-reviewed, pending expert review.
