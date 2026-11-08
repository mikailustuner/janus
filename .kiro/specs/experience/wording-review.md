# Wording review: summary (experience, task 22) — review stop

**Date:** 2026-11-08. Three separate review passes were run from the `.kiro/agents` definitions, each as an independent read-only agent:

| Sheet | Reviewer | Blocking | Advisory |
|---|---|---|---|
| `wording-localization-review.md` | localization-reviewer | 5 | 22 |
| `wording-pharmacologist-review.md` | pharmacologist | 3 | 13 |
| `wording-safety-audit.md` | safety-auditor | 2 | 13 |

Several findings overlap (status label, "anonymous", "Befunde", "Rapor/bildirim", "notificación/informe"); they are merged in the decision list below.

## Fixed before the stop (defects, not wording choices)

- **Safety B1:** the Collective Memory screen now shows the emergency notice first and the safety line next to any event that has one (combination rows, chosen event).
- **Safety B2:** read aloud uses only voices of the device (`localService`); without one the control is hidden, so "nothing is sent to a server" stays true.
- **Safety A5:** a note without its disclaimer block is a contract error, never a PDF without the disclaimer.
- **Safety A8:** typed or pasted element strings and printed "GTIN … SN … LOT" lines go through the outbound GS1 filter (serial and lot never sent); property test added.
- **Localization TR-1/TR-2, safety A11:** Turkish emergency lines fixed for case endings and keep "önce" (first).
- **Pharmacologist A2:** the results eyebrow counts the patterns actually checked (63), not the total (65).

## Decisions for the owner

1. **Finding status label** (pharmacologist B1, safety A2): replace "Probable / Possible" by timing wording ("Order fits the pattern" / "Order not confirmed"), in the app and possibly in the doctor note.
2. **"then" between the two medicines** (pharmacologist B2): role wording ("First medicine of the pattern … Second …") or "then" only when the order is known.
3. **Outcome-loop consent text** (pharmacologist B3, safety A9): say that the rule, the two ingredient codes and the event of each answered pattern are stored, and that the list is not stored (instead of "stays on this device"); bump to `OutcomeConsent.2026-11-v2` and add it to `JANUS_OUTCOME_CONSENT_VERSIONS`.
4. **"Anonymous" donation** (localization EN-1, pharmacologist A12): the data are pseudonymous (GDPR Art. 9, deletion token). Proposed: "a donated report, without your name or contact details"; note that `privacy.md` itself says "anonymous" and may need the same change. Consent version bump to `Donate.consent.2026-11-v2`.
5. **One word for "report" per language** (localization TR and ES blocking, safety A13): TR "bildirim" everywhere (as in `Memory`); ES "notificación" (reopens `Memory`) or "informe" (changes the new namespaces). Also TR "Kolektif Bellek" vs "Hafıza", DE/FR/ES "Türkiye" vs local names in `Memory`.
6. **Collective Memory caveats** (safety A1): show the spontaneous-reporting and not-incidence sentences (and the weak label) outside the fold.
7. **Smaller wording batch** (all advisory; accept as a block or pick): DE "Befunde" → "Ergebnisse", DE "Dosen", "deren", "Startmonaten", Glass soft hyphen; FR "données données", "a été commencé", emergency "en composant"; ES "no está disponible" → "no admite"; demo labels in `Doctor.demo`; pharmacologist A1, A3–A7, A9–A11 (priority sentence, window wording, row 27/57 reason, "pattern" not "cascade", "doctor-confirmed" → "reported through doctor notes (not verified)", event labels for rows 48/51, row 49 label, "nothing else" sentence); safety A3 (source on the card), A4 (emergency notice on the note screen), A6 (print), A7 (global 404 disclaimer); A12 "faint" in DE/FR/ES (reviewed `Memory` and glossary texts).
8. **Ohio demo fixture** (pharmacologist A13): rename "vial" boxes as tablets/capsules and re-record furosemide with an oral product.
9. **Budgets** (design DP38): accept the measured budgets (doctor page 183 KB, routes up to 220 KB, OCR 8.4 MB for Turkish), or ask for a lighter doctor page / English-only OCR.

## Final demo cases (design §13.1, recorded on the real engine 2026-11-08)

| Patient | Findings | Notes |
|---|---|---|
| Istanbul (TR) | `pipc:5` probable 5 months; `pipc:6` probable 2 months; `pipc:9` probable 4 months (BMJ incidence); `pipc:12` possible, start unknown | combination box decomposed (C08CA01 + C09AA03; C09BB03 only as published); abrupt-stop: sertraline, alprazolam; 63 of 65 rules |
| Cologne (EU) | `pipc:1` probable 3 months (ramipril → ambroxol); `pipc:51` probable 2 months (ibuprofen → pantoprazole) | both form-unconfirmed (German boxes by name); `urgent_care_gi` shown |
| Ohio (US) | `pipc:24` probable 5 months (donepezil → oxybutynin); `pipc:31` probable 4 months (gabapentin → furosemide) | abrupt-stop: gabapentin; pharmacologist: plausible, fix box names (decision 8) |

## Open items of design §20

All four were decided on 2026-11-08 (design "Owner decisions"). New items from this review are the decisions above. Before launch (pre-launch checklist, task 23): native-speaker clinical review of the new namespaces in four languages; print-and-scan test of the demo QR at 50 mm on several phones; re-check of the emergency and crisis numbers; real-device check of local speech voices.
