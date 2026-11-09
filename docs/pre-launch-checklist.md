# Pre-launch checklist (Phase 5)

Items that must be checked before Janus is deployed or announced. Add items here when a spec
defers a check to launch.

- [ ] **MedDRA terms for public display.** FAERS event terms are shown as the MedDRA Preferred
  Terms published by FDA, without any MedDRA hierarchy (SOC, HLT, LLT). Verify the MSSO terms for
  public display of PTs, and whether the notice may be translated (it is English in all five languages). The notice wording is decided (owner, 2026-11-08): short form on every screen that shows a PT
  ("MedDRA® trademark is registered by IFPMA on behalf of ICH."), long form in NOTICE and exports (`MEDDRA_NOTICE_LONG`); confirm that it appears on every screen, export and
  document that shows a PT, including the doctor note (`data-pipelines` DP33).
- [ ] **Scheduling.** Weekly, monthly and quarterly pipeline runs (`data-pipelines` DP11, DP27).
- [ ] **GS1 AI table and a real box.** Confirm AI 710 to 714 from the GS1 General Specifications
  and test the French and Spanish adapters with a real box if one becomes available
  (`.kiro/specs/drug-resolution/eu-code-encodings.md`).
- [ ] **Phase 2 name rules and EU data (`drug-resolution` Req 12, design §15, §19).** A pharmacist or physician reviews
  the French, Spanish and English salt and ester word lists, the anion-acid table (`data/anion_acid_forms.csv`), the
  French route rows of `data/route_atc_groups.csv` and the synonym rows added after the review sheet
  (`.kiro/specs/drug-resolution/name-rules-review.md`). The owner accepted the sheet; a clinical review has not happened.
  Also: confirm the GS1 company-prefix ranges of the country table (France, Spain, Germany; add other EU countries only
  from the GS1 prefix list); test the French and Spanish adapters with a real box; check that the client shows the BDPM and
  AEMPS attribution, the update date and the "not endorsed" wording; re-check the WHOCC `J01DH` page for imipenem (the
  owner chose a component-code exception, `data/component_codes.csv`; last checked 2026-11-08).
  The prefix table in `apps/api/janus/regions/base.py` was verified on 2026-11-08 against a secondary copy (the Wikipedia
  list of GS1 country codes), because gs1.org was not readable from the research environment: confirm it against the
  GS1 list. AI 710 to 714 are still unconfirmed (see the item above). The Spanish final-vowel name rule is left off
  (owner decision 1) and stays a possible later change (`drug-resolution` design §19).
- [ ] **Pharmacist or physician review of the whole event mapping.** The Janus event vocabulary
  (`apps/api/janus/memory/memory_events.csv`: 34 adverse keys with their PT lists, 5 benefit keys) was drafted by the AI
  assistant, reviewed by the pharmacologist agent and accepted by the project owner on 2026-11-08. A pharmacist or
  physician must review it before any public claim. Questions to put to them: the blood-loss point (the iron PTs of
  `vitamin_mineral_deficiency` partly reflect blood loss, itself a reason to start a PPI; they follow the
  cascade-engine narrowing of row 49 to oral iron); Peripheral swelling inside `peripheral_oedema` (71 percent of the
  key; the assessment class of amlodipine, nifedipine, gabapentin and pregabalin does not change with or without it,
  the ratios do); Torsade de pointes, Ventricular tachycardia and Ventricular fibrillation inside `arrhythmia`;
  Fluid retention inside `oedema`; Balanoposthitis kept out of `genital_fungal_infection`; the indication-like PTs left
  out (dementia, epilepsy).
- [ ] **Native-speaker check of the labels** in Turkish, German, French and Spanish
  (`memory_events.csv`, and the `Memory` message namespace), after the localization-reviewer agent's pass.
- [ ] **Crisis and emergency numbers per region: re-check.** Decided 2026-11-08 (`experience` Requirement 7.3; tables
  `Memory.emergency` and `Memory.crisis` in five languages and `EMERGENCY`/`CRISIS` in `messages.py`): US 911 and 988
  (call or text, Suicide and Crisis Lifeline); TR 112; EU 112 plus the local crisis service; OTHER and UNKNOWN the local
  emergency number. Re-check every number and the 988 name against the official sources, and confirm the urgent-care wording of
  the six lines (skin, heart, GI bleeding, seizure, breathlessness, crisis) with a clinician.
