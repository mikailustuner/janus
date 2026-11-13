# Cascade detection validation: pre-registered protocol

Status: registered before any reference data was collected and before Janus was run on it. The git commit
that adds this file, pushed to the public repository, is its timestamp; its SHA-256 is recorded in
`docs/research/cascade-validation.md` next to the results. Any change after registration is listed there
as a deviation, with its reason.

## 1. Question

Does the Janus cascade engine flag published prescribing cascades (drug A → adverse event → drug B), and
does it stay silent for drug pairs that are not cascades?

## 2. Index test (frozen)

- The cascade engine as of the registration commit (`apps/api/janus/cascades/`), with its rule base:
  `data/pipc.csv`, `data/cascade_classes.csv`, `data/cascade_priority.csv`. Their SHA-256 values at
  registration are recorded in the results file; these files are not changed until the evaluation ends.
- Positive call (pair level): the engine reports a cascade finding whose index side holds drug A and
  whose marker side holds drug B, when given A and B as the only medicines, A started before B.
- Positive call (case level): the expected cascade is among the engine's findings for the case's full
  medication list.
- No setting, rule or mapping is tuned on the reference data.

## 3. Reference standard

### 3.1 Positive pairs

Published, named prescribing cascades from sources **independent of the PIPC list** (Rochon et al. 2025,
the source of the rule base): systematic and scoping reviews of prescribing cascades, prescription
sequence symmetry analysis studies reporting an adjusted sequence ratio with a lower 95 % bound above 1,
and published cascade lists other than PIPC. The PIPC paper and documents derived from it are excluded
as sources; a cascade that also appears in PIPC is still included when an independent source reports it.

Inclusion: drug A, the adverse event and drug B are named; A is reported to cause the event; B is
reported as prescribed for it; A and B map to WHO ATC codes. Only the fact (A, event, B) is recorded,
with the citation and the location in the source (table, row or section); no text is copied.

Ingredient choice: when the source names ingredients, those are used. When it names a class, the
ingredient named first in the source's text for that class is used; when none is named, the ingredient
with the lowest WHO ATC code in that class. Each pair is recorded at ingredient level with ATC codes.

Duplicates: the same (A ingredient, B ingredient) pair counts once; the number of independent sources
per pair is kept.

### 3.2 Negative pairs

Two per positive pair, by a fixed rule with a fixed random seed (recorded with the set): keep drug A;
draw B′ uniformly from WHO ATC ingredient codes that share B's first ATC level and differ at the third
level. B′ is redrawn when (a) any adverse event listed for A in OnSIDES is an indication of B′ in its
US label (a possible cascade), or (b) (A, B′) is a positive pair. Neither OnSIDES nor the labels are
part of Janus's cascade rule base.

### 3.3 Cases

- Cascade cases: at least 40 case reports with an open licence in PubMed Central that describe a
  prescribing cascade and list the patient's medicines. Recorded per case: the medication list at the
  time the cascade was recognised, the expected cascade (A, event, B), citation and location.
- Comparison cases: at least 40 open-licence PMC case reports on other topics that list the full
  medication list of a patient aged 65 or over and do not describe a prescribing cascade.

### 3.4 Separation of steps

The reference set is built in a separate step that has no access to the rule base files, the engine or
its output. It is completed, hashed and committed before Janus is run on it. The step that runs Janus
does not change the reference set; disagreements found afterwards are reported, not corrected.

## 4. Outcomes and hypotheses

Primary (pair level, 95 % Wilson intervals):

- H1: sensitivity = flagged positive pairs / all positive pairs. Met if the lower bound is ≥ 0.80.
- H2: specificity = unflagged negative pairs / all negative pairs. Met if the lower bound is ≥ 0.90.

Secondary:

- PPV and NPV at pair level. The 1:2 ratio is fixed by design, so these depend on it; they are reported
  for that ratio only and not as clinical predictive values.
- Case-level detection rate on cascade cases (Wilson interval).
- Alert rate on comparison cases: share of cases with at least one finding (Wilson interval). It is not
  called specificity: a report that does not describe a cascade does not prove there is none.
- Sensitivity within the rule base's scope: positive pairs whose (A class, B class) appears in PIPC.
  This analysis uses the rule base and is labelled exploratory.
- Error table for every missed positive and every flagged negative: name or code resolution failure,
  ingredient outside the mapped class, cascade absent from the rule base, timing, rule disabled by the
  evidence gate, other.

## 5. Sample size

With an expected sensitivity of 0.90, 80 positive pairs give a 95 % Wilson lower bound of about 0.81;
with an expected specificity of 0.97, 160 negative pairs give a lower bound of about 0.93. Target: at
least 80 positive pairs (160 negative), 40 cascade cases, 40 comparison cases. If fewer positive pairs
meet the inclusion rules, the achieved number and its interval width are reported; the hypotheses are
not changed.

## 6. Analysis

All counts and intervals are computed by a script committed with the results; the script reads only the
frozen reference set and the engine output. Pairs reported by several sources count once. A sensitivity
analysis repeats H1 counting one pair per cascade (A class, B class) to limit the weight of classes with
many ingredients. Results are reported whether or not the hypotheses are met.

## 7. Limits stated in advance

- Published cascades over-represent well-known ones; sensitivity on them may exceed sensitivity on rare
  cascades.
- Negative pairs are constructed, not observed; specificity on them is a property of this construction.
- The reference set is assembled by an automated literature step, not by clinicians. Expert review has not
  yet been done; the reference set is part of the expert validation packet.
