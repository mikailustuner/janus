# Model kit precision, round B3a: pre-registered protocol

**Status:** pre-registration, written 2026-11-13 (UTC) before any new sample was drawn and before any new verdict was
read. The time of the git push of this file is the timestamp. Research use only. Not for clinical decisions.
**Expert review has not yet been done.** Every reading, check and review pass in this protocol is automated; the review
passes are an evaluation instrument only and never part of the product. No language model reads values for the product.

## 1. Why a new round

The model kit shows pharmacokinetic (PK) values (clearance CL, volume V, half-life t½, Cmax, AUC, tmax, bioavailability F)
read by two independent rule-based readers from public sources and confirmed only when both agree. The precision shown
today, 0.99 (125 of 126 values, Wilson 95 % 0.956–0.999), is a census of ClinicalTrials.gov values that pass the strict
publication check at level 3. It has three known limits:

1. It covers **one source** and about 13 % of the values the readers agree on.
2. The 126 values come from **14 studies** (one study has 36). Values from one study share their errors; the Wilson
   interval assumes independent values and is therefore too narrow.
3. The registry is **exhausted** for fresh measurement: earlier samples touched 333 of the 360 studies that ever had a
   confirmed value. A value once looked at cannot be measured again.

This round (a) re-states the existing ClinicalTrials.gov measurements as a risk–coverage curve with cluster-aware
intervals, and (b) measures two document sources on value pools that no one has looked at.

## 2. Hypotheses and expectations (stated before any result)

- H1 (PubMed Central tables, iteration 2 of the strict table check): the cluster-aware lower 95 % bound of precision at
  level 3 is ≥ 0.90. Expectation: **not met**. The previous fresh measurement was 0.57 at level 3 (n = 37); the new rules
  look better only on development items (15 of 16 at level 3, which is optimistic by construction) and keep far fewer
  values (66 of 2,289 confirmed rows of the earlier run at level 3).
- H2 (Drugs@FDA clinical pharmacology reviews, two-reader confirmation without a strict check): the cluster-aware lower
  bound is ≥ 0.90. Expectation: **not met** (previous measurement 0.48, n = 92).
- H3 (ClinicalTrials.gov, re-analysis): the cluster-aware interval of the shipped figure is wider than its Wilson interval
  (design effect > 1 when estimable). This is a re-analysis of samples already looked at, not a new measurement.

## 3. Sources and frames

A **frame** is the set of values a sample is drawn from. A value enters a frame only if no earlier sample contains it, its
study was never sampled, and its drug is not a development drug (the 50 drugs whose values were used to write rules).

### 3.1 ClinicalTrials.gov (re-analysis only)
- Sample A, frame F (iteration 1 of the strict check; 1,010 rows in 177 studies; bands L0 550, L1 204, L2 73, L≥3 183
  rows; sampled 30/30/14/100 values, at most 3 per study, a study in one band only).
- Census C (iteration 2, level 3, the shipped set: all 126 then-unreviewed values, 14 studies).
- Sample A, frame X (studies with an earlier error, level ≥ 3, 30 values) is reported as a secondary line.
These samples were drawn and judged on 2026-11-12. Their numbers are **re-analysed** here (study clusters, design
effect, curve); they are not new measurements and are labelled so.

### 3.2 PubMed Central open-access tables (new frame P2)
- Articles: the hits of the same Europe PMC search as the earlier round (title names the drug and a PK word, open access,
  CC BY or CC0), cached 2026-11-12, newest first, **beyond the 10 articles per drug read earlier, at most 10 more per drug**
  (ranks 11–20), non-development drugs. None of these articles was ever fetched or read. Counted before this protocol:
  534 articles of 81 drugs. The three licence checks and the human-only filter of the existing job apply unchanged.
- Readers A and B and the confirmation code are unchanged. New: the strict table check iteration 2
  (`strict_pmc.py`, sha256 `c007b32d…7263a`, reference tables `analytes.csv` `e90e436b…`, `combination_products.csv`
  `7dfc4079…`): the whole table, not only the value's own header and row, is searched for a metabolite, prodrug or
  reversal-agent name of the drug, metabolite or enantiomer words, another pool drug, a sampling matrix other than
  blood/plasma/serum, and single-patient rows; a marketed combination product of the drug in title, caption or methods;
  and model inputs (PBPK) abstain. Development numbers (earlier PMC samples, all already judged; **not precision**):
  level ≥ 3 15/16, level ≥ 2 24/32, level ≥ 1 25/34, no rule 75/146.
- Units: confirmed stated parent values (two readers agree, analyte parent).
- Strata (bands): L3, L2, L0–1. Weights = frame counts per band.

