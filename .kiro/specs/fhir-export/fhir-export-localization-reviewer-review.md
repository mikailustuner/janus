# FHIR export review: localization-reviewer

**Date:** 2026-11-09
**Reviewer:** localization-reviewer (`.kiro/agents/localization-reviewer.md`), run as a separate read-only agent pass
against `medical-safety.md` and `product.md`. The reviewer edited no files. English is the source; tr, de, fr and es are
AI drafts.

## Scope and method
- The `Fhir` namespace (10 keys at review time) in `apps/web/messages/{en,tr,de,fr,es}.json`, read with `FhirExport.tsx`,
  `bundle.ts` and the spec (Req 5, design §4, §6).
- Forbidden phrases with inflected and near forms (EN safe/diagnos/cure, TR tanı/güvenli/bırak/tedavi, DE
  sicher/heil/diagnos/absetz, FR sûr/guéri/diagnost, ES segur/cura/diagnós): no hits.
- ICU placeholders rendered with intl-messageformat for (1/1/1), (3/4/5), (2/0/3), (1/0/0): all parse; plurals right.
- Terms compared with the rest of each file (ingredient, medicine list, this device, "Demo · synthetic patient", "Name on
  the box", privacy texts); formal address throughout.

## Summary
| Language | Blocking | Advisory |
|---|---|---|
| EN | 0 | 5 |
| TR | 1 | 3 |
| DE | 0 | 7 |
| FR | 0 | 2 |
| ES | 0 | 4 |

## Findings and what was done
| # | Key, language | Finding | Done |
|---|---|---|---|
| 1 | `preview`, TR (**blocking**) | "etken madde"; the file uses "etkin madde" (47×) | **Fixed:** "etkin madde" (also in the new `contents`). |
| 2 | `what`, all | "health systems" reads as a national health service | **Fixed:** "health software systems" / "sağlık yazılımı" / "Programme im Gesundheitswesen" / "logiciels de santé" / "programas sanitarios". |
| 3 | `preview`, EN and all | "coded" is jargon | **Fixed:** "with a standard code" in all five. |
| 4 | `includeNames`, all | The UI calls it "Name on the box"; "product names" means the invented demo names elsewhere | **Fixed:** "Include the names on the boxes" and equivalents. |
| 5 | `notChecked`, EN and all | "your list as you entered it" is untrue in demo; "restates" is uncommon | **Fixed:** "The file contains the list as it was entered." and equivalents. |
| 6 | `saved`, all | Shown after `click()`, the browser may block or cancel the save | **Fixed:** "Download started: {file}." and equivalents. |
| 7 | `saved`, layout | 33-character file name could overflow with large text | **Fixed:** `[overflow-wrap:anywhere]` on the status line. |
| 8, 9 | `notChecked`, TR | "aktarır" vague; "sağlık çalışanı" more natural | **Fixed** both. |
| 10–13 | `what`, `demo`, `includeNamesHint`, `notChecked`, DE | Reference of "Damit"; trailing participle; agent of linking; "medizinische Akte" | **Fixed** all four ("Hier speichern Sie…", "…und ist als Testdaten gekennzeichnet", "Mit dem Namen auf der Packung lässt sich…", "keine Patientenakte"). |
| 14, 15 | `preview`, `saved`, DE | "codiert"; word order | Resolved by 3 and 6. |
| 16 | `includeNamesHint`, FR | Clumsy | **Fixed:** "…peut aider à faire le lien entre ce fichier et vous." |
| 17, 18 | `notSent`, `includeNamesHint`, ES | "su sistema" ambiguous with usted; "se relacione" | **Fixed** both. |
| 19 | `title`, ES | "Exportar en formato FHIR" more idiomatic | **Fixed.** |
| — | `preview` | "0 of 0 ingredients" possible when nothing was recognised | Kept: truthful, and every item that reaches the list has at least one ingredient in practice. |

## Still needed
A native-speaker review before launch: TR "sağlık çalışanı" register; DE "Patientenakte" and "Fachperson"; FR hint
phrasing; ES "historia clínica" vs "historial médico" for US Spanish.

## Verdict
Blocking finding fixed; all advisories applied except the 0-of-0 edge. Ready.
