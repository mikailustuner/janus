# Light face: statistician review of the inverse rule, ranking and validation

**Statistician pass (agent), 2026-11-08 — AI-reviewed, pending expert review**

Scope: DP5, DP6, DP9, DP10, DP17, DP20, design §5.3, §6, §8 and the generated report (`docs/light-face-validation.md`,
build `ca2bb569c5216716`). This pass does not cover clinical content: the goals, the effect → goal mapping and the case
list belong to the pharmacologist pass.
Every number below was recomputed from `.data/light/current/light.json`, with the build inputs rebuilt in memory and
read-only by the build's own readers (`read_onsides`, `read_openfda`, `read_faers`). The scratch scripts are outside the
repository. All counts are FAERS **reports**, not people. FAERS is spontaneous reporting: it does not measure incidence
and reports are not deduplicated.

## Summary verdict

**CHANGE.** The inverse rule and the tied-rank reporting are sound with small fixes. Three findings change the result
or how it reads:

1. **The topiramate primary hit comes from the filtering.** In the primary run the case drug loses its US labels that
   openFDA does not have. Every other drug keeps them. For topiramate those 93 labels list the effect at a lower rate
   (81/93) than the labels that stay (109/109). If they are kept, topiramate ranks **21 of 253 (miss)**, not 3.
   Minoxidil (1) and sildenafil (6) do not move. Status stays `prototype`, but the primary run has **2 informative
   hits, not 3**.
2. **The primary run and the researcher's list use different rankings.** With US labels only, every label candidate
   has exactly one region, so the regions key does nothing. The primary run is in effect ranked by the Wilson bound,
   while the list researchers see is ranked by region count. That is why topiramate is 3 in the primary run and 35 in
   the sensitivity run.
3. **The inverse layer has no support from the validation, yet it decides the top of several lists.** None of the 8
   evaluable cases has an inverse signal. Labels and inverse signals agree only slightly more often than chance
   (constipation 50 drugs with both vs 30.6 expected if independent; insomnia 11 vs 23.8, fewer than chance). Even so,
   "signal types" comes first in the key and puts these drugs at the top (constipation: 9 of the top 10 have a
   Wilson bound < 0.25).

The `denominator_sensitive` flag is also never true for an inverse signal, so it tells the reader nothing (Q1).

## 1. Inverse-signal rule (DP6)

| Goal | Pairs tested (a ≥ 3) | Inverse | % | Expected under the null (2.5 %) | Kept by BH q = 0.05 | Upper ≥ 1 with N = all |
|---|---|---|---|---|---|---|
| alopecia | 828 | 112 | 14 % | 20.7 | 85 | 4 |
| constipation | 1066 | 114 | 11 % | 26.7 | 88 | 9 |
| diarrhoea | 1307 | 154 | 12 % | 32.7 | 112 | 4 |
| erectile_dysfunction | 307 | 46 | 15 % | 7.7 | 24 | 9 |
| hyperhidrosis | 797 | 66 | 8 % | 19.9 | 35 | 8 |
| hypertension | 1206 | 87 | 7 % | 30.2 | 56 | 10 |
| insomnia | 1030 | 97 | 9 % | 25.8 | 71 | 8 |
| low_mood | 899 | 67 | 7 % | 22.5 | 50 | 5 |
| multiple_myeloma | 305 | 45 | 15 % | 7.6 | 10 | 7 |
| nausea | 1366 | 166 | 12 % | 34.1 | 127 | 6 |
| obesity | 477 | 6 | 1 % | 11.9 | 2 | 1 |
| parkinsons_disease | 330 | 20 | 6 % | 8.2 | 8 | 1 |
| pulmonary_arterial_hypertension | 301 | 4 | 1 % | 7.5 | 2 | 1 |
| swelling | 1006 | 36 | 4 % | 25.2 | 14 | 6 |
| **total** | **11,318** | **1,020** | **9.0 %** | **283** | **684** | **79** |

The per-goal inverse counts match `coverage.inverse_by_goal` exactly. The other goals have no inverse signal:
eyelash (89 tested), premature ejaculation (4 tested) and ENL (0 tested, 5 event reports).

- **Is a ≥ 3 enough? ACCEPT, plus a display change.** An upper-bound rule already requires a large expected count. With
  a = 3, the Woolf SE is about √(1/3) = 0.58, so upper < 1 needs ROR < 0.32, which means E ≳ 9.4. The smallest E among
  the 1,020 inverse signals is 9.4, and the median per goal is 13.7–71.5. A separate minimum on E (E = ingredient
  reports × event reports / N mapped) would only bite above about 10. E ≥ 20 would drop 212 signals (1,020 → 808) for
  no principled gain. **CHANGE:** show E and O/E = a/E on every inverse card, so a reader sees "24 reports where about
  87 were expected" (tirzepatide → obesity).
