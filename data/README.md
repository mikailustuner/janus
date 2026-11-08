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
  with the combination rules.
- `ingredient_synonyms.csv`: published ingredient name → ingredient key, for frequent names the
  matching ladder cannot map (`drug-resolution` DP5). Each row names the evidence it rests on.
  102 rows were added on 2026-11-07 from the PIPC coverage report (cascade-engine task 12),
  proposed by the pharmacologist agent and approved by the owner.
- `janus_ingredients.csv`: curated Janus ingredient keys `J<n>` for substances that no
  Wikidata item in the extract covers with an ATC code (`drug-resolution` Req 11.2, DP25).
  Columns `key,label_en,label_tr,label_de,label_fr,label_es,atc_codes,added_on,note`. First key:
  J1 dimenhydrinate, `R06AA11` (owner decision 2026-11-07). Codes only, checked by hand on the
  WHOCC index (URL and date in the note).

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
