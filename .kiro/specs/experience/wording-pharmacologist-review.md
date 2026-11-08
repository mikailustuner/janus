# Wording review: pharmacologist (experience, task 22)

**Date:** 2026-11-08
**Reviewer:** pharmacologist (`.kiro/agents/pharmacologist.md`), run as a separate read-only agent pass; no files changed by the reviewer.
**Rules applied:** `medical-safety.md` (patterns not verdicts, no false reassurance, abrupt-stop line, evidence), cascade-engine Req 2 (status and timing logic), doctor-loop Req 3.2 (what is stored).

## Scope

- `apps/web/messages/en.json`: Findings, Confirm, Medicines, Timeline, Evidence, MemoryView, Note (QR opt-in), OutcomeConsent, Donate, Doctor; tr/de/fr/es spot-checked for meaning drift on the same keys.
- `apps/web/src/doctor/messages.json` and the doctor form texts and options in the fixtures.
- `apps/web/src/vocabulary/en.json` (`sentences`, and the `events` and `cascades` entries shown on findings); the `abrupt_stop` sentence in all five languages.
- Demo fixtures `apps/web/src/demo/fixtures/{istanbul,cologne,ohio}.json` checked against `data/pipc.csv`, `data/cascade_classes.csv`, `data/abrupt_stop_classes.csv`; the Ohio product RxCUIs looked up read-only on RxNav.

## Summary

- **Blocking: 3** (two findings-card wordings that overstate; one consent text that understates what is stored). **Advisory: 13.**
- **Demo cases:** all three plausible; every expected row reproduces and no other row fires. Only Ohio needs a fixture fix (advisory).
- **Sound, no change:** `Findings.pattern`, `Findings.discuss`, `Findings.noPattern` in all five languages; the abrupt-stop sentence in all five languages; every `not_checked.*` reason, `Confirm.homeopathic`, `Confirm.matchedDigits`, `Medicines.combinationCode` (C09BB03 correctly not an ingredient code); the four timing sentences; Evidence statuses; doctor form options ("Medicine stopped" reports a fact, it does not advise).

## Findings

