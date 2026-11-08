# Séance screen: localization-reviewer and safety-auditor passes (2026-11-08)

Scope: the séance web screen (`apps/web/src/components/seance/Seance.tsx`, `apps/web/src/seance/`), the hypothesis-card
cross-reference (`components/light/CardView.tsx`), the `Seance` namespace and `Research.review` in EN, TR, DE, FR, ES, and
the catalogue field `present_ingredient_key` (API). Two separate, labelled passes by the read-only agents of
`.kiro/agents/`; neither saw the other's findings. Status of everything here: **AI-reviewed, pending expert review**
(see `docs/pre-launch-checklist.md`, "Expert review (Phase 4)").

## Pass 1: localization-reviewer

Passed: key parity (112 `Seance` keys + `Research.review` in all five files), placeholders, ICU plurals (the French count
needs its own plural), no forbidden phrase whole-word or inflected (ES "cura" not inside any word; TR "tanı" only inside
"tanık"/"tanımlama"), no theme-device word in any `glass` value, the same hedging in all five languages (rule-7 line equal
to `Light.rule7`, "machine translation", "AI-reviewed, pending expert review", reports not people). Long German words wrap
(`hyphens: auto`, `overflow-wrap: anywhere`).

| # | Key | Lang | Finding | Severity | Outcome |
|---|---|---|---|---|---|
| L1 | `headline.eligible`, `headline.reason.hazardous_substance` | all | "is not a hazardous substance" claims more than the data (only a toxic/caustic flag) | blocking | **Applied**: "not flagged as toxic or caustic" in all five |
| L2 | ingredient term | TR, FR | "etken madde" / "principe actif" differ from the app's "etkin madde" / "substance active" | blocking | **Applied** |
| L3 | `present.pts` | FR | "Termes préférés" → "Termes préférentiels" (MedDRA French, as `MemoryView`) | advisory | **Applied** |
| L4 | `present.item` vs `MemoryView.ratio` | FR | "déclaration" vs "signalement" for one statistic on one screen; app-wide split | advisory | **For the experts** (one app-wide choice) |
| L5 | pattern term | FR | "profil" here, "schéma" in Memory | advisory | **For the experts** (with L4) |
| L6 | condition term | FR | "affection" here, "état" in Light | advisory | **For the experts** (harmonise Light later or accept) |
| L7 | `present.pts` | TR | capitalise "Tercih Edilen Terimleri" as in `MemoryView` | advisory | **Applied** |
| L8 | `present.snapshot`, `present.observed` | DE | "verdächtige Arzneimittel" reads "suspicious" → "Verdachtsarzneimittel" | advisory | **Applied** (`MemoryView.scopeSuspect` left for the experts) |
| L9 | `science.integrity.ok` | FR, TR | FR "notice" = package leaflet → "Aucun avis"; TR "endişe ifadesi" vs "endişe bildirimi" | advisory | FR **applied** in `Seance`; `Evidence.status` and the TR term **for the experts** |
| L10 | `missing` | all | number agreement with two missing witnesses | advisory | **Applied**: "Missing witnesses: …" |
| L11 | `infectionBridge` | FR, ES | ungrammatical "qui s'étendent ou fétides" | advisory | **Applied**: "extensifs ou fétides" / "extensivas o fétidas" |
| L12 | `demo` | ES | "se grabaron" → "se registraron" | advisory | **Applied** |
| L13 | `substance.hazard.*` | FR | "Trace historique" → "Mention historique" | advisory | **Applied** |
| L14 | `missingReason.no_protective_association`, `codes.screening_pattern_not_effect` | DE | "unterhalb der Erwartung" | advisory | **Applied** |
| L15 | `confidence`, `seat.confidence` | DE | "Vertrauen: keines" unidiomatic | advisory | **For the experts** (short chip label needed) |
| L16 | `seat.confidence` | TR | "Güven düzeyi" | advisory | **Applied** |
| L17 | `codes.spontaneous_reports` | TR | "spontan bildirim" is the pharmacovigilance term; Memory also says "gönüllü" | advisory | **For the experts** (change both together) |
| L19 | `seat.silent` | all | "Silent" next to visible counts or studies reads as "nothing found" | advisory | **Applied**: "Does not support" / "Desteklemiyor" / "Stützt nicht" / "N'appuie pas" / "No respalda" |

