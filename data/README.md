# data/

Small, redistributable files only (for example the PIPC table, CC BY 4.0, and curated
mappings). Every file keeps its source, license and snapshot date next to it.

Never put files with unclear redistribution terms here. TİTCK lists in particular are
fetched at runtime and must not be committed; CI fails if one is tracked.

## Curated drug-resolution files (Janus, Apache-2.0)

- `atc_combination_rules.csv`: ATC codes and groups treated as combination codes, plus
  exceptions (`drug-resolution` design §5.4, DP3). Derived on 2026-11-07 from three sources:
  the WHO ATC numbering convention (5th level 20/30 and the 50-series mean combinations),
  observations in the current TİTCK list (codes on multi-ingredient products; codes only), and
  pharmacological knowledge. Drafted by the pharmacologist agent and **reviewed by the owner on
  2026-11-07**. Rows that needed confirmation were checked by hand against the public WHOCC
  ATC/DDD Index pages (URL and date in the note). The file holds codes and Janus's own notes
  only; no WHO index text is copied. **Re-review it whenever WHOCC publishes a new ATC
  version** (the index checked was last updated 2026-01-20).
- `route_atc_groups.csv`: openFDA route of administration → ATC groups a product given by that
  route may carry (`drug-resolution` design §5.5, DP20). Same derivation date and review. Re-review
  with the combination rules. Since 2026-11-08 it also holds 24 rows for the French BDPM route
  strings (exact spelling, lower case, e.g. `orale`, `sous-cutanée`), proposed by the pharmacologist
  agent in the name-rules review sheet (Appendix C) and accepted by the owner; they select an
  ingredient's codes for a BDPM product, which has no published ATC code (Req 5.9).
- `ingredient_synonyms.csv`: published ingredient name → ingredient key, for frequent names the
  matching ladder cannot map (`drug-resolution` DP5). Each row names the evidence it rests on.
  102 rows were added on 2026-11-07 from the PIPC coverage report (cascade-engine task 12),
  proposed by the pharmacologist agent and approved by the owner; 26 more on 2026-11-08 from the
  name-rules review (Appendix D of the sheet; 134 rows in total), accepted by the owner. One further
  row (the Turkish spelling of fenofibric acid) is **not** in the repository: it lives in the optional
  file `$JANUS_DATA_DIR/resolution/local_synonyms.csv` (same header), which the loader reads and
  which is part of the dataset version, because a source-derived Turkish string must not be committed.
- `janus_ingredients.csv`: curated Janus ingredient keys `J<n>` for substances that no
  Wikidata item in the extract covers with an ATC code (`drug-resolution` Req 11.2, DP25).
  Columns `key,label_en,label_tr,label_de,label_fr,label_es,atc_codes,added_on,note`. Keys: J1
  dimenhydrinate, `R06AA11` (owner decision 2026-11-07); J2 imipenem, with **no** `atc_codes` of its
  own: its one code is the reviewed pair in `component_codes.csv` (owner decision 2026-11-08). Codes
  only, checked by hand on the WHOCC index (URL and date in the note).
- `component_codes.csv`: the reviewed (key, combination code) pairs of `drug-resolution` Req 14 and
  DP43. Columns `key,code,evidence,whocc_url,whocc_date,note`. One row: `J2,J01DH51` (imipenem; the
  WHOCC `J01DH` page, checked 2026-11-08 and last updated by WHOCC on 2026-01-20, lists only
  `J01DH51` "imipenem and cilastatin", note "Refers to imipenem"). The code may reach the cascade
  engine for that key only; for every other ingredient it stays a combination code. The loader refuses
  a row with a bad key or code, a repeated pair, an empty evidence or note, or a missing WHOCC address
  or date, and a code that is not a combination code of the dataset. **Re-check the WHOCC page
  whenever WHOCC publishes a new ATC version.**

