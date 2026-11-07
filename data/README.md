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
- `ingredient_synonyms.csv`: published ingredient name → Wikidata item, for frequent names the
  matching ladder cannot map (`drug-resolution` DP5). Each row names the evidence it rests on.

## Curated evidence files (Janus, Apache-2.0)
- `evidence_papers.csv`: papers that Janus cites as evidence (`evidence-integrity` design §3.1,
  DP13). Columns: `key` (id part: the evidence id is `paper:<source_id>:<key>`), `doi`,
  `source_id` (an id in `pipelines/sources.toml`, which supplies licence and region),
  `title`, `verified_on` (the day the bibliographic record was checked, `YYYY-MM-DD`), `note`.
  The `retractions` pipeline checks every DOI listed here, and the integrity loader creates the
  evidence records. Rows (added by `cascade-engine` on 2026-11-07, each DOI, title, authors,
  journal and year checked against its Crossref record first): BMJ 2026 (priority data for the
  cascades named in its abstract), ThinkCascades (supporting id, cited only), Hendrix 2024 (the
  12-month window) and Vander Zanden 2001 (ophthalmic beta-blockers). A paper whose DOI cannot be
  verified is not added.

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