- [ ] **EudraVigilance link: re-check.** The link is `https://www.adrreports.eu` (owner, 2026-11-08; link only, no ingestion;
  `collective-memory` Requirement 3.2). Check that it still opens the public reports site and that its reuse terms still
  allow a link from Janus.
- [ ] **Doctor note glossary and templates: native-speaker and pharmacist or physician review.** The five-language
  glossary (`apps/api/janus/notes/glossary/`: 1,126 ingredient names, 65 cascade names, 115 templates) was drafted by the
  AI assistant, reviewed by the pharmacologist and localization-reviewer agents and accepted by the owner on 2026-11-08.
  A pharmacist or physician and a native speaker per language must still review it before any public claim. Points the
  reviewers left for natives (`.kiro/specs/doctor-loop/glossary-localization-review.md`): French *signalement* and
  Spanish *informe* for "report"; *ROR* terms; the German title and *Verschreibung* against *Verordnung*; French
  *schéma* for "pattern"; cascade rows 15, 20, 56 and the French supplement terms; Turkish *kesmek* in the abrupt-stop
  line; every ingredient cell after the mechanical pass; the reassurance word lists. Cells cleared as wrong (about 80)
  fall back to the English INN with "name not translated"; native forms can be added after the review.
- [ ] **Wrong ATC codes: pharmacist review of the whole mapping.** `data/atc_code_exclusions.csv` removes 12 reviewed wrong
  (key, code) pairs (`.kiro/specs/drug-resolution/atc-code-review.md`). 222 in-scope keys have one source only and were
  checked by name against the WHOCC index; a pharmacist must review the rest. Re-check after every WHOCC ATC release.
- [ ] **Duplicate ingredient keys** (five product items and the two mometasone items) are merged in `drug-resolution`.
- [ ] **Outcome loop at the proxy:** request limits for `/notes/token`, `/notes/withdraw`, `/outcomes/form` and `/outcomes`
  without storing or logging IP addresses (`doctor-loop` design §7.6). Until then the privacy page states the padding limit.
- [ ] **Print-and-scan test of the QR code** at 50 mm on A4 with several phones (version 25, level M, byte mode; the
  realistic worst case needs version 21). Key rotation runbook: `docs/note-token-keys.md`.
- [ ] **FTC Health Breach Notification Rule:** re-check how it applies to the outcome loop (doctor-reported outcomes) before launch.
- [ ] **`privacy.md` token line:** it still says the token holds "note id + HMAC signature + expiry only"; the token also carries
  finding codes, language, region, issue week, key id and consent version (owner decision 2026-11-08, no personal data). The
  owner left `privacy.md` unchanged; decide whether to update the line before launch.
- [ ] **Dose-form groups and strength codes (Passport):** `data/dose_form_groups.csv` (931 rows, 14 groups) and the strength
  grammar of `janus/passport/strength.py` were reviewed by the pharmacologist agent and accepted by the owner on 2026-11-08
  (`.kiro/specs/medication-passport/dose-form-review.md`); a pharmacist or physician must review them before any public claim.
- [ ] **Privacy page text:** the outcome loop stores hashes of used note ids until the token expires and the doctor's answers
  by week and region; the QR token is a signed list of codes.


## Experience (Phase 3, owner decisions 2026-11-08)
- [ ] **Native-speaker review of the new namespaces** in Turkish, German, French and Spanish (Findings, Confirm, Medicines, Timeline, Evidence, MemoryView, Note, OutcomeConsent v2, Donate v2, Doctor, Privacy, Home), including the terms listed in `.kiro/specs/experience/wording-localization-review.md` ("reçete kaskadı", "Bildirim odds oranı (ROR)", "Medikament" vs "Arzneimittel", repurposing terms, "razón de odds de notificación").
- [ ] **Pharmacist or physician sign-off** of the timing-based status labels in app and note, the 12-month window for every row, the class inclusions and the doctor form (`wording-pharmacologist-review.md`, "Needs a physician or pharmacist").
- [ ] **Print-and-scan test of the demo QR at 50 mm** on A4 with several phones (Android and iOS, different cameras).
- [ ] **Re-check of the emergency and crisis numbers** per region in all five languages, and of the urgent-care thresholds.
- [ ] **Consent versions in the deployment:** `JANUS_CONSENT_VERSIONS=2026-11-v1,2026-11-v2` and `JANUS_OUTCOME_CONSENT_VERSIONS=2026-11-v1,2026-11-v2` (the client sends v2; v1 keeps tokens and donations made under it valid). Privacy and legal review of both v2 texts (GDPR Art. 9(2)(a), KVKK).
- [ ] **Home hero art direction** (bust or isometric home diorama, possibly 3D): swap it in `apps/web/src/components/home/HomeHero.tsx` (experience DP45); check contrast, alt text and the 375 px layout again.
- [ ] **Real devices:** local speech voices, camera scanning, PDF fonts and the Print button (it opens the PDF; check popup behaviour on iOS Safari).

