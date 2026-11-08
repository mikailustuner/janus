# Statistics review: Collective Memory

**Reviewer:** statistician agent. **Date:** 2026-11-08. **Scope:** Requirements 1–5, 9, 10.3 and the properties list of `requirements.md`.

**Read:** `collective-memory/requirements.md`; `data-pipelines` Requirement 15, design §10.1, §14, DP15, DP16, DP20, DP21, DP32, DP33; `privacy` Requirement 4, DP13, DP14, DP16; `janus/memory/disclosure.py`, `noise.py`, `faers_build.py` (`aggregate`); `medical-safety.md`, `privacy.md`.
**Data:** `.data/memory/faers_counts/current/faers_counts.duckdb` (build `20261108T005927Z-7445632a-f55a79cf-61fc`, read-only, region ALL, scope suspect unless stated, 829,531 pairs, 372,863 with a ≥ 3). Scripts: `/tmp/janus-cm-bench/rev_a.py` … `rev_g.py`. Every number below was recomputed from the file; I re-found your counts (N, 829,531 / 372,863 pairs, 378 and 938 zero cells, Evans 250,026 Pearson / 242,100 Yates).
**Not done:** no web access, so nothing from Evans 2001 or other papers is verified (see the last section).

## Verdicts

| Q | Topic | Verdict |
|---|---|---|
| 1 | Primary N, cells, `denominator_sensitive` | CHANGE (N and cells accepted; flag rule changed) |
| 2 | Haldane | CHANGE (zero-margin guard, field names) |
| 3 | Evans criteria, χ² form, minimum a | CHANGE (Yates; a ≥ 3 accepted) |
| 4 | ROR interval | ACCEPT (add method fields) |
| 5 | Assessment rule | CHANGE (exact rule below) |
| 6 | Multiple comparisons, ranking | CHANGE (wording; `disproportionate` needs a ≥ 5; no formal correction) |
| 7 | Regions | CHANGE (add two statements) |
| 8 | Combination as exposure | CHANGE (caveat and per-ingredient counts) |
| 9 | User layers, differencing | CHANGE (sibling rule; wording; known limits) |
| 10 | Evidence for a ≥ 3 only | ACCEPT (one addition) |
| 11 | Wording | CHANGE (four sentences replaced) |
| 12 | Properties | CHANGE (additions; integer arithmetic for decisions) |

## Q1. Denominator and cells: CHANGE

**N and cells: accept.** Reports with no mapped ingredient (257,904, 17.1% of 1,510,804) have unknown exposure to D. Putting them in the unexposed cells (N = all) is the worse choice, and moving to it changes the five-class assessment of only 9,278 of 372,863 pairs (2.5%, Yates form; 737 lose `disproportionate`, 3,423 gain it). The ALL result is mostly US (67.8% of all reports), and the choice does not depend on that.

