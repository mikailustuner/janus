# Requirements: Weekly data-quality report

> Owner request 2026-11-09: real, continuing research value, not a showcase. Builds on the drug-resolution ATC review
> (`.kiro/specs/drug-resolution/atc-code-review.md`: 93 TİTCK/Wikidata key-code pairs with no common level-4 group,
> 12 confirmed errors in `data/atc_code_exclusions.csv`) and on `docs/contributing-corrections.md`. The web screen is
> built later by the `experience` step from the API contract in design §9; this spec does not touch `apps/web`.

## Introduction
Janus resolves medicines through five sources that each publish identity fields for ingredients: TİTCK (Türkiye),
Wikidata, openFDA NDC (US), BDPM (France) and AEMPS CIMA (Spain). When they disagree on which ATC code belongs to an
ingredient, a medicine can land in the wrong cascade class. A one-off review found twelve errors. This feature turns
that review into a weekly, versioned, open report: every run compares the sources again, classifies each difference,
says what is new, what persists and what was resolved since the previous run, and publishes the result without
republishing anything whose terms forbid it.

## Glossary
- **Key:** a Janus ingredient key (a Wikidata item id, or a curated `J…` key of `data/janus_ingredients.csv`).
- **Item codes:** the ATC codes the key's item gives (Wikidata P267, or the curated row), before exclusions.
- **Observation:** (source, key, code, number of products): a code a regulator publishes on single-ingredient
  products whose one ingredient maps to the key.
- **Level-4 group:** the first five characters of an ATC code (e.g. `R06AE`).
- **Finding:** one difference found by a check, with a stable id `check:source:key:code`.
- **Class:** `confirmed_error`, `needs_pharmacist` or `benign_difference`.
- **Run:** one execution of the build; the previous run is the one `current` pointed to before.

## Requirements

### Requirement 1: Checks
1. THE build SHALL report each row of `data/atc_code_exclusions.csv` as a `confirmed_error` finding and SHALL state
   whether its source still publishes the code for the key (`persisting`) or no longer does (`resolved_upstream`).
2. WHEN a regulator (TİTCK, CIMA) publishes on single-ingredient products of a key a code that shares no level-4
   group with any item code of that key, THE build SHALL report an `item_group` finding, unless the (key, code,
   source) triple is a confirmed error (it is reported under 1.1).
3. WHEN a key has single-ingredient products in both regulators and no TİTCK code shares a level-4 group with any
   CIMA code, THE build SHALL report a `regulator_group` finding.
4. WHEN one substance code of BDPM or CIMA has published names that map to two or more keys, THE build SHALL report
   a `substance_code_keys` finding.
5. THE build SHALL state that openFDA NDC publishes no ATC code and only product-level RxCUIs and SHALL use it for
   presence counts only.
6. THE checks SHALL be pure functions of counts; the order of the input products SHALL NOT change the findings.

### Requirement 2: Classification
1. A finding SHALL be `confirmed_error` IF AND ONLY IF its (key, code, source) is a row of the exclusions file.
2. An `item_group` finding SHALL be `benign_difference` only WHEN both regulators publish the code for the key on
   single-ingredient products, no other key carries the code and the code is not a combination code; otherwise it
   SHALL be `needs_pharmacist`.
3. `regulator_group` and `substance_code_keys` findings SHALL be `needs_pharmacist`.
4. EACH finding SHALL carry machine-readable reasons (e.g. `code_of_other_substance`,
   `combination_code_on_single_ingredient_product`, `both_regulators_publish_it`, `same_level2_group`).
5. No rule SHALL call a difference an error unless a person confirmed it (the exclusions file).

### Requirement 3: Diff against the previous run
1. EACH current finding SHALL be `new` (absent from the previous run) or `persisting` (present in it).
2. EVERY finding of the previous run that is absent now SHALL be listed as `resolved` with the record it had.
3. WHEN a persisting finding changed class, THE record SHALL name the previous class.
4. THE first run SHALL report every finding as `new`.

### Requirement 4: Evidence and licences
1. EACH finding SHALL carry the codes it was compared with, the number of products that showed it, the WHOCC group
   page addresses of the codes (addresses only; no WHOCC text), the Wikidata address of a Q-key and how to find the
   finding at its source.
2. THE report SHALL NOT contain any TİTCK list row, product name, barcode or ingredient spelling; for TİTCK it SHALL
   give the key, the code, the product count and how to find it in the current list.
3. THE report SHALL name each source's run, snapshot date and licence, the resolution dataset version and the code
   version.
4. THE report SHALL be released under CC BY 4.0 with an attribution that names Wikidata (CC0), CIMA (AEMPS, reuse
   with attribution), BDPM (not altered, no endorsement) and states that no TİTCK row is included.

### Requirement 5: Versioned outputs
1. EACH run SHALL write `report.json`, `findings.csv` and `summary.md` under
   `<JANUS_DATA_DIR>/quality/runs/<run_id>/` and SHALL then move `quality/current` to it in one step.
2. THE report version SHALL be the rule version plus a hash of the findings: equal findings give an equal version
   and different findings a different one.
3. WITH `--publish`, THE build SHALL also write the open copy `data/open/data-quality/` (the three files and a
   Frictionless `datapackage.json` with a hash per file) for the repository.
4. THE CSV SHALL have one row per finding (resolved included) with the version in every row.

### Requirement 6: Read-only API
1. THE API SHALL serve `GET /open/data-quality` (JSON), `GET /open/data-quality.csv` and `GET /open/data-quality.md`
   from the current run, read once, with nothing computed per request.
2. WHEN no report is installed or the file does not match the contract, THE routes SHALL answer 503
   `data_quality_unavailable`.
3. THE routes SHALL be medical routes (no-store, nothing logged but the access line) and SHALL be in the public API
   document `docs/openapi-public.json`.

### Requirement 7: Weekly cadence
1. THE source registry `pipelines/sources.toml` SHALL hold a `data_quality` entry with `cadence_days = 7`, its
   licence and its inputs; `NOTICE` SHALL be regenerated.
2. THE build SHALL run after the weekly TİTCK pipeline; it SHALL print counts only (no ingredient, code or product).

### Requirement 8: Upstream reports (private drafts)
1. FOR the twelve confirmed errors THE project SHALL prepare a Wikidata edit list (item, statement, deprecation
   reason, WHOCC reference address) and a formal Turkish letter to TİTCK, both ONLY in `docs/internal/upstream-reports/`
   (gitignored), each marked as needing a pharmacist's check before sending.
2. Janus SHALL NOT send, post or submit anything to an external party.

### Requirement 9: Quality
1. Property tests: classification (2.1-2.3); diff partition (3.1-3.4); order independence (1.6); no product string
   in any output (4.2); CSV ↔ JSON (5.4); version iff findings (5.2).
2. Route tests: 503 without a report; JSON, CSV and Markdown from an installed report; the public document lists the
   three routes.
