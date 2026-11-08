# Pre-launch checklist (Phase 5)

Items that must be checked before Janus is deployed or announced. Add items here when a spec
defers a check to launch.

- [ ] **MedDRA terms for public display.** FAERS event terms are shown as the MedDRA Preferred
  Terms published by FDA, without any MedDRA hierarchy (SOC, HLT, LLT). Verify the MSSO terms for
  public display of PTs, and confirm that the notice "MedDRA® is a registered trademark of ICH"
  appears on every screen, export and document that shows a PT (`data-pipelines` DP33).
- [ ] **Scheduling.** Weekly, monthly and quarterly pipeline runs (`data-pipelines` DP11, DP27).
- [ ] **GS1 AI table and a real box.** Confirm AI 710 to 714 from the GS1 General Specifications
  and test the French and Spanish adapters with a real box if one becomes available
  (`.kiro/specs/drug-resolution/eu-code-encodings.md`).
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
- [ ] **Crisis and support lines per region** (`experience` Requirement 7): curate and verify the numbers for TR, EU and US
  before they are shown; confirm the urgent-care wording for severe skin reactions and arrhythmia with a clinician.
- [ ] **EudraVigilance public address.** Verify the exact address form of adrreports.eu before the link is used
  (`collective-memory` Requirement 3.2).
- [ ] **MedDRA notice wording.** Check the exact required wording of the MedDRA trademark notice (the owner of MedDRA is
  named as IFPMA acting for ICH) and whether it may be translated; the `Memory.meddra` string is English in all five
  languages today (`collective-memory` safety review S10).
- [ ] **Further safety lines.** The owner decides whether `gastric_ulcer_bleed` (blood in vomit or black stools), `seizures`
  and `heart_failure` also get an urgent-care line (safety review S4, drafts in `memory-safety-review.md`).
