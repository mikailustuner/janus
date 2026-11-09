# Time machine screens and owner-decision texts: localization-reviewer review

**Date:** 2026-11-09
**Reviewer:** localization-reviewer (`.kiro/agents/localization-reviewer.md`), a separate read-only agent pass.

## Scope
`TimeMachine` namespace (five languages); `Cards.results.medicinesChecked`, `Report.summaryLine`,
`Report.image.headline`, `Report.image.medicines`; `ReportAssistant.draft.typeUnknown`, `labels.usE10`,
`janus.othersOtc`; the note sentence `medicines.count`.

## Findings (2 blocking, 8 advisory) and actions
| # | Finding | Action |
|---|---|---|
| L1 | TR `reasons.few_reports`: "{n}'den" breaks vowel harmony for a variable number | Fixed: "… bildirim sayısı yetersiz (en az {n} gerekir)." |
| L2 | DE `labels.usE10`: "und pflanzlichen Mittel" | Fixed: "pflanzliche Mittel" |
| L3 | TR "reçeteleme kaskadı" vs "reçete kaskadı" elsewhere | Fixed in the namespace |
| L4 | ES "acontecimiento adverso" vs "evento adverso" in Memory | Fixed |
| L5 | DE patient sentence "Arzneimittel" vs "Medikament" in the patient UI | Fixed ("des ersten Medikaments"; the sentence was then rewritten with the drug name, DP65) |
| L6 | FR/ES parenthetical plurals in `validation.summary` | Fixed with ICU plurals; ES "En el límite" |
| L7 | FR/ES/DE `Report.image.headline` last clause | Fixed: "comparaison avec", "comparación con", "abgeglichen mit" |
| L8 | FR `activitiesCount` plural | Fixed: "Enregistrements montrés : {shown} sur {total}." |
| L9 | TR "remedy" as "ilaç" blurs Canon remedies and modern medicines | Left to a native speaker (checklist) |
| L10 | FR `sections.how` → "Méthode" | Fixed |

## Clean
Key parity; placeholders; the patient sentence's safety wording and the end equal to `Findings.discuss`; review labels
equal to `Seance.past.aiReviewed`; report words (bildirim, Meldung, signalement, notificación); number and percent
conventions; formal register; no forbidden phrase; no length problem at 375 px.
