# Review sheet: dose-form groups and strength codes (medication-passport task 4, review stop)

> Written 2026-11-08 by Claude Code (Claude Opus 5.5) standing in for Kiro. **Status: accepted by the owner on
> 2026-11-08 (Part C); applied in one commit (Part D).** Parts A and B describe the draft as reviewed (927 rows); the
> accepted table has 931 rows, all `accepted`. A pharmacist or physician review is still open
> (`docs/pre-launch-checklist.md`).
> Inputs: `data/dose_form_groups.csv` (927 rows), the strength grammar of design §5.1 as built in
> `apps/api/janus/passport/strength.py`, OD4, owner decision 6. Dev dataset `7db3a513…` (openFDA NDC 2026-11-06, BDPM
> 2026-11-03). Counts are products of the dev dataset. Only openFDA (CC0) and BDPM (Licence Ouverte) strings appear
> here; no TİTCK string.

## Part A. What was drafted (implementer)

### A.1 Groups (owner decision 6, plus one required by Req 6.5)
| Group | Contents | openFDA rows / products | BDPM rows / products |
|---|---|---|---|
| `oral_solid` | tablets (plain, film-coated, coated, chewable, effervescent, dispersible, orodispersible, soluble), capsules, orodispersible film, tablets for oral solution or suspension | 16 / 40,730 | 37 / 10,580 |
| `oral_solid_modified_release` | extended, prolonged, modified, delayed release, gastro-resistant, osmotic tablets and capsules | 10 / 6,456 | 18 / 1,492 |
| `oral_liquid` | oral solutions, suspensions, syrups, drops, elixirs; powders and granules for an oral liquid | 18 / 8,532 | 32 / 978 |
| `injection` | every parenteral form (IV, IM, SC, infusion, intravitreal, intrathecal, …), powders and solvents for them | 40 / 12,338 | 86 / 4,669 |
| `inhaled` | pressurised and powder inhalers, nebuliser liquids, inhalation capsules (BDPM), medical gases | 15 / 1,430 | 16 / 528 |
| `nasal`, `ophthalmic`, `otic` | by route | 12+13+6 / 2,336 | 5+9+2 / 437 |
| `cutaneous` | creams, ointments, gels, lotions, topical liquids and sprays, shampoos, medicated plasters on the skin | 78 / 28,635 | 32 / 682 |
| `transdermal` | transdermal patches and plasters | 3 / 482 | 1 / 2 |
| `rectal`, `vaginal` | suppositories, enemas, rectal foams; pessaries, vaginal creams, rings, inserts | 23 / 543 | 19 / 156 |
| `other` (never compared) | sublingual, buccal, dental and oromucosal forms, lozenges, chewing gum, mouth sprays, kits, devices, implants, radiopharmaceuticals, dialysis and irrigation solutions, homeopathic pellets | 60 / 14,846 | 93 / 808 |
| unknown (empty group) | route not published or mixed, modified-release forms outside the oral solids, liposomal and lipid-complex injections, powders and granules whose basis is unclear, multi-part presentations of different forms | 208 / 21,934 | 75 / 578 |

Coverage: openFDA 84.1 % of products have a group, 73.4 % a compared group; BDPM 97.2 % and 93.4 %.

### A.2 Design changes made while drafting (need the owner's acceptance)
1. **Route column (D1).** openFDA `SOLUTION` is oral for 1,729 products, topical for 1,042, ophthalmic for 323,
   sublingual for 318; `TABLET` is sublingual for 242 products. Keying by the published form alone would put eye drops
   and oral solutions in one group. The key is now `(source, form, route)`; `*` rows (122 of them for route-dependent
   forms) are written only when every route set seen gives the same group.
2. **Thirteen groups (D2):** `oral_solid_modified_release` added to the owner's twelve, because Req 6.5 forbids putting
   modified-release and immediate-release forms in one group.
3. **`other` is never compared (D3).** Owner decision 6 lists `other`; two products in it may be a lozenge and a kit, so
   the code treats `other` as "form not compared".
