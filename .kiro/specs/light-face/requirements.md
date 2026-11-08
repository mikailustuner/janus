# Requirements: Light Face ("Dead Drugs Rise")

> Refined 2026-11-08 from the draft seed (Claude Code standing in for the Kiro spec workflow). Every criterion and
> property of the seed is kept; refinements are marked *(Refined)*, new criteria *(Added in refinement)*. Decisions are
> numbered DP1… in `design.md`; properties P1… there trace to the criteria below.
> **Scope:** the pure engine `apps/api/janus/light/` (inverse signals, side effect → therapeutic goal, candidates, ranking,
> retrospective validation, card content), the `onsides` and `openfda_label` pipelines, the curated files under
> `data/light/`, the `/light/*` API routes, and the researcher-area screens (hypothesis cards, validation report, export).
> **Seams:** `collective-memory` gives the counts file, `janus.memory.stats` and the user-layer release (k = 20, noise,
> sibling rule); `evidence-integrity` gives `cite` and the evidence records; `drug-resolution` gives the ingredient keys
> (Wikidata item, RxCUI); `experience` gives the shell, themes, components and the research route; `seance` will give the
> molecular witness (ChEMBL). This spec changes none of their code paths.
> **Owner decisions (2026-11-08, Phase 4 brief):** experts test after Phase 4; every curated mapping and validation case
> is reviewed by the pharmacologist and statistician agents in separate, labelled passes and marked "AI-reviewed, pending
> expert review"; no stop for owner review (decisions recorded as DPs); retrospective validation is the credibility gate;
> outputs are "candidate worth investigating — not a treatment" and never in the patient flow; every external licence
> and every citation is verified (Crossref) before use.

## Introduction
For researchers and clinicians: turn side-effect knowledge around to generate drug-repurposing **hypotheses** — inverse signals, side effect → new indication, and patient-reported unexpected benefits. Spontaneous-report signals are weak evidence on their own (literature requires validation in vivo, ex vivo and in trials), so the method's credibility comes from **retrospective validation**: it must rediscover known repurposings and report its misses honestly.

## Glossary *(Added in refinement)*
- **Therapeutic goal:** a curated condition key (e.g. `alopecia`) with labels in five languages, the side-effect terms
  that point to it, the FAERS Preferred Terms that name it, and the Janus benefit keys that report it
  (`data/light/goals.csv`).
- **Signal type:** `label_effect` (OnSIDES side effect mapped to the goal), `inverse_faers` (FAERS reporting lower than
  expected), `patient_reported` (Janus donated reports of an improvement, k = 20 and noise).
- **Candidate:** a pair (ingredient key, goal) with at least one signal. **Card:** a candidate with at least one citable
  source. Counts are reports or labels, never people.
- **Validation case:** a fixed, cited historical repurposing (ingredient, original indication, later goal, year)
  (`data/light/validation_cases.csv`).

## Requirements

### Requirement 1: Inverse signals
#### Acceptance criteria
1. WHEN the upper 95% CI bound of ROR for (drug, condition) is < 1 THE system SHALL list it as a possible protective association.
   - *(Refined.)* A condition is a goal's FAERS PT set (union, report level). The table uses scope `any`, region `ALL`,
     N = mapped reports, `janus.memory.stats.evaluate` (Haldane when a cell is zero, Woolf interval, Yates χ²), and
     requires `a ≥ MIN_REPORTS` (3); with fewer reports nothing is listed. The sensitivity table (N = all reports) is
     carried and `denominator_sensitive` is shown. The wording is "reported less often than expected", never
     "protects", "reduces risk" or "benefit" (DP6).
2. Every inverse signal SHALL carry a reporting-bias warning (including notoriety and indication bias) and the FAERS snapshot date.
   - *(Refined.)* Also the screening sentence (`Memory.screening`), the limits sentence, the window, and the
     citations of the bias warning (notoriety: Pariente 2007; interpretation of inverse signals: Uesawa 2026).