### 3.3 Drugs@FDA clinical pharmacology reviews (new frame D2)
- Documents: priority-1 (clinical pharmacology or biopharmaceutics) and priority-2 (multidiscipline or integrated)
  review PDFs of the original applications of pool drugs (single-ingredient NDAs) that the earlier round did **not**
  fetch (it took at most 3 per drug), non-development drugs, at most 5 more per drug: 261 PDFs of 99 drugs counted before
  this protocol. Born-digital text layers only (scanned PDFs are counted, not read).
- If, after reading, fewer than 40 documents have a confirmed value, the frame is extended **before any draw and from
  counts only** with the review pages of supplements (priority 1 or 2, at most 3 more per drug).
- Readers and confirmation unchanged; there is no strict check for review tables, so the frame has one band (L0).
- Cluster: the review document (it may report several studies; the document is the unit that can be identified
  reliably, which makes the interval conservative).

### 3.4 Sources checked but not measured in this round
- EMA European public assessment reports (EPARs): re-use for commercial and non-commercial purposes is allowed with
  acknowledgement of EMA (legal notice); third-party content excluded. PK values are mostly in running text, and no reader
  exists for that layout; the source is registered (`sources.toml`, `cited_only`) and not measured.
- EU Clinical Trials Register (EudraCT) and CTIS, ISRCTN, ANZCTR: see `modelkit-precision.md`, section on registries.

## 4. Samples (fixed now)
- **P2:** L3 up to 50 values, L2 up to 40, L0–1 up to 30; at most 3 values per article, and an article is used in one band
  only (bands drawn in the order L3, L2, L0–1); within an article, values with different parameters first; round robin
  over articles so that as many articles as possible contribute. Seed 20261711.
- **D2:** up to 90 values, at most 3 per document, different parameters first, round robin over documents. Seed 20261712.
- One blinded list per source, shuffled (seed 20261713). Each item shows only the claim and the source excerpt, never the
  band, level, stratum or any confidence.
- Target across both sources: ≥ 120 values from ≥ 40 studies; if a frame is smaller, the whole frame is taken (census) and
  the shortfall is reported.

## 5. Truth, tier 1 (automated)
- Two independent automated review passes per item. Each pass sees only the items and the instructions, not the other
  pass, not the code, not the levels. Pass 1 and pass 2 are run by separate reviewers. Instructions: identical in
  substance to the earlier document-source review (value, analyte, dose, context, summary section; formulation and route
  recorded separately, not counted), plus an error type for wrong values (value, analyte, dose, context, summary, other).
- Verdicts: correct, incorrect (with error type), cannot judge.
- Tier 2 (two experts, Cohen's kappa, third expert for disagreements) is phase B3b and is not part of this round.

## 6. Analysis (fixed now; code `pipelines/janus_pipelines/modelkit/precision_stats.py`, sha256 `e7903e77…1bb1`)
- Precision = values both passes call correct / values both passes give the same verdict (correct or incorrect).
  Conservative precision = both correct / all items. Cohen's kappa over all items (three categories).
- Stratified estimate: band precisions combined with the frame weights; precision at level ≥ k uses the bands at or above k.
- Intervals for every reported precision: (1) Wilson 95 % (for a weighted estimate with effective n = 1 / Σ w²/n);
  (2) **study-level cluster bootstrap**: studies resampled with replacement within each band, 4,000 resamples, seed
  20261113, percentile 95 % interval; (3) Wilson with n / design effect, where design effect = bootstrap variance /
  variance under independence; if no error was found (variance not estimable), the design effect is the mean number of
  agreed values per study (intra-cluster correlation 1, the conservative bound).
- **Cluster-aware lower bound** = the smaller of the bootstrap and the adjusted-Wilson lower bounds.
- Risk–coverage curve: for each level, precision (with intervals) and coverage = share of the source's confirmed values
  at that level or above.
- Combined figure across sources (informational): source estimates weighted by their frame sizes at the levels reported.
- Also reported: precision per parameter (descriptive, small n), error types of agreed wrong values, pass-level
  precision of each pass.

## 7. Acceptance rule (unchanged from the plan)
A source ships only if the **cluster-aware lower bound of its precision is ≥ 0.90**. For PMC the rule is applied at
level 3 and, if met there, at level 2 (the lowest level that meets it ships). For Drugs@FDA it is applied to the single
band. A source that fails stays held back and is reported. ClinicalTrials.gov keeps its shipped state; its re-analysis is
reported with its cluster-aware interval and the same rule is stated against it.

## 8. What this round does not measure
Recall (how many values in a document the readers miss) is **not yet measured**; it needs expert annotation of whole
documents (phase B3b). Precision is measured against two automated passes, not against experts.
