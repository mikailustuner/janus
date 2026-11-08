# Requirements: Cascade Engine ("Ghost Diseases")

> Refined 2026-11-07 for Phase 1 (`docs/internal/PLAN.md` Phase 1, gate 1). Requirements 1–4 are
> the original ones; every original criterion keeps its number and wording, with refinements as
> sub-bullets. Requirements 5–10 were added in the refinement. No original criterion or property
> was dropped. Criteria marked *(Added in refinement)* are new.
> Tags: **[Later phase: OnSIDES]** criteria stay here but are designed and built when the
> `onsides` pipeline exists (PLAN.md "Could" item 14). **[Phase 2: collective-memory]** criteria
> depend on the FAERS pipeline. **[Client: …]** criteria describe what a screen or document shows;
> this spec provides the data and the UI is built in the named spec.
> Phase 1 scope: the rule base (PIPC 65) with its curated ATC class mapping, the pure engine
> (matching, time logic, chains, warnings, statements), the rule-base loader, the evaluation API
> route and the PIPC coverage report. Inputs come from `drug-resolution`, evidence status from
> `evidence-integrity`.

## Introduction
Detect prescribing cascades in a user's medication list: drug A causes an adverse effect that is treated with drug B. Deterministic, explainable, fully cited, region-neutral (it only sees ingredient-level ATC codes from Drug Resolution). The LLM only explains results; it never decides them.

## Glossary
- **Index drug (A):** the drug whose adverse effect starts the cascade.
- **Marker drug (B):** the drug prescribed to treat that effect.
- **Rule:** (index ATC class, adverse effect, marker ATC class, source, priority). Primary rule base: PIPC list (65 cascades, CC BY 4.0); priority from the BMJ 2026 study where available.
- **Window:** maximum time between starting A and starting B for a "probable" finding (default 12 months, configurable; justification recorded in design).
- *(Added in refinement.)* **PIPC row:** one row of `data/pipc.csv` (Table 1 of Rochon et al. 2025), identified by its `position` 1–65. **Rule id:** `pipc:<position>`. **Rule evidence id:** `rule:pipc:<position>`.
- *(Added in refinement.)* **ATC class:** a named set of ATC prefix patterns (include and exclude) that stands for a PIPC drug class or individual drug, e.g. "Calcium channel blocker". Each rule has an index class and a marker class.
- *(Added in refinement.)* **Class mapping:** the curated, cited files that give each PIPC row its index and marker class and define each class's patterns (`data-pipelines` DP8).
- *(Added in refinement.)* **List item:** one medicine the user entered: a product (resolved by code or name) or an ingredient (found by name), with an optional start month.
- *(Added in refinement.)* **Ingredient key:** the Wikidata item id of an ingredient (`drug-resolution`). Findings are made per ingredient key, not per product.
- *(Added in refinement.)* **Rule input:** the ingredient-level ATC codes of a `mapped` ingredient, read only through `janus.resolution.model.rule_input`.
- *(Added in refinement.)* **Form-confirmed:** the ingredient's codes were selected with the product's own code or route (`atc_selection` `single_ingredient_product`, `therapeutic_group`, `anatomical_group`, `route_group`). **Form-unconfirmed:** the codes are all codes of the ingredient (`all_codes`), so the dosage form, and with it the route-specific code, is not known.
- *(Added in refinement.)* **Form extension:** a route-specific ATC group of a non-oral form that acts systemically (e.g. ophthalmic beta-blockers, `S01ED`), added to an index class with its own cited source.
- *(Added in refinement.)* **Start month:** the month and year the user gives for "since when?" (`YYYY-MM`), or unknown (`experience` Req 1.1).
- *(Added in refinement.)* **Finding:** one rule matched by one index ingredient and one different marker ingredient in the list. **Chain:** a sequence of findings in which the marker ingredient of one finding is the index ingredient of the next.
- *(Added in refinement.)* **Abrupt-stop list:** the curated ATC classes for which `medical-safety.md` rule 4 requires the warning "Do not stop this medicine suddenly."
- *(Added in refinement.)* **Rule base version:** a hash of the PIPC rows, the class mapping, the priority and support data, the abrupt-stop list, the window and the engine's rule code version.
- *(Added in refinement.)* **Coverage report:** the per-rule count of TİTCK and US products that resolve to an ingredient in each rule's index and marker classes, with the unmapped ingredient names that probably belong to those classes.

