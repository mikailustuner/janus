# Time machine screens and owner-decision texts: safety-auditor review

**Date:** 2026-11-09
**Reviewer:** safety-auditor (`.kiro/agents/safety-auditor.md`), run as a separate read-only agent pass against
`medical-safety.md`, `privacy.md` and `product.md`. The reviewer edited no files and ran nothing.

## Scope
Experience Req 30 (time machine screens, `src/components/timemachine/*`, `src/timemachine/view.ts`, the patient
sentence in `FindingDetail`, links from the séance and the cascade map), the `TimeMachine` namespace in five languages,
the recorded fixture, screenshots; owner decisions of 2026-11-09 (fully / partly checked keys, note sentence
`medicines.count`, 3500B E10/E11 texts).

## Findings (0 blocking, 7 advisory)
| # | Finding | Action |
|---|---|---|
| S1 | The interval table of the reported-vs-published chart was headed P5 / P50 / P95 although the rows are a quartile range and a published window | Fixed: `IntervalChart` takes `columns`; the comparison uses `TimeMachine.compare.cols.*` (Low / Median / High) |
| S2 | Steady-state bands, ratios and days to steady state of drugs whose httk model failed validation were shown without a verdict next to them | Fixed: each drug line starts with its validation verdict (`population.credibility`); the days to steady state are shown only for a credible model (with pharmacologist B3); the title says the absolute values are not validated |
| S3 | The gate text said "does not agree" for every non-small onset that fails the gate | Fixed: `gate.notComparable` for `not_comparable` / no agreement; `gate.agreement` only for `disagrees` |
| S4 | For small samples the fitted curve and the "from the fitted curve" window still showed the early shape as a picture | Fixed: no onset curve and no fitted-basis window for a small sample |
| S5 | The published window (day 1–120) reads as one figure; the hidden English note said it is combined from two studies | Fixed: `published.combined` when the window cites more than one study |
| S6 | "Most often reported between" overstates the middle half | Fixed with pharmacologist B1: "half of the reports of “{event}” fell between {start} and {end} days after {drug} was started; the other half were earlier or later" (five languages; time-machine design §10.5 amended, DP65) |
| S7 | "8 fully checked · no pattern" on the share image could read as a safety check; suggested "fully checked against the rule list" | Left to the owner: the wording is the owner's decision of 2026-11-09; the image keeps the no-pattern caveat and the "checked against n of 65 patterns" clause. Pre-launch item |
| S8 | Screenshots predated the legend fix; axis ticks wrapped | Fixed (`compare.legend`, ticks `whitespace-nowrap`); screenshots retaken |

## What holds
Patient gate (exactly one cascade, not small, agrees; only amlodipine, 7–104 days); "reports" throughout; zero-day and
subset caveats; agreement never a bare verdict; every validation verdict shown, failures included; reasons in place of
verdicts; historical and modelled amounts labelled "not a dose"; no PBPK next to a compartmental model; labels on every
screen; E10/E11 split and the unknown-type sentence; no forbidden phrase in any of the five languages.
