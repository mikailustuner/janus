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