| # | Key or case | Issue | Suggested wording or decision | Severity |
|---|---|---|---|---|
| B1 | `Findings.status.probable` / `.possible` (all locales), the chip next to `Findings.kind.glass` | "Possible prescribing cascade" followed by a chip "Probable · 4 months apart". The status is purely a timing class (cascade-engine Req 2.2–2.5). "Probable"/"Possible" are WHO-UMC causality words, so a clinician reads a causality judgement (rule 1). In Turkish "Olası … kaskadı" next to "Muhtemel" has no visible contrast. | Keep the codes; change the labels to timing: probable "Order fits the pattern", possible "Order not confirmed"; with months "Order fits the pattern · 4 months apart". TR "Sıra örüntüye uyuyor" / "Sıra doğrulanmadı"; de, fr, es to match. | Blocking |
| B2 | `Findings.medicines` (all locales: then / sonra / danach / puis / después) | "atorvastatin (Atordem 20), then alprazolam (Alpradem 0.5)" claims an order; in Istanbul row 12 the start is unknown and the same card says the order could not be checked. Same for `same_month`. | Role wording: "First medicine of the pattern: {index} ({indexBox}). Second: {marker} ({markerBox})." (matches the doctor form). Alternative: keep "then" only for `within_window` / `after_window`. | Blocking |
| B3 | `OutcomeConsent.2026-11-v1.stored` (all locales) | Says Janus stores "the codes of the patterns" and "the medicine list stays on this device". Doctor-loop Req 3.2 stores the rule id, the index and marker ingredient keys, the event, the action and its medicine, and form-confirmed: two ingredients per answered pattern leave the device. A consent text must not understate. | "Janus stores only the doctor's answers, the week of the answer, the region of the note, and for each answered pattern its rule and the codes of its two medicines and of the event. No names, no box names and no dates finer than a week. The rest of the medicine list stays on this device." Consent version bump to 2026-11-v2. | Blocking |
| A1 | `Findings.priority` + `Findings.measure.incidence` | "incidence, % 10.9 (range 10.7 to 11.0)" does not say incidence of what; can be read as an 11 % chance of a cascade. | "In a published study of older adults (BMJ 2026), {value}% of people starting the first medicine class then started the second (range {low} to {high})." Check the exact denominator against the abstract first. | Advisory |
| A2 | `Findings.checkedOf` (Results passes `total`) | "checked against 65 patterns", but `rules.checked` is 63 (rows 27 and 57 not matchable). | Pass `checked`. | Advisory |
| A3 | `Findings.groupUnconfirmedIntro` (EN, TR) | "to be sure the pattern applies": confirming the form never makes a pattern certain (de/fr/es already say "whether it applies"). | EN "…to check whether the pattern applies to this form." TR "…örüntünün bu form için geçerli olup olmadığını görmek için…" | Advisory |
| A4 | `Findings.timing.within_window` / `.after_window` | "window used for this kind of pattern" suggests a per-row window; it is one Janus setting with a cited justification. | "…within the {window}-month window Janus uses for these patterns." | Advisory |
| A5 | `Findings.notMatchable.no_atc_code` | "the medicine class has no code" is wrong for row 27 (bismuth subsalicylate, a substance) and row 57 (saliva substitute, a product type). | "the medicine named in the pattern has no ATC code" | Advisory |
| A6 | `Findings.supporting` | "The same cascade is also described…" calls the finding a cascade; elsewhere "pattern". | "This pattern is also described in another published cascade list (ThinkCascades)." | Advisory |
| A7 | `MemoryView.outcomesTitle` (all locales) | "Doctor-confirmed outcomes" implies a verified physician; answers come through an account-less QR link and anyone can create tokens (known limit). | "Outcomes reported through doctor notes (not verified)"; TR "Doktor notlarıyla bildirilen sonuçlar (doğrulanmamış)". | Advisory |
| A8 | `MemoryView.ratio` (TR) | "Raporlama oranı (ROR)" drops "odds" and reads as a reporting rate, against `not_incidence`. | Localization: e.g. "Raporlama odds oranı (ROR)", which avoids the `Memory` word-list ban on "olasılık". | Advisory |
| A9 | vocabulary `events.gastric_ulcer_bleed`, `events.osteoporosis_fracture` | Labels narrower than the published events (row 51 includes gastritis; row 48 includes fractures). | "Stomach irritation, ulcer or bleeding in the stomach or bowel"; "Weaker bones or fractures (osteoporosis)". Change in `memory_events.csv`, regenerate. | Advisory |
| A10 | vocabulary `cascades.49.drug_b` (all locales) | "Vitamin or Mineral Deficiency" as the second medicine reads "PPI → deficiency → deficiency". Kept as published (owner decision 2026-11-07), but unreadable for a patient. | Keep the published text and add the matched class: "Vitamin or Mineral Deficiency (as published; matched: vitamin B12, magnesium or iron supplements)". | Advisory |
| A11 | `Donate.storedNothingElse` | "no … date, place" next to "The week of the report" and "Region". | "Nothing else: no name, email, exact date, place finer than the region, or device identifier." | Advisory |
| A12 | `Donate.intro` / `Donate.consent…check` ("anonymous") vs `Donate.consent…body` (GDPR Art. 9) | Data linkable through a deletion token and processed under Art. 9 consent is pseudonymous, not anonymous. Outside the pharmacologist's remit. | Privacy owner; e.g. "a donated report without your name". | Advisory |
| A13 | Ohio fixture box names (`scripts/record-demo.mjs`) and recorded products | "10 mg vial" reads as an injection (donepezil, gabapentin, oxybutynin have no injectable form). The furosemide pick resolves to RxCUI 1719286 (10 mg/mL injection); the oxybutynin pick to RxCUI 863619 (24-hour ER 10 mg) while the box says 5 mg. Matching unaffected. | "Donedem 10 mg tablets (demo)", "Gabadem 300 mg capsules (demo)", "Oxydem 10 mg ER tablets (demo)", "Furodem US 20 mg tablets (demo)"; re-record furosemide with an oral product. | Advisory |

