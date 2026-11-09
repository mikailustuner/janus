# Negative and null results

**Status:** research log of the Janus project (open-source research prototype, not a medical device), November 2026.
**Expert review has not yet been done.** Nothing here is guidance for any person.

Janus tested several new ideas for finding or explaining prescribing cascades in open data. Each test was
pre-registered before results were computed (hypothesis, data, metrics, decision rule), compared against standard
methods on the same data, and checked for leakage and confounding. Most hypotheses were **not supported**. We publish
them so that others do not repeat the same paths, and because a null result on open data is itself information.

Common data: FDA Adverse Event Reporting System (FAERS) quarterly files 2025Q4–2026Q3 (~1.28 million reports mapped to
ingredients; CC0); the PIPC list of potentially inappropriate prescribing cascades (Rochon et al., *Eur Geriatr Med*
2025, doi:10.1007/s41999-025-01215-x; CC BY 4.0); OnSIDES v3.1.1 (CC BY 4.0); openFDA drug labels (CC0). Confidence
intervals are bootstrap intervals (≥1,000 resamples) unless stated. FAERS counts are reports, not people, and are not
incidence.

## Summary

| # | Idea | Result | Key numbers |
|---|---|---|---|
| 1 | "Triad signature": a cascade A→E→B leaves a three-way pattern in spontaneous reports | Not supported | AUROC 0.681 vs ROR 0.686, IC 0.698, EBGM 0.697; a simple sum of two pairwise IC signals reached 0.838 |
| 2 | PK timing: true adverse effects show onset times consistent with the drug's half-life | Not supported | AUROC 0.517; shuffled half-lives as good (p = 0.62); adding it hurt held-out performance |
| 3 | Label divergence between regions drives cascades | Not supported | OnSIDES cannot measure regional label differences (25 of 30 checked "differences" were extraction misses); known cascades were *less* divergent than other signals |
| 4 | Cascade discovery from label knowledge (v1) and combined with FAERS reported indications (v2) | Partly supported | Combined ranking beat pairwise FAERS disproportionality (AP gain significant even without leaky synonyms); new top candidates were mostly appropriate management of a side effect, not cascades |
| 5 | Separating inappropriate cascades from appropriate management of an expected side effect | Not supported | Separation AUROC 0.579 (needed lower bound > 0.6) |
| 6 | Older-adult exposure explains which cascades appear in older patients | Not supported | ρ = 0.09 (95% CI −0.24 to 0.39), p = 0.55 |

## 1. Triad signature in spontaneous reports

- **Hypothesis.** Among reports with drug A as suspect and event E, drug B (a treatment for E) appears as a concomitant
  drug more often than expected, with a weaker reverse pattern; a triad score ranks known cascades above other triads
  better than pairwise disproportionality.
- **Design.** 63 PIPC cascades against 41,674 non-cascade triads. Comparators: ROR, PRR, IC/BCPNN, EBGM (openEBGM
  0.11.0), a co-reporting count and the Ω interaction measure.
- **Result.** Triad score AUROC 0.681 (0.595–0.760), no better than ROR, IC or EBGM. IC(A,E) + IC(B,E) reached 0.838
  (0.783–0.887). The role-asymmetry component pointed the wrong way (0.451): reporters often mark the treating drug as
  suspect. The enrichment component was real (0.651, survived shuffling) but added +0.008 in a held-out test.
- **Lesson.** In FAERS, the treating drug's own association with the event carries most of the signal.

## 2. Pharmacokinetic timing consistency

- **Hypothesis.** A dose-dependent adverse effect should start at times consistent with the drug's pharmacokinetics
  (time to steady state ≈ 4–5 half-lives); a PK-consistency feature separates labelled adverse effects from
  unlabelled disproportionate pairs.
- **Design.** 5,990 disproportionate drug–event pairs (1,646 labelled in OnSIDES), measured half-lives (Obach 2008).
- **Result.** AUROC 0.517 (0.492–0.542); shuffled half-lives did as well; held-out ΔAUROC −0.009. Correlation of
  half-life with median onset 0.04.
