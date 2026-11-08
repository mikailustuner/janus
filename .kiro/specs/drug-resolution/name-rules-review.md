# Name rules review: salt, ester, connector and switch rules (Phase 2)

> Review sheet for the owner (drug-resolution task 20, review stop). Drafted by the pharmacologist
> agent on 2026-11-08. It covers the word lists, connectors, three switches, anion-acid table,
> French route rows and synonym proposals of Requirement 12. **No rule data is enabled:**
> `name_lists.py`, `data/anion_acid_forms.csv`, `data/route_atc_groups.csv` and
> `data/ingredient_synonyms.csv` are unchanged; the appendices are the exact text to paste after the
> owner's decision.
>
> **Review status.** Reviewed by the AI pharmacologist agent on 2026-11-08; accepted by the owner:
> **pending**. It **still needs a review by a pharmacist or physician before any public claim** is
> made about these rules.
>
> Accepted set measured with the what-if tool (`coverage_snapshot snapshot --label accepted`,
> rule file = Appendix E plus one Turkish synonym row kept in the data directory): dataset inputs
> hash `bab89a5b`. Baseline `f55a79cf` (Phase 1 code, nothing enabled).

## 1. How it was derived

- **Evidence files** (all in the git-ignored data directory, `.data/resolution/`): the rule-impact
  report `name-rules-fedc234a.json` (every candidate word, switch and acid row, per source), the
  baseline snapshot `coverage-baseline-f55a79cf.json` with its per-name sidecar, and the what-if run
  with every candidate on (`coverage-all-candidates-bed1cf07.json`). Artifacts: BDPM 2026-11-03,
  Nomenclátor 2026-11-07, FAERS 2026-10-28, the current openFDA NDC and TİTCK artifacts, Wikidata extract run
  `20261107T163917Z-6bb8fcbc-6855` (3,766 items, 3,272 eligible).
- **Sources and sizes** (distinct names / occurrences): TİTCK 4,502 / 31,885; openFDA 7,655 /
  220,238; BDPM 2,847 / 27,477 (274 homeopathic presentations left out); Nomenclátor 2,583 / 35,875;
  FAERS 6,716 / 6,201,428.
- **Method.** Every word of the report was read with its effect, and for the Nomenclátor with the
  published-code agreement. Beyond the report I (a) ran a scratch harness (in `/tmp`, not committed)
  that maps all names of the five sources for any rule set in about 10 seconds, and used it to take
  each connector, each `NOT_ALONE` word, each switch and each acid row out of the accepted set in turn
  and see what changes; (b) traced every mapped→other-key, mapped→ambiguous and mapped→unmapped case
  to the word or switch that causes it; (c) listed every new mapping that rests on an alias only (not
  on a label), every Nomenclátor mapping whose key has no code in the published code's 5-character
  group, and every new mapping where the name and the mapped label carry a different counter-ion or
  anion; (d) searched all still-unmapped names for words in a different order than a label and for
  anions whose acid has a label.
- **ATC codes.** 54 WHOCC index group pages were fetched one at a time with `curl` on 2026-11-08
  (URL form `https://atcddd.fhi.no/atc_ddd_index/?code=<group>&showdescription=no`, index last updated
  2026-01-20) and read; nothing is copied, and each note below states the conclusion in my own words.
  Pages: A09AA A09AB A11HA A12CA A14AA A16AX B01AC B01AE B03BB B05CB B05XA B05XB C01DA C08CA C09CA
  C10AB D04AX D07AB D07AC D08AG D10AE G02BA G03BA G03CA H02AA H02AB J01CE J01DC J01XX J04AA J05AE
  J06BD L01EH L01EX L04AA M03BX M05BA M09AX N01BB N02AA N02BA N02BG N03AG N06AA N07AA N07XX P01BA
  R07AX S01BA S01LA S01XA V03AB V03AE V03AF.
- **Not checked.** No pharmacist or physician has read this. The about 400 newly mapped French names have
  no published code, so for BDPM the checks are the three detectors in (c) plus the top gains by
  occurrence, not a code comparison. Wikidata label quality was checked only where a case surfaced
  (two label errors are reported in Sections 4 and 10). No TİTCK product name or ingredient string is
  quoted; TİTCK appears as counts and as English descriptions.

## 2. Decisions by language

**Rules I applied.** A word is rejected when it changes the substance (different code or class),
collapses a substance that has a code of its own into its parent (checked on WHOCC), only creates
ambiguity, is a class or placeholder word, or leaves a name part that happens to be another
substance. A word that occurs in no name is not added (no evidence, no word). The tables give each
word's effect alone, with the connectors of its language switched on; "+a / b mapped" = a names and b
occurrences move from unmapped to mapped; "amb" = become ambiguous; "ATC" = of the single-ingredient
products that publish a code, how many map and how many of those map to an ingredient with a code in
the same 5-character group (after the word; before it the figure is zero for almost every word).

### 2.1 French (BDPM)

| Word | Names | Occ. | Effect (names / occ.) | ATC | Decision | Reason |
|---|---|---|---|---|---|---|
| `chlorhydrate` | 172 | 1,178 | +148 / 1,045 mapped; amb 2 / 10 | – | accept | hydrochloride; the 2 ambiguous names are lysozyme (two items share the name) |
| `dichlorhydrate` | 13 | 115 | +10 / 111 mapped | – | accept | dihydrochloride |
| `anhydre` | 74 | 846 | +33 / 513 mapped; amb 2 / 20 | – | accept | "anhydrous"; the base hydrate pattern does not match it, so it is an ordinary salt word (owner decision 3) |
| `sodique` | 46 | 492 | +34 / 401 mapped | – | accept | counter-ion adjective, same policy as Phase 1 `sodium` |
| `potassique` | 1 | 85 | +1 / 85 mapped | – | accept | as `sodique` |
| `calcique` | 6 | 42 | +4 / 40 mapped | – | accept | as `sodique` |
| `hemifumarate` | 2 | 70 | +2 / 70 mapped | – | accept | hemifumarate (bisoprolol) |
| `chlorure` | 43 | 868 | +10 / 40 mapped; amb→mapped 2 / 221; amb→unm 5 / 91; mapped→amb 1 / 1 | – | accept | salt word like Phase 1 `chloride`; mineral chlorides stay whole by the "nothing left" rule; net effect in Section 2.4 |
| `bromure` | 17 | 57 | +7 / 22 mapped; mapped→unm 2 / 2 | – | accept | salt word like `bromide`; the 2 mapped→unmapped exist only against the connector-only state (`BROMURE DE SODIUM` would reach the bromide ion item once `de` is a connector); with the word both stay whole |
| `fumarate` | 10 | 247 | none | – | no entry | already in the base list; no change |
| `acetate` | 38 | 220 | none | – | no entry | already in the base list |
| `maleate` | 11 | 115 | none | – | no entry | already in the base list |
| `tartrate` | 7 | 50 | none | – | no entry | already in the base list |
| `propionate` | 3 | 76 | none | – | no entry | already in the base list |
| `digluconate` | 4 | 85 | none | – | no entry | already in the base list |
| `tryptophane` | 3 | 99 | +1 / 74 mapped; mapped→other key 1 / 17 | – | reject | stereo marker "L"; mapped to magnesium aspartate: wrong substance |
| `acide` | 79 | 799 | +14 / 62 mapped | – | reject | not a salt word; acid names are handled by `acid_word_order`; as a salt word it maps to unrelated names |
| `solution` | 13 | 56 | +3 / 28 mapped | – | reject | pharmaceutical form word, not part of the substance |
| `alfa` | 37 | 193 | +1 / 27 mapped | – | reject | part of an INN (epoetin alfa mapped to darbepoetin alfa): wrong substance |
| `magnesique` | 0 | 0 | none | – | not added | no name contains it |
| `monosodique` | 5 | 38 | +1 / 2 mapped | – | accept | multiplier form of `sodique`; leaving it out lets two anions with the same leftover adjective collide |
| `disodique` | 8 | 20 | +2 / 8 mapped | – | accept | as `monosodique` |
| `trisodique` | 2 | 2 | none | – | accept | as `monosodique`: `CITRATE TRISODIQUE` mapped to trisodium phosphate in the draft run |
| `monopotassique` | 2 | 6 | mapped→unm 1 / 5 | – | accept | as `monosodique`; the 5 occurrences were mapped to potassium hydrogen tartrate in Phase 1 (wrong) |
| `dipotassique` | 3 | 13 | +1 / 4 mapped | – | accept | as `monosodique` |
| `monocalcique` | 1 | 2 | none | – | accept | as `monosodique` |
| `tricalcique` | 1 | 1 | mapped→unm 1 / 1 | – | accept | as `monosodique`; Phase 1 mapped `PHOSPHATE TRICALCIQUE` to calcium citrate (wrong) |
| `hydrogenosuccinate` | 1 | 13 | +1 / 13 mapped | – | accept | hydrogen succinate (doxylamine) |

`acide` is handled by `acid_word_order` (Section 4.3); `alfa`, `solution` and the stereo marker belong
to the name. **Result:** 17 words accepted (9 of the 16 candidates plus 8 found here: seven counter-ion
forms with a multiplier prefix and `hydrogenosuccinate`), 4 rejected, 6 already in the base list, 1 not
added (`magnesique`: no name contains it).

