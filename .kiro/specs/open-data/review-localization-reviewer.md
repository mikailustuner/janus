# Open data: localization-reviewer review

**Date:** 2026-11-09 · **Reviewer:** localization-reviewer (`.kiro/agents/localization-reviewer.md`), a separate
read-only agent pass on the `OpenData` namespace.

| # | Finding | Action |
|---|---|---|
| L1 | EN "doctor-confirmed outcomes" claims more than "Janus has not verified them" | Fixed: "outcomes reported by doctors" (and the translations) |
| L2 | TR "hekimin doğruladığı" contradicts "doğrulamamıştır"; the file says "doktor" | Fixed: "doktorların bildirdiği sonuçlar" |
| L3 | DE "Ergebnisse" means results elsewhere | Fixed: "ärztlich gemeldete Behandlungsverläufe" |
| L4–L6 | FR "comptes" → "chiffres"; "signalements issus de dons"; "issues signalées par des médecins"; "Proposer des corrections" | Fixed |
| L7 | ES "según el recuento real", "se registró a partir de", "Aportar correcciones" | Fixed |
| L8 | DE word order "es ist kein Text … enthalten", "tatsächlichen Zahl" | Fixed (the package sentence was then rewritten after O5) |
| L9 | TR `rule.hidden` unnatural | Fixed |
| L10 | Tile labels long in DE/FR | Checked at 375 px in the e2e (no overflow) |
| L11 | TR `TimeMachine` "Reçeteleme kaskadları" left over | Fixed |

**Clean:** key parity, placeholders, ICU plurals, Turkish suffixes after placeholders, report words, formal register,
no forbidden phrase. A native clinical review of the word for "outcome" is still needed (checklist).