## Requirements

### Requirement 1: Rule base
#### Acceptance criteria
1. THE system SHALL load cascade rules from the PIPC list with a source reference for each rule.
   - *(Added in refinement.)* THE rule-base loader SHALL read the 65 rows of `data/pipc.csv`, SHALL verify their content hash against `data/pipc.meta.json`, and SHALL refuse a file with any other number of rows, a missing or repeated position, or a hash mismatch.
   - *(Added in refinement.)* EACH rule SHALL keep the row's published text (`system`, `kind`, `drug_a`, `adverse_event`, `drug_b`, `locator`) unchanged, and SHALL reference its rule evidence id `rule:pipc:<position>`.
   - *(Added in refinement.)* THE loader SHALL register one evidence record per rule (kind `rule`, source `pipc`, locator "Table 1, row n", basis `dataset:pipc`) through `janus.integrity.load.register_records`, in the same transaction as the rule base.
2. THE system SHALL support ATC prefix matching (a rule class `C08CA` matches ingredient `C08CA01`).
   - *(Added in refinement.)* A class pattern SHALL be a valid ATC prefix of level 1 to 5 (1, 3, 4, 5 or 7 characters). An ingredient code SHALL match a class if and only if the longest of the class's patterns that is a prefix of the code is an include pattern.
   - *(Added in refinement.)* IF a class pattern is a combination group or combination code of `data/atc_combination_rules.csv` THEN THE loader SHALL refuse the class mapping, because such codes never reach the engine.
3. THE system SHALL match rules only against ingredient-level ATC codes and SHALL reject combination ATC codes as input.
   - *(Added in refinement.)* THE engine SHALL read ingredient codes only through `rule_input` (the codes of `mapped` ingredients). Ingredients that are `ambiguous` or `unmapped` SHALL contribute no code (Requirement 7).
   - *(Added in refinement.)* IF a code passed to the engine is not of the form `^[A-Z][0-9]{2}[A-Z]{2}[0-9]{2}$` or is a combination code of the current resolution dataset THEN THE engine SHALL raise an error and the request SHALL fail with HTTP 500; it SHALL NOT drop the code silently. A product's published code SHALL never be passed to the engine.
4. WHEN a rule set is updated THE system SHALL record its version, and every finding SHALL reference the rule version used.
   - *(Added in refinement.)* THE rule base version SHALL be a deterministic hash of every input listed in the glossary; the same inputs SHALL give the same version and any change SHALL give a different one.
   - *(Added in refinement.)* THE system SHALL keep every loaded rule base version (they are small) and SHALL mark one as current. Every evaluation result SHALL carry the rule base version, the resolution dataset version and the integrity version it used.