- **Side findings.** 16.2% of FAERS event dates fall on the 1st of a month (3.3% expected), so many "complete" dates
  are filled in. httk half-lives agreed poorly with measured values (r = 0.25, median 3-fold error).

## 3. Regional label divergence

- **Hypothesis.** When a side effect is in drug A's label in some regions but not others, prescribers where it is
  missing start cascades more often.
- **Result.** OnSIDES recovered about 40% of EU and 20% of UK label effects in its own annotations; in a hand-checked
  sample, 25 of 30 "omissions" were extraction misses. One pre-registered test was nominally positive (OR 1.76) but did
  not survive a dilution-resistant test (p = 0.13). Known cascades were less divergent (61% vs 76%, p = 0.0002).
- **Lesson.** An effect missing from an extracted label dataset must never be shown as "not in the label".

## 4. Cascade discovery from labels and reported indications

- **v1.** Candidates A→E→B where E is a labelled adverse effect of A and B is indicated for E. On ~280,000 open-world
  triads, label + FAERS ranking beat FAERS alone (AUROC 0.871 vs 0.841; recall in the top 10,000: 47% vs 24%). Label
  information alone ranked known cascades worse than random in the top 1,000.
- **v2.** Added FAERS reported indications (the share of drug B's uses that are for E), exact term matching, an
  own-indication filter and a small synonym table. Against pairwise FAERS disproportionality on a held-out half, AP
  improved significantly and stayed significant after removing synonym rows that touched held-out rules
  (+0.014, 95% CI +0.001 to +0.039); recall in the top 10,000 did not differ significantly. Against v1, the gain
  disappeared without the leaky synonym rows. FAERS reported indications let the method generate 33 of 35 held-out
  rules (v1: 19).
- **Key limitation.** The top new candidates were mostly appropriate management of a known side effect (e.g.
  diuretic → hypokalaemia → potassium; heparin → heparin-induced thrombocytopenia → argatroban), not inappropriate
  cascades. Candidate plausibility was judged by two independent automated reviewers (new 4.0 vs decoys 2.2 on a
  1–5 scale); expert review has not yet been done.

## 5. Inappropriate cascade vs appropriate management

- **Hypothesis.** Open signals (label recommends B for E; E predictable for A's class; B specific for E; A continued
  when E occurs) separate inappropriate cascades from appropriate management.
- **Result.** AUROC 0.579 (0.450–0.696); none of the decision rules passed. "B is used mostly for E" is as high for
  symptomatic remedies as for antidotes; the FAERS "drug continued" field is rarely filled.
- **Lead for future testing (post hoc, not evidence).** Laboratory- or test-detected events were common among
  pairs judged appropriate management and absent among pairs judged cascades. A pre-registered test on independent
  sets is under way.

## 6. Older-adult exposure and the age profile of cascade reports

- **Hypothesis.** Drugs whose exposure rises more in older adults show cascade reports concentrated in older patients.
- **Result.** Across 48 drugs, ρ = 0.09 (−0.24 to 0.39), p = 0.55; the ≥75-year share was not significant after
  adjusting for the event's own age profile. Power to detect ρ = 0.3 was 0.53; 36% of FAERS reports lack age.
- **Related positive result.** The label-derived older-adult exposure atlas and the finding that HTTK-Pop's age ratios
  carry little drug-specific information are described in
  [httk-pop-older-adult-exposure.md](httk-pop-older-adult-exposure.md).

## What this means for Janus

- Janus keeps checking only published, expert-agreed cascade patterns (PIPC). None of the discovery methods above is
  reliable enough to create new rules.
- FAERS reported indications improve candidate coverage and may support a future research-only candidate list for
  expert review.
- Extracted label data are used only as positive evidence, with the source sentence quoted.

## Limitations

Small reference sets (~35–66 known cascades), spontaneous-report biases (duplicates, stimulated reporting, missing
dates and ages), no access to the MedDRA hierarchy, and automated rather than expert judgement of plausibility.
Detailed reports, scripts and pre-registrations are kept by the project and can be shared on request.
