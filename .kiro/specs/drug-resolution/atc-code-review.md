# ATC code review of the in-scope ingredient keys (drug-resolution Req 15, DP45)

Date: 2026-11-08. Trigger: the `doctor-loop` glossary review found ingredient keys that carry the ATC code of another
substance (pharmacologist F13). Scope: the 1,129 ingredient keys that can appear in a cascade finding or an abrupt-stop
warning (members of the 66 cascade classes and of the abrupt-stop list; dataset `e9e55772…`, rule base `8d4881fc…`) and
their 1,383 ingredient-level ATC codes. Status line (kept): reviewed by the project owner with AI assistance; needs a
pharmacist or physician before any public claim (`docs/pre-launch-checklist.md`).

## 1. How the codes were checked
| Check | Covers | Result |
|---|---|---|
| A. **RxClass** (NLM, ATC classes of the key's RxCUI, level 1–4) | 858 keys with an RxCUI (30 of them without RxClass data) | 15 codes outside the key's RxClass groups |
| A′. RxClass by drug name | the 271 keys without an RxCUI and the 30 without data (301 keys) | 53 keys answered; 1 further code outside |
| B. **Shared codes**: one code on two or more in-scope keys | all 1,383 codes | 15 codes shared |
| C. **WHOCC group pages against the key's labels** (all five languages; the pages were read into memory for the comparison and not stored) | all 1,383 codes, 259 group pages | 39 codes whose WHOCC name shares no word stem with any label; 10 codes not in the current index; 44 more pairs whose names share a stem but no whole word, all read by hand |

Limits, stated plainly: check C compares names by a five-letter stem, so two substances that begin with the same five
letters (prednisone and prednisolone, say) are not told apart by it; check A covers US-market substances only; 222 keys
(233 codes) are covered by check C and the shared-code check B alone, because they have no RxClass data and no TİTCK
product that could confirm them. The TİTCK/Wikidata disagreement list (93 key-code pairs with no common level-4 group) was
read as well and holds only legitimate differences of use and route. A pharmacist or physician must still review the
whole mapping (checklist).

## 2. Where the wrong codes came from
The pharmacologist's report called them Wikidata codes. Seven of the twelve excluded codes come from
**TİTCK single-ingredient products** whose published code belongs to another substance (the product keeps the code as
published; the key's code set took it over, DP2 "the single-product code wins"). Five come from Wikidata items. The
exclusion file therefore carries a `source` column.

## 3. Exclusions (`data/atc_code_exclusions.csv`, 12 rows)
| Key | Code | Source | Reason | What the code was |
|---|---|---|---|---|
| Q407883 ketoconazole | M01AE03 | TİTCK | wrong substance | ketoprofen's code |
| Q284321 mefenamic acid | N02AX02 | TİTCK | wrong substance | tramadol's code |
| Q553223 esomeprazole | N03AX16 | TİTCK | wrong substance | former pregabalin code (no longer in the index) |
| Q421091 levocetirizine | R06AB04 | TİTCK | wrong substance | chlorphenamine's code |
| Q11426176 prednisolone | D07AB08 | TİTCK | wrong substance | desonide's code |
| Q417141 econazole | D01AC04 | TİTCK | wrong substance | chlormidazole's code |
| Q216935 lidocaine | R02AA05 | TİTCK | wrong substance | chlorhexidine's code |
| Q7226181 polycarbophil calcium | A06AC07 | Wikidata | wrong substance | wheat fibre's code (the item keeps A06AC08) |
| Q16252338 insulin degludec | A10AD06 | Wikidata | wrong substance | the two-insulin combination of degludec and aspart (a combination code that the classifier did not catch; the key keeps A10AE06) |
| Q422241 sodium lauryl sulfate | A06AD13 | Wikidata | wrong substance | sodium sulfate, a laxative; the item has no other code and leaves the name index |
| Q419020 JWH-018 | N02BG10 | Wikidata | not a medicine | cannabinoid class code on a research chemical; leaves the name index |
| Q22075864 ferric citrate item | B03AB06 | Wikidata | old code | not in the current index; leaves the name index |

The pharmacologist's list had eight keys; checks A–C found four more (polycarbophil calcium, insulin degludec, sodium
lauryl sulfate, and the ferric citrate item).

## 4. Reviewed and kept
- **Retired codes of the same substance, the current code also present** (no wrong class): exenatide A10BX04,
  liraglutide A10BX07, lixisenatide A10BX10, albiglutide A10BX13, empagliflozin A10BX12 and canagliflozin A10BX11
  (Wikidata). They are not in the current index. Kept: removing them changes no class.
- **Gabapentin N03AX12 and pregabalin N03AX16** (TİTCK, retired codes of the same substance): kept on purpose, the
  gabapentinoid class lists them (`.kiro/specs/cascade-engine/mapping-review.md`, class `gabapentinoid`).
- **Premixed insulins**: insulin aspart A10AD05 and insulin lispro A10AD04 name the same substance as a premix; kept.
- **Label or INN spelling differences, not code errors** (the WHOCC name is the same substance): polyethylene glycol
  (macrogol), 5-HTP (oxitriptan), iron(II) sulfate (ferrous sulfate), flaxseed (linseed), ticrynafen, heroin
  (diamorphine), methylcobalamin (mecobalamin), chlophedianol (clofedanol), verbenone, cortisol (hydrocortisone, seven
  codes), uricase, gum karaya (sterculia), (R)-rabeprazole (dexrabeprazole), bromodiphenhydramine (bromazine), iron(II)
  iodide, ethallobarbital, esatenolol, calcium levulinate, tetrahydrocannabinol (dronabinol), danthron (dantron),
  neocitrullamon, and the 44 stem-only pairs (for example pyrilamine, zimelidine, thiothixene). These are English label
  problems for the glossary, handled there.
- **Product keys that duplicate a substance key** (WHOCC names the substance): Q97479031 (lactulose), Q2034113 (insulin
  human), Q29006606 (dulaglutide), Q139890384 (ibuprofen), Q139890449 (paracetamol). Renamed in the glossary; the key
  merge is a follow-up below.
- **Iron(III) citrate B03AB01** names ferric sodium citrate in the index: a different salt, same class; kept, listed for
  the pharmacist. **Bromide (anion item) N05CM11** names the class "bromides": kept, noted (an anion item in the
  sleep-agent class, already known from the coverage report).
- **Shared codes that are legitimate**: trisodium phosphate and sodium phosphates (A06AG01); mometasone and mometasone
  furoate (three codes, duplicate keys: follow-up).

## 5. What changed (measured on the development database and the real FAERS counts)
Dataset `7db3a513…` (all twelve exclusions), compared with the previous dataset `e9e55772…`. The comparison of the
first eleven exclusions was run while `e9e55772…` was still stored; insulin degludec was added afterwards (the
loader then removed the old dataset, so its own effect is read from the new dataset only).

**Resolution dataset**
- Ingredient keys 3,273 → 3,270. The three keys that left are Q22075864, Q419020 and Q422241: after the exclusion they
  have no code, so they leave the name index.
- Eight further keys changed their code set (the first eleven exclusions): prednisolone, lidocaine, mefenamic acid,
  ketoconazole, econazole, levocetirizine, esomeprazole and polycarbophil calcium. Insulin degludec now has A10AE06 only.
- Of 317,055 product-ingredient lines, 1,076 changed (first eleven exclusions): 20 went from mapped to unmapped (13 for
  Q22075864, 7 for Q422241) and 9 moved from `single_ingredient_product` to a group or all-codes selection. All 40
  degludec lines (4 CIMA, 3 BDPM, 14 openFDA, 19 TİTCK) carry A10AE06 only now.
- Product codes as published are unchanged; only the ingredient's code set changed.

**Cascade engine** (class roles lost, computed on the old dataset)
- Ketoconazole: marker in rows 9 and 40, index in rows 51–54 (it had been matched through ketoprofen's code).
- Mefenamic acid: index in row 55, and the abrupt-stop warning (it had been matched through tramadol's code).
- Esomeprazole: index in row 31, and the abrupt-stop warning (former pregabalin code).
- JWH-018: marker in row 9. Q22075864: marker in row 49 and index in row 65.
- No other key changed a class role; insulin degludec is in no class. The real-data gate 1 (rows 5, 6, 9 and 12) and the
  other real-data tests (EU, memory counts, integrity artifacts) pass: 12 tests.

**FAERS counts** (build `20261108T130944Z-7445632a-7db3a513-7f67`, compared with `…e9e55772-bdae`)
- Only three keys' counts changed, all to none: Q22075864 (230 reports), Q419020 (80), Q422241 (29).
- Reports with a mapped ingredient (region ALL) 1,281,798 → 1,281,753 (−45: US −36, OTHER −9; EU, TR and UNKNOWN
  unchanged). 339 report-ingredient rows removed; 22 ingredient-count rows, 2,028 pair-count rows and 127 event-count
  rows changed (event counts change because the denominator of mapped reports changed). The 1,510,804 reports are
  unchanged.
- The three keys are the ones that lost their last code (Q22075864 and Q419020 also lost the class roles listed above).

## 6. Follow-ups
1. **Merge duplicate keys** in `drug-resolution`: the five product items above and the two mometasone items. Until then the
   glossary renames them to the substance INN and the engine treats them as separate keys.
2. **Run the check again** whenever WHOCC publishes a new ATC version, when a source is re-fetched and when a key is added
   to a class. The loader already refuses a stale exclusion (an entry whose code its source no longer gives the key).
3. **The 222 keys with one source only** (no RxClass data, no TİTCK product) are checked by name only (check C) and by
   the shared-code check; a pharmacist's review of the mapping remains on the pre-launch checklist.
