# Expert validation: protocol (plan E; measurement B3b)

**Status:** pre-registered before the validation packet is sent to any expert. No expert answer exists yet.
Research prototype, not a medical device. Expert review has not yet been done.

The protocol is committed and pushed before the packet leaves the project. A change after the first answer arrives is
reported as a deviation with its reason, and both analyses are reported where the change affects a result. Until the
answers are scored, every page keeps the sentence "Expert review has not yet been done."

## 1. Why

Every check of Janus so far is automated: the cascade reference set was built by an automated reader from published
sources (B1), the drug model values were judged by two automated review passes (B3a), and the patient and doctor texts
were drafted and checked automatically. This round asks people with the right training to judge samples of the same
material, so that:

1. the B1 reference set can be checked against expert judgement (are the "published cascades" cascades; are the
   "non-cascade" pairs not);
2. the wording a patient and a doctor read is judged for accuracy, risk of harm and clarity;
3. the drug model values get an expert precision (tier 2 of B3) and, for the first time, a recall;
4. pending product mappings and the drug model method get a decision.

## 2. Experts

| Group | At least | Sections |
|---|---|---|
| Clinical pharmacologists | 2 | C, D, F |
| Geriatricians or family physicians | 2 | A, B |
| Clinical pharmacists | 2 | A, B, E |

Each item goes to at least two experts who judge it independently. Experts are recruited by the project owner.
Participation is voluntary; each expert states their conflicts of interest on the form in the packet. Experts may be
thanked by name in the results only if they say so on the form.

**Workload.** The time of each item is fixed in advance (§4). An expert's share is capped at 3 hours 45 minutes. If
fewer experts take part than the assignment needs, items are dropped in the fixed random order of §5, never chosen by
their content, and the number actually judged is reported.

## 3. Blinding

- Experts do not see Janus's own confidence: no strict-check level, sampling stratum, automated verdict or
  "probable/possible" label.
- In section A the reference-set positives and negatives are mixed in one random order with no label, and the pair's
  source is not shown.
- Experts do not see each other's answers. Each expert gets an answer file with their own identifier; which items went
  to whom is kept in a private mapping file.

## 4. Sections, samples and time per item

All samples are drawn with seed 20261113 from the files named, at the commit that registers this protocol.

| Section | What | Sample | Question and scale | Min per item |
|---|---|---|---|---|
| **A1** | B1 reference pairs (`data/validation/cascades/positive_pairs.csv`, `negative_pairs.csv`) | 60 positives and 40 negatives, simple random, mixed in one random order | "Is it clinically realistic that drug B is started to treat an adverse effect of drug A?" 1 (not at all) to 5 (clearly); free comment | 1 |
| **A2** | Class membership used by the rules (`data/cascade_classes.csv`, rows with `match = include`) | 40 rows, random | "Does this pattern of codes describe the drug class the cascade row means?" yes / no / unsure | 0.5 |
| **B** | Wording: the result card (three parts), the screening sentence, the abrupt-stop line, the emergency line, the doctor-note sections and the outcome request, English and Turkish | all (about 25 texts per language; each expert rates the language(s) they read) | accuracy, risk of harm, clarity, each 1 to 5; suggested wording | 2 |
| **C1** | Drug model values: confirmed values of the current release | 50 values, stratified by source (ClinicalTrials.gov 30, PubMed Central tables 10, Drugs@FDA reviews 10), at most 2 values per study | correct; incorrect (value, unit, parameter, drug or analyte, population, other); cannot judge | 1 |
| **C2** | Recall: whole documents | 20 documents (10 ClinicalTrials.gov results records, 10 PubMed Central articles with a PK table), random among documents with a confirmed value; each expert takes at most 6 | mark every PK value of the document (drug, parameter, value, unit, population) | 8 |
| **D** | Special-population sentences (`atlas_high`, 80 rows) | 24 rows, random | does the sentence say what the quoted label says; does the direction (higher/lower exposure) match | 2.5 |
| **E** | Dose-form group proposals for Canada, Italy and Spain | 30 per country (90), random | accept / reject / unsure; correct group if rejected | 0.5 |
| **F** | Drug model method, 20 drugs (`method20.json`) | all 20 | is each parameter's derivation sound; is the drug's status (validated / not validated / failed) justified; comments | 3 |

Estimated time per expert:
- clinical pharmacologist: C1 50 + C2 6 × 8 = 48 + D 60 + F 60 = 3 h 38 min;
- geriatrician or family physician: A1 100 + A2 20 + B 50 = 2 h 50 min;
- clinical pharmacist: A1 100 + A2 20 + B 50 + E 45 = 3 h 35 min.

With two pharmacologists, C2 reaches 6 documents judged twice; each further pharmacologist adds 3. The number of
documents reached is reported with the recall.

