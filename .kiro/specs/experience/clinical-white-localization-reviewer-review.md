# Review: Glass Janus "Clinical White" (localization-reviewer, Req 31)

**Pass:** `localization-reviewer` (`.kiro/agents/localization-reviewer.md`), one read-only agent pass (2026-11-09) over
`apps/web/messages/{en,tr,de,fr,es}.json`: the new `Home.glass.*` block (24 keys per language), the changed
`Home.alt.glassHero` and `Settings.reduceTransparencyHint`, and where they render (`components/home/GlassJanusHero.tsx`,
`GlassHomeSections.tsx`, the sizes in `src/theme/home-scenes.css`).

## Findings: 0 blocking, 15 advisory

| Key | Lang | Finding | Applied |
|---|---|---|---|
| `Settings.reduceTransparencyHint` | all | Bracket used the old theme name ("Glass theme", "Cam teması" …), not the Settings name | Theme names of `Settings.themeGlass`: "Glass Janus", "Cam Janus", "Glas-Janus", "Janus de verre", "Janus de cristal" |
| `Settings.reduceTransparencyHint` | all | Incomplete: the floating hero cards turn solid too (`--nav-surface`) | "Solid header, tab bar and floating cards …" and equivalents |
| `Home.alt.glassHero` | tr | "İllüstrasyon:" while the sibling alts use "Çizim:" | "Çizim: …" |
| `Home.alt.glassHero` | es | "vidrio" while the theme says "cristal" | "cabeza de cristal transparente …" |
| `Home.alt.glassHero` | en | "white ground" is studio jargon | "white background" |
| `Home.alt.glassHero` | de | "Glaskopf" is also a mineral name | "ein Kopf aus klarem Glas …" |
| `Home.glass.patterns` | en, de, fr, es | "patterns checked" can read as "verified patterns" | The `Home.how2` verb: "compared", "verglichen", "comparés", "comparados" (TR already "karşılaştırılır") |
| `Home.glass.patterns` | de | No soft hyphen in "Verschreibungskaskaden" (hero card ≈ 195 px) | Soft hyphen in both branches |
| `Home.glass.how3Title` | de | "für die Praxis" changes the addressee | "Die Arztnotiz" (as `Findings.makeNote`) |
| `Home.glass.sourcesTitle` | tr | "geri çekilmeye karşı" sounds odd | "Kaynakların geri çekilme durumu kontrol edilir." |
| `Home.glass.sourcesTitle` | fr | Calque of English | "Sources vérifiées au regard des rétractations." (native check listed) |
| `Home.glass.sourcesTitle` | es | Stiff | "Fuentes revisadas en busca de retractaciones." |
| `Home.glass.noteText` | fr | "par lequel" stiff | "… grâce auquel le médecin peut répondre." |
| `monthsApart`, `sources`, `patterns`, `phoneMonths` | tr, fr | Only an `other` branch (valid ICU), unlike the catalogue habit | `one` added, identical to `other` |
| `Home.glass.regionsText` | all | "Public medicine lists from Türkiye, the EU and the US": the EU tile is BDPM · CIMA (France, Spain) only | Passed to the safety audit (see `clinical-white-safety-auditor-review.md`) |

Layout note (not a translation finding): the phone mock's tiles are narrow; the mock is `aria-hidden` and clipped, so
nothing is lost for screen readers; DE and EN screenshots of the tile were reviewed.

## Checked and clean (reviewer)
Forbidden phrases and theme words: none in any new or changed value (inflected forms included). Key and placeholder
parity: 24 keys in every language, `{months}` / `{count}` intact. Terminology: report (bildirim / Meldung /
signalement / notificación), pattern (örüntü / Muster / schéma / patrón), prescribing cascade, range; Istanbul demo
named as in `Home.scene3Intro`; both hero cards carry `Demo.label`. "Reports, not people" kept in every language.
Drug names per language correct; "then / danach / puis / después / ardından" keep the order and add no cause. Formal
register throughout. 375 px: floating cards hidden below 1,100 px, grid one column below 960 px, longest words fit.

Native clinical review still advised before launch (TR and FR sentence-level wording).
