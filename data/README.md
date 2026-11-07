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