- **Power and plausibility.** Only heavily reported drugs can meet the rule. The median ingredient report count of
  inverse drugs is 1.7k–59k per goal, against a median of 142 over all 2,218 keys. The inverse lists are therefore
  dominated by the most-reported products (dupilumab, tirzepatide, lenalidomide…). The counts are plausible for FAERS
  and not evidence of protection. The null of ROR = 1 clearly does not hold: 6,527 of the 11,318 tested pairs (58 %)
  have a lower bound > 1. Heterogeneity and reporting bias, not chance, explain most of the table. The design's
  Uesawa/Pariente warnings are the right framing.
- **The sensitivity table: CHANGE (bug in meaning).** `Sensitivity.differs` compares the five-class assessment. For an
  inverse pair that class is `not_disproportionate` in both tables, so `differs` is false for **all 1,020** signals.
  Yet **79 (7.7 %)** of them have an upper bound ≥ 1 when N = all reports. For inverse signals,
  `denominator_sensitive` must mean `sensitivity.ror_ci.high ≥ 1`. Keep listing these signals, as collective-memory
  does, but flag them.
- **Multiple comparisons: CHANGE (reporting), QUESTION (gate).** Under the null, 283 of the 1,020 would be expected by
  chance alone. Benjamini–Hochberg (q = 0.05, one-sided, per goal) keeps 684; Bonferroni keeps 356. An FDR gate only
  controls random error, while the dominant error here is systematic, so I do not require one. Publish, per goal, the
  pairs tested, the inverse count and the null-expected count (0.025 × tested). The gate is a question for the expert.
- **a = 0 is excluded by design.** 62 pairs have a = 0 with E ≥ 10, which are the strongest cases of "missing" reports.
  This is consistent with collective-memory (no estimate when a = 0). Name it as a limit.
- **Union of the goal's PTs, scope `any`, N mapped: ACCEPT.** Counting at report level avoids double counting.

## 2. Ranking key (DP5)

Problems with the current key, in general and not only for the cases:

- **The regions count measures data coverage.** Single-ingredient labels per region: US 30,423, UK 2,573, JP 1,697,
  EU 630. Only 40 of 1,230 keys have labels in all four regions. A drug sold only in the US can never pass a
  four-region drug, whatever its share. Putting regions before the Wilson bound mostly rewards wide marketing and
  OnSIDES coverage, not agreement between regulators.
- **Signal types first.** The inverse layer is noisy (see Q1), and its agreement with labels is close to chance:
  diarrhoea 60 both vs 40.0 expected, hypertension 31 vs 19.8, obesity 2 vs 1.7, insomnia 11 vs 23.8. Putting types
  first lets one inverse signal lift a weak label above a strong one. Obesity is the example: tirzepatide (1/1 label,
  EU, Wilson 0.21) and levodopa (1/3, Wilson 0.06) rank 1–2, ahead of levetiracetam (211/212, Wilson 0.97).
- **Robustness.** I perturbed the label set by removing the case drug's non-US labels and filtering its US labels as
  in the primary run. Under the current key the ranks moved from 1/4/35 to **8/16/128** (minoxidil, sildenafil,
  topiramate). Under the Wilson-first key they moved to **1/5/2**.
- **Generic copies.** The Wilson bound gets narrower as labels are added, so drugs with many near-identical generics
  (US) get a higher lower bound. That is a known weakness. It is acceptable as an ordering device, as the design says,
  but it is not inference (QUESTION 2).

**Recommended key (K1), CHANGE:** has a label signal ↓, Wilson lower bound ↓, regions ↓, labels with the effect ↓,
inverse signal present ↓, FAERS a ↓. Inverse-only candidates stay below all label candidates, which already happens
under the current key. The ratio still never enters the key.

Ranks of the case drugs (worst rank / population). I reproduced the current key exactly:

| Case | Run | Current K0 | **K1 Wilson-first** | K2 regions ÷ regions with labels | K3 types dropped, regions first |
|---|---|---|---|---|---|
| minoxidil → alopecia | primary | 1/127 | 1/127 | 1/127 | 1/127 |
| | sensitivity | 1/146 | 1/146 | 1/146 | 1/146 |
| sildenafil → ED | primary | 6/68 | 6/68 | 6/68 | 6/68 |
| | sensitivity | 4/84 | **6/84** (worse) | 6/84 | 4/84 |
| topiramate → obesity | primary | 3/253 | 3/253 | 3/253 | 3/253 |
| | sensitivity | 35/400 | **9/400** | 10/400 | 33/400 |
| bimatoprost → eyelash | primary | 3/3 | 3/3 | 3/3 | 3/3 |
| | sensitivity | 4/4 | 3/4 | 3/4 | 4/4 |
| liraglutide → obesity | primary | not evaluable | not evaluable | not evaluable | not evaluable |
| | sensitivity | 295–311/400 | 284–300/400 | 193–196/400 | 294–310/400 |

