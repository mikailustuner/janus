# Statistician review pass — Time Machine

> **AI review pass**, not a human review. Performed by the `statistician` agent profile
> (`.kiro/agents/statistician.md`) on 2026-11-09 against the built artifact and the
> `faers_onset` run 20261108T235604Z. Verdicts: **accept**, **correct**, **reject**.

## Scope reviewed
The time-to-onset extraction and its data quality, the Weibull fit and its interval, the risk
window, the agreement rule, the Monte Carlo bands, the small-sample policy, and every number
that reaches a user.

## Verdicts

### 1. Data quality is reported honestly — accept
8.9 % of (report, drug) pairs yield a usable interval (456,948 of 5,114,466) and 42.7 % of
reports carry a complete event date; both shares travel with every result in `faers_quality`.
Exclusions are counted by reason and the counts reconcile exactly to the input
(`output + Σ excluded = input`, property P18). Counts are called reports throughout. Accept.

### 2. Selection bias in the usable subset — **correct**
The 8.9 % is not a random sample. A report reaches the usable set only when a reporter supplied
both a complete therapy start date and a complete event date, which is associated with reporter
type (manufacturer reports are more complete) and with event seriousness. The artifact states
the share but does not warn that the subset is selected.
**Correction required:** add one sentence to the contract and to the research screen saying the
usable subset is not representative of all reports. Added to the checklist; the field already
exists to carry it.

### 3. The Weibull shape interval — accept
Profile likelihood for the shape with the scale in closed form, computed through log-sum-exp, and
a likelihood-ratio interval at χ²₁ = 3.841 is a correct and standard construction, and it is the
right choice over a Wald interval at these sample sizes. The property test recovers shape and
scale on 3,000 synthetic draws within five asymptotic standard errors, and the interval always
contains the estimate. The shape rule is correctly attributed (Hatahira 2017, Hasegawa 2020) and
the method paper is cited (Cornelius 2012). Accept.

### 4. Fitting a Weibull to 17–35 observations — **correct**
All four cascades with data return a shape near 0.4–0.5 with intervals excluding 1, i.e. a
strongly decreasing hazard. That is plausible for spontaneous reports, but it is also exactly
what heaping at short intervals produces, and at n = 17 the fit is being asked to do a lot.
Cornelius 2012 itself notes the method has low power in some regimes.
**Correction:** the `small_sample` flag is present and set correctly (exactly below 30: 19, 29
and 17 flagged; 35 not flagged, property P12), but a shape class should not be presented as a
finding for a flagged cascade. Recommend the research screen show the shape class greyed or
annotated when `small_sample` is true. Added to the checklist.

### 5. Zero-day onsets — **correct**
Same-day reports are a large share of several cascades: 10 of 29 for the antipsychotic cascade,
4 of 35 for amlodipine, 2 of 17 for the ACE inhibitor. A same-day interval often means the
reporter gave one date for both fields rather than a genuine same-day onset, and such heaping at
zero pulls the Weibull shape down — which is precisely the "early hazard" conclusion being
drawn. The half-day shift (DP-T11) makes the fit possible but does nothing about the heaping.
**Correction required:** report the zero-day count alongside each cascade so a reader can see how
much of the "early" signal is same-day reporting, and state that a same-day interval may be a
data artefact. Added to the checklist as a change to the contract.

### 6. The risk window — **reject as published originally; fixed during this pass**
With a shape of 0.50, the central-80 % band for the amlodipine cascade runs from 0.5 to 475
days while the median is 23 days. Publishing that as "the risk window", and worse putting it in
a patient sentence, would be true and useless.
**Fixed (DP-T14):** the patient sentence now uses the interquartile range (7–104 days for
amlodipine) and the 80 % band stays in the research area with its coverage stated. Accept as
fixed. Note the IQR is still wide; the sentence's "most often" wording is defensible for a
middle half, and must not be strengthened.

### 7. The bootstrap interval for the median — accept
A 1,000-sample percentile bootstrap on 17–35 observations is appropriate and its result is
honest about the uncertainty: the amlodipine median is 23 days with an interval of 21–73 days.
Accept, and note that this interval, not the point median, is what any comparison should use.

### 8. The agreement rule — **correct**
IQR overlap for a published median-with-IQR and containment for a published window are
reasonable, but both are crude: with an IQR of 7–104 days, our amlodipine window overlaps almost
any published window, so `agrees` is close to unfalsifiable here. The verdict `agrees` is
therefore weak evidence of agreement, not confirmation.
**Correction required:** the research screen must present `agreement` with the two intervals
side by side rather than as a verdict alone, so the reader sees how wide ours is. Added to the
checklist. The honest reading of the amlodipine result is "not inconsistent with", not "agrees".

### 9. Monte Carlo bands — accept
2,000 draws with a fixed seed, log-normal CL, V and ka, uniform F and lag; bands are the 5th,
50th and 95th percentile and are reproducible (property P8). The parameter spreads are a
judgement, not published variances, and the table says so. Accept with that caveat recorded.

### 10. No incidence claim anywhere — accept
Nothing in the output converts report counts into rates, and no denominator is implied. The
output states FAERS is spontaneous reporting, not incidence and not deduplicated across cases.
No "people like you" phrasing. Accept.

## Summary
Accept 5, correct 4, reject 1 (fixed during the pass). The two changes that matter most: the
patient sentence no longer uses the 80 % band, and the zero-day heaping must be shown because it
drives the "early hazard" conclusion. Every onset result in this build rests on 17–35 reports and
must be read as a small, selected sample.