### 2.2 Spanish (Nomenclátor)

| Word | Names | Occ. | Effect | ATC agree/mapped of products | Decision | Reason |
|---|---|---|---|---|---|---|
| `hidrocloruro` | 247 | 4,311 | +195 / 3,656 mapped; amb 2 / 5 | 2788/2839 of 3375 | accept | hydrochloride |
| `dihidrocloruro` | 23 | 247 | +9 / 142 mapped | 116/116 of 216 | accept | dihydrochloride |
| `hidrobromuro` | 8 | 273 | +7 / 269 mapped | 228/228 of 229 | accept | hydrobromide |
| `besilato` | 5 | 500 | +4 / 476 mapped | 119/119 of 143 | accept | besylate (amlodipine, clopidogrel, atracurium) |
| `medoxomilo` | 1 | 411 | +1 / 411 mapped | 95/95 of 95 | accept | ester; Phase 1 strips `medoxomil`; 95 of 95 agree (see Result) |
| `cilexetilo` | 1 | 192 | +1 / 192 mapped | 111/111 of 111 | accept | ester; Phase 1 has `cilexetil` |
| `axetilo` | 1 | 93 | +1 / 93 mapped | 93/93 of 93 | accept | ester; Phase 1 has `axetil` |
| `etexilato` | 2 | 69 | none | 0/0 of 69 | reject | WHOCC B01AE: the code is named "dabigatran etexilate" (B01AE07); no measured gain |
| `trihidrato` | 13 | 795 | +5 / 323 mapped | 173/173 of 524 | accept | hydrate |
| `monohidrato` | 56 | 703 | +21 / 400 mapped; amb 1 / 22 | 119/309 of 527 | accept | hydrate; the ambiguous name is a substance with two items |
| `dihidrato` | 22 | 415 | +4 / 131 mapped | 119/122 of 282 | accept | hydrate |
| `hemihidrato` | 13 | 185 | +7 / 132 mapped | 107/107 of 143 | accept | hydrate |
| `pentahidrato` | 3 | 34 | +1 / 28 mapped | 26/26 of 31 | accept | hydrate |
| `anhidra` | 5 | 48 | +5 / 48 mapped | 10/37 of 37 | accept | anhydrous (matches the hydrate pattern) |
| `calcica` | 7 | 697 | +5 / 373 mapped | 272/272 of 496 | accept | counter-ion adjective |
| `calcico` | 2 | 4 | +1 / 2 mapped | 2/2 of 2 | accept | counter-ion adjective |
| `sodica` | 29 | 658 | +22 / 538 mapped | 507/508 of 611 | accept | counter-ion adjective |
| `sodico` | 24 | 637 | +17 / 546 mapped | 527/527 of 614 | accept | counter-ion adjective |
| `potasico` | 2 | 166 | +1 / 164 mapped | 89/89 of 91 | accept | counter-ion adjective |
| `magnesico` | 4 | 181 | +2 / 118 mapped | 104/104 of 167 | accept | counter-ion adjective |
| `sodio` | 81 | 915 | +25 / 567 mapped | 99/274 of 484 | accept | counter-ion noun (Section 2.4); low agreement because infusion products publish solution codes (B05BB) while the item carries B05XA, B05CB, A12; substance right |
| `potasio` | 16 | 297 | +5 / 20 mapped | 20/26 of 27 | accept | as `sodio` |
| `calcio` | 20 | 215 | +4 / 50 mapped | 46/46 of 71 | accept | as `sodio` |
| `fumarato` | 16 | 539 | +11 / 454 mapped | 453/453 of 466 | accept | fumarate |
| `hemifumarato` | 2 | 69 | +2 / 69 mapped | 61/61 of 61 | accept | hemifumarate |
| `maleato` | 23 | 379 | +16 / 342 mapped | 141/143 of 179 | accept | maleate |
| `citrato` | 16 | 403 | +10 / 381 mapped | 370/375 of 383 | accept | citrate |
| `oxalato` | 3 | 258 | +3 / 258 mapped | 258/258 of 258 | accept | oxalate |
| `mesilato` | 22 | 191 | +18 / 119 mapped | 86/115 of 182 | accept | mesylate; low agreement is kinase-inhibitor code renumbering (L01XE to L01EX/L01EA), same substance |
| `succinato` | 13 | 147 | +6 / 37 mapped | 30/30 of 122 | accept | succinate (metoprolol, solifenacin) |
| `hidrogenosuccinato` | 2 | 29 | +2 / 29 mapped | 20/20 of 20 | accept | hydrogen succinate |
| `tartrato` | 15 | 209 | +11 / 152 mapped | 134/135 of 192 | accept | tartrate |
| `bitartrato` | 7 | 63 | +6 / 61 mapped | 21/22 of 24 | accept | bitartrate |
| `sulfato` | 49 | 303 | +27 / 229 mapped | 137/137 of 192 | accept | sulfate |
| `hidrogenosulfato` | 2 | 48 | +2 / 48 mapped | 46/46 of 46 | accept | hydrogen sulfate |
| `acetato` | 49 | 310 | +28 / 180 mapped; amb 3 / 27 | 125/127 of 224 | accept | acetate; some bases have two items (ulipristal, megestrol), so the result is ambiguous, never a guess |
| `propionato` | 3 | 107 | +3 / 107 mapped | 40/40 of 40 | accept | propionate |
| `dipropionato` | 2 | 80 | +2 / 80 mapped | 21/21 of 21 | accept | dipropionate |
| `fosfato` | 25 | 218 | +11 / 100 mapped | 65/68 of 134 | accept | phosphate |
| `digluconato` | 1 | 90 | +1 / 90 mapped | 59/59 of 59 | accept | digluconate (chlorhexidine) |
| `benzoato` | 4 | 69 | +4 / 69 mapped | 68/68 of 68 | accept | benzoate |
| `nitrato` | 8 | 27 | +7 / 26 mapped | 24/24 of 24 | accept | nitrate (azole antifungals) |
| `malato` | 4 | 32 | +3 / 31 mapped | 12/31 of 31 | accept | malate |
| `esilato` | 1 | 23 | +1 / 23 mapped | 23/23 of 23 | accept | esylate (nintedanib) |
| `xinafoato` | 1 | 46 | +1 / 46 mapped | 7/7 of 7 | accept | xinafoate (salmeterol) |
| `olamina` | 2 | 50 | +2 / 50 mapped | 50/50 of 50 | accept | olamine |
| `erbumina` | 1 | 31 | +1 / 31 mapped | 6/6 of 6 | accept | erbumine (perindopril) |
| `resinato` | 1 | 42 | +1 / 42 mapped | 42/42 of 42 | accept | resinate (nicotine) |
| `furoato` | 3 | 74 | +2 / 70 mapped | 26/49 of 52 | reject | esters with codes of their own (fluticasone, mometasone furoate); 26 of 49 agree; Phase 1 precedent |
| `aceponato` | 2 | 26 | +2 / 26 mapped | 0/26 of 26 | reject | methylprednisolone aceponate D07AC14 has its own code; 0 of 26 agree |
| `dietilamina` | 2 | 30 | +2 / 30 mapped | 25/25 of 25 | reject | 25 diclofenac products are fine, but `SALICILATO DIETILAMINA` would map to salicylic acid; diethylamine salicylate must not (Req 12.7) |
| `arginina` | 4 | 34 | +2 / 29 mapped | 14/14 of 15 | reject | amino acid, a substance in its own right; `ARGININA` alone would be lost; use synonyms |
| `tipo` | 8 | 35 | +1 / 26 mapped | 26/26 of 30 | reject | `TOXINA BOTULINICA TIPO A` maps to the group item "botulinum toxin group": a class stand-in |
| `diclorobencilico` | 1 | 25 | +1 / 25 mapped | – | reject | `ALCOHOL DICLOROBENCILICO` maps to ethanol (leftover word `alcohol`): wrong substance |
| `sesquihidrato` | 3 | 86 | none alone | – | accept | hydrate; gains only together with `sodico` (pantoprazole 75, bromfenac 3), visible in the final run |
| `hemipentahidrato` | 2 | 21 | none alone | – | accept | hydrate; as above (pemetrexed 16, risedronate 5) |
| `mofetilo` | 1 | 43 | none alone | – | accept | needed with the `micofenolato` row (Appendix B) |
| `disodio` | 14 | 53 | +3 / 8 mapped | 8/8 of 38 | accept | counter-ion with multiplier |
| `trisodio`, `monosodio` | 3 | 7 | none | – | accept | counter-ion with multiplier (same reason as the French forms) |
| `tosilato` | 7 | 25 | +5 / 17 mapped | 7/17 of 23 | accept | tosylate; low agreement is kinase-inhibitor code renumbering |
| `hiclato` | 1 | 15 | +1 / 15 mapped | 14/14 of 14 | accept | hyclate (doxycycline) |
| `magnesio` | 18 | 70 | +6 / 31 mapped | 3/8 of 24 | accept | counter-ion noun; low agreement is published antacid and infusion codes; substance right |
| `cloruro` | 25 | 594 | +4 / 359 mapped | 26/194 of 214 | accept | salt word like `chloride` (Section 2.4); agreement low because infusion products publish B05BB codes |
| `bromuro` | 16 | 95 | +9 / 68 mapped | 56/56 of 62 | accept | salt word like `bromide` |
| `lactato` | 4 | 30 | +2 / 2 mapped | 1/1 of 2 | accept | Section 2.4 |
| `gluconato` | 2 | 4 | none | – | accept | Section 2.4 (keeps the anion from colliding across cations) |

