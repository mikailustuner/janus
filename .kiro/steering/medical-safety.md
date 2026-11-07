---
inclusion: always
---

# Medical safety rules (non-negotiable)

1. **Never diagnose, never recommend starting, stopping or changing a medicine.** Allowed framing: "This may be worth discussing with your doctor." Describe findings as patterns, not verdicts: "These two medicines match a prescribing-cascade pattern described in the literature [source]" — never "this medicine is unnecessary".
2. **Forbidden phrases in any user-facing text** (code, templates, LLM prompts, outputs), in every supported language. Tests must enforce this list:
   - EN: "stop taking", "you should stop", "discontinue", "unnecessary medicine", "cure", "cures", "treatment for" (when describing a repurposing candidate), "diagnosis", "you have", "safe to stop", "your medicines are safe".
   - TR: "ilacı bırakın", "ilacınızı kesin", "gereksiz ilaç", "tedavi eder", "tanı", "ilaçlarınız güvenli".
   - DE: "absetzen Sie", "nicht mehr einnehmen", "unnötiges Medikament", "heilt", "Diagnose".
   - FR: "arrêtez de prendre", "médicament inutile", "guérit", "diagnostic".
   - ES: "deje de tomar", "medicamento innecesario", "cura", "diagnóstico".
3. **No false reassurance.** When nothing is found, say "Janus found no pattern from its rule list. This does not mean your medicines are free of problems." Never "safe", "no problems", "all clear".
4. **Abrupt-stop red flags:** for drug classes that are dangerous to stop suddenly (e.g. beta-blockers, antiepileptics, corticosteroids, benzodiazepines, antidepressants, clonidine), always show an extra warning: "Do not stop this medicine suddenly."
5. **Every claim cites evidence** (rule source, paper, FAERS statistic with confidence interval, text locator). If evidence is missing — or the evidence is retracted — the sentence is removed.
6. **Statistics are honest:** show confidence intervals; label weak signals; state that FAERS is spontaneous reporting (not incidence, not deduplicated). Counts are "reports", never "people".
7. **Repurposing outputs** are researcher-facing "candidates worth investigating — not treatments".
8. **Ancient texts:** label translations as machine translations; label identifications as uncertain where the source says so; overlaps are hypotheses.
9. Every screen and the doctor note carry: "Janus provides information, not medical advice. Research prototype — not a medical device."
10. Emergency symptoms (chest pain, breathing difficulty, signs of stroke, severe allergic reaction): show "Call emergency services" first (112 in TR/EU, 911 in US), before anything else.

## Regulatory awareness (for write-ups and product copy)
- **US:** FDA's Clinical Decision Support guidance (revised 29 Jan 2026) — software that gives recommendations to patients or caregivers meets the device definition; FDA applies enforcement discretion to many functions that organise information without specific treatment suggestions. Janus stays on the "organise and inform, refer to the clinician" side.
- **EU:** MDR Annex VIII Rule 11 — software providing information used for diagnostic or therapeutic decisions is at least class IIa. A real EU launch would need CE marking; the hackathon build is a research prototype.
- **Türkiye:** medical-device rules follow the EU MDR approach (to be confirmed before any launch).
- Marketing copy is part of intended use: the same rules apply to the README, the video and the Devpost text.