The keys give the same primary ranks because with US labels only, regions is constant. Under K1, top-10 overlap with
the current key is 0/10 for constipation, diarrhoea, hypertension and insomnia, and 3/10 for obesity. Under K1 no
top-10 entry has a Wilson bound < 0.25 in any goal that has labels.

**K1 is recommended for general reasons, not for the cases:**
- it does not depend on uneven regional coverage;
- the primary and sensitivity runs then rank on the same principle;
- it does not promote the unvalidated inverse layer;
- it is stable when the label set is perturbed.

The case results are mixed: sildenafil gets worse (4 → 6) and topiramate gets better (35 → 9). The key was chosen
after the case ranks were known. Record this as a post-hoc change in design §14 and keep it in the "not blind"
caveat. Do not count the topiramate sensitivity hit under K1 as confirmation.

## 3. Tied ranks, hit, informativeness, status (DP17, DP20)

- **Competition range, hit = worst rank ≤ 10, top-10: ACCEPT.** The cut-off was declared before the build, and worst
  rank is the conservative choice under ties.
- **Informative iff population > 10: CHANGE to publishing the chance baseline.** A population of 11 gives a 0.91
  chance of a hit for a random candidate, so "> 10" is too weak. For each case and run, publish
  P(hit by chance) = (candidates whose worst rank ≤ 10) / population, and the percentile worst / population.

| Case | Primary: rank / pop, P(chance), percentile | Sensitivity: rank / pop, P(chance), percentile |
|---|---|---|
| minoxidil | 1/127, 0.079, 0.8 % | 1/146, 0.068, 0.7 % |
| sildenafil ED | 6/68, 0.147, 8.8 % | 4/84, 0.119, 4.8 % |
| topiramate | 3/253, 0.040, 1.2 % (21/253 if not-in-openFDA labels kept, Q4) | 35/400, 0.022, 8.7 % |
| bimatoprost | 3/3, 1.000 | 4/4, 1.000 |
| liraglutide | not evaluable | 295–311/400, 0.022, 77.8 % |

- **Expected hits by chance.** Across the primary run's informative cases, a random candidate in place of each case
  drug would give 0.079 + 0.147 + 0.040 = **0.27** hits; 3 were observed (2 after Q4). **Do not publish a p-value.**
  The mapping was curated knowing the cases (DP10), and the cases were chosen because they are famous side-effect
  discoveries. A p-value would claim more than the design supports.
- **Status iff no informative primary hit: ACCEPT.** The rule leaves the status at `prototype` in every variant above,
  because minoxidil hits in all of them. My preferred stricter rule is in QUESTION 3.

**Suggested wording per case:** "Rank 1 of 127 candidates. If this medicine had been picked at random from the
candidates, it would land in the top 10 with probability 0.08."

## 4. Validation design (DP9, DP10)

- **Removing labels openFDA does not have: CHANGE.** The openFDA artifact holds only the case drugs' labels, so the
  filter can only ever touch the case drug. Effect rates in the labels it removes are lower than in the labels it keeps:

  | Case drug | Kept US labels with the effect | Removed (not in openFDA) | Removed (names the later use) |
  |---|---|---|---|
  | topiramate | 109/109 | 81/93 | 0 |
  | minoxidil | 22/22 | 4/6 | 0 |
  | sildenafil | 63/63 | 62/63 | 69/69 |

  The filter raises the case drug's share and therefore its Wilson bound, which biases the result in its favour.
  Change: run the primary twice for the case drug, (a) dropping only labels whose indications text names the later use
  and (b) also dropping the labels openFDA lacks. Publish the **worse** rank, and count a hit only if both variants are
  hits. Results: minoxidil 1/127 in both, sildenafil 6/68 in both, topiramate **21/253** (a) vs 3/253 (b), so it is a
  miss. The intent of P11 ("removing a case drug's labels never improves its rank") is violated here. Add a test that
  the published primary rank is never better than variant (a).
- **Removing only the case drug's labels: ACCEPT.** Competitors keep labels for the goal (for example vardenafil and
  tadalafil for ED, approved after sildenafil), which can only push the case drug down. That bias is conservative.
- **US-only primary: ACCEPT as a comparison set, with a caveat.** It is a consistent set of competitors, but under the
  current key it ranks differently from the list researchers see (§2). Under K1 the two agree. Publish the primary
  population next to the population researchers see (127 vs 146, 68 vs 84, 253 vs 400).
- **Leakage over time is not removed.** The labels that stay are today's texts of original-use products. Their
  side-effect sections may have been written or expanded after the later use became known. The primary run removes
  labels that name the later use; it does not rebuild the labels as they were before it. Say so.
