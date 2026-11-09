# Time machine screens: pharmacologist review

**Date:** 2026-11-09
**Reviewer:** pharmacologist (`.kiro/agents/pharmacologist.md`), a separate read-only agent pass. No files edited.

## Scope
`src/components/timemachine/*`, `src/timemachine/view.ts` (patient gate), `index.json`, the English `TimeMachine`
texts, the recorded fixture and screenshots, against time-machine design §6–§10.

## Findings (3 blocking, 7 advisory)
| # | Finding | Action |
|---|---|---|
| B1 | The patient sentence said "this combination was reported" but the FAERS interval is from starting the first drug to the event, not to the second drug; and half the reports lie outside the middle half | Fixed: the sentence names the event (vocabulary lay label) and the index drug, says "half of the reports … the other half were earlier or later" (DP65) |
| B2 | The comparison chart showed the 5th–95th percentile legend | Fixed: `compare.legend` and column heads |
| B3 | Days to 90 % steady state came from httk models that failed validation (haloperidol 20 days) | Fixed: shown only for a credible model (none today) |
| A4 | Absolute mg/L on a "relative only" chart | Partly: the title says the absolute values are not validated; normalising to the younger median left for the experts (checklist) |
| A5 | Impossible ADMET values (PPBR 112.6 %, negative half-life or volume) shown as numbers | Fixed: `admetUsable` shows "—" with "prediction outside the possible range" |
| A6 | Rhein time to peak ignores colonic activation; modelled amounts exceed the validated dose | Time to peak removed; the dose-range caveat goes to the checklist |
| A7 | The established interaction showed no citation | Fixed: "Evidence: {citation}" from the reference list |
| A8 | The AUC note was wrong for amlodipine | Fixed: AUC tests the cited clearance; only for rhein may clearance and AUC share subjects. AUC kind per row left for the experts |
| A9 | The amlodipine page names a compartmental method but shows no model output | Fixed: `methodNoOutput` |
| A10 | Smaller items: `gate.notComparable` (fixed); the hidden amlodipine note (published window now labelled "combined"); "for this drug" next to rhein (now "here"); metoclopramide row-18 extension badge (fixed, `TimeMachine.extension`); fold-error direction and the design §7.4 ratios (checklist) | As stated |

## What holds
Matching the gate on the finding's index ingredient (ingredient level after decomposition) is right; no marker check is
needed; `hits.length === 1`, small sample, `agrees` and the middle half are correct; single-drug titles are right;
screening results labelled; validation shown with every concentration.

## For a human expert
FAERS event onset compared with published diuretic-start windows (Largeau 2022 as a like-for-like comparator for
gabapentinoids); whether any httk output beyond the ratio should be shown; final wording of the patient sentence; how
the hyperforin PXR induction vs the CYP3A4 IC50 record is explained; rhein's colonic activation.