**Result:** 60 words accepted (47 of the 54 in the report plus 13 found here), 7 rejected. The three
Spanish ester words follow the Phase 1 English ones (`medoxomil`, `cilexetil`, `axetil`). `etexilato`
is rejected because WHO names its code after the ester (B01AE07) and the word brings no gain; WHO also
names C09CA08 "olmesartan medoxomil", but there the Wikidata item for the code is labeled "olmesartan",
Phase 1 already strips `medoxomil`, and 95 of 95 products agree. If you prefer symmetry, adding
`etexilato` changes no number.

### 2.3 English (FAERS, openFDA)

| Word | Names | Occ. | Effect | Decision | Reason |
|---|---|---|---|---|---|
| `cypionate` | 3 | 944 | +3 / 944 mapped | accept | testosterone, estradiol cypionate; one code for all esters (G03BA03, G03CA03) |
| `enanthate` | 3 | 415 | +2 / 412 mapped | accept | testosterone, metenolone enanthate (G03BA03, A14AA04) |
| `pivalate` | 4 | 2,780 | +3 / 2,768 mapped | accept | flumetasone, fluocortolone, tixocortol, deoxycortone pivalate; WHO codes carry the parent name |
| `ditosylate` | 2 | 1,771 | +2 / 1,771 mapped | accept | lapatinib, valbenazine ditosylate |
| `terephthalate` | 1 | 1,624 | +1 / 1,624 mapped | accept | oxycodone terephthalate (one name) |
| `probutate` | 1 | 416 | +1 / 416 mapped | reject | hydrocortisone probutate (buteprate) has its own code D07AB11 |
| `glycinate` | 7 | 1,152 | +1 / 21 mapped | reject | 21 occurrences gained; the other names are mineral glycinates (elemental, left unmapped) |
| `hippurate` | 1 | 335 | +1 / 335 mapped | accept | methenamine J01XX05 lists hippurate and mandelate as notes |
| `mandelate` | 1 | 25 | +1 / 25 mapped | accept | as `hippurate` |
| `arginine` | 7 | 1,253 | +3 / 558 mapped; mapped→unm 2 / 249 | reject | amino acid; makes `ARGININE` and `ARGININE HYDROCHLORIDE` unmapped (249 occurrences lost); synonyms instead |
| `lysine` | 13 | 3,940 | +5 / 1,134 mapped; mapped→unm 2 / 170 | reject | as `arginine` (170 occurrences lost) |
| `ethanolate` | 2 | 325 | +1 / 319 mapped | accept | darunavir ethanolate (J05AE10 darunavir) (found by discovery) |
| `camsylate` | 3 | 146 | +3 / 146 mapped | accept | amlodipine, clopidogrel camsylate (C08CA01, B01AC04) (found by discovery) |
| `diacetate` | 6 | 157 | +3 / 126 mapped | accept | chlorhexidine, triamcinolone, gonadorelin diacetate (found by discovery) |
| `tetrahydrochloride` | 1 | 275 | +1 / 275 mapped | accept | trientine tetrahydrochloride (A16AX12) (found by discovery) |
| `esylate` | 1 | 252 | +1 / 252 mapped | accept | nintedanib esylate (L01EX09) (found by discovery) |
| `metazoate` | 1 | 156 | +1 / 156 mapped | accept | prednisolone sodium metazoate (H02AB06, no ester code) (found by discovery) |
| `diolamine` | 1 | 94 | +1 / 94 mapped | accept | treprostinil diolamine (B01AC21) (found by discovery) |
| `lauroxil` | 1 | 384 | +1 / 384 mapped | reject | aripiprazole lauroxil: prodrug with its own INN; owner rule, left unmapped and listed (Section 8) |
| `enacarbil` | 1 | 107 | +1 / 107 mapped | reject | gabapentin enacarbil: prodrug with its own INN; owner rule, left unmapped and listed (Section 8) |
| `methylsulfate` | 1 | 63 | +1 / 63 mapped (openFDA) | accept | neostigmine methylsulfate (N07AA01) |

**Result:** 15 words accepted (7 of the 11 candidates plus 8 from the discovery lists), 4 candidates
rejected, plus `lauroxil` and `enacarbil` rejected as prodrug words. Further discovered words (single-word removal, at least 20 occurrences; the two counts are
words in FAERS / openFDA, groups assigned by hand). All rejected:

| Group | Words | Reason |
|---|---|---|
| Four-letter biosimilar suffixes (`dyyb`, `szzs`, ...) | 52 / 1 | Not words. The `biologic_suffix` switch handles them (Section 4.1) |
| Inorganic or metal words (`oxide`, `hydroxide`, `iodide`, `zinc`, `lithium`, `barium`, `trisulfide`, ...) | 7 / 27 | Would turn inorganic compounds into an unrelated substance (antimony trisulfide → an antimonial drug, cupric oxide → cupric sulfate) |
| Class or placeholder words (`human`, `insulin`, `vitamin`, `nos`, `unspecified`, `recombinant`, `leaf`, `live`, ...) | 19 / 13 | Not salt words. Removing them leaves a word that is another substance (`NOS` is an alias of nitrous oxide) |
| Names that are INNs themselves (`vonoprazan`, `perindopril`, `aztreonam`, ...) | 19 / 4 | Heuristic artifact: removing the word left the counter-ion (arginine, lysine), which maps |
| Brand strings (`tylenol`, `mucinex`, `sudafed`, `colace`) | 4 / 1 | Brands, not salts |
| Prodrugs with their own INN (`lauroxil`, `enacarbil`) and esters with their own codes (`butyrate`, `salicylate`) | 3 / 1 | Owner rule and Phase 1 precedent; WHOCC N02BA lists sodium and potassium salicylate with codes of their own |
| Nucleotides (`diphosphate`, `triphosphate`) | 1 / 2 | `ADENOSINE DIPHOSPHATE` would become adenosine; a rule for two names (336 occurrences) is not worth it |

**TİTCK (Turkish): no change.** The report's 13 discovered words are 11 amino-acid names, the
Turkish cholecalciferol spelling and `furoat`. Turkish keeps the Phase 1 behavior (Req 12.1); `furoat`
is rejected for the same reason as `furoato`.

### 2.4 Counter-ions, chloride and bromide forms, and `NOT_ALONE`

- **Counter-ion words** (`sodio`, `potasio`, `calcio`, `magnesio`; `sodique`, `potassique`,
  `calcique`; adjective forms `sodica/sodico`, ...; multiplier forms `disodio`, `monosodique`, ...) are
  **salt words, not `NOT_ALONE`**: the same policy as Phase 1 `sodium` and `potassium`, because WHO
  usually gives the salts of one active anion a single code. A name made only of counter-ion and
  anion words (`CHLORURE DE CALCIUM`) is left whole by the "nothing left" rule. Taking `sodio`,
  `potasio`, `calcio` and `magnesio` out of the Spanish set costs 350 occurrences mapped (86.07 % →
  85.10 %) and adds 70 ambiguous, so they stay.
- **Chloride and bromide forms** (`chlorure`, `bromure`, `cloruro`, `bromuro`) are **salt words**,
  like Phase 1 `chloride` and `bromide`. As `NOT_ALONE` only (the first draft) they would not be
  stripped from `X CHLORURE`, and the measured loss is 0.22 points for BDPM and 0.21 for the
  Nomenclátor (81.73 % and 85.86 % against 81.95 % and 86.07 %). `lactato` and `gluconato` are added
  as salt words for the same reason as their Phase 1 English forms: without them (single-word run) `LACTATO MAGNESIO`
  maps to lactic acid, and in the accepted set 29 occurrences turn ambiguous because the leftover anion
  collides across cations.
- **`NOT_ALONE`** (kept whole when only they remain) holds the inorganic anions and elements whose
  stripped remainder would be another substance, plus anions where the cation changes the substance.
  Each entry below was tested by taking it out; "would map" = occurrences that then map or turn ambiguous.

| Language | Entries | Without it |
|---|---|---|
| fr | `oxyde`, `hydroxyde`, `fluorure`, `iodure` | 5, 22, 2 and 1 occurrences would map to a hydroxide, oxide or fluoride of another metal (for example sodium hydroxide → magnesium hydroxide, which Phase 1 already does) |
| fr | `fer`, `cuivre`, `argent` | iron names turn ambiguous (41 occurrences); copper names map to cupric sulfate (19); silver to silver nitrate (2) |
| es | `bicarbonato`, `carbonato`, `oxido`, `hidroxido`, `fluoruro`, `ioduro` | 2, 6, 10, 13, 2 and 12 occurrences (potassium bicarbonate would map to sodium bicarbonate) |
| es | `hierro`, `aluminio`, `cobre`, `plata`, `cinc` | `cinc` (Spanish "zinc") matters most: without it the elemental names `ZINC` become ambiguous between zinc acetate and zinc chloride (FAERS 4,077, openFDA 289, BDPM 16) |
| es | `glicerofosfato`, `edetato`, `alginato` | glycerophosphate of sodium maps to the calcium salt (sodium glycerophosphate has its own code B05XA14); `EDETATO DISODIO` (S01XA05) maps to calcium disodium edetate (V03AB03); sodium alginate maps to calcium alginate (17 occurrences) |
| en | `alginate`, `pidolate` | 395 FAERS occurrences of sodium and magnesium alginate and 6 of calcium pidolate map today to the calcium alginate and magnesium pidolate items (Phase 1 wrong keys); they become unmapped |
| fr, es, en | `ion` | `CHLORIDE ION` mapped to the bromide ion item (17 FAERS occurrences) once `bromure`/`bromuro` strip the labels of that item; removing `ion` from one list alone changes nothing, from all three it does |