## Demo cases

**Istanbul (TR, note in Turkish): plausible and fairly presented.**
- Amlodipine reaches the engine as an ingredient (C08CA01) from the amlodipine + lisinopril box (C09BB03); the combination code is never matched.
- Row 5, amlodipine → furosemide, 5 months, probable: the classic CCB-oedema cascade.
- Row 6, amlodipine → lactulose, 2 months, probable: a valid class match; constipation is mainly a verapamil effect, so this is the weaker amlodipine finding. Acceptable as a pattern.
- Row 9, atorvastatin → paracetamol, 4 months, probable, with the BMJ incidence: fair; statin → pain reliever has the highest incidence in the abstract. With B1 it reads correctly.
- Row 12, atorvastatin → alprazolam, start unknown, possible: fair as "possible" (N05BA in `sleep_agent` by design; sertraline on the list is another reason for alprazolam; statin insomnia is the weakest evidence of the four). Shows `date_unknown` and a marker-side abrupt-stop line; B2 needed here.
- Warnings sertraline (N06A) and alprazolam (N05BA) correct; none missing. No missed rows (1, 2, 7, 8, 23, 42, 47, 48, 49, 51 lack their partner).

**Cologne (EU, note in German): plausible and fairly presented.**
- Row 1, ramipril → ambroxol, 3 months, form-unconfirmed: plausible self-treatment; ambroxol is a mucolytic while ACE-inhibitor cough is dry. Fine for a demo; a cough suppressant would be more on target (optional).
- Row 51, ibuprofen → pantoprazole, 2 months, form-unconfirmed: valid (only M01AE01 matched). Caveat for the doctor: a PPI is often started on purpose as gastroprotection; "may be worth discussing" is fair, B1 removes the "Probable" overstatement.
- Both findings correctly under "Product form not confirmed"; no abrupt-stop medicine on the list.

**Ohio (US, note in English): plausible clinically; fix the fixture's product presentation (A13).**
- Row 24, donepezil → oxybutynin, 5 months: the best-documented cascade in the set.
- Row 31, gabapentin → furosemide, 4 months: plausible and well described.
- Gabapentin warning (N02BF, owner-confirmed extension) correct. Row 8 (diuretic → oxybutynin) correctly does not fire: oxybutynin was started before furosemide.

## Needs a physician or pharmacist before launch

1. Status labels: sign off the timing-based labels (B1); decide whether "Probable" may appear anywhere, including the doctor note.
2. The single 12-month window for every row: some events (row 48, osteoporosis or fractures) develop over years; decide on per-row windows.
3. Inclusion judgements in `cascade_classes.csv`: N05BA anxiolytics and trazodone as "sleep agent"; paracetamol and opioids as "pain reliever"; mucolytics as "cough remedy"; potassium-sparing diuretics as index drugs for gout.
4. NSAID → PPI (row 51): is a deliberately started prophylactic PPI worth a finding; should the note say gastroprotection can be intended.
5. Abrupt-stop list extensions (owner-confirmed 2026-11-07): gabapentinoids, opioids, antipsychotics, lithium, Z-drugs, dopaminergic drugs, baclofen, tizanidine, central alpha-agonists.
6. Urgent-care and crisis lines: the `Memory.codes.urgent_care_*` thresholds and the emergency and crisis numbers.
7. Doctor form: the assessment and action options and question wording.
8. Clinical class translations in the vocabulary (e.g. DE "Nichtsteroidales Antirheumatikum", TR "Mide koruyucu ilaç").
9. Consent texts: OutcomeConsent v2 (B3) and the Donate wording (A12) with privacy and legal review.