4. **No route published → unknown (D4)**, also for tablets and capsules (openFDA `TABLET` 750, `TABLET, FILM COATED`
   889, `CAPSULE` 554 products with an empty route list).

### A.3 Strength codes (design §5.1, task 2) on the dev dataset
`python -m janus.passport.strength` (counts only):

| Source | Ingredient rows | With strength | Parsed | Code given |
|---|---|---|---|---|
| openFDA | 220,238 | 220,222 | 135,010 | 131,571 (59.7 %) |
| BDPM | 29,057 | 28,994 | 26,055 | 14,168 (48.8 %, countable forms only) |
| Nomenclátor | 35,875 | 35,875 | 32,927 | 0 (basis not loaded, owner decision 3) |
| TİTCK | 31,885 | 0 | 0 | 0 |

The openFDA rows that do not parse are mostly homeopathic units (`[hp_X]`, `[hp_C]`) and mass-per-mass or volume ratios
(`kg/kg`, `mL/mL`), which are refused by design; parsed rows without a code are non-terminating divisions
(`100 mg/3 mL`) and amounts outside the request pattern.

### A.4 Packaging finding (not a review item, but blocks task 7)
The API image is built from `apps/api` only (`docker-compose.yml`, `apps/api/Dockerfile`), so `data/dose_form_groups.csv`
is not in the container and the route would always answer 503. `memory_events.csv` solved the same problem by living
inside the package. Proposal (owner): ship the accepted table as `apps/api/janus/passport/dose_form_groups.csv` with
`data/` keeping a pointer, or copy it into the image at build time.

## Part B. Pharmacologist pass (`agent://pharmacologist`, separate pass)

> Role: `.kiro/agents/pharmacologist.md` (ingredient-level matching, combination products, `medical-safety.md`). Run by
> Claude Code as a separate, explicitly labelled pass after the draft was finished: the reviewer re-read the 927 rows,
> the keyword rules of `forms_draft.py` and the grammar of `strength.py` without changing them. Every flag below is a
> recommendation for the owner; no row was edited in this pass.