## Expert review (Phase 4)
Every Phase 4 result (light-face hypothesis cards, validation and export; the séance's Canon passages, identifications,
claims and science findings; their wording) is **AI-reviewed and pending expert review**. The researcher area says so
(`Research.review`, `Seance.review`, `Light.review`), and every Canon passage is labelled "AI-reviewed, pending expert
review". Nothing below has been checked by a human expert. When an item is done, record who reviewed it and when, then
remove the matching notice (and, for the Canon claims, set `expert_review = reviewed` and re-run `canon_package`).

- [ ] **Light face: mappings** (pharmacist or physician). `data/light/goals.csv` (18 conditions, FAERS PT sets,
  five-language names) and `data/light/effect_goal_map.csv` (30 side-effect term → condition rows, `nonspecific`
  marker, citations). Questions (light-face design §13, §14; `.kiro/specs/light-face/mapping-pharmacologist-review.md`):
  local (application-site) effects counted with systemic ones (DP21; the topical corticosteroids in the alopecia list);
  the post-hoc exclusions of `Priapism`, `Abnormal hair growth`, `Hair growth abnormal` and the 13 `nonspecific` terms
  (DP22); narrowing obesity by ATC class (L01); specific citations for the rows that cite only Yang and Agarwal 2011.
- [ ] **Light face: validation decisions** (statistician). `data/light/validation_cases.csv` (13 cases) and
  `docs/light-face-validation.md` (`.kiro/specs/light-face/validation-statistician-review.md`): the post-hoc ranking key
  K1 (DP23) and mapping changes (DP22); the primary run as the worse of variants (a) and (b) (DP24); TOP_K = 10 and the
  "informative" rule (DP17); the validation is not blind (DP10); negative controls; an FDR gate for inverse signals;
  the Wilson bound over non-independent generic labels (DP5).
- [ ] **Séance: identifications** (pharmacognosist or pharmacologist, with a historian of Arabic medicine). The 31
  substances of `datasets/canon/substances.csv` (15 match the PMC3941892 gold table, 6 uncertain, 10 not in it; 4
  hazard flags: isfidaj, litharge, verdigris, narcissus). Open questions (séance design §9): lablab vs ivy
  (*habl al-masakin*); *sawsan* iris vs white lily; *sirish* Eremurus vs Asphodelus; frankincense and mallow species;
  *isfidaj* white lead vs zinc oxide; the source plant of dragon's blood. The screen shows "Identified" only for gold
  matches; check that rule too (DP9).