5. WHEN a rule's source paper is flagged as retracted by Evidence Integrity THE system SHALL disable the rule and report why.
   - *(Added in refinement.)* FOR each request THE system SHALL read the integrity snapshot once (`load_snapshot`, in the request's read-only transaction) and SHALL call `rule_gate(["rule:pipc:<n>"], snapshot)` for every rule. A rule whose gate is disabled SHALL produce no finding.
   - *(Added in refinement.)* THE result SHALL list every disabled rule with the gate's reason (`no_source`, `all_sources_retracted`, `no_citable_source`) and its removed sources with their reasons and notices.
   - *(Added in refinement.)* A finding's evidence ids SHALL contain only citable ids (`gate.usable` and, for other ids, `cite`). THE gate keeps nothing between calls, so a rule returns as soon as its source is citable again.
   - *(Added in refinement.)* `corrected`, `expression_of_concern` and `unknown` sources stay citable (`evidence-integrity` DP4). Today `dataset:pipc` is `corrected` (publisher correction of 2025-12-18); its PIPC rules stay enabled and their findings SHALL carry the integrity codes of their evidence (e.g. `corrected_notice`).

### Requirement 2: Detection with time logic
**User story:** As a caregiver, I want to see which medicines may only be there to treat side effects of others, so that I can discuss them with the doctor.

#### Acceptance criteria
1. WHEN the list contains an ingredient matching a rule's index class and another matching its marker class THE system SHALL evaluate the pair.
   - *(Added in refinement.)* THE index and the marker SHALL be different ingredient keys. One ingredient SHALL never form a finding with itself.
   - *(Added in refinement.)* IF the index ingredient and the marker ingredient occur only in the same list items (for example both in one fixed-dose combination product) THEN THE system SHALL NOT report a finding for that pair, because they were started together by design, and SHALL list the pair as `same_product` in the result.
   - *(Added in refinement.)* Findings SHALL be made per (rule, index ingredient key, marker ingredient key). Several list items with the same ingredient key SHALL be merged: an ingredient matches a class if any of its items' codes match; its start month for that class SHALL be the earliest start month of the matching items when all of them are known, and unknown otherwise.
2. WHEN B started after A and within the window THE system SHALL report the finding as `probable`.
   - *(Added in refinement.)* Start months SHALL be compared as whole months: `d = month(B) − month(A)`. THE finding SHALL be `probable` with timing `within_window` WHEN `1 ≤ d ≤ window`.
   - *(Added in refinement.)* THE default window SHALL be 12 months, set in the rule-base loader (1–60 months) and stored in the rule base version. THE justification and its source SHALL be recorded in the design and the source registered as evidence; a `probable` finding SHALL carry that evidence id, and IF it is not citable THEN no finding SHALL be labelled `probable` (those findings become `possible` with the same timing).
   - *(Added in refinement.)* WHEN `d = 0` (same month) THE order is unknown and THE system SHALL report the finding as `possible` with timing `same_month`.
3. WHEN either start date is unknown THE system SHALL report the finding as `possible`.
   - *(Added in refinement.)* Timing `date_unknown`.
4. WHEN B started before A THE system SHALL NOT report the finding.
   - *(Added in refinement.)* That is, WHEN `d < 0`.
5. WHEN B started after A but outside the window THE system SHALL report `possible` with low priority.
   - *(Added in refinement.)* Timing `after_window`, `low_priority = true`.
6. WHEN findings A→B and B→C exist THE system SHALL also report the chain A→B→C.
   - *(Added in refinement.)* A chain SHALL be a maximal path of two or more links over different ingredient keys, where a link A→B exists when at least one finding has index A and marker B. THE chain SHALL list its findings per link; its status SHALL be `probable` only if every link has a `probable` finding, else `possible`.
   - *(Added in refinement.)* Findings SHALL still be reported one by one; a chain only groups them. THE number of chains SHALL be bounded (design); IF the bound is reached THEN THE result SHALL say so with the notice `chains_truncated`.
7. Each finding SHALL include evidence ids (rule, source paper, and where available a FAERS statistic).
   - *(Added in refinement.)* THE evidence ids SHALL include the rule (`rule:pipc:<n>`) and the source paper (`dataset:pipc`, the PIPC article with its DOI), plus, where they apply and are citable, the window source (Req 2.2), the BMJ 2026 paper (Req 6.1), supporting papers (Req 6.2) and the form-extension source (Req 7.4).
   - **[Phase 2: collective-memory]** *(Owner decision 2026-11-08, DP22.)* FAERS is cited by the dataset record `dataset:faers` with a locator `faers:ingredient=…;event=…;region=ALL;scope=suspect` (field `faers_locator`), not by `faers_stat:` ids; added when the rule has a reviewed Janus event key.
8. Medicines bought without prescription (e.g. laxatives, painkillers) SHALL be accepted as list items, because many marker drugs are over-the-counter.
   - *(Added in refinement.)* THE engine SHALL NOT filter by product type, prescription status or region. US OTC products (`HUMAN OTC DRUG`), TİTCK products and ingredients found by name SHALL be evaluated the same way.
   - **[Client: experience]** Adding OTC medicines and supplements by name.
9. *(Added in refinement.)* EVERY finding SHALL state its rule id and the PIPC row's published text, its index and marker ingredient keys with the list items and matched codes they came from, its status, timing, months between starts (when known), `low_priority`, whether both ingredients are form-confirmed, whether a form extension was used, its priority data (Req 6.1), its abrupt-stop warnings (Req 4.1) and its evidence ids and integrity codes.
10. *(Added in refinement.)* THE result SHALL be sorted deterministically: `probable` before `possible`; then timing (`within_window`, `date_unknown`, `same_month`, `after_window`); then form-confirmed before form-unconfirmed; then BMJ-named before others; then rule position and ingredient keys.

### Requirement 3: Exploratory label-based mode
**[Later phase: OnSIDES]** The `onsides` pipeline does not exist yet. These criteria are kept and designed when it does; Phase 1 builds no exploratory code and its API does not accept an exploratory option.

#### Acceptance criteria
1. WHERE exploratory mode is enabled, WHEN an OnSIDES adverse effect of A matches an indication of B THE system SHALL report an `exploratory` finding, visually separate from rule-based findings.
   - *(Added in refinement.)* Exploratory findings SHALL be returned in a separate list, never merged into rule-based findings, and SHALL carry their own evidence ids (OnSIDES, openFDA label) gated the same way.
2. Exploratory findings SHALL never be included in the doctor note's main section.

### Requirement 4: Safety and wording
#### Acceptance criteria
1. WHEN a finding involves a drug class on the abrupt-stop list THE system SHALL attach a "do not stop suddenly" warning.
   - *(Added in refinement.)* THE abrupt-stop list SHALL be a curated file of ATC classes covering at least the classes named in `medical-safety.md` rule 4 (beta-blockers, antiepileptics, corticosteroids, benzodiazepines, antidepressants, clonidine), matched with the same pattern rules as Req 1.2, on systemic forms.
   - *(Added in refinement.)* THE warning SHALL be attached to the finding for each of its two ingredients that matches the list. THE result SHALL also flag every list item with an ingredient on the list, whether or not it is in a finding (`medical-safety.md` rule 4: "always show"), so the doctor note can show the warning next to the medicine (`doctor-loop` Req 1.1).
   - *(Added in refinement.)* THE warning SHALL be a fixed code (`do_not_stop_suddenly`) with the canonical English sentence "Do not stop this medicine suddenly."; the five-language wording belongs to the client. **[Client: experience / doctor-loop]**
2. THE engine output SHALL contain no recommendation to start, stop or change any medicine, and SHALL describe findings as matching a published pattern.
   - *(Added in refinement.)* THE result SHALL carry codes and data only, apart from the published PIPC text, the fixed statements of Req 4.3 and 4.1 and the disclaimer. Every finding SHALL carry the code `matches_published_pattern`.
   - *(Added in refinement.)* No response text SHALL contain a forbidden phrase of `medical-safety.md` rule 2 in any of the five languages, or a reassurance word ("safe", "no problems", "all clear"); tests SHALL enforce this.
   - *(Added in refinement.)* Every result SHALL carry the disclaimer "Janus provides information, not medical advice. Research prototype - not a medical device." (`medical-safety.md` rule 9).
3. WHEN no finding is produced THE system SHALL return the "no pattern found — not a guarantee" statement, never a reassurance.
   - *(Added in refinement.)* THE statement SHALL be the code `no_pattern_found` with the canonical sentence of `medical-safety.md` rule 3: "Janus found no pattern from its rule list. This does not mean your medicines are free of problems."
   - *(Added in refinement.)* THE result SHALL also say how much was checked: the number of rules checked, the disabled and not-matchable rules, and the list items and ingredients that could not be checked (Req 7.2), so the statement never covers more than was checked.
   - *(Added in refinement.)* IF no rule is enabled THEN THE system SHALL return the code `rule_base_unavailable` instead, and SHALL NOT return `no_pattern_found`.
   - *(Added in refinement.)* **Emergency symptoms** (`medical-safety.md` rule 10) are not engine input in Phase 1 (the user enters medicines, not symptoms); the client shows the emergency notice where symptoms are entered. **[Client: experience]**

### Requirement 5: Curated class mapping (added in refinement)
**User story:** As the owner, I want every PIPC drug class translated into ATC codes in one reviewable, cited place, so that I can check each clinical judgement before the engine uses it.

#### Acceptance criteria
1. THE class mapping SHALL be curated files under `data/`, drafted by the pharmacologist agent and reviewed by the owner before any engine task runs. It SHALL hold ATC codes and Janus's own notes only; no WHO ATC index text SHALL be copied.
2. EACH of the 65 PIPC rows SHALL have exactly one index class and one marker class, or SHALL be marked not matchable for that role with a reason (e.g. a class with no ATC code). Not-matchable rules SHALL never produce a finding and SHALL be listed in every result and in the coverage report.
3. EACH class pattern SHALL record its basis: where the code membership was checked (WHOCC ATC/DDD Index page URL and lookup date for manually checked rows, or the source of the codes: TİTCK, Wikidata, RxClass) and a note on the clinical judgement (e.g. "systemic forms only").
4. Classes that PIPC names with the same words SHALL use one class definition per role unless the note says why they differ (e.g. "Beta-blocker" as index includes the ophthalmic form extension, as marker it does not).
5. IF the class mapping has a defect (unknown position, a position missing or repeated, unknown class, invalid or combination pattern, the same pattern twice in a class, a class with no include pattern, a form extension without a registered source or used in a marker role) THEN THE loader SHALL refuse it with a specific code and change nothing.
6. Published PIPC text that looks inconsistent SHALL be kept as published and interpreted in the mapping note (e.g. row 49, Drug B "Vitamin or Mineral Deficiency", read as vitamin or mineral supplements), for owner review.

### Requirement 6: Priority and supporting sources (added in refinement)
#### Acceptance criteria
1. THE system SHALL use BMJ 2026 (Rochon et al., BMJ 2026;394:e100499, doi:10.1136/bmj-2026-100499) priority only for cascades named in its abstract. For each such PIPC row the rule base SHALL record the measure the abstract gives (incidence or adjusted sequence ratio), its value and 95% CI, and the locator "Abstract, Results", with evidence id `paper:bmj_2026:e100499`.
   - THE system SHALL describe these rows as "named in the BMJ 2026 abstract" with their measure, and SHALL NOT call them members of the paper's prioritised list of 24, because the abstract does not list that set.
   - A finding SHALL show the priority data only while the BMJ paper is citable; the rule itself rests on PIPC and SHALL NOT be disabled or enabled by the BMJ paper's status.
2. THE system SHALL add the DOIs of BMJ 2026 and ThinkCascades (McCarthy et al., Drugs Aging 2022;39(10):829–840, doi:10.1007/s40266-022-00964-9) to `data/evidence_papers.csv` so the `retractions` pipeline checks them and the integrity loader registers them. A PIPC rule that describes the same cascade as a ThinkCascades cascade SHALL list `paper:thinkcascades:…` as a supporting evidence id; ThinkCascades SHALL be cited only (restricted licence), never copied.
3. Every other paper the rule base cites (the window source, Req 2.2; form-extension sources, Req 7.4) SHALL be added to `data/evidence_papers.csv` with a source entry in `pipelines/sources.toml`, so that it is checked for retraction like any other source.
   - *(Owner decision, 2026-11-07.)* BEFORE a paper is added THE system's maintainers SHALL verify that its DOI exists in Crossref and that the title, authors, journal and year match; IF a DOI cannot be verified THEN the paper SHALL NOT be cited and anything resting on it SHALL be removed.
4. *(Owner decision, 2026-11-07, DP18.)* THE ThinkCascades cascades that are not in PIPC SHALL NOT be added as rules.

### Requirement 7: Input contract and labelling (added in refinement)
#### Acceptance criteria
1. THE engine SHALL take, per list item, the ingredient key and the rule-input codes of each `mapped` ingredient, whether those codes are form-confirmed, and the item's start month. It SHALL take nothing region-specific: TR, EU and US products with the same ingredients, codes and start months SHALL give the same result.
2. WHEN an ingredient is `ambiguous` or `unmapped` THE result SHALL list it as not checked, with its list item, position and reason. IF the user chose one of an ambiguous ingredient's key candidates THEN THE system SHALL evaluate that key with all its ingredient-level codes, as form-unconfirmed.
   - *(Owner decision, 2026-11-07.)* WHEN a product is homeopathic (drug-resolution Req 11.1) THE engine SHALL NOT evaluate any of its ingredients and SHALL list each as not checked with reason `homeopathic_product`.
3. WHEN a finding rests on a form-unconfirmed ingredient (`atc_selection = all_codes`, an ingredient found by name, or a user's choice under 7.2) THE finding SHALL be labelled `form_confirmed = false` and SHALL name the matched codes, so the client can ask the user to confirm the product. Such findings SHALL keep their status and SHALL sort after form-confirmed ones.
4. A non-oral form that acts systemically SHALL belong to an index class only as a form extension: a route-specific ATC group (for example ophthalmic beta-blockers, `S01ED`) whose systemic adverse effect is the rule's adverse event, documented by a registered, citable source. Findings that match only through a form extension SHALL carry `via_form_extension = true` and that source's evidence id; IF that source is not citable THEN the extension SHALL not match. Marker classes SHALL contain the forms used to treat the adverse event (which may be topical, e.g. topical corticosteroids, vaginal antifungals) and SHALL have no form extensions.
5. THE route map of `drug-resolution` (`data/route_atc_groups.csv`) SHALL stay unchanged; form extensions live in the class mapping only.

### Requirement 8: PIPC coverage report (added in refinement)
**User story:** As the owner, I want to know for every rule how many real products in Türkiye and the US can trigger it, and which unmapped ingredient names would, so that synonyms are added where they matter most.

#### Acceptance criteria
1. THE system SHALL provide a command that reads the current resolution dataset and the current rule base and writes a coverage report with, for every rule and each role (index, marker): the number of distinct ingredient keys in the class, the number of TİTCK products and of US products (split by product type, Rx and OTC shown separately) with at least one mapped ingredient whose rule-input codes match the class, and the class members that have no product in each region.
2. THE report SHALL list, per rule and role, the unmapped or ambiguous ingredient names that probably belong to the class, with their number of products per region, ranked by that number: names on TİTCK products whose published ATC code (any level, including combination codes, used here only as a hint) falls in the class, and names similar to a label or alias of a class member.
3. THE report SHALL use the engine's matching function; it SHALL NOT have a second implementation of class matching. Hints SHALL never be used for findings.
4. THE report SHALL mark marker classes whose members are commonly over-the-counter (e.g. laxatives, analgesics, antihistamines, antidiarrhoeals) and show their OTC product counts first.
5. THE report SHALL be written to the data directory (`$JANUS_DATA_DIR/cascades/`), never into the repository, because it contains TİTCK names; the command SHALL print and log counts only.
6. THE report SHALL list the rules that cannot fire in a region (a role with no product there) and the not-matchable rules.

### Requirement 9: Evaluation API, privacy and determinism (added in refinement)
#### Acceptance criteria
1. THE API SHALL offer `POST /cascades/evaluate` as a medical route (JSON body only, `no-store`, read-only transaction, body limit of the privacy spec). THE body SHALL hold the resolution dataset version the client resolved against and 1–50 list items; each item SHALL be a product candidate id (with optional choices for ambiguous ingredients) or an ingredient key, and an optional start month `YYYY-MM`.
2. THE server SHALL re-resolve product items and ingredient items from the current resolution dataset and SHALL read codes through `rule_input`; the client SHALL NOT send ATC codes. IF the dataset version differs from the current one THEN THE API SHALL answer 409 `dataset_version_mismatch` so the client re-resolves its items.
3. IF a body is invalid (unknown candidate id or ingredient key, a choice that is not a key candidate of an ambiguous ingredient, a start month that is malformed, before 1900-01 or after the current month, more than 50 items, extra keys) THEN THE API SHALL answer 422 `invalid_request` naming the failing fields only, without echoing any value.
4. IF the rule base, the resolution dataset or the evidence is not loaded THEN THE API SHALL answer 503 `cascades_unavailable` and SHALL produce no finding and no `no_pattern_found` statement.
5. THE server SHALL NOT persist the list, the start months or the result, and SHALL NOT log any of them, or any ingredient, code, product id or rule id of a request (`privacy.md`). Logs SHALL carry request id, route, status and latency only.
6. THE same request against the same rule base, dataset, evidence and month SHALL give a byte-identical response. Permuting the list items SHALL give the same findings (up to item numbering).
7. THE evaluation of a 15-item list SHALL take less than one second on the server (PLAN.md §1).
8. Gate 1 (PLAN.md Phase 1): the Istanbul synthetic patient (9 medicines, one of them AMLIPIN, amlodipine + lisinopril, `C09BB03`) SHALL produce the cascade that starts from the amlodipine inside the combination product, through the API, end to end.

### Requirement 10: Rule-base loading and tests per rule (added in refinement)
#### Acceptance criteria
1. THE rule-base loader (`python -m janus.cascades.load`) SHALL validate all inputs before writing, SHALL write the rule base, the current pointer and the rule evidence records in one transaction, and IF anything fails THEN the stored state SHALL be as before.
2. WHEN the loader is run again on unchanged inputs THE stored data SHALL be unchanged.
3. THE tables SHALL be created by a forward-only Alembic migration with a downgrade, SHALL hold no user data, and SHALL be written only by the loader (import-boundary test).
4. FOR each of the 65 rules THE tests SHALL include at least one positive and one negative example (PLAN.md §1); a not-matchable rule's test SHALL show it never fires and is reported.

## Properties to test (PBT candidates)
- **Order independence:** permuting the medication list yields the same set of findings.
- **Monotonicity:** adding an ingredient that matches no rule never removes or changes existing findings.
- **Temporal soundness:** no finding is ever reported where B started before A.
- **Date refinement:** replacing an unknown date with a known date can only change `possible` to `probable` or remove the finding; it never creates an unrelated finding.
- **Duplicate invariance:** listing the same ingredient twice (e.g. two brands, or brands from two regions) does not duplicate findings.
- **Region invariance:** the same ingredients with the same dates give the same findings whether they were resolved from TR, EU or US products.
- **Evidence completeness:** every finding has at least one non-retracted evidence id with a source URL.
- Added in refinement:
  - Class matching follows the longest matching pattern, for any patterns and codes; adding an ingredient with a new key never removes or changes existing findings. (Req 1.2, 2.1)
  - A combination code or malformed code passed to the engine is always refused, never matched. (Req 1.3)
  - No finding pairs an ingredient with itself or two ingredients that occur only in the same items. (Req 2.1)
  - Status and timing follow the month table exactly, including the window boundary and the same month. (Req 2.2–2.5)
  - Chains are maximal paths over reported findings, without repeated ingredients, with the weakest-link status, independent of list order. (Req 2.6)
  - A disabled rule never produces a finding; retracting any record only removes findings, priorities, extensions and `probable` labels, never adds them. (Req 1.5, 2.2, 6.1, 7.4)
  - A finding carries the abrupt-stop warning exactly for its ingredients on the list, and every list item on the list is flagged. (Req 4.1)
  - `no_pattern_found` appears exactly when there is no finding and at least one rule is enabled; no response contains a forbidden phrase or a reassurance word. (Req 4.2, 4.3)
  - Ambiguous and unmapped ingredients are always reported as not checked and never contribute; form-unconfirmed codes are always labelled. (Req 7.2, 7.3)
  - Invalid class mappings and rule-base inputs are refused with a specific code; the rule base version is deterministic. (Req 1.4, 5.5, 10.1)
  - Every rule fires on codes inside its classes with dates in the window, and does not fire outside them. (Req 10.4)
  - The coverage report's counts equal an independent recount and its hints never contain mapped names. (Req 8)
  - The evaluation route is stateless, logs nothing of the request, echoes no input, and gives identical bytes for identical requests. (Req 9)
  - *(Owner decision 2026-11-07.)* A homeopathic product never contributes to a finding, a chain or an abrupt-stop warning. (Req 7.2)

## Open items from drug-resolution (2026-11-07)
- **Input contract.** Read ingredient codes only through `janus.resolution.model.rule_input`
  (ingredient-level ATC codes of `mapped` ingredients). Codes selected as `all_codes` are not
  confirmed by a product code or a route and are less specific than `single_ingredient_product`,
  `therapeutic_group`, `anatomical_group` or `route_group`; decide how findings built on them are
  labelled.
  - *Resolved in refinement:* Req 7.1–7.3 (form-unconfirmed label, same status, sorted after
    confirmed findings); design DP7.
- **Non-oral forms that act systemically (owner, 2026-11-07).** Some cascades start from
  products that are not taken by mouth but act systemically, e.g. timolol eye drops (`S01ED…`)
  causing bronchospasm or bradycardia. Drug resolution gives such products only their route's
  codes (an ophthalmic timolol carries `S01ED01`, not `C07AA06`). The rule base must decide
  whether each rule's index-drug classes also include such codes (e.g. `S01ED` alongside `C07`).
  The route map stays as it is.
  - *Resolved in refinement:* Req 7.4–7.5 (form extensions with their own cited source, index
    role only); design DP8 with the clinical justification.

## Open items from evidence-integrity (2026-11-07)
- **Rule gate contract (Req 1.5).** Read the integrity snapshot once per request with
  `janus.integrity.repository.load_snapshot(conn)` (inside the same read-only transaction) and pass
  it to the pure functions. For each rule call `janus.integrity.gate.rule_gate(source_ids,
  snapshot)`: a disabled rule (`gate.enabled` false) produces no finding, and `gate.reason`
  (`no_source`, `all_sources_retracted`, `no_citable_source`) with `gate.removed` (ids, reasons and
  the retraction notices) is the "why". Put only `gate.usable` into a finding's evidence ids. The
  gate keeps nothing between calls, so a rule returns when a source becomes citable again.
  - *Resolved in refinement:* Req 1.5.
- **Evidence records for rules.** Register one `rule:pipc:<position>` record per PIPC row with
  `register_records` (`janus.integrity.load`), basis `dataset:pipc` (and the BMJ 2026 paper where
  a rule takes its priority from it, added to `data/evidence_papers.csv` with its DOI so the
  `retractions` pipeline checks it). A `rule` record without basis is refused.
  - *Resolved in refinement:* Req 1.1, 6.1. The BMJ paper is not a basis of the rule record: a
    rule's existence rests on PIPC alone, and the BMJ paper only gates the priority data
    (design DP5).
- **Outputs.** Carry `snapshot.version()` (the integrity version) next to the rule-base version in
  every result. Use `cite(snapshot, ids)` and `keep_output(snapshot, ids)` for any finding,
  sentence or card; only `retracted` removes a record, `corrected`, `expression_of_concern` and
  `unknown` stay citable with their notice or status (evidence-integrity DP4).
  - *Resolved in refinement:* Req 1.4, 1.5, 2.7.
- **Status today.** The PIPC list (`dataset:pipc`) is `corrected` (a publisher correction notice
  of 2025-12-18). It stays citable and its notice is returned with every PIPC rule.
  - *Resolved in refinement:* Req 1.5 (integrity codes on every finding).

## Open items from collective-memory (2026-11-08)
- Done (DP22): `RuleBase.faers_event_keys` (PIPC position -> Janus event key of the active vocabulary,
  `apps/api/janus/memory/memory_events.csv`), `Finding.faers_locator`, and `dataset:faers` in `evidence_ids` through the existing
  `cite`. The locator names the index ingredient, the Janus key, region ALL and scope `suspect`. The numbers come from
  `POST /memory/pair`; the finding itself carries no FAERS figure.
