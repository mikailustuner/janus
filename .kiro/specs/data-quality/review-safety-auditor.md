# Safety-auditor review (agent `.kiro/agents/safety-auditor.md`, read-only), 2026-11-09

AI review of the code and a generated report.

Checked clean: all 23,137 rows of the local TİTCK artifact against report.json, findings.csv and summary.md — 0
barcodes, 0 product names; the 74 ingredient strings that appear are English Wikidata labels (CC0), none outside a
label. Prints and logs carry counts only; routes are medical. No forbidden phrase.

| # | Finding | Severity | Resolution |
|---|---|---|---|
| A1 | BDPM and CIMA attribution without update dates; BDPM "no endorsement" and Licence Ouverte not named | blocking for publish | `report.attribution(sources)` builds the text with each source's date; datapackage `sources` carry the dates |
| A2 | Generated report older than the code (empty `compared_codes` on exclusion rows) | blocking | Rebuilt; exclusion findings carry the item codes |
| A3 | "benign" reads as harmless; "confirmed" was owner + AI, not a pharmacist | advisory | Class names kept (owner's terms); `class_meaning` text in JSON and in the summary header states both limits |
| A4 | Standard disclaimer line missing | advisory | `disclaimer` in JSON, summary and datapackage (both datasets) |
| A5 | WHOCC not credited | advisory | Credit in the attribution and datapackage sources |
| A6 | `how_to_find` for a future CIMA substance-code finding would be wrong | advisory | Chosen by check and source |
| A7 | A resolved confirmed error would be listed as current | advisory | Section limited to current ones; an Upstream column added |
| minor | Registry entry lacks inputs; "not altered" wording for BDPM | minor | Inputs note added; "used unaltered as input (this report is a derived comparison)" |

After the fixes the published files were checked again: 0 TİTCK barcodes, 0 product names.