- [ ] **Séance: extracted claims** (historian of Arabic medicine and a pharmacologist). The 43 clauses of
  `datasets/canon/reader_ai.csv` and the 76 claims of `datasets/canon/claims.csv` (two AI passes:
  `review_historian.csv`, `review_pharmacologist*.csv`; `quality.json`). Check every Arabic span against a printed
  edition, every machine translation, every condition category, the locators, and: the "infection" bridge (DP4:
  putrefaction, pus, spreading or foul ulcers, whitlow, carbuncle, gangrene, fistula), conditions as the intersection of
  both passes (DP14), the historian's translation winning (DP15), "harfiyya" ulcers, pellitory "given to drink" for burns,
  the 260-character span cut (DP5). The two headline pairs (St John's wort / wound, vinegar / infection, both "2 of 3
  witnesses") rest on these claims.
- [ ] **Séance: present and science witnesses** (clinician or pharmacologist). The one-line findings of
  `data/seance_science.csv` against the four papers (Samadi 2010, Halstead 2015, Nagoba 2013, Jull 2015); the
  component bridge vinegar → acetic acid in `data/seance_present.csv` (also used to link a hypothesis card of acetic acid
  to the séance); salt → sodium chloride kept as a different exposure (DP11); the per-witness confidence levels (DP13).
- [ ] **Wording** (native speaker per language and a clinician). The `Seance` and `Light` namespaces and
  `Research.review` in TR, DE, FR, ES, after the localization-reviewer passes
  (`.kiro/specs/seance/seance-screen-review.md`, light-face design §12); the condition names in `data/light/goals.csv`
  and the four séance condition names; the points left for natives in the séance sheet (listed there under "For the
  experts"); the excluded-study line (the contract gives no reason per excluded paper, so the screen says "retracted or
  not registered" instead of the zombie stamp).

## Séance (Phase 4, owner decisions 2026-11-08)
- [ ] **NC licence:** the Canon data package is CC BY-NC-SA 4.0. Re-check that the deployment and any prize or commercial use stay non-commercial, and that the package is never merged into Apache-licensed files.
- [ ] **Ottoman samples:** none were added (no verifiable page-level source in Phase 4). Add 10-20 only from a thesis or edition the team has read, with citation and page; never claim "we mined Ottoman manuscripts".
- [ ] **Retraction check of the séance papers:** run the `retractions` pipeline so the four séance DOIs leave "not yet checked"; reload integrity and re-record `apps/web/src/seance/fixture.recorded.json` (`scripts/record-seance.mjs`).
- [ ] **API image:** ship `datasets/canon/` in the API Docker image (séance design §10); without it `/seance/*` answers 503 and the screen says the data package is not installed.

## Light face (Phase 4, owner decisions 2026-11-08)
- [ ] **Mechanism field:** connect the séance spec's molecular witness (ChEMBL, CC BY-SA 3.0) or keep "no mechanism source
  connected"; if ChEMBL data enters the export, the export licence must change (share-alike).
- [ ] **OnSIDES refresh:** the pipeline pins the v3.1.1 asset by SHA-256; a new data release is a reviewed code change, after which
  the light build and `docs/light-face-validation.md` are regenerated.

## Time machine (owner-approved feature, 2026-11-09)
All items below come from the three labelled AI review passes
(`.kiro/specs/time-machine/review-{pharmacologist,statistician,historian}.md`). Nothing in this
feature is expert-reviewed; every screen says "AI-reviewed, pending expert review".

### Models and validation (pharmacologist, clinical pharmacologist or PK modeller)
- [ ] **No simulation model is credible enough to carry an exposure statement.** httk PBPK scored
  0 of 4 credible against published human PK (metoclopramide borderline at 2.36x on AUC;
  risperidone 3.27x on Cmax; midazolam 11.9x and haloperidol **32x** on AUC, both AUC
  over-predictions, i.e. under-predicted clearance). Janus's compartmental model: rhein credible
  (1.08x / 1.13x), amlodipine borderline (2.37x on Cmax). Decide whether the PBPK layer should be
  published at all, even as the relative older-versus-younger comparison it is limited to now,
  and whether httk should be reparameterised for pharmaceuticals or dropped for this purpose.
- [ ] **Rhein's AUC check is not independent** (CL/F from Magnard 1993, observed AUC from Debord
  1993, possibly the same control group). Only its Cmax agreement is a real test. Confirm or
  replace with an independent study.
- [ ] **Risperidone was validated on parent drug only**, with no metabolite compartment and no
  CYP2D6 genotyping in the observed study. Confirm whether the active moiety should be used.
- [ ] **The rhubarb model has no colonic activation step.** 60-80 % of rhubarb's
  hydroxyanthracenes are glycosides cleaved by gut bacteria hours after ingestion; a
  one-compartment oral model gives the wrong Tmax for a glycoside prodrug.
- [ ] **Measured protein binding must replace the predicted one.** The unbound fraction comes
  from an ADMET-AI `PPBR_AZ` prediction, which exceeds 100 % for hyperforin (112.6 %),
  chrysophanol (101.9 %) and emodin (101.6 %). Out-of-range values are now rejected (DP-T15) and
  the comparison falls back to total concentration, but a measured value (rhein ~99 %, Nicolas
  1998) should be used before any verdict is published.
- [ ] **Induction versus inhibition must not be conflated** in any write-up: hyperforin's PXR
  binding causes CYP3A4 *induction*, while the CYP3A4 record carried beside it is an *inhibition*
  IC50.
- [ ] **ADMET-AI training-set licence:** FreeSolv in the TDC ADME set is CC BY-NC-SA 4.0. Confirm
  this does not constrain how predictions may be used or published.

### Statistics (statistician or pharmacoepidemiologist)
- [ ] **Every onset result rests on 17-35 reports** and four of five cascades are flagged small
  samples; one (metoclopramide) has no usable report at all. Confirm whether a Weibull shape
  class should be shown at all below 30 reports.
- [ ] **The usable subset is selected, not random.** Only 8.9 % of (report, drug) pairs have both
  a complete therapy start and a complete event date; completeness is associated with reporter
  type and event seriousness. The caveat is now in the artifact; confirm the wording.
- [ ] **Zero-day heaping drives the "early hazard" conclusion** (10 of 29 antipsychotic reports,
  4 of 35 amlodipine). A same-day interval is often one date entered twice. Counts are now
  published per cascade; confirm whether such reports should be excluded instead.
- [ ] **`agreement` is close to unfalsifiable at these interval widths** (our amlodipine IQR is
  7-104 days). Confirm that the research screen shows both intervals side by side and that
  "agrees" is read as "not inconsistent with".
- [ ] **Monte Carlo parameter spreads are a judgement, not published variances.** Confirm the
  log-normal geometric standard deviations in `data/time_machine/compartmental_pk.csv`.

### History and identification (historian or philologist of Arabic medicine)
- [ ] **Rhubarb and anise have had no identification review.** Both were added by this build
  because their entries state a dose, so they were never in the séance's reviewed set.
  `data/time_machine/identifications_added.csv` marks both `uncertain`; medieval `rawand` may be
  *Rheum palmatum*, *R. officinale* or *R. ribes*, and the Canon's `anisun` entry may cover more
  than one umbellifer. No gold row exists for either in PMC3941892.
- [ ] **Unit conversion.** Confirm the dirham range 2.80-3.30 g and the mithqal 4.00-4.464 g for
  an 11th-century *medical* context. Two caveats stand: Hinz's values (3.125 g, 4.464 g) were
  verified only from indexed footnote snippets of Bos 1996, not the article itself; and Bates
  1995 states the weight-dirham was often not the coin-dirham, so coin evidence does not pin the
  medical dirham down.
- [ ] **Condition bridges.** The anise bridge is matched on symptom (gut spasm and wind), not on
  a diagnosis: irritable bowel syndrome has no Canon counterpart. Confirm this and the sciatica
  and musculoskeletal bridges. Note the Canon claims a cure for sciatica with St John's wort; the
  build must never repeat that, and currently gives St John's wort no dose scenario and no
  verdict.
- [ ] **The rhubarb dose is attributed by the Canon to al-Khuzi**, not asserted by Ibn Sina. The
  note now says so; confirm the reading and the transliteration.

### Product, safety and data
- [ ] **The one patient-facing sentence** (design §10.5) in all five languages, past the
  safety-auditor and localization-reviewer passes. It uses the interquartile range, not the
  central-80 % band (DP-T14), and appears only when the cascade is not a small sample and agrees
  with the literature — today only `amlodipine_oedema_diuretic` qualifies.
- [ ] **No target overlap was found** between the Canon constituents and today's drugs in open
  interaction data (Wikidata P129 has interactions for ibuprofen, naproxen and dicyclomine, none
  for the constituents). Confirm this negative result is presented as a negative result and not
  as a gap to be filled from a share-alike source.
- [ ] **PubChem's data-use policy** was read from a Wayback capture (2025-01-02) because the live
  page is behind reCAPTCHA. Re-verify on the live page before launch.
- [ ] **ChEMBL stays out.** The hyperforin-PXR Ki and all other ChEMBL-deposited values are
  withheld by licence and kept only as pointers. If a share-alike data package is ever added,
  the export licence must change.
- [ ] **The API image carries no time-machine artifact.** `apps/api/Dockerfile` copies only
  `janus`, `alembic.ini` and `migrations`, so `/timemachine/*` answers 503 unless
  `.data/timemachine/current/time_machine.json` is mounted or added at deploy time. Decide which,
  as for `datasets/canon/` in the séance. (`janus/timemachine/httk_run.R` is copied with the
  package but is never executed at runtime.)
- [ ] **`.data/tools` is never committed** (user R library with httk, the ADMET-AI environment).
  Confirm the deployment builds its artifacts offline and ships only
  `.data/timemachine/current/time_machine.json`; the API image needs neither R nor torch.