3. *(Added in refinement.)* Inverse signals SHALL be ordered by report count (then key), never by the ratio; an
   assessment class SHALL NOT appear as a badge or colour in a list (collective-memory display rules).

### Requirement 2: Side effect → indication mapping
#### Acceptance criteria
1. THE system SHALL use a curated, cited mapping from adverse-effect terms to therapeutic goals (e.g. hypertrichosis → alopecia; weight loss → obesity).
   - *(Refined.)* Each row names the term exactly as OnSIDES publishes it (MedDRA PT or LLT name), the goal, a rationale
     and at least one evidence id of a paper in `data/evidence_papers.csv`, and a review status; rows with status
     `excluded` are kept with their reason and never used. The loader refuses a row without citation, an unknown goal,
     a duplicate term, or a term that is not in the OnSIDES vocabulary of the current snapshot.
2. WHEN a drug's OnSIDES side effect maps to a therapeutic goal THE system SHALL propose (drug, condition) as a candidate.
   - *(Refined.)* Only single-ingredient labels count (a combination label cannot attribute an effect to one
     ingredient, DP2). The candidate records the matched terms, the number of the ingredient's labels listing them, the
     number of its labels, the label sections, and the regions.
3. WHEN OnSIDES has label data for the drug in several regions (US, EU, UK, JP) THE system SHALL show in which regions the side effect is labelled.
4. *(Added in refinement.)* THE system SHALL say that OnSIDES is extracted by a language model from labels and can be
   wrong or incomplete, and SHALL attribute it (Tanaka et al., Med 2025; CC BY 4.0) with its data version.

### Requirement 3: Unexpected-benefit reports
#### Acceptance criteria
1. WHEN at least k = 20 consented reports describe the same (ingredient, improvement) THE system SHALL show it as a patient-reported signal (with noise per the privacy spec).
   - *(Refined.)* The cell is released through the collective-memory user-layer release for one ingredient and one
     benefit key (regions TR, EU, US; sibling rule; k = 20 on the true count; discrete Laplace noise; the total of
     released cells only). A hidden cell carries no number. A benefit-only candidate is listed as a patient-reported
     signal, not as a hypothesis card, until a signal with a citable source supports it (DP7).
2. *(Added in refinement.)* WHEN the database or the noise key is not available THE patient-reported layer SHALL say
   "layer unavailable"; the other layers SHALL still be shown.

### Requirement 4: Hypothesis cards
**User story:** As a researcher, I want each candidate as a transparent card so that I can judge whether to investigate it.

#### Acceptance criteria
1. Each card SHALL show: candidate (drug, condition), which signal types support it, statistics with CI, sources (integrity-checked), possible mechanism (ChEMBL target, if any), and the label "candidate worth investigating — not a treatment".
   - *(Refined.)* Statistics: label counts and share for `label_effect`; cells, ROR with interval bar, report count and
     sensitivity for `inverse_faers`; the released noisy count for `patient_reported`. Sources pass `cite`
     (evidence-integrity); retracted sources are removed and named as such. Mechanism: shown when a mechanism source is
     connected (the séance spec's ChEMBL witness); until then the card says that no mechanism source is connected (DP14).
2. THE system SHALL let researchers export cards and the anonymized aggregate dataset under an open license.
   - *(Refined.)* Export: JSON from the API and CSV built in the browser; licence CC BY 4.0 with the attributions of
     OnSIDES and FAERS; only counts already shown (released noisy counts for the user layer, never true counts). The
     word used is "aggregated", and the text says the user layer is pseudonymous donated data released as noisy counts
     of groups of at least 20 (privacy steering: never "anonymous" for donations).
3. Hypothesis cards SHALL be shown in the researcher area, not in the patient flow; the patient flow only asks the "unexpected improvement?" question.
4. *(Added in refinement.)* Cards of a goal SHALL be ordered by the ranking of design §6 with ties shown as tied ranks;
   the ratio SHALL never order a list.
5. *(Added in refinement.)* Every card, list and export SHALL carry the disclaimer and the rule-7 label; no card text
   SHALL say or imply that the drug treats, cures or should be used for the condition.

### Requirement 5: Retrospective validation (credibility gate)
#### Acceptance criteria
1. THE engine SHALL be evaluated on a fixed, cited set of known historical repurposings (at least: minoxidil → alopecia, thalidomide → multiple myeloma / erythema nodosum leprosum, sildenafil → its later indication) using data that does not include the later indication where possible.
   - *(Refined.)* Nine cases (design §8.1), every citation checked in Crossref. The primary run uses US labels only and
     removes the case drug's labels whose openFDA indications text names the later indication (or that openFDA does not
     have); a sensitivity run uses all labels. FAERS cannot be restricted by indication in the current artifact, so its
     result is reported as including the later indication. The patient-reported layer has no historical data and is
     not evaluated.
