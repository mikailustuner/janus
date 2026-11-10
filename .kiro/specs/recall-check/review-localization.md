# Localization review (agent `.kiro/agents/localization-reviewer.md`, read-only), 2026-11-10

Automated review pass of the `Recall` texts in tr, de, fr and es against en. Expert review has not yet been done; a
native-speaker clinical review is still needed.

Checked clean: key and placeholder parity (38 texts per language); no forbidden, reassurance or "AI" word; "appears
in a record" never becomes "is recalled"; the nothing-found sentence matches `Findings.noPattern` in each file; the
review sentence equals `TimeMachine.review`; "United States" equals `Common.region.US`; pharmacist, lot, product
code and package follow the file's existing terms; valid plural forms; no overflow expected at 375 px.

| # | Finding | Severity | Resolution |
|---|---|---|---|
| 1 | "Enforcement reports" had no established rendering (tr, fr read as "app" reports; de a 26-letter coinage) | advisory | The English name "Enforcement Reports" kept in tr, de, fr, es |
| 2 | "Completed" and "Terminated" came out as near-synonyms | advisory | FDA's value added in brackets; fr "Terminé" / "Clôturé" |
| 3 | fr "une fois le rappel classé" can read as "closed" | advisory | "une fois la classification du rappel attribuée"; "Classification (telle que publiée par la FDA)" |
| 4 | de, es: ambiguous subject in the status note | advisory | "der Status kann sich …", "el estado puede haber cambiado …" |
| 5 | es "su envase" for the box where the file says "caja" | advisory | "caja" in the lot lines and the pharmacist sentence |
| 6 | tr: missing objects; "bulmadı" | advisory | "bunu kontrol edebilir: ona …", "bulamadı", "bunu … karşılaştırın" |
| 7 | tr "şekliyle" where the file says "haliyle" | advisory | "haliyle" |
| 8 | de "Das automatische Lesen hat … nicht gefunden" stilted | advisory | "Beim automatischen Lesen wurde … nicht gefunden" |

Left for a native-speaker clinical review: tr "geri çağırma" against "geri çekme"; es "retirada" (peninsular)
against FDA's "retiro"; fr "fiche de rappel"; de "Eintrag" for a regulator's record; `Recall.coverage` has no plural
form for exactly one record.
