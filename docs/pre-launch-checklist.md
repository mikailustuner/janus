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
  AEMPS attribution, the update date and the "not endorsed" wording; re-check the WHOCC `J01DH` page for imipenem if the
  owner chose a component-code exception.
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