- `atc_code_exclusions.csv`: reviewed (key, ATC code, source) triples to drop from an ingredient key's codes
  (`drug-resolution` Req 15, DP45; found by the `doctor-loop` glossary review, 2026-11-08). Columns
  `key,code,source,reason,evidence,whocc_url,whocc_date,note`. `source` is `wikidata` (the item's own code) or
  `titck` (the code of a TİTCK single-ingredient product, which stays on the product as published but does not
  become the ingredient's code). `reason` is `wrong_substance` (the code names another substance), `old_code` (no
  longer in the index) or `not_a_medicine`. Twelve rows, each checked by hand against the WHOCC group page (address and
  date in the row; no index text is copied) and, where the substance is on the US market, against RxClass. Codes
  only, no product names. The loader refuses a bad row and a stale one (a code its source no longer gives the key).
  Review report: `.kiro/specs/drug-resolution/atc-code-review.md`. **Re-check it whenever WHOCC publishes a new ATC
  version or a source is corrected.**
- `onset_key_exclusions.csv`: ingredient keys left out of one drug class for the FAERS onset table only
  (`faers-onset-table` DP-O5; pharmacologist review). Columns `class_id,key,label_en,reason,note`; `reason` is
  `other_use_dominates` or `not_used_for_the_indication`. Never used by the cascade engine.
- `onset_row_notes.csv`: known limits of single PIPC rows in the FAERS onset table (event-term gaps, mixed uses,
  name-mapping gaps). Columns `position,code,note`.
- `open/data-quality/`, `open/faers-onset/`: the published weekly data-quality report and the FAERS onset table
  (CC BY 4.0, generated; `docs/open-data.md` §3-§4). No TİTCK row, product name or barcode.
- `anion_acid_forms.csv`: reviewed anion-to-acid rows of the `anion_acid` ladder step
  (`drug-resolution` Req 12.7, design §15.4). Columns `lang,anion,acid,note`; `lang` is
  `tr`, `en`, `fr`, `es` or `any`. Seven rows, proposed by the pharmacologist agent in the name-rules
  review sheet (`.kiro/specs/drug-resolution/name-rules-review.md`, Appendix B) and **accepted by the
  owner on 2026-11-08**; a clinical review has not happened. A row names the evidence it rests on; a
  code, if discussed, is checked by hand on the WHOCC index (URL and date in the note). There is no
  generic "-ate → -ic acid" rewrite. The per-language salt and ester word lists of the same review
  live in code (`apps/api/janus/resolution/name_lists.py`), not here.
## Curated evidence files (Janus, Apache-2.0)
- `evidence_papers.csv`: papers that Janus cites as evidence (`evidence-integrity` design §3.1,
  DP13). Columns: `key` (id part: the evidence id is `paper:<source_id>:<key>`), `doi`,
  `source_id` (an id in `pipelines/sources.toml`, which supplies licence and region),
  `title`, `verified_on` (the day the bibliographic record was checked, `YYYY-MM-DD`), `note`.
  The `retractions` pipeline checks every DOI listed here, and the integrity loader creates the
  evidence records. Rows (added by `cascade-engine` on 2026-11-07, each DOI, title, authors,
  journal and year checked against its Crossref record first): BMJ 2026 (priority data for the
  cascades named in its abstract), ThinkCascades (supporting id, cited only), Hendrix 2024 (the
  12-month window) and Vander Zanden 2001 (ophthalmic beta-blockers). Added by `collective-memory` on
  2026-11-08: Evans, Waller and Davis 2001 (DOI 10.1002/pds.677, checked in Crossref: journal article,
  no notice), source of the screening criteria PRR >= 2, chi-squared >= 4, at least 3 reports; its full
  text is paywalled, so the Yates-corrected chi-squared is cited from its use in the literature. A paper
  whose DOI cannot be verified is not added.
## Curated collective-memory files (Janus, Apache-2.0)
- `memory_events.csv` is **not** in `data/`: it ships inside the API package as
  `apps/api/janus/memory/memory_events.csv` (the API image is built from `apps/api` only). It is the Janus
  event vocabulary (`collective-memory` design §4.6, DP23): one row per event key with labels in five
  languages (English with US spelling; the PT strings stay as published), the FAERS MedDRA Preferred Terms
  it covers (as published in FAERS, no hierarchy; MedDRA® trademark is registered by IFPMA on behalf of ICH),
  the PIPC rows it stands for, a `status`, and an optional `safety_line` (six lines, owner decisions
  2026-11-08: `crisis_support`, `urgent_care_skin`, `urgent_care_heart`, `urgent_care_gi`, `urgent_care_seizure`,
  `urgent_care_breathing`; wording and regional numbers are in the `Memory` message namespace). Drafted by the AI
  assistant, reviewed by the pharmacologist agent and the localization-reviewer agent, and **accepted by the
  project owner on 2026-11-08** (`.kiro/specs/collective-memory/event-mapping-review.md`). The whole mapping
  still needs review by a pharmacist or physician, and the labels a native check, before any public claim.

## Curated cascade-engine files (Janus, Apache-2.0)

The PIPC-to-ATC class mapping of the cascade engine (`cascade-engine` design §3.1-3.3, DP2,
DP8, DP13; `data-pipelines` DP8). Curated by Janus, Apache-2.0. Drafted by the pharmacologist
agent on 2026-11-07 and **reviewed on 2026-11-07 by the project owner with AI assistance**
(review sheet and decisions: `.kiro/specs/cascade-engine/mapping-review.md`). It still needs a
review by a pharmacist or physician before any public claim. The files hold ATC codes and Janus's own
notes only; no WHO index text, TİTCK product name or TİTCK ingredient string is copied. Codes
come from the ATC structure (`basis = pharmacology`), the Wikidata extract (CC0), the TİTCK
list (codes and row counts only) or a hand check of one WHOCC ATC/DDD Index page per prefix
(URL and lookup date in the note; the index checked was last updated 2026-01-20). **Re-review
them whenever WHOCC publishes a new ATC version**, together with the combination rules.

- `cascade_classes.csv`: class → ATC prefix patterns (`class_id,pattern,match,scope,basis,
  evidence_id,note`). A code belongs to a class when the longest matching pattern of that class
  is an include. `scope = form_extension` marks a non-oral form that acts systemically, allowed
  in index classes only and cited to a paper in `evidence_papers.csv` (today: ophthalmic
  beta-blockers for PIPC row 3). Combination codes and groups of `atc_combination_rules.csv`
  are refused as patterns.
- `pipc_rules.csv`: one row per PIPC row 1-65 with its index and marker class, or the role that
  cannot be mapped and why (`no_atc_code`, `not_a_drug_class`, `ambiguous_text`), and
  supporting paper ids (ThinkCascades on the rows that describe the same cascade).
- `cascade_priority.csv`: the measures the BMJ 2026 abstract gives for the six PIPC rows it names
  with a number (incidence or adjusted sequence ratio, value and 95% CI, locator
  "Abstract, Results").
- `abrupt_stop_classes.csv`: ATC patterns that get the warning "Do not stop this medicine
  suddenly." (`pattern,match,group,note`), systemic forms only. It covers the six groups of
  `medical-safety.md` rule 4 and ten more groups confirmed by the owner on 2026-11-07.

## Curated medication-passport files (Janus, Apache-2.0)

- `dose_form_groups.csv`: published dose form → coarse Janus dose-form group (`medication-passport` design §5.2, DP7,
  owner decision 6 of 2026-11-08). Columns `source_id,published_form,route,group,note`. `published_form` is the form
  exactly as the source publishes it: openFDA NDC directory SPL dosage form names (CC0 1.0, snapshot 2026-11-06) and
  BDPM pharmaceutical forms (Base de données publique des médicaments, Licence Ouverte / Etalab, data of 2026-11-03,
  shown as published; the BDPM does not endorse Janus). `route` is `*`, empty (no route published) or the product's
  published route set joined with `|`; `group` is one of fourteen Janus groups or empty (unknown); `route_from_form`
  names the route class a `*` row's form string fixes by itself (no route is guessed otherwise). No EDQM Standard Terms
  are used. Drafted on 2026-11-08 by `python -m janus.passport.forms_draft` from the dev dataset, reviewed by the
  pharmacologist agent and **accepted by the owner on 2026-11-08** (931 rows, `.kiro/specs/medication-passport/
  dose-form-review.md`). A byte-identical copy ships in the API package (`apps/api/janus/passport/dose_form_groups.csv`;
  a test checks it). It still needs a review by a pharmacist before any public claim. Re-draft and diff it whenever a
  source adds dose forms or route sets.

## Séance files (Phase 4, `seance` design §5)

- `canon_gold_pmc3941892.csv` (+ `.meta.json`): the identification gold table, written by
  `janus-pipelines run canon_gold`. Name columns only (name in the Canon, common name, scientific
  name) of Tables 1 and 2 of Aliasl J, Khoshzaban F, Jundishapur J Nat Pharm Prod
  2013;8(4):192-196, doi:10.17795/jjnpp-11686, PMC3941892, **CC BY 3.0**. 29 rows.
- `seance_conditions.csv` (Janus, Apache-2.0): séance condition → MedDRA Preferred Terms counted by
  the present witness. PT names as published in FAERS (MedDRA notice in NOTICE).
- `seance_present.csv` (Janus, Apache-2.0): substance → Janus ingredient key and how well the
  FAERS exposure matches the ancient one (`same`, `component`, `different`; `different` is never
  counted). Reviewed by the pharmacologist agent (AI) 2026-11-08, pending expert review.
- `seance_science.csv` (Janus, Apache-2.0): (substance, condition) → listed studies (keys of
  `evidence_papers.csv`, source `seance_science`), study type, direction and a one-line finding in
  Janus's own words. Every DOI goes through Evidence Integrity.

The Canon text itself and everything derived from it are **not** here: they are in the separate
CC BY-NC-SA 4.0 data package `datasets/canon/`.

## Light face (Janus, Apache-2.0; light-face design §4)

- `light/goals.csv`, `light/effect_goal_map.csv`, `light/validation_cases.csv`: curated conditions, side-effect term → condition
  mapping and the fixed retrospective-validation cases. Terms are OnSIDES MedDRA names (no MedDRA hierarchy is copied); every
  active row and case cites a paper of `evidence_papers.csv` (Crossref checked 2026-11-08). Drafted by Claude Code, reviewed by the
  pharmacologist and statistician agents: **AI-reviewed, pending expert review** (pre-launch checklist).

## Reporting channels (Janus, Apache-2.0; `report-assistant` spec)
- `report_channels.csv` (+ `report_channels.meta.json`): official channels for reporting a suspected side effect
  of a medicine in Türkiye (TİTCK/TÜFAM), the US (FDA MedWatch Form 3500B), the EU (EMA guidance and national
  authority finder) and Germany (BfArM/PEI), France (ANSM) and Spain (AEMPS). One row per channel: `channel_id`,
  `region`, `country`, `authority`, `channel_name`, `audience` (`patient`, `relative`, `carer`, `citizen`, `consumer`,
  `representative`, `hcp`), `kind` (`online`, `pdf`, `document`, `email`, `phone`, `guidance`, `directory`), `url`,
  `form_id`, `form_version`, `language`, `patient_may_report`, `fields_status` (`verified`, `derived`, `partial`,
  `unverified`, `none`; meanings in the meta file), `field_source` (the channel whose field list applies),
  `fields` and `required_fields` (labels as published, `;`-separated, the form section before ` > `; `one-of(a|b)`
  means at least one of them), `outcome_field` and `outcome_options` (the form's own outcome choices, only where
  they were read), `source_url`, `checked_on`, `notes`. Checked by hand on official sites only, on 2026-11-09;
  anything not confirmed is written UNVERIFIED and the app builds no field mapping on it. No MedDRA term is stored
  (`report-assistant` DP3). **Re-check every row at least every three months** (next: 2027-02-09) and whenever
  an authority republishes a form; the TÜFAM e-form's published-version id changes on every republication. The web
  app ships `apps/web/src/report/channels.json`, generated from this file by
  `node apps/web/scripts/gen-report-channels.mjs`; a test fails when the two differ.

## Open cascade data package (`open-data` spec, 2026-11-09)

- `open/cascade-package/`: generated by `python -m janus.open.package` (in `apps/api`) from the files above; do not
  edit by hand, CI checks it is current. Seven CSV files with a licence per file (the PIPC table CC BY 4.0; Janus
  mappings Apache-2.0; dose-form names CC0 / Licence Ouverte 2.0), a Frictionless `datapackage.json` and a README.
  Ingredient-synonym rows that cite or match the TİTCK list are left out (by evidence note and by the hashes in
  `apps/api/janus/open/titck_name_hashes.txt`). Described in `docs/open-data.md`.