- **"Not blind" is stated but not complete.** Also state:
  - that the cases are known successes only, with no negative controls, so the check cannot estimate false positives
    or precision;
  - that n = 9, of which 3 are informative and evaluable in the primary run;
  - that 4 cases cannot be reached by construction (amantadine, sildenafil → PAH, thalidomide × 2);
  - that the ranking key was revised after seeing case ranks, if K1 is adopted.
- **The FAERS window includes the later use.** This did not affect any case drug's rank, since no case drug has an
  inverse signal. It can only help competitors (obesity: tirzepatide and levodopa with two signal types).

## 5. Report wording (val.md)

These lines overstate the result or need a caveat:
- **Headline count.** "Primary: 4 hits (3 informative)" counts bimatoprost (3 of 3 candidates) as a hit. Lead with
  informative hits only, and list uninformative results and cases unreachable by construction separately.
- **Status sentence.** "Some known repurposings were found again" should give the numbers: "2 of the 9 cases (after
  the label-filter check) were in the top 10 of the primary run; about 0.3 would be expected if each case medicine
  were a random candidate. The mapping was written knowing these cases, so this is not evidence that the method finds
  new candidates."
- **FAERS table.** Each case shows ROR 2.2–77 with "Reported less often than expected: no", with no comment. Add:
  "The inverse-signal layer found none of the 8 evaluable cases. Where a ratio exists, the condition is reported
  more often than expected with the case medicine. This is consistent with indication and notoriety bias, not with
  harm."
- **Method.** Add a sentence: "In the primary run every candidate has US labels only, so the regions key does not
  separate them" (or remove this point by adopting K1).
- **Limits to add:** today's label texts, not historical ones; no negative controls; n = 9; inverse signals restricted
  to heavily reported medicines; the null-expected count of inverse signals per goal.

## Requested changes

| # | Where | Change | Effect |
|---|---|---|---|
| C1 | `inverse.py` / card | For inverse signals `denominator_sensitive := sensitivity.ror_ci.high ≥ 1` (not the five-class compare) | 79 of 1,020 flagged (now 0) |
| C2 | card, coverage, report | Show E and O/E on each inverse card; per goal publish pairs tested, inverse count, null-expected 0.025 × tested | Context for 1,020 signals vs 283 expected under the null |
| C3 | `ranking.py`, DP5 | Key K1: has label ↓, Wilson low ↓, regions ↓, labels ↓, inverse present ↓, FAERS a ↓; record as post-hoc in §14 | Primary ranks unchanged; sensitivity ranks per table in §2 |
| C4 | `validation.py`, DP9, P11 | Primary = worse of (a) indication-only removal and (b) + not-in-openFDA removal; hit only if both; property test | Topiramate primary 3 → 21 (miss); informative primary hits 3 → 2; status stays `prototype` |
| C5 | report, `/light/validation` | Per case/run: P(hit by chance), percentile, primary vs visible population; total expected hits by chance; no p-value | Minoxidil 0.079, sildenafil 0.147, topiramate 0.040 |
| C6 | report summary | Headline = informative hits; uninformative hits and unreachable-by-construction cases listed separately | Removes the bimatoprost inflation |
| C7 | report FAERS section | Sentence on the case RORs > 1 and zero inverse support (text in §5) | Prevents reading as harm or as support |
| C8 | report limits, DP10 | Add today's label texts, known-success cases without negative controls, n = 9, post-hoc key change, a = 0 pairs excluded (62 with E ≥ 10) | Honest scope |

## Questions for the human statistician

1. Should the inverse layer be gated by a per-goal FDR (BH keeps 684 of 1,020), or is FDR the wrong tool when
   systematic reporting bias dominates (58 % of tested pairs have a lower bound > 1)?
2. Generic copies: should the Wilson bound use an effective n, for example labels deduplicated by (region, mapped-term
   set), or a per-region average share, instead of raw label counts?
3. Informativeness: replace "population > 10" with "P(hit by chance) ≤ 0.10"? Then sildenafil ED in the primary run
   (0.147) would be weakly informative, and minoxidil would be the only informative primary hit. Status is unchanged.
4. Should pairs with a = 0 and large E be evaluated with an exact Poisson upper bound for O/E, outside the
   collective-memory "no estimate when a = 0" rule?
5. Negative controls: what is the minimum set of drug–goal pairs with no known repurposing needed to estimate a
   false-positive rate for the top 10?
6. Given 0 of 8 evaluable cases with inverse support, should the inverse layer stay in the ranking at all (K1 keeps it
   only as a tie-break), or be shown only on cards?

Not reviewed here: the goals, the effect → goal mapping, the case list and the years (pharmacologist pass).
