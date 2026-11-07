# Requirements: Cascade Engine ("Ghost Diseases")

> Draft seed. Refine with Kiro, then let Kiro generate `design.md` and `tasks.md`.

## Introduction
Detect prescribing cascades in a user's medication list: drug A causes an adverse effect that is treated with drug B. Deterministic, explainable, fully cited, region-neutral (it only sees ingredient-level ATC codes from Drug Resolution). The LLM only explains results; it never decides them.

## Glossary
- **Index drug (A):** the drug whose adverse effect starts the cascade.
- **Marker drug (B):** the drug prescribed to treat that effect.
- **Rule:** (index ATC class, adverse effect, marker ATC class, source, priority). Primary rule base: PIPC list (65 cascades, CC BY 4.0); priority from the BMJ 2026 study where available.
- **Window:** maximum time between starting A and starting B for a "probable" finding (default 12 months, configurable; justification recorded in design).

## Requirements

### Requirement 1: Rule base
#### Acceptance criteria
1. THE system SHALL load cascade rules from the PIPC list with a source reference for each rule.
2. THE system SHALL support ATC prefix matching (a rule class `C08CA` matches ingredient `C08CA01`).
3. THE system SHALL match rules only against ingredient-level ATC codes and SHALL reject combination ATC codes as input.
4. WHEN a rule set is updated THE system SHALL record its version, and every finding SHALL reference the rule version used.
5. WHEN a rule's source paper is flagged as retracted by Evidence Integrity THE system SHALL disable the rule and report why.

### Requirement 2: Detection with time logic
**User story:** As a caregiver, I want to see which medicines may only be there to treat side effects of others, so that I can discuss them with the doctor.

#### Acceptance criteria
1. WHEN the list contains an ingredient matching a rule's index class and another matching its marker class THE system SHALL evaluate the pair.
2. WHEN B started after A and within the window THE system SHALL report the finding as `probable`.
3. WHEN either start date is unknown THE system SHALL report the finding as `possible`.
4. WHEN B started before A THE system SHALL NOT report the finding.
5. WHEN B started after A but outside the window THE system SHALL report `possible` with low priority.
6. WHEN findings A→B and B→C exist THE system SHALL also report the chain A→B→C.
7. Each finding SHALL include evidence ids (rule, source paper, and where available a FAERS statistic).
8. Medicines bought without prescription (e.g. laxatives, painkillers) SHALL be accepted as list items, because many marker drugs are over-the-counter.

### Requirement 3: Exploratory label-based mode
#### Acceptance criteria
1. WHERE exploratory mode is enabled, WHEN an OnSIDES adverse effect of A matches an indication of B THE system SHALL report an `exploratory` finding, visually separate from rule-based findings.
2. Exploratory findings SHALL never be included in the doctor note's main section.

### Requirement 4: Safety and wording
#### Acceptance criteria
1. WHEN a finding involves a drug class on the abrupt-stop list THE system SHALL attach a "do not stop suddenly" warning.
2. THE engine output SHALL contain no recommendation to start, stop or change any medicine, and SHALL describe findings as matching a published pattern.
3. WHEN no finding is produced THE system SHALL return the "no pattern found — not a guarantee" statement, never a reassurance.

## Properties to test (PBT candidates)
- **Order independence:** permuting the medication list yields the same set of findings.
- **Monotonicity:** adding an ingredient that matches no rule never removes or changes existing findings.
- **Temporal soundness:** no finding is ever reported where B started before A.
- **Date refinement:** replacing an unknown date with a known date can only change `possible` to `probable` or remove the finding; it never creates an unrelated finding.
- **Duplicate invariance:** listing the same ingredient twice (e.g. two brands, or brands from two regions) does not duplicate findings.
- **Region invariance:** the same ingredients with the same dates give the same findings whether they were resolved from TR, EU or US products.
- **Evidence completeness:** every finding has at least one non-retracted evidence id with a source URL.

## Open items from drug-resolution (2026-11-07)
- **Input contract.** Read ingredient codes only through `janus.resolution.model.rule_input`
  (ingredient-level ATC codes of `mapped` ingredients). Codes selected as `all_codes` are not
  confirmed by a product code or a route and are less specific than `single_ingredient_product`,
  `therapeutic_group`, `anatomical_group` or `route_group`; decide how findings built on them are
  labelled.
- **Non-oral forms that act systemically (owner, 2026-11-07).** Some cascades start from
  products that are not taken by mouth but act systemically, e.g. timolol eye drops (`S01ED…`)
  causing bronchospasm or bradycardia. Drug resolution gives such products only their route's
  codes (an ophthalmic timolol carries `S01ED01`, not `C07AA06`). The rule base must decide
  whether each rule's index-drug classes also include such codes (e.g. `S01ED` alongside `C07`).
  The route map stays as it is.
