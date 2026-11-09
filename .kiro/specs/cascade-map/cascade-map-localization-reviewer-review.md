# Cascade map: localization-reviewer pass (2026-11-09)

Scope: the `CascadeMap` namespace in `apps/web/messages/{en,tr,de,fr,es}.json` (64 keys), the
reused `Findings.*` keys on the screen (`cascade`, `source`, `supporting`, `row49`,
`medicinesRoles`, `discuss`, `openDetail`, `noPattern`, `notChecked`, the scope-card reasons) and
the star labels taken from the generated vocabulary. One labelled AI pass in the role of
`.kiro/agents/localization-reviewer.md`, done separately from the safety audit. Status:
**AI-reviewed, pending native-speaker clinical review** (`docs/pre-launch-checklist.md`).

## Passed
- Key parity in all five files; placeholders `{total}`, `{shown}`, `{count}`, `{index}`, `{marker}`,
  `{name}`, `{row}`, `{reason}` intact; ICU plurals valid (TR keeps one form for both, as the rest of
  the app).
- No forbidden phrase, whole-word or inflected: EN "diagnosis" avoided (the framing line uses
  "not a verdict"); TR "tanı" appears only inside "tanımlanmış"; DE "Diagnose", FR "diagnostic",
  ES "diagnóstico"/"cura" absent. `pnpm exec vitest --run src/i18n` passes.
- Fixed terms match the app: pattern = örüntü / Muster / schéma / patrón; side effect = yan etki /
  Nebenwirkung / effet indésirable / efecto adverso; finding = bulgu / Ergebnis / résultat /
  resultado; evidence = kanıt / Evidenz / preuves / evidencia; row = satır / Zeile / ligne / fila;
  the source line and the cannot-check reasons are the scope card's own keys.
- Same hedging in all five: the framing line says "described in the literature", "to discuss with
  your doctor", "not a verdict" (hüküm / Urteil / verdict / veredicto) in each language.
- No theme-device word in any value (the screen has no Night Pharmacy / Glass pair).
- Long words: DE "Arzneimittelklasse", "Verschreibungskaskaden" wrap at 375 px (`hyphens: auto`
  on `:lang(de)`); the table has two columns so nothing scrolls sideways (checked in e2e at 375 px).

## Findings

| # | Key | Lang | Finding | Severity | Outcome |
|---|---|---|---|---|---|
| L1 | `filter.label`, `filter.clear`, `empty` | TR | "süz / süzgeç" is rare in Turkish interfaces; "filtrele / filtre" is the usual word. | advisory | **Applied**: "Örüntüleri filtrele", "Filtreleri temizle", "Bu filtrelere uyan bir örüntü yok." |
| L2 | `keys` | DE | "Escape schließt das Feld": "Feld" reads as an input field. | advisory | **Applied**: "Esc schließt die Detailansicht". |
| L3 | `keys` | TR, DE, ES | Key names should be the printed ones: "Esc" (TR, DE, ES keyboards), "Échap" (FR), "Intro" (ES Enter). | advisory | **Applied** (TR, DE, ES use "Esc"; FR already "Échap"; EN keeps "Escape"). |
| L4 | `intro`, `legend.star` | all | "the medicine classes" — some stars are single medicines (pharmacologist P5). | advisory | **Applied** in all five. |
| L5 | `legend.matched` vs `matches.count` | ES | Gender follows the noun described (línea → "más gruesa, discontinua"; patrón → "más grueso y discontinuo"). Consistent within each sentence. | — | Passed |
| L6 | `legend.title` | TR | "Açıklama" is understood; cartography uses "lejant". | advisory | Kept ("Açıklama" is plainer for older readers); for the native reviewer. |
| L7 | `inYourFindings`, `list.matched` | DE | "Ergebnis" is the app's word for a finding; a native reviewer may prefer "Befund" in a clinical context. | advisory | Kept for consistency with `Findings`; **for the experts** (app-wide choice). |
| L8 | star labels | FR | Vocabulary labels are the glossary's accepted names (e.g. "Antalgique", "Inhibiteur calcique"); not changed here. | — | Out of scope (glossary). |

Native-speaker review still needed for: TR "Kaskad haritası" (vs "Kaskat"), DE "Kaskadenkarte",
FR "schéma" for pattern (an app-wide choice already listed for the experts), ES "Intro" key name in
Latin American Spanish ("Enter").

Verdict: **pass** after L1–L4.