Not added (no name changes in any source): `peroxyde`, `peroxido`, `yoduro`, `gluceptato`, `pidolato`
(Spanish; they matter only if the vowel rule is enabled, Section 4.2).

## 3. Connectors

Connectors are removed only at the start or end of a name after the salt words (Req 12.3) and count
as salt words for the "nothing left" test. Each was taken out of the accepted set in turn:

| Connector | Occurrences that change when it is removed | Decision |
|---|---|---|
| fr `de` | 2,004 mapped → unmapped, 288 mapped → ambiguous, 101 unmapped → mapped, 133 unmapped → ambiguous (BDPM); 11 TİTCK mapped → unmapped | keep |
| fr `d` | 366 mapped → unmapped (`CHLORHYDRATE D'ADRÉNALINE`) | keep |
| fr `du`, `des` | none | **drop** (no evidence) |
| es `de` | 149 mapped → unmapped (Nomenclátor), 115 FAERS (an English name that maps through a Spanish label) | keep |
| es `del` | none | **drop** (no evidence) |

Effect of keeping `de` and `d`: the Phase 1 key of 20 BDPM names becomes unmapped (17) or ambiguous
(3) (Section 9). In 17 of them the Phase 1 key was a different substance, reached because the
leftover `de` or a counter-ion matched an unrelated label; in 3 (4 occurrences) it was right by
coincidence. Recommended sets: fr `{de, d}`, es `{de}`.
The design draft listed `du`, `des`, `del`; they can be added when a source needs them.

## 4. The three switches

| Switch | Gain alone (names / occurrences) | Decision |
|---|---|---|
| `biologic_suffix` | FAERS 92 / 114,106; openFDA 24 / 66; others none | **turn on** |
| `acid_word_order` | BDPM 17 / 165; Nomenclátor 31 / 375; FAERS 1 / 67; openFDA 1 / 12; TİTCK 1 / 4 | **turn on**, with the fenofibric-acid rows (Appendix D) |
| `es_final_vowel` | Nomenclátor 94 / 763; BDPM 3 / 9; FAERS 3 / 886; openFDA 2 / 96; TİTCK 2 / 2 | **leave off as coded**; owner decision 1 |

### 4.1 `biologic_suffix`

