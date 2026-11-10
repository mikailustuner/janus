# Review: localization-reviewer pass (ocr-first)

> 2026-11-10. Automated review with the `.kiro/agents/localization-reviewer.md` role, read-only, of the 26 new or
> changed keys in en, tr, de, fr, es. Expert review has not yet been done; a native-speaker clinical review is
> still needed before launch.

## Findings and what was done
| # | Key | Lang | Severity | Finding | Resolution |
|---|---|---|---|---|---|
| 1 | `Scan.anyCountry`, `Home.how1`, `Confirm.tryOther` | tr | blocking | "her kutuda işe yarar" = "works on every box", wider than English. | "herhangi bir ülkeden gelen kutuda"; `tryOther` reworded in all languages after the safety pass. |
| 2 | `Scan.anyCountry` | tr | advisory | "ürün listesini tuttuğu ülkelerde" unidiomatic. | "Janus'un elinde ürün listesi bulunan ülkeler için". |
| 3 | `Scan.ocr.noIngredient` | tr | advisory | Read as "one particular name". | "…adlarından hiçbirini tanımadı." |
| 4 | `Scan.ocr.privacy` | tr | advisory | "Fotoğraf ve metni" looked ungrammatical. | "Fotoğraf ve içindeki metin". |
| 5 | `Scan.labelLead` | tr | advisory | Stacked genitive. | "Kutunun, etkin maddenin yazılı olduğu yüzünün". |
| 6 | `Scan.codeLead` | tr | advisory | "yine" → "yine de". | Applied. |
| 7 | `Confirm.tryOther` | tr | advisory | Sentence after a colon in lower case. | Capitalised. (`Scan.intro` is a list and stays.) |
| 8 | `Scan.ocr.similar` | de | advisory | Missing object. | "Bitte vergleichen Sie sie mit der Packung." |
| 9 | `Scan.ocr.noIngredient` | de | advisory | "tippen" and "eintippen" in one sentence. | "…oder den Namen eingeben." |
| 10 | `Scan.ocr.remove` | de | advisory | "Fotoergebnis". | "Ergebnis dieses Fotos entfernen". |
| 11 | `Scan.codeLead` | fr | advisory | "toujours" can read as "always". | "quand même". |
| 12 | `Scan.ocr.remove` | fr | advisory | Awkward. | "Retirer le résultat de cette photo". |
| 13 | `Scan.ocr.turning` | fr | advisory | Telegraphic. | "…avec la photo pivotée…". |
| 14 | `Scan.anyCountry`, `Home.how1` | es | advisory | "sirve con". | "funciona con". |
| 15 | `Scan.ocr.remove` | es | advisory | Ambiguous. | "Quitar el resultado de esta foto". |
| 16 | `Scan.ocr.wordsTitle` | es | advisory | Gendered "usted mismo". | "por su cuenta". |
| 17 | `Scan.ocr.similar` | es | advisory | "Escritura parecida" vague. | "Grafía parecida." |
| 18 | `Scan.ocr.capture`, `several`, `noIngredient`, `cameraHint` | es | advisory | "tomar la foto" (the file is otherwise peninsular). | "hacer la foto". |
| 19 | `Scan.ocr.privacy` | all | advisory | Narrower than the behaviour. | "Only the name, words or NDC you choose are sent." in five languages. |
| 20 | `Scan.wayType` | fr, es | advisory | Longest button labels. | "Saisir la substance active", "Escribir el principio activo". Buttons wrap; checked at 375 px in the e2e run. |

Found in order: key parity (26 keys × 5), placeholders, no forbidden phrase (the Turkish `tanı-` forms are
"recognise" and do not match the whole-word rule), no "AI / yapay zekâ / KI / IA", one term for ingredient, box
and label per language.

Outside this change, noted and not touched: French `Scan.typeHint` and three `Confirm` keys use "substance"
without "active".