2. THE system SHALL publish the evaluation (hits, misses, rank of each known case, data snapshot) in the researcher area and in `docs/`.
   - *(Refined.)* Rank = tied rank range within the goal's candidates (best–worst), with the population size; hit =
     worst rank ≤ 10; a hit in a population of 10 or fewer is marked uninformative. `docs/light-face-validation.md` is
     generated by the build from the same result.
3. WHEN the evaluation shows no known case in the top results THE light face SHALL be presented as experimental in the demo.
   - *(Refined.)* "No known case in the top results" = no informative hit in the primary run. Then every light-face
     screen shows the "experimental" notice. Hits are never described as proof.
4. *(Added in refinement.)* THE case list, the goals and the mapping SHALL be marked "AI-reviewed, pending expert review"
   until a pharmacist or physician and a statistician review them (pre-launch checklist).

### Requirement 6: Data sources and build *(Added in refinement)*
1. THE `onsides` pipeline SHALL fetch the pinned OnSIDES v3.1.1 release (data CC BY 4.0, verified 2026-11-08), check its
   SHA-256, and store per-label rows with their effects as a cache artifact (never committed).
2. THE `openfda_label` pipeline SHALL fetch, for the validation-case ingredients only, the indications text of their US
   labels (CC0) as a cache artifact.
3. THE light build SHALL be a deterministic function of (OnSIDES run, openFDA run, counts file, Wikidata run, curated
   files): the same inputs give byte-identical output; the output records every input's version.
4. THE API SHALL fail closed (`503 light_unavailable`) when the build output is missing or has another schema version, and
   when the integrity snapshot cannot be read.
5. No ingredient, goal, term or count SHALL be logged (privacy steering); requests carry no user data.

## Properties to test (PBT candidates)
- A candidate never appears without at least one supporting signal and one non-retracted source.
- Adding unrelated reports never removes an existing candidate's supporting evidence.
- No card text contains forbidden treatment language in any supported language.
- The evaluation is deterministic for a fixed data snapshot.
- *(Added in refinement.)* Further properties P5–P16 in `design.md` §11 (inverse rule against an independent reference,
  ranking ties and permutation invariance, release never shows a cell under k, export holds only shown counts, loader
  refusals).

## Open items from collective-memory (2026-11-08)
- The researcher area reads the same counts file through `janus.memory.reader.CountsReader` (read-only, in process); there is
  no PT search endpoint in `collective-memory` (DP21). Inverse signals use the same statistics (`janus.memory.stats`): Yates
  chi-squared, Woolf interval, Haldane when a cell is zero, `MIN_REPORTS = 3`, and the sensitivity table with N = all reports.
  - *Resolved (design DP6, DP11):* the build opens the counts file read-only with the reader's settings and uses
    `janus.memory.stats` unchanged.
- Lists are ordered by report count, never by the ratio. Every inverse signal carries the screening sentence
  (`Memory.screening`), the limits sentences and the snapshot date and window. Reporting bias (notoriety, indication bias) is
  this spec's own warning. Evans criteria (Yates-corrected chi-squared) are screening criteria and 65 percent of examined pairs
  meet them: do not present them as findings.
  - *Resolved (Req 1.2, 1.3; design §7).* Evans criteria are not shown on cards at all; only the interval rule of Req 1.1.