## 5. Assignment and dropping

Items of a section are put in one fixed random order (seed 20261113). Each item is assigned to two experts of the
section's groups, round-robin in that order, until every expert reaches the cap. Items left without two experts are
dropped from the end of the order. The mapping file records the assignment and the dropped items.

## 6. Agreement and consensus

- **Agreement** per section: Cohen's κ for categorical answers (quadratic-weighted for the 1–5 scales), with its 95 %
  interval, over items judged by the same two experts.
- **Consensus** of an item: the two experts agree (same category; on 1–5 scales both ≥ 4, or both ≤ 2). Otherwise a
  third expert of the section's groups decides; if none is available the item is "not settled" and is reported as such.
- For E, a proposal enters the product data only with a consensus "accept".

## 7. Analysis

| Section | Primary result | Secondary |
|---|---|---|
| A1 | Share of reference positives that experts call realistic (consensus ≥ 4) and share of reference negatives they call not realistic (consensus ≤ 2), each with a Wilson 95 % interval | B1 sensitivity and specificity re-computed on the expert-confirmed pairs only (a sensitivity analysis of B1, not a replacement) |
| A2 | Share of class rows judged correct (Wilson) | list of rows to change |
| B | Mean and range of each rating per text | every text rated risk of harm ≥ 3 by any expert is rewritten before the next release, and its new wording goes back to one expert |
| C1 | Expert precision (tier 2) per source: correct ÷ (correct + incorrect), Wilson and study-level cluster bootstrap, the cluster-aware lower bound as in B3a | agreement of the automated verdicts (tier 1) with the expert consensus (κ) |
| C2 | Recall: values the readers confirmed ÷ values the experts marked, per source, with a Wilson interval and a document-level bootstrap | the kinds of values missed |
| D | Share of sentences judged correct; share with the right direction | |
| E | Proposals accepted, rejected and not settled per country | accepted rows enter the product data in the next release |
| F | Per drug: method sound yes/no; status justified yes/no | open questions |

No result of this round changes a pre-registered B1, B2 or B3a result; the expert results are reported next to them.
The decision rule of B3a (cluster-aware lower bound ≥ 0.90) is applied to the tier-2 precision as well; a source that
passes tier 1 but fails tier 2 is held back.

## 8. What changes on the site

The sentence "Expert review has not yet been done." changes only after the answers are scored and recorded, and only
for what was reviewed: it then says which material was reviewed, by how many experts of which training, and links the
results. Material outside the samples keeps the sentence.

## 9. Data handling

Answer files carry an expert identifier (E01, E02, …), not a name. The mapping of identifiers to names and e-mail
addresses, the conflict-of-interest forms and the raw answer files stay outside the repository. Results are published
in aggregate; free comments are quoted only without anything that identifies the expert.

## Amendment 1 (2026-11-13, before the packet is sent; no answer exists)

Found while building the packet: the current drug model release holds only 12 PubMed Central values (2 studies) and 4
Drugs@FDA values (1 study), because those sources did not pass the B3a rule and were held back. C1 and C2 cannot be
drawn as written. Changes, made before any expert has seen an item:

1. **C1 frames.** ClinicalTrials.gov: 30 values from the current release, as registered. PubMed Central: 10 values
   from the B3a fresh sample P2 (`data/validation/modelkit/items.csv`, 53 values in 38 articles). Drugs@FDA: 10 values
   from the B3a fresh sample D2 (26 values in 11 documents). At most 2 values per study, seed 20261113. The B3a
   automated verdicts of these values stay hidden from the experts. Purpose of the two held-back parts: an expert
   precision of the held-back sources and a check of the automated review passes against experts (κ); they do not
   decide whether these sources ship, which needs a fresh sample under the B3a rule.
2. **C2 frames and order.** ClinicalTrials.gov: 10 results records with a confirmed value in the current release.
   PubMed Central: 10 articles of the P2 frame. Each source has its own fixed random order (seed 20261113), so the
   documents of one source do not depend on the other. Assignment alternates between the two sources.
3. **Time per expert (§4).** §5 governs: each A1, A2 and B item goes to two experts, one geriatrician or family
   physician and one clinical pharmacist. With two experts in each of these groups each expert judges half of A1, A2
   and B; the cover letter gives the times that follow from the actual assignment.
4. **Choices fixed now** where §6 left them open:
   - The third expert's answer decides when two disagree. On a 1–5 scale, a third answer of 3 decides nothing, and
     the item is "not settled".
   - The κ interval is a bootstrap over items.
   - In C2, a value counts as marked by the experts when both mark the same drug and parameter with values within
     1 % of each other.
   - In F, the evidence class (A/B/C) is hidden; it is Janus's own confidence grade.
   - A group with a single expert cannot pair; its items are dropped and reported.