### B.1 Verdict
**Accept with changes.** The coarse grouping is clinically defensible for the purpose Req 6 gives it (say whether a
listed product shares the item's broad dose-form group, never that it can replace it), and the draft is conservative
where it matters: liposomal and depot injections, prolonged-release eye and vaginal forms and multi-part packs are
unknown, sublingual and buccal forms are kept away from oral ones, and route-ambiguous strings are split by route.
Three changes are recommended before the owner accepts (R1–R3); the rest are granularity questions. The table has not
been seen by a pharmacist or physician; it must not be described as clinically validated.

### B.2 Recommended changes
- **R1 (high). Split `oral_solid_modified_release` into `oral_solid_delayed_release` (gastro-resistant, delayed
  release; 9 rows, 2,384 products) and `oral_solid_prolonged_release` (extended, prolonged, modified, osmotic; 19 rows,
  5,564 products).** Delayed and prolonged release are different release profiles. For the same ingredient both exist
  (diclofenac gastro-resistant 50 mg and prolonged-release 75/100 mg; mesalazine gastro-resistant and prolonged-release;
  aspirin), and one group would let the comparison say "same form group" across them. Both stay countable. Result:
  14 groups.
- **R2 (high). openFDA `/1` strengths: basis `unit` only for the countable groups.** openFDA writes per-actuation and
  per-unit amounts the same way (`50 ug/1` for a nasal spray, `90 ug/1` for an inhaler, `5 mg/1` for a tablet). Today a
  French 0.1 mg tablet and a US spray listing 100 ug per actuation would give `strength: matched`. Apply the BDPM rule
  (§5.1, DP5) to openFDA `/1` as well: `unit` only when the product's form group is countable, else `None`; `/N mL` and
  `/N g` stay as they are. `strength_code` already takes the form group, so this is a two-line change plus P5 cases.
- **R3 (medium). openFDA `CAPSULE` with route `RESPIRATORY (INHALATION)` (6 products) → `inhaled`**, as the BDPM
  `poudre pour inhalation en gélule` rows already are. Capsules for inhalers must not be unknown while their French
  counterparts are `inhaled`; they must never be `oral_solid` either (the draft does not make that mistake).

### B.3 Rows and rules checked and found acceptable (no change)
- Effervescent, dispersible, orodispersible and chewable tablets in `oral_solid`; tablets for an oral solution or
  suspension (`comprimé pour suspension buvable`, `TABLET, FOR SUSPENSION`) in `oral_solid`: the strength is per tablet
  and the route is oral.
- Liposomal and lipid-complex injections unknown (amphotericin B and doxorubicin liposomal forms are not the
  conventional products); depot injections unknown (Req 6.5).
- Oral sprays (`SPRAY` and `AEROSOL, METERED` with route `ORAL`, mostly lingual and throat sprays) in `other`, not
  `oral_liquid`.
- Sublingual tablets, solutions and drops (`TABLET` 242, `SOLUTION` 318, `SOLUTION/ DROPS` 123 products) in `other`.
- Allergen extracts (`SOLUTION`, route `INTRADERMAL|PERCUTANEOUS|SUBCUTANEOUS`, 1,321 products) in `injection`: correct
  route class; they will rarely appear in a medicine list.
- Topical patches (`PATCH`, `PLASTER` on `TOPICAL`/`CUTANEOUS`) in `cutaneous`, transdermal ones in `transdermal`; the
  one topical extended-release patch row is unknown.
- Homeopathic forms (`PELLET`, `GLOBULE`, BDPM `granules`) in `other`; homeopathic products are left out of presence
  anyway (DP9).
- BDPM multi-part presentations of different forms (`comprimé à libération prolongée et comprimé pelliculé`,
  `comprimé et gélule`) unknown; presentations of one form repeated (`gélule et gélule`) keep the group.
- Strength grammar: exact conversion, IU never against mass, homeopathic units refused, no tolerance; BDPM only for
  countable forms. The salt/base caveat must stay in the `differs` wording (Req 6.3).

### B.4 Questions for the owner (granularity, OD4)
- **Q1.** Keep the `*` wildcard rows (122 rows for route-dependent forms: a future product with an unseen route set takes
  that group), or key every row by its exact route set (1,424 rows instead of 927, no generalisation)?
  Pharmacologist preference: keep `*`, and re-run the draft with a diff at each dataset refresh.
- **Q2.** Tablets and capsules with no published route (3,068 openFDA products): unknown (draft) or `oral_solid`?
  Preference: unknown; a vaginal or sublingual tablet without a route would otherwise be compared as oral.
- **Q3.** `comprimé à croquer ou à sucer` and `comprimé à sucer` (chew-or-suck tablets, 18 BDPM rows with lozenges):
  `other` (draft) or `oral_solid`? Preference: `other`.
- **Q4.** Inhalers, nebuliser liquids and medical gases share `inhaled`; IV, IM and SC share `injection` (owner's coarse
  list). Accept, with the wording rule of task 11 that answers say "same dose-form group", never "same form"?
- **Q5.** EDQM Standard Terms: closed by owner decision 6 (no EDQM data copied); OD4 can be marked closed with this
  review.

### B.5 Safety notes for the later tasks
- Task 11 wording: a `dose_form: matched` result must read as "listed in the same dose-form group (Janus grouping)",
  labelled as Janus's comparison (Req 7.3), never as "same medicine" or "same form".
- Task 5/7: do not use the table for any answer until the owner has accepted it (`FormTable.reviewed`).

## Part C. Owner decisions (2026-11-08, relayed by the coordinator)
| # | Decision | Owner answer |
|---|---|---|
| D1 | Route column in the key (A.2.1) | **Accepted** (tells oral, eye and skin solutions apart); recorded as design DP22 |
| D2 | Thirteen groups, or fourteen with R1 | **Accepted as it results: 14 groups** (12 + modified release split in two); Req 6.5 stands |
| D3 | `other` never compared | **Accepted** (shown, never compared) |
| D4 / Q2 | No route → unknown | **Accepted, no guessing**, including the 3,068 openFDA tablets and capsules without a route. Exception: when the form string fixes the route by itself (film-coated tablet, capsule, transdermal patch, eye drops, suppository), the route is derived from the form and recorded per row in the new column `route_from_form` (design DP23) |
| R1 | Split modified release | **Accepted**: `oral_solid_delayed_release`, `oral_solid_prolonged_release` |
| R2 | openFDA `/1` basis only for countable groups | **Accepted** (tablets and capsules only) |
| R3 | Inhalation capsules → `inhaled` | **Accepted** |
| Q1 | Keep `*` rows | **Only where the form string fixes the route** (same rule as D4); every other `*` row becomes route-specific or unknown; removed rows listed in D.2 |
| Q3 | Chew-or-suck tablets → `other` | **Accepted** |
| Q4 | Coarse `inhaled` and `injection` | **Accepted** |
| A.4 | Where the accepted table ships | **Inside the package**: `apps/api/janus/passport/dose_form_groups.csv`, with a test that it equals `data/dose_form_groups.csv` |
| Rows | Rows accepted | **Accepted** (notes `accepted; …`); the pharmacologist or physician review stays on `docs/pre-launch-checklist.md` |
| Q5 / OD4 | EDQM terms; granularity | Closed (owner decision 6 and this table) |

## Part D. Applied (2026-11-08)
### D.1 What changed
- `forms_draft.py`: R1 (two oral modified-release groups, split by the words *delayed release*, *gastro-résistant* vs
  *extended release*, *libération prolongée*, *libération modifiée*, *osmotique*), R3, `route_from_form`, and the new
  wildcard rule. A `*` row is written only for (a) a form whose group is named by the form itself (injection,
  inhalation, eye drops, oral liquid *buvable*, pessary) or which is `other` or unknown whatever the route, and
  (b) a form whose string fixes the route: film-coated tablet (`TABLET, FILM COATED`, `comprimé pelliculé`), capsule
  (`CAPSULE…`, `gélule…`), orodispersible / orally disintegrating tablet, tablet for an oral solution, transdermal patch
  (the word *transdermal*), suppository and enema. For (b), observed route sets with another result keep their own row
  (`TABLET, FILM COATED` on `VAGINAL` stays `vaginal`, `CAPSULE` on `RESPIRATORY (INHALATION)` becomes `inhaled`, mixed
  route sets stay unknown) and a product without a route takes the form's route. A plain `TABLET`, `SOLUTION`, `PATCH`,
  `crème` fixes nothing.
- `strength.py`: R2 (openFDA `/1` gives basis `unit` only for the three countable groups).
- `forms.py`: 14 groups, column `route_from_form` (a route class, only on `*` rows), packaged copy read at startup.
- Result: 931 rows, all `accepted`; openFDA 85.6 % of products with a group (74.9 % compared), BDPM 97.2 % (93.4 %);
  strength codes for 57.1 % of openFDA ingredient rows (59.7 % before R2) and 48.8 % of BDPM rows.

### D.2 Wildcard rows removed (107)
Each former `*` row, its draft group and product count, and what the accepted table has instead (route set → group).
Most become one row for the only route seen; none changes a group except the modified-release split.

| Source | Published form | Draft `*` group | Products | Accepted rows |
|---|---|---|---|---|
| eu_fr_bdpm | ` comprimé(s)` | oral_solid | 5 | orale -> oral_solid |
| eu_fr_bdpm | ` patch(s)` | cutaneous | 1 | cutanée -> cutaneous |
| eu_fr_bdpm | `bâton pour application` | cutaneous | 4 | cutanée -> cutaneous |
| eu_fr_bdpm | `compresse imprégné(e)` | cutaneous | 6 | cutanée -> cutaneous |
| eu_fr_bdpm | `comprimé dispersible` | oral_solid | 63 | orale -> oral_solid |
| eu_fr_bdpm | `comprimé dispersible ou à croquer` | oral_solid | 26 | orale -> oral_solid |
| eu_fr_bdpm | `comprimé dispersible sécable` | oral_solid | 24 | orale -> oral_solid |
| eu_fr_bdpm | `comprimé effervescent(e)` | oral_solid | 61 | orale -> oral_solid |
| eu_fr_bdpm | `comprimé effervescent(e) sécable` | oral_solid | 28 | orale -> oral_solid |
| eu_fr_bdpm | `comprimé enrobé` | oral_solid | 223 | orale -> oral_solid |
| eu_fr_bdpm | `comprimé enrobé et  comprimé enrobé` | oral_solid | 5 | orale -> oral_solid |
| eu_fr_bdpm | `comprimé enrobé et  comprimé enrobé et  comprimé enrobé` | oral_solid | 7 | orale -> oral_solid |
| eu_fr_bdpm | `comprimé enrobé gastro-résistant(e)` | oral_solid_modified_release | 25 | orale -> oral_solid_delayed_release |
| eu_fr_bdpm | `comprimé enrobé sécable` | oral_solid | 5 | orale -> oral_solid |
| eu_fr_bdpm | `comprimé enrobé à libération prolongée` | oral_solid_modified_release | 22 | orale -> oral_solid_prolonged_release |
| eu_fr_bdpm | `comprimé et  comprimé et  comprimé` | oral_solid | 1 | orale -> oral_solid |
| eu_fr_bdpm | `comprimé gastro-résistant(e)` | oral_solid_modified_release | 239 | orale -> oral_solid_delayed_release |
| eu_fr_bdpm | `comprimé osmotique` | oral_solid_modified_release | 4 | orale -> oral_solid_prolonged_release |
| eu_fr_bdpm | `comprimé quadrisécable` | oral_solid | 60 | orale -> oral_solid |
| eu_fr_bdpm | `comprimé sécable à libération modifiée` | oral_solid_modified_release | 21 | orale -> oral_solid_prolonged_release |
| eu_fr_bdpm | `comprimé sécable à libération prolongée` | oral_solid_modified_release | 19 | orale -> oral_solid_prolonged_release |
| eu_fr_bdpm | `comprimé à libération modifiée` | oral_solid_modified_release | 50 | orale -> oral_solid_prolonged_release |
| eu_fr_bdpm | `comprimé à libération modifiée sécable` | oral_solid_modified_release | 4 | orale -> oral_solid_prolonged_release |
| eu_fr_bdpm | `comprimé à libération prolongée` | oral_solid_modified_release | 316 | orale -> oral_solid_prolonged_release |
| eu_fr_bdpm | `crème pour application` | cutaneous | 1 | cutanée -> cutaneous |
| eu_fr_bdpm | `crème stérile` | cutaneous | 1 | cutanée -> cutaneous |
| eu_fr_bdpm | `crème épaisse pour application` | cutaneous | 1 | cutanée -> cutaneous |
| eu_fr_bdpm | `dispositif` | unknown | 154 | intra-utérine -> unknown; transdermique -> unknown |
| eu_fr_bdpm | `dispositif pour application` | unknown | 2 | cutanée -> unknown |
| eu_fr_bdpm | `emplâtre` | cutaneous | 1 | cutanée -> cutaneous |
| eu_fr_bdpm | `emplâtre adhésif(ve)` | cutaneous | 2 | cutanée -> cutaneous |
| eu_fr_bdpm | `emplâtre médicamenteux(se)` | cutaneous | 16 | cutanée -> cutaneous |
| eu_fr_bdpm | `gel et` | other | 1 | gingivale|voie buccale autre -> other |
| eu_fr_bdpm | `gel intestinal` | unknown | 2 | intestinale -> unknown |
| eu_fr_bdpm | `gel stérile` | unknown | 1 | intracervicale -> unknown |
| eu_fr_bdpm | `gelée` | unknown | 1 | orale -> unknown |
| eu_fr_bdpm | `granulés` | unknown | 44 | orale -> unknown |
| eu_fr_bdpm | `granulés enrobé` | unknown | 19 | orale -> unknown |
| eu_fr_bdpm | `granulés enrobé en vrac` | unknown | 1 | orale -> unknown |
| eu_fr_bdpm | `granulés gastro-résistant(e)` | unknown | 3 | orale -> unknown |
| eu_fr_bdpm | `granulés orodispersible` | unknown | 1 | orale -> unknown |
| eu_fr_bdpm | `granulés à croquer` | unknown | 1 | orale -> unknown |
| eu_fr_bdpm | `granulés à libération prolongée` | unknown | 9 | orale -> unknown |
| eu_fr_bdpm | `insert` | ophthalmic | 2 | ophtalmique -> ophthalmic |
| eu_fr_bdpm | `liquide pour application` | cutaneous | 4 | cutanée -> cutaneous |
| eu_fr_bdpm | `lotion` | cutaneous | 5 | cutanée -> cutaneous |
| eu_fr_bdpm | `microgranule en comprimé` | oral_solid | 4 | orale -> oral_solid |
| eu_fr_bdpm | `mousse pour application` | cutaneous | 2 | cutanée -> cutaneous |
| eu_fr_bdpm | `pansement adhésif(ve)` | cutaneous | 6 | cutanée -> cutaneous |
| eu_fr_bdpm | `pansement médicamenteux(se)` | cutaneous | 2 | cutanée -> cutaneous |
| eu_fr_bdpm | `patch` | transdermal | 2 | transdermique -> transdermal |
| eu_fr_bdpm | `patch et  gel` | unknown | 1 | cutanée -> unknown |
| eu_fr_bdpm | `pommade pour application et` | unknown | 1 | cutanée|nasale -> unknown |
| eu_fr_bdpm | `poudre` | unknown | 23 | nasale -> unknown; orale -> unknown; orale|sublinguale -> unknown |
| eu_fr_bdpm | `poudre et  poudre` | unknown | 1 | orale -> unknown |
| eu_fr_bdpm | `poudre et  solution` | unknown | 1 | orale|sublinguale -> unknown |
| eu_fr_bdpm | `poudre et  solvant` | unknown | 4 | intramusculaire -> unknown; intraveineuse|sous-cutanée -> unknown |
| eu_fr_bdpm | `poudre et  solvant pour solution` | unknown | 2 | intraoculaire -> unknown; intravésicale -> unknown |
| eu_fr_bdpm | `poudre et  solvant pour suspension` | unknown | 3 | intravésicale -> unknown |
| eu_fr_bdpm | `poudre pour application` | cutaneous | 14 | cutanée -> cutaneous |
| eu_fr_bdpm | `poudre pour suspension et` | unknown | 6 | orale|rectale -> unknown |
| eu_fr_bdpm | `poudre pour suspension ou` | unknown | 1 | orale|rectale -> unknown |
| eu_fr_bdpm | `poudre à diluer à diluer et  solution pour solution pour solution` | unknown | 2 | intraveineuse -> unknown |
| eu_fr_bdpm | `pâte` | unknown | 6 | orale -> unknown |
| eu_fr_bdpm | `pâte pour application` | cutaneous | 3 | cutanée -> cutaneous |
| eu_fr_bdpm | `shampooing` | cutaneous | 14 | cutanée -> cutaneous |
| eu_fr_bdpm | `sirop` | oral_liquid | 94 | orale -> oral_liquid |
| eu_fr_bdpm | `solution en gouttes` | other | 1 | sublinguale -> other |
| eu_fr_bdpm | `solution et` | other | 1 | gingivale|voie buccale autre -> other |
| eu_fr_bdpm | `solution et  solution et  solution` | oral_liquid | 1 | orale -> oral_liquid |
| eu_fr_bdpm | `solution et  solution pour application` | unknown | 2 | cutanée -> unknown |
| eu_fr_bdpm | `solution filmogène pour application` | cutaneous | 1 | cutanée -> cutaneous |
| eu_fr_bdpm | `solution gouttes` | otic | 3 | auriculaire -> otic |
| eu_fr_bdpm | `solution moussant(e)` | cutaneous | 4 | cutanée -> cutaneous |
| eu_fr_bdpm | `solution ou` | unknown | 2 | orale|rectale -> unknown |
| eu_fr_bdpm | `solution pour application stérile` | cutaneous | 1 | cutanée -> cutaneous |
| eu_fr_bdpm | `solution pour pulvérisation endo-buccal(e)` | other | 1 | voie buccale autre -> other |
| eu_fr_bdpm | `solution pour pulvérisation et` | other | 1 | laryngopharyngée|voie buccale autre -> other |
| eu_fr_bdpm | `suspension et  gel pour gel` | unknown | 1 | cutanée -> unknown |
| eu_fr_bdpm | `système de diffusion` | unknown | 13 | intra-utérine -> unknown; vaginale -> unknown |
| eu_fr_bdpm | `tampon imprégné(e)` | cutaneous | 1 | cutanée -> cutaneous |
| eu_fr_bdpm | `vernis à ongles médicamenteux(se)` | cutaneous | 24 | cutanée -> cutaneous |
| eu_fr_bdpm | `émulsion fluide pour application` | cutaneous | 3 | cutanée -> cutaneous |
| eu_fr_bdpm | `émulsion pour application` | cutaneous | 14 | cutanée -> cutaneous |
| openfda_ndc | `BAR, CHEWABLE` | unknown | 13 | ORAL -> unknown |
| openfda_ndc | `CREAM, AUGMENTED` | cutaneous | 7 | CUTANEOUS -> cutaneous; TOPICAL -> cutaneous |
| openfda_ndc | `DISC` | cutaneous | 11 | TOPICAL -> cutaneous |
| openfda_ndc | `DOUCHE` | vaginal | 2 | VAGINAL -> vaginal |
| openfda_ndc | `FILM, EXTENDED RELEASE` | unknown | 17 | TRANSDERMAL -> unknown |
| openfda_ndc | `FOR SUSPENSION, EXTENDED RELEASE` | unknown | 13 | (no route) -> unknown; ORAL -> unknown |
| openfda_ndc | `GRANULE, DELAYED RELEASE` | unknown | 30 | (no route) -> unknown; ORAL -> unknown |
| openfda_ndc | `GRANULE, EFFERVESCENT` | unknown | 8 | ORAL -> unknown |
| openfda_ndc | `GRANULE, FOR SUSPENSION, EXTENDED RELEASE` | unknown | 2 | ORAL -> unknown |
| openfda_ndc | `INSERT, EXTENDED RELEASE` | unknown | 8 | (no route) -> unknown; VAGINAL -> unknown |
| openfda_ndc | `JELLY` | cutaneous | 172 | TOPICAL -> cutaneous |
| openfda_ndc | `LOTION, AUGMENTED` | cutaneous | 6 | TOPICAL -> cutaneous |
| openfda_ndc | `LOTION/SHAMPOO` | cutaneous | 71 | CUTANEOUS -> cutaneous; INTRAEPIDERMAL -> cutaneous; TOPICAL -> cutaneous |
| openfda_ndc | `OINTMENT, AUGMENTED` | cutaneous | 7 | TOPICAL -> cutaneous |
| openfda_ndc | `PILL` | oral_solid | 3 | ORAL -> oral_solid |
| openfda_ndc | `SHAMPOO, SUSPENSION` | cutaneous | 19 | TOPICAL -> cutaneous |
| openfda_ndc | `SPRAY, SUSPENSION` | cutaneous | 1 | TOPICAL -> cutaneous |
| openfda_ndc | `SUSPENSION, EXTENDED RELEASE` | unknown | 39 | ORAL -> unknown |
| openfda_ndc | `TABLET, CHEWABLE, EXTENDED RELEASE` | oral_solid_modified_release | 5 | ORAL -> oral_solid_prolonged_release |
| openfda_ndc | `TABLET, DELAYED RELEASE PARTICLES` | unknown | 1 | (no route) -> unknown |
| openfda_ndc | `TABLET, FOR SOLUTION` | unknown | 2 | (no route) -> unknown; NASAL -> unknown |
| openfda_ndc | `TABLET, MULTILAYER` | oral_solid | 3 | ORAL -> oral_solid |
| openfda_ndc | `WAFER` | unknown | 2 | (no route) -> unknown; INTRACAVITARY -> unknown |
