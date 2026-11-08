# Review sheet: dose-form groups and strength codes (medication-passport task 4, review stop)

> Written 2026-11-08 by Claude Code (Claude Opus 5.5) standing in for Kiro. **Status: waiting for the owner.** Nothing
> here is enabled for user-facing answers: every row of `data/dose_form_groups.csv` is `proposed`, `FormTable.reviewed`
> is false, and the tasks that would use the table (5–8) are not started.
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

## Part C. Owner decisions
| # | Decision | Owner answer |
|---|---|---|
| D1 | Route column in the key (A.2.1) | |
| D2 | Thirteen groups, or fourteen with R1 | |
| D3 | `other` never compared | |
| D4 / Q2 | No route → unknown | |
| R2 | openFDA `/1` basis only for countable groups | |
| R3 | Inhalation capsules → `inhaled` | |
| Q1 | Keep `*` rows | |
| Q3 | Chew-or-suck tablets → `other` | |
| Q4 | Coarse `inhaled` and `injection` | |
| A.4 | Where the accepted table ships (package or image) | |
| Rows | All 927 rows accepted (notes become `accepted; …`), with the changes above applied by a re-draft | |