**Concomitant-only reports in the unexposed cells (scope suspect): accept, state it.** Among 1,175 ingredients with at least 100 reports, the suspect share of the `any` count has median 0.52; 563 have a share below 0.5. Excluding D-concomitant-only reports from the comparison group (c' = event − pair_any, d' = (N − ing_any) − c') changes the assessment of 617 pairs (0.17%), and 272 of those become stronger. The effect is too small to justify a different cell definition. Keep Requirement 15.5 as written and say in the design that "other reports" includes reports where the medicine is only concomitant.

**Mapping gaps for one ingredient: not captured by the all-N table.** Unmapped spellings of D put D's reports into b and c (misclassification into the unexposed cells). I measured the FDA four-letter-suffix names whose stem maps (88 names, 111,752 occurrences, 34 ingredients): the share of an ingredient's reports (counted + leaked) that sit in the unexposed cells has median 8.6%, p90 33.9%, maximum 52.2%; 6 ingredients are at 25% or more. 269,224 mapped reports (21.5% of N) contain at least one unmapped exposure-role name, so the unexposed cells are not clean either. Scenario test: if a fraction f of D's exposed reports sit in the unexposed cells with the same event rate, the assessment of 4,032 pairs changes at f = 0.10, 34,067 at f = 0.25 and 73,229 at f = 0.50 (9.2% and 19.7% of the pairs at 0.25 and 0.50). In every case the pair moves toward `disproportionate`; none loses it. So the gap biases toward 1: it hides patterns, it does not create them. A `not_disproportionate` answer is therefore the least reliable answer, which supports the no-reassurance rule.

**Flag rule (adopt):**
```
primary = assess(a, b, c, d)                       # N = reports_mapped, event = reports_mapped
sens    = assess(a, b', c', d')                    # same region and scope, N = reports_all, event = reports_all
          b' = b ; c' = event_all - a ; d' = N_all - ing - event_all + a
denominator_sensitive = (primary != sens)          # compare the five-class assessment, not only the Evans verdict
```
Compare the full five-class `assessment` (the Evans-only comparison used in the measurement misses `weak` ↔ `disproportionate` moves: 9,278 vs 5,946 differing pairs). Return the full sensitivity cells, PRR, ROR with interval, χ² and assessment, not only the flag. Validate the sensitivity cells like the primary ones (no negative cell).
**Optional task, not blocking:** the builder can write `faers_mapping_gap(ingredient_key, reports_in_candidate_spellings)` from the candidate rules it already counts (biologic suffix, salt forms, parts of combination strings: 258,823, 22,821 and 207,811 occurrences). A response could then carry `mapping_gap_possible` for those ingredients. Until then the sentence of Q11(d) carries the limit for every result.

## Q2. Haldane: CHANGE (small)

Correct as stated: +0.5 on all four cells when any raw cell is zero; PRR, ROR and the interval from the corrected cells; χ² from the raw table; `a = 0` returns the counts and `no_reports` and no estimates. A zero in b, c or d leaves every raw marginal positive when a ≥ 1, so the raw χ² is defined and the PRR denominator c/(c+d) is the only problem when c = 0; the correction fixes it.
Measured, a ≥ 3: b = 0 in 378 pairs, c = 0 in 938 (0.25%), no pair with d = 0. All 1,316 meet the Evans criteria and the ROR bound. With c = 0 the corrected PRR reaches 2,446,101 (a = 4); the number depends on the 0.5 and says only "the event was never reported without D among mapped reports". Median a of these pairs is 4.
Changes:
1. Guard: if any marginal (a+b, c+d, a+c, b+d) is 0 then χ² = 0.0 (no division). Not seen in the data (0 pairs); the pure function must be total.
2. Name the two corrections so they are not confused: field `haldane_applied` (cells, +0.5) and `chi2_form = "yates"` (Q3). Do not call both "corrected".
3. When `haldane_applied`, the response adds the notice code `estimate_uses_continuity_correction` ("The size of this ratio depends on a small adjustment made because a count is zero."). The client should show a ratio above 1,000 as "over 1,000" (formatting stays the client's job; the API returns the number).

## Q3. Evans criteria and χ² form: CHANGE

I cannot verify from the paper whether Evans, Waller and Davis (2001) specify a continuity correction (no web access; I will not assert it). Choose on the merits: **use χ² with Yates' continuity correction**, χ² = N·max(0, |ad − bc| − N/2)² / ((a+b)(c+d)(a+c)(b+d)), on the raw table. Reasons: (1) the criteria are applied to counts as small as 3, where the uncorrected statistic is the more liberal one: 7,926 pairs (2.1% of the a ≥ 3 pairs) pass PRR ≥ 2 and χ² ≥ 4 only without the correction, 5,342 of them with a ≤ 4; (2) Janus can afford to be conservative, since the criteria already pass 65% of pairs (Q6); (3) with the correction no pair in this build meets the Evans criteria and fails the ROR bound (0, against 698 without it), so the two signals stop contradicting each other. The cost is 7,926 fewer Evans verdicts (250,026 → 242,100).
Fix the form in the response (`chi2_form: "yates"`) and in copy call the criteria "Evans-type screening criteria (PRR ≥ 2, χ² ≥ 4, at least 3 reports)" until the owner checks the paper's own wording. Minimum a: **3, accepted**; it is also the display threshold (Q10) and the smallest a for which the Woolf bound is not already above 1 at a = 2 (Q4).

## Q4. ROR interval: ACCEPT

Woolf: exp(ln ROR ± 1.96·√(1/a + 1/b + 1/c + 1/d)) on the (corrected) cells, level 95%. Keep 95% and the constant 1.96 (the glossary formula); a 99% level would break the usual convention and is not a multiplicity correction (Q6).
Check by exact enumeration: take a ~ Poisson(λ) with true ROR 1 and large b, c, d. The chance that the lower bound exceeds 1 is 2.7–5.3% for λ between 2 and 50 (nominal one-sided 2.5%), so the interval is somewhat narrow for small a. With a = 2 the bound is already 1.0003 (so it exceeds 1: a minimum of 3 is needed); with a ≥ 3 required and λ = 0.5 it is 1.4%.
Unreliable when: a < 5, any raw cell < 5 (including zero cells, where the 0.5 drives the result), or the table was corrected. Add `interval_method: "woolf_log"` and `interval_level: 0.95`. Canonical sentence when a < 5 or `haldane_applied`: "The range is approximate and is less reliable when few reports are involved."

## Q5. Assessment rule: CHANGE (exact rule)

```
MIN_REPORTS = 3 ; WEAK_BELOW = 5 ; PRR_MIN = 2.0 ; CHI2_MIN = 4.0
def assess(a, b, c, d):                       # raw counts; correction applied inside
    if a == 0:            return "no_reports"
    if a < MIN_REPORTS:   return "insufficient_data"
    evans = prr >= PRR_MIN and chi2_yates >= CHI2_MIN       # a >= 3 holds here
    ror   = ror_lower > 1.0                                  # a >= 3 holds here
    if evans and ror and a >= WEAK_BELOW: return "disproportionate"
    if evans or ror:                      return "weak"
    return "not_disproportionate"
```
`weak` = at least one of the two criteria is met but not "both with a ≥ 5". This is your proposal; I checked it on the data (Yates form, a ≥ 3: 372,863 pairs; 456,668 pairs with a of 1 or 2 are `insufficient_data`, none has a = 0): `disproportionate` 190,565 (51.1%), `weak` 67,435 (18.1%), `not_disproportionate` 114,863 (30.8%). Of the `weak` pairs, 51,535 meet both criteria with a < 5, 15,900 meet only the ROR bound, 0 meet only the Evans criteria. Return `evans_met` and `ror_signal` as separate booleans (each false when a < 3). Every `weak` or `disproportionate` result carries a, PRR, ROR, both intervals as numbers, and the sentence "Few reports; treat as a weak pattern." for `weak`.
Property targets: totality (exactly one class for every valid table); `a == 0` ⇔ `no_reports`; `0 < a < 3` ⇔ `insufficient_data`; `disproportionate` ⇒ a ≥ 5 ∧ evans ∧ ror; `weak` ⇒ a ≥ 3; the response fields equal a direct re-evaluation from the returned numbers; rank order not_disproportionate < weak < disproportionate is non-decreasing in a for fixed b, c, d ≥ 1 (1.18 million table checks, 0 violations; if Hypothesis finds a counterexample, drop it and keep only the monotonicity of the ROR lower bound).

## Q6. Multiple comparisons and ranking: CHANGE (wording and display; no formal correction)

The pair table is a screen over 372,863 examined pairs. With Yates, 242,100 (64.9%) meet the Evans criteria and 51.1% reach `disproportionate`. Among the 20 most-reported events of each of the 373 ingredients with at least 1,000 reports, 79.9% meet the criteria. A criterion that most examined pairs meet does not discriminate, and it measures how the comparison group looks (all other reports) more than a property of the pair.
**Canonical sentence (EN):** "This is a screening statistic. Many medicine–event pairs are examined at once and most of them meet these criteria, so meeting them is common and shows only a pattern in the reports, not what lies behind it."
(If Memory-namespace word lists permit a negated form, the plainer ending is "not evidence that the medicine causes the event". Requirement 8.4 as written forbids causal words in the namespace, and 1.8 asks for that statement, so one of the two needs an exact-sentence exception. Decide this when applying the verdict.)
**Ordering by report count only: right.** Ordering by PRR puts small, one-sided tables first: the top 1,000 pairs by PRR (a ≥ 3) have median a = 8, 33.6% have a ≤ 5 and 23.1% have c = 0. Ordering by report count also does not select on the statistic being displayed.
**Display rules (adopt):** (1) `disproportionate` needs a ≥ 5 (WEAK_BELOW); (2) no 99% level, no Bonferroni or false-discovery-rate step: the null of "same share as all other reports" is not a calibrated null here (65% reject it), so a corrected threshold would only look rigorous; (3) in event lists the client shows count and interval first and does not use a badge, colour or icon for `disproportionate` (80% of a typical top-20 list would carry it); the label belongs in the detail view with the screening sentence.

## Q7. Regions: CHANGE

**Per-cell rule: accept** (a < 3 in the regional cell is `insufficient_data` whatever the pooled cell shows). No extra rule on regional N. TR: 3,720 mapped reports, 10,808 pairs, 1,345 with a ≥ 3; 837 of those (62%) have a < 5 and so cannot exceed `weak`; 484 are `disproportionate`; 147 (10.9%, against 0.35% pooled) need Haldane. EU, OTHER and UNKNOWN have no pairs with negative cells. The interval and `weak` already carry the small-N effect; a separate N rule would double count.
**"Not comparable as rates": correct, not sufficient.** Add:
1. "A different label in two regions can come from different numbers of reports, not from a different pattern." (TR has 3,595 reports by occurrence country and 432 by reporter country; EU 155,803 and 5,845.)
2. "Each region is compared only with the other reports from the same region." (Requirement 3.5 does this; the reader should be told, since pooled ALL is 67.8% US.)
Also state, in place of "not where the patient lives" (Q11c), which country field was used. Also state that EU is 27 states pooled and that TR reports in FAERS are a small, self-selected set of reports, not a picture of medicine use in Türkiye.

## Q8. Combination as exposure: CHANGE

Sound as a count: reports naming all ingredients, once per report, scope `any`, top events ranked by a, display threshold 3, ladder combination → pairs reaching the threshold → single ingredients. Two points:
1. **The comparison group is every other mapped report, including reports naming only some of the medicines.** A PRR or ROR for the combination therefore shows that the event is reported more with the set than with the rest, which can be entirely due to one member. It is not an analysis of the combination. Giving PRR/ROR is not wrong, but it is misleading unless the response says what it compares and shows the members alone.
2. **Mapping gaps compound:** the set is counted only if every ingredient is mapped, so a set of m ingredients loses reports in proportion to roughly the product of the coverages (with 84.0% coverage per occurrence, about 71% for two). Counts of larger sets are lower bounds of reports that name them.
Changes: (a) each top event also returns, for each member alone (same scope and region), its report count for that event; (b) the response states `exposure: "all_of_set"` and `comparison: "all_other_mapped_reports"`; (c) when the shown level is a fallback, the statistics refer to that level and the response says which. **Caveat sentence (EN):** "These counts are for reports that name all of these medicines. The comparison group is every other report, including reports that name only some of them, so a pattern here may come from just one of the medicines. It does not show an effect of taking them together."

## Q9. User layers: CHANGE

**Differencing is real and the wording is not met.** Discrete Laplace at scale 1 has sd 1.36; the difference of two cells has sd 1.92, and the difference lies within ±3 with probability 92.7% and within ±4 with 96.9%. The cell {A} and the cell {A,B}, each ≥ 20, give the size of "A without B" to about ±4 although that group may hold 1 to 19 donations. "Hidden under 20" is then false for that group. Per-request limits do not help: there is no caller identity, so the same caller makes two requests.
**Mitigation to adopt (sibling rule), done before `release_table` on the true counts:**
```
n  = donations naming all of S, the event, direction, region
for each ingredient X not in S: m_X = donations in that group that also name X
eligible = (n >= k) and for all X: (n - m_X == 0 or n - m_X >= k)
cell count passed to release_table = n if eligible else 0       # then hidden, identical answer
```
Property: for any donation set and any two released cells S ⊂ T (same event, direction, region), n_S − n_T is 0 or ≥ 20. Cost: one extra grouped statement per requested cell (adds 1 to the statement budget of `shared`), and more hidden cells when one co-ingredient X is in all but fewer than 20 of the donations of S. At current volumes nearly every cell is hidden anyway, so the practical cost is small now.
Rejected alternatives: exact-set matching (a cell counts only donations naming exactly S) removes the overlap but also the meaning: "donations naming A" becomes "donations naming only A", and sets of three or more rarely reach 20; one cell per response or a cell limit per request do not stop several requests; a noisy threshold is DP14's rejected option.
**Residual limits (state in the privacy page text, not hide):** (1) two-step differencing (A) − (A,B) − (A,C) + (A,B,C) is not covered; it has sd 2.7; (2) rate limiting is deferred (DP13), so one source can add donations: it can pad a cell to 19 and read whether it reaches 20, which tells whether one more donation exists (threshold crossing on true counts), and each added or deleted donation changes the data version and gives fresh noise to average. These are the known limit of DP13, not new, but they mean "hidden under 20, noise added" holds against ordinary readers, not against someone who can add donations.
**One person donating several times:** k counts donations (DP13), so 20 is 20 donated reports, not 20 individuals. Memory-layer strings say "donated reports", never "people". `privacy` Requirement 4.1 says "fewer than k = 20 people" and conflicts with its own DP13; the Memory wording follows DP13.
**Other points accepted:** counts only, no PRR/ROR (no comparison group); true count decides, uniform `hidden`; totals from released cells; same value for the same cell and version.

## Q10. Evidence only for a ≥ 3: ACCEPT (one addition)

A cell with 1–2 reports is not shown as a number (display threshold 3), and a statistic with a < 3 should not be citable. Addition: the sentences for `no_reports` and `insufficient_data` state a coverage fact, not a statistic, and would also be removed. Register one deterministic evidence record per (snapshot, region) of kind `faers_snapshot` (source, licence, snapshot date) that those sentences may cite, so the no-reassurance sentence of Requirement 8.7 survives the `cite` filter. Test that a sentence and its evidence record come from the same build (the id excludes dates and run ids by design).

## Q11. Wording: CHANGE

(a) PRR ≥ 2 is about shares, not counts. Replace with: "The event appears in a larger share of the reports that name this medicine than in the other reports that name a recognised medicine." For `not_disproportionate`: "The event does not appear in a clearly larger share of the reports that name this medicine. This does not mean there is no association."
(b) Replace with: "Reports are sent voluntarily and are not checked. The counts do not show how often an event happens. Only repeated versions of the same case are merged, so one event can still appear in more than one case."
(c) The region is the occurrence country (else the reporter country), so "where the report came from" is incomplete. Replace with: "A report's region is the country where the event is said to have happened or, when that is missing, where the reporter is. It does not tell where the patient lives or where the medicine was bought."
(d) Replace with: "Counts use only reports that name at least one medicine Janus recognises (82.9% of the reports in this window). Some spellings are not recognised, so a pattern can be missed. Figures for all reports are shown beside these." (Take the percentage from the snapshot, not from copy.)

## Q12. Properties and arithmetic: CHANGE

**Integer or fraction arithmetic (must):** cell derivation (Python `int`; SQL in `HUGEINT` or `DOUBLE`, never `INT64` products); PRR ≥ 2 and χ² ≥ 4 decisions; the Haldane doubled-cell form. Decisions exactly: raw, `a(c+d) ≥ 2c(a+b)`; corrected (double every cell and add 1): `(2a+1)(c+d+1) ≥ 2(2c+1)(a+b+1)`. Yates: `2|ad − bc| ≥ N and N(2|ad − bc| − N)² ≥ 16(a+b)(c+d)(a+c)(b+d)`. I checked all 372,863 real tables: the float decisions and the integer decisions agree in every case (0 mismatches for PRR, Pearson and Yates). The ROR bound involves log and square root; keep it in floats (ratio ad/bc formed first, counts ≤ 3·10⁶ are exact in a double) and test it against a 50-digit `decimal` reference except within 1e-9 of the boundary. Intermediate products reach ≈ 10³¹: fine for Python ints, overflow for INT64.
**Spec list: keep, with these edits:** replace "no output from user layers ever represents a group with fewer than 20 people" by "donated reports"; the transposition property below replaces "swapping exposed and unexposed inverts the ROR" (that property is true only for the row swap).

## Parameters to adopt

- `MIN_REPORTS = 3` (also the display threshold and the minimum a of the criteria)
- `WEAK_BELOW = 5` (`disproportionate` needs a ≥ 5)
- `PRR_MIN = 2.0`, `CHI2_MIN = 4.0`
- `CHI2_FORM = "yates"` on the raw table; χ² = 0 when a margin is 0
- `HALDANE = 0.5` on all four cells when any raw cell is 0; field `haldane_applied`
- `CI_LEVEL = 0.95`, `Z_95 = 1.96`, `INTERVAL_METHOD = "woolf_log"`; interval shown for every PRR/ROR result
- `ASSESSMENT` rule of Q5; `evans_met` and `ror_signal` returned separately
- `denominator_sensitive = (assess(primary) != assess(all-reports cells))`, same region and scope, five-class comparison
- List order: reports descending, then PT ascending; no badge for `disproportionate` in lists
- `K = 20`, sibling rule of Q9 before `release_table`; ε = 1, scale 1

## Added properties

- Transposition (swap b and c): ROR, its interval and χ² are unchanged. Row swap (a↔c, b↔d): ROR → 1/ROR, bounds swap and invert, χ² unchanged.
- Scaling: multiplying all four non-zero cells by k > 1 leaves PRR and ROR unchanged, narrows the interval and raises Pearson χ² by exactly the factor k (Yates χ² rises by at least that factor).
- Monotonicity in a (b, c, d ≥ 1 fixed): PRR, ROR and the ROR lower bound do not decrease; the assessment class does not decrease.
- Exactness: the PRR ≥ 2 and χ² ≥ 4 decisions equal the integer inequalities of Q12 for counts up to 1,600,000 (N up to 2³¹ in the generator); no NaN or infinity for any valid table including zero cells and a margin of 0.
- Stability: PRR and ROR from the float path agree with a `Fraction` or 50-digit `decimal` reference to relative 1e-12.
- Haldane: `haldane_applied` ⇔ a raw cell is 0; χ² is identical with and without it; with a = 0 no estimate field exists.
- Round trip: the booleans re-evaluated from the serialized numbers equal the returned booleans.
- Sensitivity: swapping the roles of mapped and all-report totals changes only c, d; `denominator_sensitive` is false when `reports_all = reports_mapped`.
- Sibling rule: any two released user-layer cells S ⊂ T (same event, direction, region) have n_S − n_T = 0 or ≥ 20; the answer for an ineligible cell equals the answer for a cell with count 0.
- Combination: the member-alone count of an event is never below the combination count for that event (same scope and region); the combination's `level` is the highest level whose count reaches 3.

## Not verified or open

- **Evans, Waller and Davis 2001 (Pharmacoepidemiol Drug Saf 10:483–486):** I did not read the paper. The DOI 10.1002/pds.677 must be verified in Crossref by the owner before any product copy cites it, and the paper's own χ² form should be checked against the Yates choice here.
- Whether Requirement 8.4's causal-word list allows the negated sentence of Q6 (open wording decision).
- The mapping-gap estimate covers only suffix names whose stem maps (34 ingredients); MYCOPHENOLATE and parts-of-combination spellings were not attributed per ingredient.
- The Woolf check is a Poisson model with large b, c, d, not a full simulation of 2×2 tables.
- Regional conclusions for EU, OTHER and US were not tabulated by assessment class; only TR was.
- The `faers_snapshot` evidence kind (Q10) and `faers_mapping_gap` table (Q1) need decisions in `evidence-integrity` and `data-pipelines`.
- Rate limiting (Phase 5) decides how serious the padding and averaging limits of Q9 are.

VERDICT: approved with changes
