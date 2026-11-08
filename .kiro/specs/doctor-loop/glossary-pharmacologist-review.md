# Glossary review: pharmacologist (doctor-loop task 14)

Scope: `apps/api/janus/notes/glossary/ingredients.csv`, `cascades.csv`, `sentences.csv` (all rows `proposed`), read
against design §4.4, §5.1–5.7, §11, requirements 7, 8, 14 and `medical-safety.md`. ATC codes were read from the dev
database (`res_ingredient`, current dataset `e9e55772…`, read-only). No file other than this report was changed. Brand
and product names are not quoted here; the rows are named by key, language and problem.

**Fix policy used in this report** (owner rule: no AI translation of clinical terms). English cells get the proposed
INN, because every other language falls back to English. In tr, de, fr and es I propose only mechanical edits of the
source label (remove a stereo descriptor, a salt or ester, a disambiguator, a typo of one or two letters). Where the right
value would be a new national form, the proposal is **clear the cell** (the note then prints the English INN with "name
not translated" and the ATC code).

## Verdicts
- `ingredients.csv`: **approve with changes** (blocking items F1–F4; F13 blocks clinical use but is outside this file).
- `cascades.csv`: **approve with changes** (advisory items only; one owner decision on row 49).
- `sentences.csv`: **approve with changes** (S1 and S2 are blocking).

---

## 1. ingredients.csv

Counts: 1,129 rows (1,127 Wikidata QIDs, J1, J2), all `proposed`, source `dataset:e9e55772`. Filled cells: en 1,129,
tr 447, de 770, fr 840, es 710. No `en_alt`, `edited` or `note` set. All keys exist in the current dataset with at least
one ATC code. NFC and whitespace are clean. No exact duplicate name across keys in any language (case-folded).

### F1 (blocking): label names a different substance or the wrong meaning
| Key | ATC | Lang | Current | Problem | Proposed |
|---|---|---|---|---|---|
| Q7301602 | A02BX14 | es | rabeprazole | different drug (key is rebamipide) | clear |
| Q417227 | N03AX14 | en | (S)-etiracetam | chemical name; doctors know levetiracetam | levetiracetam |
| Q402633 | N04BD01 | en / de / fr | (±)-deprenyl / (±)-Deprenyl / (±)-sélégiline | racemate; the drug is selegiline | en selegiline; de clear; fr sélégiline |
| Q190875 | H02AB09 … | en, tr, de, fr, es | cortisol / Kortizol / Cortisol / cortisol / cortisol | the hormone; the medicine is hydrocortisone | en hydrocortisone; other languages clear |
| Q416791 | N06AA12 | en / de | cidoxepin / Cidoxepin | the Z-isomer; N06AA12 is doxepin (es already says doxepin) | en doxepin; de clear |
| Q27263884 | A02BC07 | en | (R)-rabeprazole | chemical name | dexrabeprazole |
| Q238544 | N06AX01 | en / fr | 5-HTP / 5-HTP | abbreviation | en oxitriptan; fr clear |
| Q1326389 | N02BA02 | en / de | aspirin aluminum / chemical name | not the INN | en aloxiprin; de clear |
| Q300989 | N04BA01 | tr / fr | L-DOPA / DOPA | fr names unspecified DOPA, not levodopa | tr clear; fr clear |
| Q214863 | B03AA07 | tr | "iron salt" | wider than ferrous sulfate | clear |
| Q161572 | R05CA13 | es | eucalyptus oil | oil, not eucalyptol | clear |
| Q413739 | A12AA03 | fr | pentahydroxyéthanoate de calcium | wrong chemical name | clear |
| Q423930 | C03AA03 | fr | hidrocloratiazida | misspelled Spanish form in the French cell | hydrochlorothiazide |
| Q423292 | N05AX13 | es | palmitato de Paliperidona | narrows to one ester | paliperidona |
| Q1452256 | N05AL07 | de | levo | truncated | clear |
| Q419944 | C02AC05 | fr | moxon | truncated | moxonidine |
| Q417884 | R06AX02 | tr | (garbled string with a number) | not a name | clear |
| Q422071 | A10BX01 | tr | (not a Turkish word) | not a name | clear |
| Q419020 | N02BG10 | all | JWH-018 | synthetic cannabinoid, not a medicine; in scope only through a class code | status `rejected` (see F13) |

### F2 (blocking): brand or product names
Cells to clear (names not quoted): Q409468 tr (metoprolol), Q412666 es (ramipril), Q418351 es (meprobamate), Q419468 fr
(ciclopirox), Q1060922 es (oxybutynin), Q924467 de (fluocinolone acetonide), Q2893248 fr and es (human insulin),
Q55186498 tr (thiopental; brand-derived spelling).

Keys that are product items, not substances. Each duplicates a substance key with the same ATC code (finding (c)).
| Key | Duplicates | Proposed en | Other cells |
|---|---|---|---|
| Q97479031 | Q422689 lactulose (A06AD11) | lactulose | – |
| Q2034113 | Q2893248 insulin (A10AB01) | insulin (human) | de: clear |
| Q29006606 | Q21011228 dulaglutide (A10BJ05) | dulaglutide | – |
| Q139890384 | Q186969 ibuprofen (M01AE01) | ibuprofen | – |
| Q139890449 | Q57055 paracetamol (N02BE01) | paracetamol | – |

Rejecting these rows would print a code with "name not reviewed", so I propose renaming them. The real fix is in
resolution: map these items to the substance key (hand to drug-resolution).

### F3 (blocking): English cells that are wrong (every language falls back to them)
| Key | Current | Proposed |
|---|---|---|
| Q410412 | carbamazepin | carbamazepine |
| Q420590 | ropinirol | ropinirole |
| Q423809 | (E)-chlorprothixene (Z according to WHO INN RL 40, conflated wikidata) | chlorprothixene |

### F4 (blocking): misspellings in other languages
| Key | Lang | Current | Proposed |
|---|---|---|---|
| Q3121121 | es | Saptagliptina | saxagliptina |
| Q4734170 | es | alogliptica | alogliptina |
| Q2736873 | es | alfusozina | alfuzosina |
| Q3731252 | es | erdosterina | erdosteína |
| Q572796 | es | medazepan | medazepam |
| Q414547 | fr | salicyclate de sodium | salicylate de sodium |
| Q4713192 | de | Aclometason | Alclometason |
| Q3791957 | de | Hydroflumethazid | Hydroflumethiazid |
| Q5404460 | de | Ethyl Ioflazepat (capital I) | Ethylloflazepat |
| Q411932 | tr | duloksetinin (genitive) | duloksetin |

### F5 (advisory): stereo descriptors that are not part of the INN
These are 147 cells: en 63, de 45, fr 37, tr 1, es 1. Remove the prefix (`(RS)-`, `(S)-`, `(S)-(−)-`, `(Z)-`, `(E)-`,
`(±)-`, `(−)-`, `(+)-`, `(6S)-`, `(3aS)-`, `(2RS,6RS)-`, `(RS,RS)-`, `rac-`, `L-`, `D-`, `D-(-)-`, `DL-`, `β-`). The
renames in F1, F3 and F8 take precedence. Examples: Q3515 (RS)-rabeprazole → rabeprazole; Q411347 de (RS)-Amlodipin →
Amlodipin (this one matters: levamlodipine exists as a separate drug); Q413994 (S)-(−)-timolol → timolol; Q422689
β-lactulose → lactulose; Q245280 D-sorbitol → sorbitol. Keys: en Q3515 Q179996 Q245280 Q326224 Q337188 Q375613
Q386441 Q407646 Q409192 Q409468 Q409632 Q409672 Q409948 Q411932 Q411985 Q413717 Q413994 Q415793 Q416701 Q417141
Q417765 Q418785 Q418928 Q418970 Q419552 Q419841 Q419890 Q420350 Q420377 Q421937 Q422418 Q422689 Q422970 Q424260
Q424771 Q593166 Q594836 Q599052 Q632405 Q662511 Q1060922 Q1169164 Q2465218 Q2555245 Q3342150 Q3479994 Q3746837
Q5135114 Q6535827 Q6676374 Q7844989 Q18350076 Q45024802 Q55186498 Q75163056 Q113514917; de and fr the same keys where
the cell carries a prefix (plus fr Q2419445 (±)-desvenlafaxine); es Q423408 L-carboximetilcisteína → clear (not the
Spanish INN).

### F6 (advisory): salt, ester or hydrate where the key is the base substance (ATC names the base)
| Key | Lang | Current | Proposed |
|---|---|---|---|
| Q374826 | en / de / fr | solifenacin succinate / Solifenacin-Succinat / succinate de solifénacine | solifenacin / Solifenacin / solifénacine |
| Q419643 | en / de / fr | amineptine hydrochloride / Amineptin-Hydrochlorid / amineptine HCl | amineptine / Amineptin / amineptine |
| Q421475 | en / de / es | beclomethasone dipropionate / Beclometasondipropionat / Dipropionato de beclometasona | beclometasone (en_alt beclomethasone) / Beclometason / beclometasona |
| Q1044248 | en / de / fr | mometasone furoate / Mometasonfuroat / furoate de mométasone | mometasone / Mometason / mométasone |
| Q4733653 | en | almagate dihydrate | almagate |
| Q20077596 | en / fr | roxatidine acetate / acétate de Roxatidine | roxatidine / roxatidine |
| Q22075864 | en | tetraferric tricitrate decahydrate | ferric citrate (check against the code's name) |
| Q4119838 | en | calcium 2-glycerophosphate | calcium glycerophosphate |
| Q419693 | en | calcium DL-lactate | calcium lactate |
Salts that are the substance (calcium carbonate, magnesium oxide), and ATC names that include the salt (metamizole
sodium, docusate sodium, methylnaltrexone bromide, tebipenem pivoxil, azilsartan medoxomil, the hydrocortisone and
methylprednisolone esters in D07), stay as they are.

### F7 (advisory): other cells that are not the recommended name
- Wrong language. Clear these cells: tr Q204954 zinc sulfate, Q421291 ferrous gluconate, Q3563148 vortioxetine,
  Q2062094 Pramlintide; es Q58375 thioridazine, Q198473 ziconotide, Q250442 Methylcobalamin, Q411932 duloxetine, Q416545
  asénapine (French form), Q593166 molindone, Q600951 Xipamide, Q904011 Desonide, Q2787672 Thebacon, Q3836403 Lofexidine,
  Q4708345 Alaproclate; de Q607349 Fluorometholone.
- Abbreviations, old names and chemical names. Clear these cells: tr Q190067 THC; tr Q415619 Narkotin; tr, de, fr
  Q579348 Prostaglandin E1 (key is alprostadil); de chemical names on Q553324, Q2496906, Q1047468, Q5221244, Q5613302,
  Q1326389; es Q420899 Bromovalerilurea.
- Minor fixes: tr Q152763 Lityum (ilaç) → Lityum; tr Q410965, Q417317, Q16252338 "İnsülin - …" → remove " - "; es
  Q155472 "valsartán, valsartano" → valsartán; es Q410074 "losartán, losartano" → losartán; de Q290001 gliclazid →
  Gliclazid; de Q15628111 Eisen(III) citrat → Eisen(III)-citrat; fr Q6731379 magnésium aspartate → clear; fr Q27284849
  lopéramide oxide → clear; en Q502327 senna glycoside → senna glycosides; en Q6676872 promethazine hydroxyethyl →
  hydroxyethylpromethazine; en Q407125 aluminum hydroxide → aluminium hydroxide (matches the other aluminium rows;
  en_alt aluminum hydroxide).
- Acceptable older national names (no change, listed for the native reviewers): de Sorbit, Mannit, Calcidiol,
  Hydroxycobalamin, Pektine; fr noramidopyrine, butéthal, cibenzoline (the French name of cifenline); French cells
  without accents (methylphenobarbital, levacetylmethadol, propafenone, zimelidine, fenbufene).

### F8 (advisory): English INN and `en_alt` (US adopted name)
Where the English cell is the US name, I propose the INN as `en` and the current value as `en_alt`. Where the cell is
already the INN, I propose only `en_alt`.
| Key | en (proposed) | en_alt |
|---|---|---|
| Q57055 | paracetamol | acetaminophen |
| Q18216 | acetylsalicylic acid | the current English cell |
| Q420626 | glibenclamide | glyburide |
| Q420133 | chlorphenamine | chlorpheniramine |
| Q937085 | dexchlorphenamine | dexchlorpheniramine |
| Q386441 | meclozine | meclizine |
| Q409231 | indometacin | indomethacin |
| Q421475 | beclometasone | beclomethasone |
| Q425289 | chlortalidone | chlorthalidone |
| Q424986 | tiabendazole | thiabendazole |
| Q426070 | dimetindene | dimethindene |
| Q415026 | benzatropine | benztropine |
| Q420350 | flupentixol | flupenthixol |
| Q2608288 | tiotixene | thiothixene |
| Q598713 | dosulepin | dothiepin |
| Q423408 | carbocisteine | carbocysteine |
| Q55434 | pethidine | meperidine |
| Q174786 | pentoxyverine | carbetapentane |
| Q2268608 | dextropropoxyphene | propoxyphene |
| Q411697 | methylphenobarbital | mephobarbital |
| Q411799 | levacetylmethadol | levomethadyl acetate |
| Q415578 | phenazone | antipyrine |
| Q422761 | metamizole sodium | dipyrone |
| Q904071 | moracizine | moricizine |
| Q906414 | mesuximide | methsuximide |
| Q2146170 | retigabine | ezogabine |
| Q2364943 | sultiame | sulthiame |
| Q2623251 | alimemazine | trimeprazine |
| Q2964078 | clofedanol | chlophedianol |
| Q1176336 | metixene | methixene |
| Q3800087 | mepyramine | pyrilamine |
| Q4926102 | bromazine | bromodiphenhydramine |
| Q5221244 | dantron | danthron |
| Q5462632 | fludroxycortide | flurandrenolide |
| Q20817068 | ulobetasol | halobetasol propionate |
| Q27108485 | trimetaphan | trimethaphan camsylate |
| Q948846 | desoxycortone | desoxycorticosterone |
| Q418850 | clorazepic acid | clorazepate |
| Q2203957 | carbasalate calcium | carbaspirin calcium |
| Q3395266 | butobarbital | butethal |
| Q3003746 | crospovidone | – |
| Q2893248 | insulin (human) | regular insulin |
| Q430675 | ispaghula | psyllium |
| Q2755412 | ipecacuanha | ipecac |
| Q60168 | diamorphine | – (keep the current cell as en_alt if the owner wants the common name) |

### F9 (advisory): capitalization
These cells start with a capital letter: en 74, tr 367, fr 134, es 478. In tr, fr, es and en a nonproprietary name is
written in lower case, and a capital inside a sentence ("… {index} followed by {marker} …") reads like a brand. Proposal:
lower-case the first letter in en, tr, fr and es. Keep the capital for Latin binomials (Q158289, Q159376, Q3395566) and
for German. Turkish needs locale-correct casing (İ→i, I→ı); Python's `str.lower` gives the wrong character for İ. Doing
this at render time instead would keep the file equal to the source labels (owner decision).

### F10 (advisory): possible duplicates (finding c)
- Q1044248 (mometasone furoate) and Q28208887 (mometasone) carry the same three codes. After F6 both read "mometasone".
  Keep both rows with the same name, and merge the keys in resolution.
- The five product keys in F2.
- Q409501 (trisodium phosphate) and Q3249706 (sodium phosphates) share A06AG01. These are separate substances, so no
  glossary change.

### F11 (advisory): J1 and J2
- Names are correct in all five languages (J1 dimenhydrinate, R06AA11; J2 imipenem).
- `source` is `dataset:e9e55772`. Design §5.1 says `janus_curated` for J keys. Fix the draft script.
- These ten strings come from `data/janus_ingredients.csv` (curated), not from Wikidata. The owner should confirm they
  are acceptable under the no-AI-translation rule. They are the standard INN forms.
- J2 has no code of its own. The note will print J01DH51 (imipenem and cilastatin) next to imipenem. Label it as the
  combination code or print no code for J2.

### F13 (blocking for clinical use; outside this file): wrong ATC codes on ingredient keys
I compared codes shared by more than one key. Wikidata gives these keys a code that belongs to a different substance:
| Key | Wrong code (belongs to) | Effect |
|---|---|---|
| Q407883 ketoconazole | M01AE03 (ketoprofen) | enters the NSAID, NSAID-marker and pain-reliever classes: PIPC rows 9, 40, 51–54 can fire |
| Q284321 mefenamic acid | N02AX02 (tramadol) | enters the opioid class (row 55) and gets the opioid abrupt-stop warning |
| Q553223 esomeprazole | N03AX16 (old pregabalin code) | enters the gabapentinoid class (row 31) and gets the gabapentinoid abrupt-stop warning |
| Q421091 levocetirizine | R06AB04 (chlorphenamine) | same class; wrong code printed |
| Q11426176 prednisolone | D07AB08 (desonide) | same class; wrong code printed |
| Q417141 econazole | D01AC04 (chlormidazole) | same class; wrong code printed |
| Q216935 lidocaine | R02AA05 (chlorhexidine) | no class; wrong code printed |
| Q419020 JWH-018 | N02BG10 | enters the pain-reliever class |

These codes are used whenever the engine takes a key's ingredient-level codes: name search, ingredient choice, and US
and EU name paths. Those findings have `form_confirmed = false`. The note also prints every ATC code (§5.7). Proposal:
add a curated per-key code-exclusion file under `data/` (owner-reviewed, like `component_codes.csv`) and cross-check all
1,129 keys' codes against RxClass. My check finds only codes shared between keys, so a wrong code held by a single key
is still undetected. Hand to drug-resolution and the cascade engine. This should be done before any note is issued.

---

## 2. cascades.csv

Counts: 65 rows, 108 distinct English terms, all `proposed`. The same English term has the same translation in every
row and language. The abbreviations are the ones local doctors use (tr NSAİİ, de NSAR, fr AINS, es AINE, fr/es
ISRS/IRSN). Class terms that could change scope keep the English scope: "Antihypertensive" (indication class C02, C03,
C07, C08, C09), "Pain reliever" (fr Antalgique, es Analgésico: any analgesic), "Cough remedy" (antitussives and
expectorants), "Antihyperglycemic" (de Antidiabetikum covers insulin, as in the German ATC).

1. **Advisory (scope narrowed).** Rows 12, 25, 59, "Sleep agent". fr "Hypnotique" and es "Hipnótico" are a
   pharmacological class. The Janus class also contains anxiolytic benzodiazepines (N05BA), trazodone, diphenhydramine
   and doxylamine. Proposed: fr "Médicament pour dormir", es "Medicamento para dormir". tr "Uyku ilacı" and de
   "Schlafmittel" already keep the scope.
2. **Advisory (scope widened).** Row 15, "Topical corticosteroid". fr "Corticoïde local" also covers nasal, inhaled
   and injected use. Proposed: "Corticoïde topique".
3. **Advisory (term).** Row 20, "Akathisia or tardive movements". The fr, es and tr drafts are literal and not
   clinical usage. Proposed: fr "Akathisie ou mouvements anormaux tardifs", es "Acatisia o movimientos anormales
   tardíos", tr "Akatizi veya tardif hareket bozuklukları". These keep the English scope, which is wider than tardive
   dyskinesia. de is already fine.
4. **Advisory (term).** Row 56, "Vestibular suppressant". de "Vestibuläres Sedativum" is not a term German GPs use.
   Proposed: "Antivertiginosum" (matches fr "Antivertigineux"). Both are slightly wider than the English term but match
   the Janus class, which includes betahistine and cinnarizine. es "Supresor vestibular" and tr "Vestibüler baskılayıcı"
   are acceptable.
5. **Advisory (term).** Row 57 tr "Tükürük yerine geçen ürün". Turkish doctors say "Yapay tükürük". The row cannot be
   checked, so the term appears only in the scope section.
6. **Advisory (consistency).** Row 47 tr "Antidiyareik ilaç" against rows 28 and 42 "Antidiyareik". The English
   differs too ("Antidiarrheal agent"), but every other language uses one term. Proposed: "Antidiyareik".
7. **Owner decision.** Row 49, Drug B is published as "Vitamin or Mineral Deficiency", the same as the adverse event.
   The translations reproduce it faithfully, which is correct under the scope rule. In the note the line reads "PPI →
   deficiency → deficiency", and a doctor will take it for a typo. Options: print a fixed tag "(as published)" after
   Drug B for this row, or add one sentence saying Janus checks vitamin B12, magnesium and oral iron supplements (the
   class of the owner decision of 2026-11-07).

---

## 3. sentences.csv

Counts: 112 rows (26 claim, 37 fixed, 29 label, 12 heading, 8 option), 31 `shared`. I found no forbidden phrase in any
language. Whole-word matching does not trigger on tr "tanınan" or "tanınmadı".

1. **S1 (blocking): `finding.cascade` states an order that is not always known.** "{index} followed by {marker}"
   (tr "ve ardından", de "und danach", fr "puis", es "seguido de") is also printed for `same_month` and `date_unknown`
   findings. In those cases the next sentence says the order is not known. Proposed: state the match in
   `finding.cascade` and the order in the timing sentences.
   - `finding.cascade`: "{index} and {marker} match the published prescribing-cascade pattern {drug_a} → {event} →
     {drug_b} (PIPC list, row {row})."
   - `finding.timing.within_window` (params `index`, `marker`, `months`, `window`; evidence `rule;window`): "{marker}
     was started {months} months after {index}, within the {window}-month window commonly used in prescription sequence
     symmetry analysis."
   - `finding.timing.after_window` (same params; evidence `rule;window`): "{marker} was started {months} months after
     {index}. This is longer than the {window}-month window commonly used in prescription sequence symmetry analysis,
     so Janus lists the pattern with lower priority."
   - `same_month` and `date_unknown` are correct as drafted.
   The localization reviewer adapts the four other languages.
2. **S2 (blocking): `finding.timing.after_window` cites only `rule`.** The sentence makes a claim about the window used
   in studies, which is the Hendrix 2024 claim. Add the `window` role, or drop the clause (rule 5: no evidence, no
   sentence). The engine currently adds the window id to `within_window` findings only, so the builder needs it from
   `rule_base.window_evidence_id`.
3. **S3 (advisory): window accuracy.** Hendrix et al. 2024 is a PSSA methods guide. Twelve months is a common
   choice, not the only one, so write "commonly used" (as in S1). The window can be configured (1–60 months), but the
   citation supports only 12. If the rule base is loaded with another window, the timing sentences should not cite
   Hendrix for it. Starts are entered by month, so "{months} months" is a difference of calendar months. That is
   acceptable, but the localization reviewer should keep "months" plural-safe.
4. **S4 (advisory): BMJ priority sentences.** The figures match `cascade_priority.csv`: incidence for rows 65, 9, 25;
   adjusted sequence ratio for rows 60, 47, 26. "Incidence {value}" has no denominator, so a doctor may read it as the
   patient's risk. The evidence record's title does not say "Ontario". Proposed:
   - "A BMJ cohort study of high-priority prescribing cascades in older adults reports this cascade among those with
     the highest incidence: {value} (confidence interval {low} to {high})."
   - "… among those with the highest adjusted sequence ratio: {value} (confidence interval {low} to {high}). A ratio
     above one means the second medicine was started after the first more often than before it."
   Before acceptance, confirm "Ontario" and the incidence definition (population, window) against the abstract. The
   interval level (95 %) cannot be written in a claim template (no digits). Pass it as a parameter or leave it out.
5. **S5 (advisory): statistics scope.** `stat.reports_ratio` and `stat.coverage.*` say that reports "name" the
   ingredient. The pair is queried with scope `suspect` (Req 9.1), so "list {ingredient} as a suspect medicine
   together with {event}" is more exact. Hand to the statistician.
6. **S6 (advisory): shared texts in a doctor note.** The wording is already reviewed. On fit:
   - `stat.absence` ("your medicines") speaks to the patient. Use a note variant ("the patient's medicines"), as
     `scope.no_pattern` already does.
   - `stat.denominator` ends "Figures for all reports are shown beside these". That is true only if the note prints
     the all-report figures. Otherwise use a note variant.
   - The safety lines speak to the patient. They fit because the patient carries the note and rule 10 puts them first.
   - The other shared rows (disclaimer, Memory limits, screening, attribution, emergency and crisis labels) fit.
7. **S7 (no change): `abrupt_stop`.** The line is correct and idiomatic in all five languages:
   - en "Do not stop this medicine suddenly." (exact rule 4 text)
   - tr "Bu ilacı aniden bırakmayın."
   - de "Setzen Sie dieses Arzneimittel nicht plötzlich ab."
   - fr "N'arrêtez pas ce médicament brutalement." (the usual French label wording)
   - es "No suspenda este medicamento de forma brusca."
   None collides with a forbidden phrase. Optional for tr: "Bu ilacı aniden kesmeyin" is closer to Turkish leaflet
   wording ("birden kesmeyiniz") and does not match "ilacınızı kesin".
8. **S8 (no change): other claim templates.** These templates describe a published pattern or a check and give no
   verdict, no diagnosis and no advice: `finding.supporting`, `finding.form_extension` (Vander Zanden 2001 is a review
   in Ann Pharmacother; row 3 eye drops), `finding.notice.*`, `finding.review`, `chain.sequence`, `scope.*`
   (`scope.no_pattern` keeps the rule 3 meaning) and `integrity.*`. The explanation in `findings_form_unconfirmed`
   matches the engine (all codes of the key are used when the form is not confirmed).
9. **S9 (advisory): outcome page.** The two questions match Requirement 3.1 and give no advice. Suggestions:
   - `outcome.action_on.index` and `.marker` ("First medicine" and "Second medicine") should carry the ingredient name
     as a parameter, so the doctor does not have to map the pattern's steps.
   - "Medicine changed" → "Switched to another medicine", to separate it from a dose change.
   - Add to `outcome.intro`: "Leave a pattern unanswered if you are not sure."
   - Only one action per finding can be recorded. If both medicines were changed, the doctor cannot say so. This is
     the owner's call, since Requirement 3.1 fixes one action.

---

## 4. Owner question: Turkish and English cells equal to TİTCK ingredient strings

I see no clinical reason to treat these cells differently. A nonproprietary name has one correct spelling per
language, so a correct Wikidata label for a widely used substance should match the regulator's ingredient string. The
212 Turkish matches are mostly the names Turkish doctors read every day. Removing them would send the most common
medicines to the English fallback and make the note harder to read in Türkiye. If anything, a match is weak evidence that
the label is right. Each row already records its Wikidata provenance (`source` = extract run id). If the owner wants
independence from the TİTCK list, the cross-check can run at review time without committing any TİTCK string. Whether
to keep these cells is a provenance and licence question, and the decision is the owner's.

## 5. Decisions for the owner
1. Fix policy for wrong non-English cells: clear them (this report), or accept named national INN forms from a native
   reviewer.
2. Capitalization (F9): edit the file, or lower-case at render time.
3. Product keys (F2): rename to the substance INN here, and merge the keys in resolution.
4. Wrong ATC codes (F13): approve a curated code-exclusion file and an RxClass cross-check before any note is issued.
5. Row 49 Drug B: print "(as published)", add an explanatory sentence, or leave it as is.
6. Rewording of `finding.cascade` and the timing templates (S1, S2), and the BMJ sentence after checking the abstract
   (S4).
7. Outcome page: names in the action labels; one action per finding (S9).
8. J1 and J2: `source` tag and acceptance of the curated labels (F11).
9. TİTCK-equal cells: keep (my view) or drop (§4).
