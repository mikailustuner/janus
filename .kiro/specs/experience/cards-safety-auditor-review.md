# Review: card design (safety-auditor, Req 29)

**Pass:** `safety-auditor` (`.kiro/agents/safety-auditor.md`), one read-only agent pass over the card redesign commits
(`70ea6bf..HEAD`, `apps/web/src`, `apps/web/messages`), Req 29 and DP50–DP56, against `medical-safety.md`, `privacy.md`,
`product.md` and the steering design rules (2026-11-09).

## Findings: 1 blocking, 6 advisory

| # | Where | Rule | Severity | Finding | Applied |
|---|---|---|---|---|---|
| F1 | `components/memory/PairPanel.tsx` | Rule 3 (no false reassurance), Req 29.4 | **blocking** | `p.reports ?? 0` drew a large "0 reports in FAERS" tile; `absence_is_not_reassurance` sits in the fold | Tile only when reports > 0; otherwise the sentence ("No reports") in bold, as the combination panel already did |
| F2 | `components/evidence/EvidenceView.tsx` | Rule 3, Req 15.2 | advisory | "No retracted source was used." led the integrity line before its scope ("N sources, M checked by DOI") | Original order restored: sources, statuses, range, stale, then the retracted sentence |
| F3 | `passport/screens/PassportItemView.tsx` | Product rule (listing ≠ availability) | advisory | "Listed in n of m countries" at the top, `Passport.presentNote` at the bottom of the aside (under the rows on a phone) | The note now sits directly under the summary; the aside keeps only the source notices |
| F4 | `components/light/Validation.tsx` | Rule 6 (honest statistics) | advisory | The validation tile dropped the chance baseline | Tile removed (and its `Cards.label.casesTop` key); the sentence with the baseline stays |
| F5 | `components/memory/MemoryPage.tsx`, `Cards.label.reports` | Rule 6, DP53 | advisory | "reports in FAERS" under the combination count lost "name all of them" | New label `Cards.label.reportsAll` ("reports name all of them", five languages, same wording as `MemoryView.combinationReports`) |
| F6 | `components/results/Results.tsx` | Rule 3 (scope) | advisory | "n medicines checked" counts boxes that "cannot be checked" too | Not changed: same count as the reviewed `Findings.checkedOf` before; the per-item "Cannot be checked" lines stay in "Medicines checked". Left for the owner |
| F7 | `tr.json` `Cards.label.witnesses` | Translation parity | advisory | Tile reads "2 / 3 tanıktan", order reversed from `Seance.count` | Kept: meaning holds; native check listed in `docs/pre-launch-checklist.md` |

## Checked and clean (auditor)
Disclaimer and demo label (shell unchanged); emergency notice first on results, finding detail and Collective Memory
whatever the filter; abrupt-stop line once per warned item on results; "This may be worth discussing with your doctor"
on every finding (also P34); integrity sentences visible; caveats `spontaneous_reporting`, `not_incidence`,
`weak`/`weak_pattern` and the deduplication limit outside every fold (`VISIBLE_CAVEATS` unchanged); attribution and
stale lines in both passport views; rule-7 labels on every research screen; no assessment in tiles, rows or segments;
no new `--risk` use; CI bar keeps axis, mark at 1, range, point and caption; the memory filter defaults to all, the
chosen event's safety line moves with its picker and panels, layers are never combined; séance count stays "n of 3
witnesses" with "not a score" visible; no new request, log, storage or query string; the passport id stays in the
fragment; no forbidden or reassurance phrase in the new texts in five languages.

## Not checked by the auditor (checked by the author)
Tests and axe were run after the fixes: vitest (P31–P35 included) and Playwright smoke, routes (en, tr), demo-flow,
passport, light, séance and states; the 375 px and 1440 px screenshots of both themes were reviewed.

## Verdict
Approved after F1 (blocking) and F2–F5 were applied. F6 and F7 are left for the owner and the native review.
