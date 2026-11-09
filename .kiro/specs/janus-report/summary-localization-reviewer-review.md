# Review: `Report` namespace, Summary screen and share image (localization-reviewer)

Pass run 2026-11-09 by the implementing agent in the role of `.kiro/agents/localization-reviewer.md`; the result was
first recorded in `tasks.md` task 6 and is filed here as a separate review (the agent could not create the file).

**Verdict:** pass — 0 blocking, 9 advisory, all applied.

## Advisory findings (all fixed)
1. TR abrupt-stop tile: "kesilmemesi" instead of "bırakılmaması", to match the abrupt-stop line.
2. FR "brutalement" and ES "de forma brusca", same reason.
3. EN "has this warning" wording of the abrupt-stop tile.
4. FR/ES plural agreement of `{full}`.
5. TR ring label "/ 65" order.
6. TR polite imperative "ekleyin".
7. DE "Angeben, worum …" for the event-names option.
8–9. Minor register and punctuation fixes in the share dialog.

## Checked clean
No report word is used for the screen name (DP2: "Summary", "Özet", "Übersicht", "Résumé", "Resumen"); no forbidden
phrase; the order wording is identical to `Findings.order`; formal register; ICU plurals and placeholders match in all
five languages.
