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

## Séance (Phase 4, owner decisions 2026-11-08)
- [ ] **Expert review of the Canon claims** (historian of Arabic medicine and a pharmacognosist or pharmacologist): the 43 clauses in `datasets/canon/reader_ai.csv` and the 76 claims in `datasets/canon/claims.csv` were read by an AI reader and passed two AI review passes (historian, pharmacologist); none is expert-reviewed (`expert_review = pending`). Check every Arabic span against a printed edition, every machine translation, every condition category, and the 31 identifications in `datasets/canon/substances.csv` (open questions: lablab vs ivy, sawsan iris vs white lily, sirish genus, frankincense and mallow species, isfidaj white lead vs zinc oxide, dragon's blood source). Only then set `expert_review = reviewed`.
- [ ] **Science witness:** a clinician or pharmacologist checks the one-line findings in `data/seance_science.csv` against the papers, and the component bridge vinegar → acetic acid in `data/seance_present.csv`.
- [ ] **NC licence:** the Canon data package is CC BY-NC-SA 4.0. Re-check that the deployment and any prize or commercial use stay non-commercial, and that the package is never merged into Apache-licensed files.
- [ ] **Ottoman samples:** none were added (no verifiable page-level source in Phase 4). Add 10-20 only from a thesis or edition the team has read, with citation and page; never claim "we mined Ottoman manuscripts".
