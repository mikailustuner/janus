# Report Assistant review: localization-reviewer

**Date:** 2026-11-09
**Reviewer:** localization-reviewer (`.kiro/agents/localization-reviewer.md`), run as a separate read-only agent pass
over the `ReportAssistant` namespace and `Doctor.report` in `apps/web/messages/{en,tr,de,fr,es}.json`, with
`ReportAssistant.tsx`, `mapping.ts` and `data/report_channels.csv` for context. The reviewer edited no files.

## What holds

Key parity and every placeholder in all five files; no forbidden phrase, inflections included (TR "tanım dosyası"
is "definition file"; the TR translation of "…tanımlayın" uses "anlatın"); each language's word for a report (EN
report, TR bildirim, DE Meldung, FR signalement, ES notificación), matching the Memory and Findings namespaces;
formal address (siz, Sie, vous, usted); no pressure or advice; the statistics sentence is correct with its caveat in
all five; no German word breaks the 375 px layout. The official-label and outcome-option translations match the
native labels.

## Findings and what was done

| id | Severity | Key | Lang | Finding | Done |
|----|----------|-----|------|---------|------|
| L1 | advisory | `intro.fact` | DE | "Interquartilsabstand" is the difference Q3−Q1, not the interval. | **Fixed:** "Interquartilsbereich 82–98 %". |
| L2 | advisory | `intro.fact` | FR | "écart interquartile" is the difference. | **Fixed:** "intervalle interquartile 82–98 %". |
| L3 | advisory | `intro.fact` | EN | EN said the review estimated the rate; the others say it analysed studies that estimated it. | **Fixed:** "A 2006 systematic review analysed 37 studies that estimated…". |
| L4 | advisory | `intro.fact`, `labels.esSymptoms` | TR | "advers reaksiyon" is jargon; the namespace uses "yan etki". | **Fixed:** "ilaç yan etkilerinin (advers reaksiyonların)…", "Advers reaksiyonun (yan etkinin) belirtileri". |
| L5 | advisory | `intro.caveat` | TR, DE, FR, ES | Stronger than EN ("valid for no country"). | **Fixed:** softened to "not a figure for a given country today" in all four. |
| L6 | advisory | `labels.trDrugName` | all | "(full name as on the box)" is not in the CSV label. | **Kept:** it is the field's own hint in the TÜFAM form definition ("İlacın tam ismi (kutuda belirtildiği gibi)", research notes §1.5); the translation explains the native label. |
| L7 | advisory | `options.trDocx.0` | EN, DE, FR, ES | "recovered" attached to the side effect; DE ungrammatical. | **Fixed:** "The side effect has completely gone / the person has recovered" and equivalents ("geheilt" avoided: it contains "heilt"). |
| L8 | advisory | `options.trEform.1` | FR | Dropped "/düzeliyor". | **Fixed:** "En cours de rétablissement/de résolution". |
| L9 | advisory | `labels.frDescribe` | DE | "Wirkung" can read as the intended effect. | **Fixed:** "Art und Beschreibung des Effekts". |
| L10 | advisory | `contacts.title` | TR | Awkward grammar. | **Fixed:** "Diğer bildirim yolları". |
| L11 | advisory | `draft.empty` | DE | "das Geschehen" stiff. | **Fixed:** "Geben Sie das Arzneimittel ein oder was passiert ist, um den Entwurf zu sehen." |
| L12 | advisory | `what.outcome` | FR | "Et maintenant ?" vague. | **Fixed:** "Comment cela va-t-il maintenant ?". |
| L13 | advisory | Light, Seance | FR | Older namespaces use "déclaration(s)". | **Out of scope** (not this feature's text); left for a separate change. |

## Verdict

Pass with advisories, all applied except L6 (kept, reason above) and L13 (out of scope).

## Still needs a native clinical speaker

TR "advers reaksiyon" vs "yan etki" for patients; DE outcome terms ("Ausgang", "abgeklungen", "bleibende Folgen") and
"Interquartilsbereich"; FR "intervalle interquartile", "Évolution"/"Issue" as ANSM uses them; ES "Desenlace" against
AEMPS wording; whether the TÜFAM outcome options match the live form (read from its definition file).