Native-speaker clinical review needed (cannot be judged by the agent): the condition words of `infectionBridge` (TR
"dolama", "şirpençe"; DE "Nagelbettentzündung" vs "Panaritium"; FR/ES "anthrax"/"ántrax" for carbuncle, which readers
may take for the disease), DE "Zustand" for condition, "expression of concern" in TR/DE/FR/ES, TR "bildirim odds oranı",
FR "rapport de cotes", ES "razón de odds de notificación", TR "maruziyet" and "müstahzar", DE "Bestimmung" for a botanical
identification, and the ingredient/report terms of L2 and L4. Never change TR "Tanımlandı/Tanımlama" to "teşhis" (a
near-synonym of the forbidden "tanı").

## Pass 2: safety-auditor

Passed: rule 7 line on the screen, in the count card and on the research hub (five languages); rule 8 (every translation
"Machine translation (English)", every passage "AI-reviewed, pending expert review", summaries and findings "machine-written",
"Identified" only for gold matches, Hamdard cited only, Arabic with `lang="ar" dir="rtl"`); the count "n of 3 witnesses"
with "not a score", no percentage, bar, colour scale or `--risk`; hazard flag in `--warn`; counts are reports, the five
caveats as text, interval bar, MedDRA notice; no reassurance or advice; the disclaimer from the shell; demo mode sends no
request (client chosen only after hydration, fixture by dynamic import); the pair travels in a POST body or in memory,
never in a URL; the API logs the access line only.

| # | Finding | Rule | Severity | Outcome |
|---|---|---|---|---|
| S1 | A science paper title holds "treatment for" (Jull 2015, honey / burn; live mode only) and the source scan does not cover `data/` | 2 | blocking | **Applied**: the screen withholds a title that holds a forbidden phrase and says so; the DOI stays (`showableTitle`, unit test). **For the owner**: whether verbatim citation titles may be shown as quoted titles, and whether to scan `data/seance_science.csv`, `data/evidence_papers.csv` and `datasets/canon/*.csv`. The light-face source list prints titles the same way |
| S2 | Excluded studies are listed as "removed by Evidence Integrity (retracted or not registered)" without the zombie stamp of design §7.3 rule 5 | 5 | advisory | **Kept** (honest: the contract gives bare ids). **For the owner**: API sends `{evidence_id, reason}`; the screen then stamps only `retracted` |
| S3 | The cross-link sentence did not say acetic acid is only a component of vinegar; "(for skin conditions, not for this condition)" may become false | 1, 5 | advisory | **Applied**: the sentence is chosen by `present_link` ("a component of a substance in the Canon, not the same exposure"); the parenthesis removed |
| S4 | A requested pair that the view cannot answer (demo) silently fell back to another pair | 3 | advisory | **Applied**: a status line says the chosen pair is not available here |
| S5 | "Studies checked by Evidence Integrity" next to "Not yet checked against retraction data" | 5 | advisory | **Applied**: "passed through Evidence Integrity (status shown for each study)". The `retractions` run for the four DOIs is a checklist item |
| S6 | The interval text says "range", not "95 % confidence interval"; `ror_ci.level` not shown | 6 | advisory | **For the owner** (shared `CiBar`, predates the séance) |
| S7 | No weak-signal code in the present witness for a supporting pattern on few reports | 6 | advisory | **For the owner** (API contract; latent: nothing supports today) |
| S8 | Unknown caveat codes would show a raw key | 6 | advisory | **Applied**: `codes` decoded as the closed list; an unknown code is a contract error |
| S9 | `past_passages` in the catalogue counts all claims, the past witness only `passed_both` | 5 | advisory | **For the owner** (equal today: all 76 claims pass both) |
| S10 | No render test of the labels | — | advisory | Covered by `e2e/seance.spec.ts` (seats, labels, locator, count, hazard, 0 witnesses, 503, demo without requests, cross-link) |

## For the experts (summary)
L4, L5, L6, L9 (TR, `Evidence.status`), L15, L17, the native-speaker list above, S1 (title policy and data scan), S2, S6,
S7, S9. Listed under "Expert review (Phase 4)" → "Wording" in `docs/pre-launch-checklist.md`.