All 116 names it maps (92 FAERS and 24 openFDA) are genuine biologics with a four-letter
suffix: infliximab, adalimumab, etanercept, rituximab, bevacizumab, trastuzumab, ustekinumab,
denosumab, pegfilgrastim, aflibercept, insulin glargine, aspart and lispro, immunoglobulin G,
ropeginterferon alfa-2b, velmanase alfa and others; the base maps by label to one key each (the WHOCC
code is the base's, for example J06BD04 for ansuvimab). Every mapped name of that shape is such a
biologic. No stem list is needed. 121 further names (144,717 occurrences) have a base without an
ingredient-level code and stay unmapped (Section 8). The step is general, so a future name of the
shape `word-abcd` whose base maps would also map; the coverage report lists names by step, which lets
the owner watch the `biologic_suffix` list.

### 4.2 `es_final_vowel` (Spanish -a, -o)

Gain alone is real (Nomenclátor +763 occurrences, +2.1 points), but the switch cannot be enabled as
coded. Every harmful case, traced to its cause:

| Case | Source | Cause |
|---|---|---|
| `VITAMINA A` (3 occ.) mapped to vitamin E instead of retinol: **mapped→other key** | Nomenclátor | The rule runs inside the fixed-point loop, so `vitaminaa` loses two vowels (`vitamin`), the key of `vitamin E` |
| `FOLITROPINA ALFA` (32) and `CORIOGONADOTROPINA ALFA` (1) become unmapped: **mapped→unmapped** | Nomenclátor | Phase 1 matched the English label `follitropin alpha` by plain spelling; English labels are not keyed with the Spanish rule, so the vowel-stripped query no longer meets it |
| `DOXEPIN` (886): **mapped→ambiguous** | FAERS | The Spanish label `Doxepina` sits on two Wikidata items (the (E/Z) item with topical D04AX01 and the cidoxepin item with N06AA12); the vowel key now reaches both. Phase 1 mapped only the (E/Z) item |
| two spellings of medroxyprogesterone acetate (1 occurrence each): **mapped→ambiguous** | TİTCK | Wikidata gives the dydrogesterone item the Spanish label `medroxiprogesterona` (label error); the vowel key reaches both items |
| `GUARANA` (2) newly maps to guar gum | Nomenclátor | The German label `Guaran` of the guar gum item equals the vowel-stripped Spanish name: a wrong substance |
| `PIDOLATO CALCIO` (7) and `GLUCEPTATO POTASIO` (1) map to the magnesium or calcium salt | Nomenclátor | Cation collapse; `pidolato` and `gluceptato` would have to be `NOT_ALONE` |

A code variant measured with the same data: apply the vowel drop **once, to the last token only, and
only when that token has 5 or more letters**. Added to the accepted set it gives Nomenclátor
**89.06 %** (+2.99 points), TİTCK 79.25 % (+35 occurrences, 2 ambiguous), FAERS 86.59 %, and removes
the other-key and unmapped cases above. What remains: DOXEPIN (886) and `CHONDROITIN SULFATE A` (115)
would need two synonym rows (`DOXEPIN` → Q71704041, `CHONDROITIN SULFATE A` → Q408014); `GUARANA`
stays wrong (2 occurrences); `pidolato` and `gluceptato` go to the Spanish `NOT_ALONE`. This is a
code change, so I only recommend it (owner decision 1).

### 4.3 `acid_word_order`

All 48 BDPM and Nomenclátor gains (17 and 31) are acids written in the other order (`ACIDE ASCORBIQUE`,
`ASCORBICO ACIDO`, acetylsalicylic, ibandronic, tranexamic, fusidic, folic, valproic, gadoteric,
salicylic acid and others), each landing on the acid's own item. Two points need an explicit note:
`ACIDE GLUTAMIQUE` (BDPM, 67 occurrences with its inverted spelling) maps to the item named "glutamic
acid hydrochloride", which is the WHO substance of A09AB01 and where Phase 1 already maps FAERS
`GLUTAMIC ACID` (91); `HIALURONICO ACIDO` maps to the sodium hyaluronate item (4 occurrences).
**One side effect:** the fenofibrate item carries the Spanish alias "ácido fenofíbrico", so the
English name `FENOFIBRIC ACID` (FAERS 67, openFDA 12) and the Turkish spelling (4 TİTCK occurrences,
which Phase 1 mapped by product code to choline fenofibrate) would map to fenofibrate. Fenofibric
acid is the active metabolite and WHO assigns it to C10AB11 choline fenofibrate (page note "refers to
fenofibric acid"). The fix is a synonym row to Q27259379 (Appendix D); the Turkish row is in
`.data/resolution/name-rules-synonyms-titck.csv` because the sheet quotes no TİTCK string. The
TİTCK `mapped→other key` of the all-candidates run (the 1 name) is this case.

## 5. Anion-acid table

Candidate rows from the report, and what I decided (acids resolve to exactly one key at load; the
report's `acid_resolves_to_keys` is 1 for all):

| Candidate row | Demand | WHOCC check (2026-11-08) | Decision |
|---|---|---|---|
| any `mycophenolate` → mycophenolic acid | FAERS 22,821, BDPM 21, openFDA 135 | L04AA: one code L04AA06; mofetil is a DDD note | **accept** (needs the Spanish word `mofetilo`) |
| fr `mycophenolate` → acide mycophénolique | BDPM 21 | same | **merge** into the `any` row |
| es `micofenolato` → acido micofenolico | Nomenclátor 49 | same | **accept**, acid label changed to the English `mycophenolic acid` (always indexed) |
| any `folate` → folic acid | FAERS 664 | B03BB: B03BB01 only | **accept** (`levomefolate` is another substance, untouched) |
| any `valproate` → valproic acid | FAERS 49, BDPM 23 | N03AG: N03AG01; valpromide is N03AG02 | **accept** |
| any `alendronate` → alendronic acid | FAERS 24 | M05BA: M05BA04 | **accept** |
| any `zoledronate` → zoledronic acid | FAERS 2 | M05BA: M05BA08 | **reject**: no demand (2 occurrences) |
| any `aminosalicylate` → aminosalicylic acid | FAERS 143 | J04AA: sodium and calcium aminosalicylate have **their own codes** J04AA02 and J04AA03 | **reject** (owner rule: salts with own codes) |
| Added: es `valproato`, es `risedronato` | Nomenclátor 17 and 51 | N03AG, M05BA (M05BA07 risedronic acid) | **accept** |

Looked at and **not rows**: salicylates (magnesium, calcium, diethylamine salicylate must not become
salicylic acid; N02BA lists sodium and potassium salicylate with codes of their own);
clavulanate (no eligible clavulanic acid item; the WHO code appears only in combinations); levomefolate;
meclofenamate, ethacrynate, fusidate, ioxaglate, glycyrrhizate (2 to 8 occurrences each, some already
reached through item aliases). Alendronate, risedronate, pamidronate, clodronate, cromoglicate and
fusidate sodium salts mostly map today through aliases of the acid items; the rows above only close
the cases the aliases miss. Final rows: **Appendix B (7 rows).**

## 6. French route rows

French strings are the published BDPM strings (lowercase, accents). The 30 most frequent contain
every route of 99.2 % of the presentations. Modeled on `data/route_atc_groups.csv`: 24 strings get a
row, 21 of them by copying the matching English row (same intent), 3 new. Six get **no row** and fall
back to all codes: `voie extracorporelle autre` (242 presentations: apheresis and dialysis fluids use
anticoagulant and electrolyte codes of B01 and B05; a wrong prefix would drop the right code),
`intrapéritonéale` (65: dialysis solutions), `intracérébroventriculaire` (30), `intradermique` (23),
`intralésionnelle` (22), `intravésicale` (35): instillations use codes from several chapters (L01,
L03, G04) and I would be guessing.

| French route | Row | Basis |
|---|---|---|
| orale, intraveineuse, sous-cutanée, intramusculaire, cutanée, inhalée, ophtalmique, sublinguale, rectale, transdermique, péridurale, vaginale, nasale, intraarticulaire, périneurale, infiltration, dentaire | copy of the English row | same route |
| voie buccale autre, gingivale | BUCCAL row; DENTAL row | oromucosal and gum products |
| intraartérielle | INTRAVENOUS groups | contrast media, radiopharmaceuticals, cytostatics, anticoagulants are the same systemic groups |
| périarticulaire | INTRA-ARTICULAR groups | corticosteroids and local anesthetics |
| intrathécale | new: `J01;L01;M03;M09;N01B;N02;V08` | WHOCC: ziconotide N02BG08 (N02BG), baclofen M03BX01 (M03BX), nusinersen M09AX07 (M09AX); local anesthetics, opioids, contrast agents |
| intra-utérine | new: `G02B` | WHOCC G02BA lists intrauterine systems by device (G02BA03 plastic IUD with progestogen) |
| intravitréenne | new: `S01` | WHOCC S01LA (verteporfin, ranibizumab, aflibercept, faricimab) and S01BA corticosteroid implants |

Rows: **Appendix C (24 rows, to append to the existing file).**

## 7. Synonym proposals

Proposals only (Appendix D, 26 rows). Each is a reviewed single ingredient whose name the rules
cannot reach, with a Wikidata item that has an ingredient-level code and a WHOCC check. Gain when all
are applied: FAERS +14,936 occurrences (+0.24 points), openFDA +197, BDPM +131 (and 5 kept), Nomenclátor
+625. Groups:

- **FAERS names with a marker the salt rule cannot handle:** `CABOZANTINIB S-MALATE` (7,888),
  `RIBOFLAVIN 5^-PHOSPHATE SODIUM` (3,381), `ASPIRIN DL-LYSINE` and `ASPIRIN LYSINE` (2,351; WHOCC
  N02BA01 covers lysine acetylsalicylate), `ROPIVACAINE` and its hydrochloride (885; the item label
  starts with `(S)-`), `SEVELAMER CARBONATE` (364; carbonate is protected), `FENOFIBRIC ACID` (67).
- **Electrolytes in inverted order** (BDPM and Nomenclátor): sodium, potassium, calcium and magnesium
  chloride and sodium bicarbonate. All words are salt words, so the rule leaves the name whole and
  the label has another order. WHOCC B05XA and A12CA confirm the codes. Sodium glycerophosphate has
  its own code (B05XA14), so the glycerophosphates are **not** mapped (Section 9).
- **Spanish and French spellings the vowel switch would reach if enabled:** `POVIDONA IODADA`,
  `FLUOCINOLONA ACETONIDO`, `NITRICO OXIDO`, `ISOSORBIDA MONONITRATO` (mononitrate has its own code
  C01DA14), `BENZOILO PEROXIDO`, `SEVELAMERO CARBONATO`, three French ropivacaine spellings.
- **Only if the vowel variant is adopted:** `DOXEPIN` → Q71704041, `CHONDROITIN SULFATE A` → Q408014
  (not in Appendix D).
- **Pancrelipase** (`PANCRELIPASE AMYLASE`, `LIPASE`, `PROTEASE`, 8,227 to 8,230 FAERS occurrences
  each): the extract has **no pancrelipase item**. It has pancreatin (Q426846, A09AA02, which WHOCC
  A09AA names "multienzymes (lipase, protease etc.)"). Pancrelipase and pancreatin are related
  preparations, not the same named substance, so I did not propose a row: owner decision 4.

## 8. Left unmapped on purpose

| Group | Examples (public names) | Occurrences, reason |
|---|---|---|
| Components with no ingredient-level code | carbidopa, vilanterol (`VILANTEROL TRIFENATATE`), foscarbidopa, foslevodopa, sacubitril alone, bictegravir, clavulanic acid | FAERS 16,682; 14,063; 10,338; 10,328; 5,994; 1,998; 5,582. BDPM and Nomenclátor: carbidopa 135, clavulanate 272. The WHO codes exist only in combinations; no proxy |
| Pancrelipase parts | see Section 7 | FAERS 3 × 8,227 |
| Prodrugs with their own INN | fosaprepitant, gabapentin enacarbil, aripiprazole lauroxil, diroximel fumarate | FAERS 3,088 for the four; openFDA fosaprepitant 41 ingredient lines. Owner rule; their own INN is not their parent |
| Elemental names | calcium, copper, iron, zinc, potassium, selenium, magnesium, manganese, chromium, iodine | FAERS 10 names, 37,109 occurrences |
| Vitamin and class words, placeholders | `VITAMINS`, `VITAMIN D NOS`, `HERBALS`, `DIETARY SUPPLEMENT`, `MINERALS`, `FISH OIL`, `PROBIOTICS NOS`, `UNSPECIFIED INGREDIENT` | FAERS 12 names, 76,889 |
| Mixtures, water, devices | `WATER`, `DEVICE` | FAERS 5,109 |
| Amino acids of infusions | histidine, alanine, leucine, valine, serine, proline and others | BDPM 14 names, 1,090 (no eligible item in the extract) |
| Oils, vaccine strains, extracts, immunoglobulins | soy and olive oil, polio and influenza strains, plant extracts | BDPM about 300 names, 1,000; Nomenclátor about 155 names, 690 |
| Biologics and new substances whose base has no code | `risankizumab-rzaa`, `bimekizumab-bkzx` and 119 more | FAERS 121 names, 144,717 (counts only; no rule can add them) |
| Names with another cation or form | glycerophosphates, lactate, sodium and calcium folinate forms, aminosalicylate salts | cation changes the substance or the salt has its own code |
| Probable data error | `colchiceine` (openFDA 6) | listed since the 2026-11-07 review |

## 9. Results for the accepted set

Measured with `coverage_snapshot snapshot --label accepted --rules <Appendix E + Turkish row>` and
`compare` (files `coverage-accepted-bab89a5b.json`, `names-accepted-bab89a5b.json`).

| Source | Occurrences mapped before → after | Products fully mapped before → after | Target (Req 13.4) |
|---|---|---|---|
| BDPM (without 274 homeopathic) | 18,579 of 27,477 (67.62 %) → 22,518 (**81.95 %**) | 14,730 of 20,634 (71.39 %) → 17,982 (87.15 %); multi-ingredient 1,644 → 2,289 of 3,360 | ≥ 80 %: **met** |
| Nomenclátor | 17,271 of 35,875 (48.14 %) → 30,879 (**86.07 %**) | 13,828 of 30,388 (45.50 %) → 25,991 (85.53 %); multi 1,002 → 3,211 of 4,436 | ≥ 80 %: **met** |
| FAERS | 5,209,387 of 6,201,428 (84.00 %) → 5,370,978 (**86.61 %**) | not applicable | ≥ 86 %: **met** (suffix +114,106; acid rows +23,558; synonyms +14,936; English salt words and label side effects about +9,400) |
| TİTCK | 26,976 of 31,885 (84.6 %) → 26,976 (**84.6 %**) | 20,427 of 23,093 (88.46 %) → 20,419 (88.42 %); multi 2,895 → 2,894 | not lower than 84.6 %: **met** (occurrences equal; 8 products fewer, see below) |
| openFDA Rx | 59,759 of 65,160 (91.71 %) → 60,214 (**92.41 %**) | 52,110 of 55,840 (93.32 %) → 52,560 (**94.13 %**) | not lower than 93.3 %: **met** |
| openFDA Rx + OTC / all types | 118,377 of 220,238 (53.75 %) → 119,084 (54.07 %) | 95,017 of 135,688 (70.03 %) → 95,720 (70.54 %) | reported |

All targets are met without `es_final_vowel`. With the code variant of Section 4.2 the Nomenclátor
reaches 89.06 %.

**Change counts by kind** (names / occurrences):

| Source | unmapped→mapped | unmapped→ambiguous | ambiguous→mapped | ambiguous→unmapped | mapped→ambiguous | mapped→unmapped | mapped→other key |
|---|---|---|---|---|---|---|---|
| TİTCK | 2 / 9 | – | – | – | 3 / 9 | – | – |
| openFDA | 52 / 708 | – | – | – | – | 1 / 1 | – |
| BDPM | 414 / 3,654 | 8 / 26 | 11 / 378 | 18 / 53 | 3 / 4 | 17 / 89 | – |
| Nomenclátor | 619 / 13,608 | 6 / 54 | – | – | – | – | – |
| FAERS | 132 / 161,992 | – | – | – | – | 3 / 401 | – |

**No mapped name changes to a different key.** The remaining mapped→ambiguous and mapped→unmapped
cases and why each is acceptable:

- **BDPM mapped→unmapped, 17 names / 89 occ.** In 15 names (86 occ.) Phase 1 reached a different
  substance: `(S)-LACTATE DE SODIUM` (28) → silver sulfadiazine; the glycerophosphates of sodium,
  potassium, magnesium (24) → calcium glycerophosphate; sodium and potassium hydroxide (20) →
  magnesium hydroxide; monopotassium phosphate (5) → potassium hydrogen tartrate; copper gluconate
  (3) → cupric sulfate; magnesium thiosulfate (2) → sodium thiosulfate; calcium fluoride (1) → sodium
  fluoride; calcium disodium edetate (1) → edetate sodium; sodium iodide (1) → potassium iodide;
  tricalcium phosphate (1) → calcium citrate. The cause is that `de` is now a connector and the
  leftover counter-ion or anion word is protected, so the name stays whole and unmapped. Two names
  (3 occ.: magnesium hydroxide, sodium fluoride) lose a right key reached by coincidence. Acceptable;
  `SODIUM (BICARBONATE DE)` (5) is the one right key that would be lost and is restored by a synonym.
- **BDPM mapped→ambiguous, 3 names / 4 occ.:** sodium salicylate and diethylamine salicylate (3) were
  mapped to potassium salicylate, a salt with its own code (N02BA12); ferrous chloride tetrahydrate (1)
  now meets two ferrous items. Ambiguous means no guess.
- **BDPM ambiguous→unmapped, 18 / 53:** names that had several candidates and now have none
  (magnesium lactate, acetate and chloride forms); nothing was wrongly chosen before or after.
- **unmapped→ambiguous** (BDPM 8 / 26, Nomenclátor 6 / 54): bases that Wikidata holds as two items
  (bosentan and bosentan hydrate, ulipristal, megestrol, lysozyme, doxepin; medroxyprogesterone meets
  the dydrogesterone item through its wrong Spanish label). Never a guess.
- **TİTCK mapped→ambiguous, 3 names / 9 occ.:** two spellings of calcium folinate pentahydrate and one of
  sodium benzylpenicillin. Phase 1 mapped the first to sodium folinate (V03AF06) although calcium
  folinate is V03AF03; they are now ambiguous between both items. The second met penicillin G
  potassium, which shares J01CE01. Cause: the French label `folinate de calcium` loses `de calcium`,
  so its key meets the Turkish one. This is why TİTCK has 8 fewer fully mapped products at equal
  occurrences. Acceptable, and the better answer than the Phase 1 key.
- **TİTCK gain, 2 names / 9 occ.:** the Turkish spellings of L-arginine now map to the arginine
  hydrochloride item (WHO B05XA names it that way), where FAERS `ARGININE` already maps.
- **FAERS mapped→unmapped, 3 names / 401 occ.; openFDA 1 name / 1 occ.:** sodium alginate (393, plus 1
  openFDA) and magnesium alginate (2) mapped to the calcium alginate item; calcium pidolate (6) to
  the magnesium pidolate item. Phase 1 wrong keys; now unmapped (Section 2.4).
- **Two Wikidata label problems found** (a correction upstream is outside this project): the Spanish
  label of the dydrogesterone item, and doxepin split over two items.

## 10. Owner decisions

1. **`es_final_vowel`.** Recommend **leave off** now. Optional: approve the code variant (drop the
   vowel once, last token only, 5 or more letters; Nomenclátor 86.07 % → 89.06 %), with the two
   conditional synonym rows (`DOXEPIN`, `CHONDROITIN SULFATE A`) and `pidolato`, `gluceptato` in the
   Spanish `NOT_ALONE` (Section 4.2). Accept that `GUARANA` (2 occurrences) would map to guar gum.
2. **Phase 1 correction, `aceponate` in `BASE_SALT_WORDS`.** WHOCC D07AC gives methylprednisolone
   aceponate (D07AC14) and hydrocortisone aceponate (D07AC16) codes of their own, yet the base list
   strips the word, so the hydrocortisone aceponate item (D07AC16, topical) is indexed as
   "hydrocortisone" and 5,230 FAERS occurrences plus 181 openFDA ingredient lines of hydrocortisone
   acetate, sodium succinate, valerate, phosphate and hemisuccinate sit on it instead of on
   hydrocortisone (H02AB09 systemic). Removing `aceponate` and the Turkish `aseponat` moves them to
   hydrocortisone and changes 3 TİTCK names to another key. Recommend a separate decision and a
   small change; I did not include it.
3. **`anhydre` as a hydrate word.** A one-regex change (`_HYDRATE_WORD` also matching `anhydr[a-z]*`)
   maps 58 more BDPM occurrences (81.95 % → 82.16 %): calcium chloride, magnesium sulfate, sodium
   sulfate, sodium acetate, zinc sulfate in `… ANHYDRE` form. Recommend.
4. **Pancrelipase.** Leave unmapped (no pancrelipase item), or map the three parts to pancreatin
   (Q426846; A09AA02 "multienzymes") if you accept the two as one ingredient. Recommend leave.
5. **Fenofibric acid and the electrolyte spellings** (Appendix D): confirm the rows, and that the
   Turkish row stays in the data-directory file.
6. **English `NOT_ALONE` entries `alginate` and `pidolate`** turn 401 FAERS occurrences from a wrong
   key to unmapped (Section 9). Recommend accept; they are Phase 1 false mappings.
7. **Connectors** trimmed to fr `{de, d}`, es `{de}` (Section 3). Recommend accept.
8. **TİTCK fully mapped products** 20,427 → 20,419 (3 names become ambiguous instead of pointing at
   the wrong salt). Recommend accept.
9. **Doxepin.** Phase 1 maps FAERS `DOXEPIN` to the (E/Z) item whose only code is topical (D04AX01);
   the antidepressant code N06AA12 is on the cidoxepin item. This is a cascade-engine question
   (membership of the tricyclic class), not a name rule; I recommend a curated Janus key later.
10. **Public claims.** Pharmacist or physician review is still needed before anything is said
    publicly about these rules.

## Appendix A. Word lists (Python style, as for `name_lists.py`)

```python
EXTRA_SALT_WORDS = {
    "tr": [],
    "en": [
        "camsylate", "cypionate", "diacetate", "diolamine", "ditosylate", "enanthate", "esylate",
        "ethanolate", "hippurate", "mandelate", "metazoate", "methylsulfate", "pivalate",
        "terephthalate", "tetrahydrochloride"
    ],
    "fr": [
        "anhydre", "bromure", "calcique", "chlorhydrate", "chlorure", "dichlorhydrate", "dipotassique",
        "disodique", "hemifumarate", "hydrogenosuccinate", "monocalcique", "monopotassique",
        "monosodique", "potassique", "sodique", "tricalcique", "trisodique"
    ],
    "es": [
        "acetato", "anhidra", "axetilo", "benzoato", "besilato", "bitartrato", "bromuro", "calcica",
        "calcico", "calcio", "cilexetilo", "citrato", "cloruro", "digluconato", "dihidrato",
        "dihidrocloruro", "dipropionato", "disodio", "erbumina", "esilato", "fosfato", "fumarato",
        "gluconato", "hemifumarato", "hemihidrato", "hemipentahidrato", "hiclato", "hidrobromuro",
        "hidrocloruro", "hidrogenosuccinato", "hidrogenosulfato", "lactato", "magnesico", "magnesio",
        "malato", "maleato", "medoxomilo", "mesilato", "mofetilo", "monohidrato", "monosodio",
        "nitrato", "olamina", "oxalato", "pentahidrato", "potasico", "potasio", "propionato",
        "resinato", "sesquihidrato", "sodica", "sodico", "sodio", "succinato", "sulfato", "tartrato",
        "tosilato", "trihidrato", "trisodio", "xinafoato"
    ],
}

EXTRA_NOT_ALONE = {
    "tr": [],
    "en": [
        "alginate", "ion", "pidolate"
    ],
    "fr": [
        "argent", "cuivre", "fer", "fluorure", "hydroxyde", "iodure", "ion", "oxyde"
    ],
    "es": [
        "alginato", "aluminio", "bicarbonato", "carbonato", "cinc", "cobre", "edetato", "fluoruro",
        "glicerofosfato", "hidroxido", "hierro", "ioduro", "ion", "oxido", "plata"
    ],
}

CONNECTORS = {
    "tr": [],
    "en": [],
    "fr": [
        "d", "de"
    ],
    "es": [
        "de"
    ],
}
```

Counts: `EXTRA_SALT_WORDS` en 15, fr 17, es 60; `EXTRA_NOT_ALONE` en 3, fr 8, es 15;
`CONNECTORS` fr 2, es 1; `tr` unchanged. Switches: `BIOLOGIC_SUFFIX_ENABLED = True`,
`ACID_WORD_ORDER_ENABLED = True`, `ES_FINAL_VOWEL_ENABLED = False`.

## Appendix B. `data/anion_acid_forms.csv` (replace the header-only file)

```csv
lang,anion,acid,note
any,mycophenolate,mycophenolic acid,"WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=L04AA&showdescription=no checked 2026-11-08 (index updated 2026-01-20): L04AA06 mycophenolic acid is the only code; mofetil forms are DDD notes under it. Demand: FAERS 22,821 (mofetil, sodium), BDPM 21, openFDA 135"
es,micofenolato,mycophenolic acid,Spanish spelling of the row above; same code L04AA06 (WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=L04AA&showdescription=no checked 2026-11-08). Needs the word mofetilo. Demand: Nomenclátor 49
any,folate,folic acid,WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=B03BB&showdescription=no checked 2026-11-08: B03BB01 folic acid is the only single-substance code; salts have none. Demand: FAERS 664 (folate sodium). Levomefolate is a different substance and is not touched
any,valproate,valproic acid,"WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=N03AG&showdescription=no checked 2026-11-08: N03AG01 valproic acid; valpromide N03AG02 is a different substance and is not touched. Demand: FAERS 49, BDPM 23"
es,valproato,valproic acid,Spanish spelling of the row above; same code N03AG01 (WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=N03AG&showdescription=no checked 2026-11-08). Demand: Nomenclátor 17
any,alendronate,alendronic acid,WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=M05BA&showdescription=no checked 2026-11-08: M05BA04 alendronic acid; salts have no code. Demand: FAERS 24 (calcium and other salts)
es,risedronato,risedronic acid,WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=M05BA&showdescription=no checked 2026-11-08: M05BA07 risedronic acid; salts have no code. Demand: Nomenclátor 51 (the French spelling already maps through the item alias once monosodique is a salt word)
```

## Appendix C. `data/route_atc_groups.csv` (append these 24 rows)

```csv
orale,A;B;C01;C02;C03;C04;C05C;C07;C08;C09;C10;D01B;D05B;D10B;G02CB;G03;G04;H;J;L;M01;M03;M04;M05;M09;N;P01;P02;R01B;R02;R03C;R03D;R05;R06;R07;S01EC;V03;V06;V08,"French ""orale"" = ORAL: same groups"
intraveineuse,A02;A03;A04;A10;A11;A12;A16;B;C01;C02;C03;C04;C05BB;C07;C08;C09;C10;G02A;G03;G04BE;H;J;L;M01;M03;M04;M05;M09;N;P01;R03C;R03D;R06;R07;S01EC;S01JA;S01LA;V03;V04;V06;V07;V08;V09;V10,"French ""intraveineuse"" = INTRAVENOUS: same groups"
sous-cutanée,A02;A03;A04;A06AH;A10;A11;A12;A16;B;C01;C02;C03;C04;C07;C08;C09;C10;D02BB;D11AH;D11AX;G02A;G03;H;J;L;M01;M03;M04;M05;M09;N;P01;R03C;R03D;R06;R07;V03;V04;V06;V07;V08;V09;V10,"French ""sous-cutanée"" = SUBCUTANEOUS: same groups"
intramusculaire,A02;A03;A04;A10;A11;A12;A16;B;C01;C02;C03;C04;C07;C08;C09;C10;G02A;G03;H;J;L;M01;M03;M04;M05;M09;N;P01;R03C;R03D;R06;R07;V03;V04;V06;V07;V08;V09;V10,"French ""intramusculaire"" = INTRAMUSCULAR: same groups"
cutanée,C05A;C05B;D;G03;M02;N07BA;P03,"French ""cutanée"" = CUTANEOUS: same groups"
inhalée,A10AF;B01AC;J01;J05;N01A;N04B;N05A;P01CX;R03A;R03B;R05;R07;V03AB;V03AN;V09E,"French ""inhalée"" = RESPIRATORY (INHALATION): same groups"
ophtalmique,S01;S03,"French ""ophtalmique"" = OPHTHALMIC: same groups"
sublinguale,A;B;C01;C02;C03;C04;C05C;C07;C08;C09;C10;D01B;D05B;D10B;G02CB;G03;G04;H;J;L;M01;M03;M04;M05;M09;N;P01;P02;R01B;R02;R03C;R03D;R05;R06;R07;S01EC;V01;V03;V06,"French ""sublinguale"" = SUBLINGUAL: same groups"
intraartérielle,A02;A03;A04;A10;A11;A12;A16;B;C01;C02;C03;C04;C05BB;C07;C08;C09;C10;G02A;G03;G04BE;H;J;L;M01;M03;M04;M05;M09;N;P01;R03C;R03D;R06;R07;S01EC;S01JA;S01LA;V03;V04;V06;V07;V08;V09;V10,"Given into an artery: contrast media, radiopharmaceuticals, cytostatics and anticoagulants are the same systemic groups as INTRAVENOUS (no separate English row)"
voie buccale autre,A;B;C01;C02;C03;C04;C05C;C07;C08;C09;C10;D01B;D05B;D10B;G02CB;G03;G04;H;J;L;M01;M03;M04;M05;M09;N;P01;P02;R01B;R02;R03C;R03D;R05;R06;R07;S01EC;V03;V06,"French ""voie buccale autre"" (other buccal route: lozenges, mouth rinses, oromucosal products) = BUCCAL: same groups"
rectale,A;B;C01;C02;C03;C04;C05A;C05C;C07;C08;C09;C10;G03;H;J;L;M01;M03;M04;M05;M09;N;P01;P02;R01B;R03C;R03D;R05;R06;V03;V08,"French ""rectale"" = RECTAL: same groups"
transdermique,A04;C01;C02;D;G03;G04;M02;N,"French ""transdermique"" = TRANSDERMAL: same groups"
intrathécale,J01;L01;M03;M09;N01B;N02;V08,Injected into the spinal canal: local anesthetics (N01B); opioids and ziconotide (N02: N02A N02BG08); baclofen (M03BX01); nusinersen (M09AX07); intrathecal antibiotics and cytostatics (J01 L01); myelography contrast (V08)
péridurale,C01CA;C02AC;N01B;N02A,"French ""péridurale"" = EPIDURAL: same groups"
vaginale,G01;G02;G03,"French ""vaginale"" = VAGINAL: same groups"
nasale,A03FA;B03BA;C01CA;G03;H01;H04;H05;M01AB;N;R01A;V03AB,"French ""nasale"" = NASAL: same groups"
intraarticulaire,H02AB;N01B,"French ""intraarticulaire"" = INTRA-ARTICULAR: same groups"
périneurale,C01CA;N01B,"French ""périneurale"" = PERINEURAL: same groups"
infiltration,C01CA;M01A;N01B,"French ""infiltration"" = INFILTRATION: same groups"
intra-utérine,G02B,Intrauterine systems: the G02B group lists them by device (G02BA03 plastic IUD with progestogen); nothing else is given into the uterus in this list
dentaire,A01;N01B;R02AA,"French ""dentaire"" = DENTAL: same groups"
gingivale,A01;N01B;R02AA,Applied to the gums: same groups as DENTAL
intravitréenne,S01,"Injected or implanted in the vitreous: ophthalmological group S01 only (S01LA anti-vascular agents, S01BA corticosteroid implants, S01XA); systemic codes of the same drugs (for example aflibercept L01XX44) are dropped"
périarticulaire,H02AB;N01B,Injected around a joint: same groups as INTRA-ARTICULAR (corticosteroids and local anesthetics)
```

## Appendix D. `data/ingredient_synonyms.csv` (append these 26 rows; proposals)

```csv
name,qid,note
CABOZANTINIB S-MALATE,Q795057,"S-malate salt; the stereo marker S blocks the salt rule. WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=L01EX&showdescription=no checked 2026-11-08: L01EX07 cabozantinib (the item still carries the older code L01XE26), no salt code. FAERS 7,888, openFDA 13"
RIBOFLAVIN 5^-PHOSPHATE SODIUM,Q130365,"Phosphate ester sodium salt of riboflavin. WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=A11HA&showdescription=no checked 2026-11-08: A11HA04 riboflavin (vit B2), no code for the phosphate. FAERS 3,381, openFDA 14 (the apostrophe spelling folds to the same string)"
ASPIRIN DL-LYSINE,Q18216,"Lysine acetylsalicylate. WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=N02BA&showdescription=no checked 2026-11-08: N02BA01 acetylsalicylic acid, parenteral DDD note names lysine acetylsalicylate. FAERS 2,027"
ASPIRIN LYSINE,Q18216,Same substance and evidence as the previous row. FAERS 324
ROPIVACAINE,Q279504,"Ropivacaine is the S-enantiomer by definition; the item label starts with (S)-, which blocks the label step. WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=N01BB&showdescription=no checked 2026-11-08: N01BB09 ropivacaine. FAERS 355, openFDA 1, BDPM 2"
ROPIVACAINE HYDROCHLORIDE,Q279504,"Same as ROPIVACAINE. FAERS 530, openFDA 95"
SEVELAMER CARBONATE,Q904153,"Carbonate is a protected word, so the rule cannot strip it. WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=V03AE&showdescription=no checked 2026-11-08: V03AE02 sevelamer (lanthanum carbonate is a different code). FAERS 364, openFDA 62"
SEVELAMERO CARBONATO,Q904153,Spanish spelling of the previous row. Nomenclátor 17
FENOFIBRIC ACID,Q27259379,"WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=C10AB&showdescription=no checked 2026-11-08: C10AB11 choline fenofibrate, note refers to fenofibric acid. Needed because acid_word_order lets a Spanish alias of the fenofibrate item (Q419724) catch this name. FAERS 67, openFDA 12. The Turkish spelling is in the data-directory file"
SODIO CLORURO,Q2314,"Inverted word order; every word is a salt word, so the rule leaves the name whole. WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=B05XA&showdescription=no checked 2026-11-08: B05XA03 sodium chloride (also A12CA01, B05CB01). Nomenclátor 346"
SODIO BICARBONATO,Q179731,WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=B05XA&showdescription=no checked 2026-11-08: B05XA02 sodium bicarbonate. Nomenclátor 76
CALCIO CLORURO DIHIDRATO,Q208451,WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=B05XA&showdescription=no checked 2026-11-08: B05XA07 calcium chloride. Nomenclátor 32
CALCIO CLORURO,Q208451,Same item as the previous row. Nomenclátor 9
POVIDONA IODADA,Q241516,Povidone-iodine; the Spanish label of the item is yodopovidona. WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=D08AG&showdescription=no checked 2026-11-08: D08AG02 povidone-iodine. Nomenclátor 42
FLUOCINOLONA ACETONIDO,Q924467,Differs from the label only by the Spanish final vowel (switch off). WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=D07AC&showdescription=no checked 2026-11-08: D07AC04 fluocinolone acetonide. Nomenclátor 28
NITRICO OXIDO,Q207843,Word order and final vowel. WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=R07AX&showdescription=no checked 2026-11-08: R07AX01 nitric oxide. Nomenclátor 27
ISOSORBIDA MONONITRATO,Q423401,Final vowel; mononitrate has its own code. WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=C01DA&showdescription=no checked 2026-11-08: C01DA14 isosorbide mononitrate (dinitrate is C01DA08). Nomenclátor 24
BENZOILO PEROXIDO,Q411424,Spanish spelling. WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=D10AE&showdescription=no checked 2026-11-08: D10AE01 benzoyl peroxide. Nomenclátor 24
CHLORHYDRATE DE ROPIVACAÏNE,Q279504,French spelling of ropivacaine hydrochloride; evidence as ROPIVACAINE. BDPM 24
CHLORHYDRATE DE ROPIVACAÏNE ANHYDRE,Q279504,As the previous row. BDPM 9
ROPIVACAÏNE BASE,Q279504,As ROPIVACAINE. BDPM 6
SODIUM (CHLORURE DE),Q2314,Inverted BDPM order of sodium chloride (evidence as SODIO CLORURO). BDPM 38
POTASSIUM (CHLORURE DE),Q184630,WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=B05XA&showdescription=no checked 2026-11-08: B05XA01 potassium chloride. BDPM 29
CALCIUM (CHLORURE DE) DIHYDRATÉ,Q208451,Evidence as CALCIO CLORURO DIHIDRATO. BDPM 16
MAGNÉSIUM (CHLORURE DE) HEXAHYDRATÉ,Q265414,WHOCC https://atcddd.fhi.no/atc_ddd_index/?code=B05XA&showdescription=no checked 2026-11-08: B05XA11 magnesium chloride. BDPM 7
SODIUM (BICARBONATE DE),Q179731,"Keeps the Phase 1 mapping of these 5 occurrences, which the connector rule would otherwise drop (Phase 1 reached the key by a spelling coincidence). Evidence as SODIO BICARBONATO. BDPM 5"
```

A 27th row, the Turkish spelling of fenofibric acid, is in
`.data/resolution/name-rules-synonyms-titck.csv` (git-ignored).

## Appendix E. What-if rule file of the accepted set

The run used this file plus the Turkish row; the `note` text of the acid rows is not used by the
what-if tool. Switches recommended on: `biologic_suffix`, `acid_word_order`.

```json
{
  "extra_salt_words": {
    "fr": [
      "chlorhydrate", "dichlorhydrate", "anhydre", "sodique", "potassique", "calcique",
      "monosodique", "disodique", "monopotassique", "dipotassique", "hemifumarate",
      "hydrogenosuccinate", "chlorure", "bromure", "trisodique", "monocalcique", "tricalcique"
    ],
    "es": [
      "hidrocloruro", "dihidrocloruro", "hidrobromuro", "besilato", "medoxomilo", "cilexetilo",
      "axetilo", "mofetilo", "trihidrato", "monohidrato", "dihidrato", "hemihidrato",
      "pentahidrato", "sesquihidrato", "hemipentahidrato", "anhidra", "calcica", "calcico",
      "sodica", "sodico", "potasico", "magnesico", "sodio", "potasio", "calcio", "magnesio",
      "disodio", "fumarato", "hemifumarato", "maleato", "citrato", "oxalato", "mesilato",
      "tosilato", "hiclato", "succinato", "hidrogenosuccinato", "tartrato", "bitartrato",
      "sulfato", "hidrogenosulfato", "acetato", "propionato", "dipropionato", "fosfato",
      "digluconato", "benzoato", "nitrato", "malato", "esilato", "xinafoato", "olamina",
      "erbumina", "resinato", "cloruro", "bromuro", "lactato", "gluconato", "trisodio",
      "monosodio"
    ],
    "en": [
      "cypionate", "enanthate", "pivalate", "ditosylate", "terephthalate", "hippurate",
      "mandelate", "ethanolate", "camsylate", "diacetate", "tetrahydrochloride", "esylate",
      "methylsulfate", "metazoate", "diolamine"
    ]
  },
  "extra_not_alone": {
    "fr": ["oxyde", "hydroxyde", "fluorure", "iodure", "fer", "ion", "cuivre", "argent"],
    "es": [
      "bicarbonato", "carbonato", "oxido", "hidroxido", "fluoruro", "ioduro", "glicerofosfato",
      "hierro", "aluminio", "cobre", "cinc", "edetato", "ion", "plata", "alginato"
    ],
    "en": ["pidolate", "ion", "alginate"]
  },
  "connectors": {
    "fr": ["de", "d"],
    "es": ["de"]
  },
  "switches": ["biologic_suffix", "acid_word_order"],
  "anion_acid": [
    ["any", "mycophenolate", "mycophenolic acid", "Appendix B"],
    ["es", "micofenolato", "mycophenolic acid", "Appendix B"],
    ["any", "folate", "folic acid", "Appendix B"],
    ["any", "valproate", "valproic acid", "Appendix B"],
    ["es", "valproato", "valproic acid", "Appendix B"],
    ["any", "alendronate", "alendronic acid", "Appendix B"],
    ["es", "risedronato", "risedronic acid", "Appendix B"]
  ],
  "synonyms": [
    ["CABOZANTINIB S-MALATE", "Q795057"],
    ["RIBOFLAVIN 5^-PHOSPHATE SODIUM", "Q130365"],
    ["ASPIRIN DL-LYSINE", "Q18216"],
    ["ASPIRIN LYSINE", "Q18216"],
    ["ROPIVACAINE", "Q279504"],
    ["ROPIVACAINE HYDROCHLORIDE", "Q279504"],
    ["SEVELAMER CARBONATE", "Q904153"],
    ["SEVELAMERO CARBONATO", "Q904153"],
    ["FENOFIBRIC ACID", "Q27259379"],
    ["SODIO CLORURO", "Q2314"],
    ["SODIO BICARBONATO", "Q179731"],
    ["CALCIO CLORURO DIHIDRATO", "Q208451"],
    ["CALCIO CLORURO", "Q208451"],
    ["POVIDONA IODADA", "Q241516"],
    ["FLUOCINOLONA ACETONIDO", "Q924467"],
    ["NITRICO OXIDO", "Q207843"],
    ["ISOSORBIDA MONONITRATO", "Q423401"],
    ["BENZOILO PEROXIDO", "Q411424"],
    ["CHLORHYDRATE DE ROPIVACAÏNE", "Q279504"],
    ["CHLORHYDRATE DE ROPIVACAÏNE ANHYDRE", "Q279504"],
    ["ROPIVACAÏNE BASE", "Q279504"],
    ["SODIUM (CHLORURE DE)", "Q2314"],
    ["POTASSIUM (CHLORURE DE)", "Q184630"],
    ["CALCIUM (CHLORURE DE) DIHYDRATÉ", "Q208451"],
    ["MAGNÉSIUM (CHLORURE DE) HEXAHYDRATÉ", "Q265414"],
    ["SODIUM (BICARBONATE DE)", "Q179731"]
  ]
}
```

