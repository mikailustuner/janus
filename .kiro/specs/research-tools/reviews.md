# Reviews of the Phase 1 screens (2026-11-09)

Three read-only automated review passes, run separately on the code and the new messages. Expert review has
not yet been done.

## Safety auditor (`.kiro/agents/safety-auditor.md`)
Clean: forbidden phrases in five locales, FAERS framing on every onset screen, disclaimer, no TİTCK product name or
barcode (decoder keeps documented fields only; recorded file has no 13-digit number), external links
(`noopener noreferrer`, evidence hosts filtered), no logging, demo mode sends no request.

| # | Finding | Severity | Resolution |
|---|---|---|---|
| A1 | EN class label "Benign difference" reads as harmless (rule 3) and differs from the other locales | advisory | EN label and class meaning now "Explained difference" (API code `benign_difference` unchanged) |
| A2 | Table could show a median whose exact interval is null | advisory | `showsMedian` (both bounds required) used by table, detail and sort; property test |
| A3 | Weibull class defaulted to "random" when null | advisory | No default: the shape line is shown only with a published class |
| A4 | Row note `nonspecific_gi_terms` (rows 26, 27) truncated in the dataset | minor | Open item for the onset-table build (`data/onset_row_notes.csv` parsing); shown verbatim |
| A5 | Several dataset caveats only in English | minor | Every dataset caveat has a translated short form (test keeps the list equal to the dataset's keys) |
| A6 | "after drug A reporters" ambiguous | minor | Reworded |
| A7 | Demo fixture load failure left the page loading | minor | `useDemoClient` reports `failed`; screens show the error state |

## Statistician (`.kiro/agents/statistician.md`)
Clean: status gate, no number on withheld rows, median always with its exact interval, sort keeps rows without a
median last, "reports" wording, not causal / not incidence.

| # | Finding | Severity | Resolution |
|---|---|---|---|
| S1 | Rows 23, 47, 52: "0 d (0–0)" in the table with no heaping flag; median sort puts them at an extreme | blocking | Table flags "same-day heaping"; such medians sort with the rows without a median; hint explains it; e2e |
| S2 | Short caveats missed `event_date_report_level`, `shortest_interval`, `weibull`, `class_membership` | blocking | All 14 dataset caveats translated; list checked against the dataset keys |
| S3 | "event dates fall on the 1st" — the build counts start or event | advisory | "intervals rest on a date (start or event) on the 1st of a month" |
| S4 | Date-quality counts on withheld rows reveal the withheld statistic at small n | advisory | Every count with its denominator ("12 of 14"); "no timing is published for this row" line; largest group hidden below 2 |
| S5 | Usable share as a percent at tiny n | advisory | "x of N" shown with the percent |
| S6 | Earliest-start and distinct-date-pair medians not shown | advisory | Decoded and shown under "Other readings" |
| S7 | Day-01 sensitivity without its n | minor | n added |
| S8 | "Bar: the range"; IQR and CI drawn alike | advisory | Legend says the two bars measure different things (spread vs uncertainty of the median) |
| S9 | Chart title read as measured onset | minor | "Reported days from the therapy start date to the event date" |
| S10 | "No reports" can read as reassurance; `no_interval` legend incomplete | advisory | "No matching reports in the window"; legends add "this is not evidence of no effect" |
| S11 | "The same method as the time machine" inaccurate | advisory | "A method based on the time machine's, with stricter rules" |
| S12-13 | Shape class default; "constant" over-reads an interval containing 1 | minor | No default; "no clear trend" |
| S14 | Short caveat wording | minor | zero_day, day_one ("not a correction", 1 January), small_sample ("may understate"), selection ("long-standing use dated less often") |
| S15 | Zero-day count without denominator | minor | "n of N intervals" |
| — | Dataset: `cluster_dominated` rows still carry shares in the CSV/JSON | advisory (API) | Open item for the onset-table build |

## Localization reviewer (`.kiro/agents/localization-reviewer.md`)
Clean: placeholders, ICU plurals, Turkish characters, no forbidden phrase or reassurance word.

| # | Finding | Resolution |
|---|---|---|
| L1 | EN "Benign" vs "explained" elsewhere | = A1 |
| L2 | TR "reçeteleme kaskadı" vs existing "reçete kaskadı" | Fixed |
| L3-5 | Time to onset: TR "başlama süresi", DE "Zeit bis zum Auftreten", ES "tiempo hasta la aparición" (existing terms) | Fixed in titles, entries, developer texts |
| L6 | FR "déclarations" vs the file's main term "signalements" | Onset and developer texts now "signalements" / "notificateur" |
| L7-8 | ES/FR CDS sentence weaker than the fixed no-finding text | Now "libres de problemas" / "exempts de problèmes" |
| L9 | FR adjective agreement with "forme" | Fixed |
| L10-13 | DE "Daten" ambiguity, mixed gender forms, "zu beginnen" | Fixed ("Datumsangaben", "Für Entwicklung und Klinik", neutral reviewers) |
| L14-18 | TR wording ("güvenlik" dropped, "deterministik", "Eczacı incelemesi gerekli", "istikrarsız", "taslak istemleri"); ES "Requiere revisión farmacéutica" | Fixed |
| L19 | ES entry body grammar | Fixed |
| L20 | "by the furthest reason" unclear | EN "by the check that excluded them", retranslated |

Pending (pre-launch checklist): a native-speaker pharmacovigilance review of the onset texts.
