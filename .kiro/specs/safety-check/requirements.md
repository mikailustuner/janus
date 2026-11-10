# Requirements: Safety check of the medicine list

> Owner request 2026-11-10. A new bounded area: `apps/api/janus/safety/`, one pipeline job
> (`us_label_interactions`), one curated data file (`data/anticholinergic_scales.csv`) and one section on the
> results screen of `apps/web`. The prescribing-cascade check (cascade-engine) stays as it is and becomes one of
> four checks on the list. Three parts, built and committed in this order: A therapeutic duplication, B label
> interaction text, C anticholinergic burden. Each part works without the later ones.

## Introduction
A person's list is checked for prescribing cascades today. This area adds three more automated comparisons of
the same list, each limited to what an open source states:

- **A. Duplication.** The same active ingredient in two list items, or two different ingredients of one ATC
  chemical subgroup in two list items. Uses the resolution dataset Janus already holds.
- **B. Label interaction text.** When the "Drug Interactions" section of a US label of one ingredient on the
  list names another ingredient on the list, the passage is quoted with its label and label date. Quoted label
  text found by automated matching: never a verdict, a severity grade or an instruction.
- **C. Anticholinergic burden.** Which ingredients on the list are listed in openly licensed (CC BY) published
  anticholinergic scales, with the published scores and their sum, under a Janus name with the scale cited.

Nothing here tells a person to start, stop or change a medicine, nothing grades a risk, and an empty result is
"nothing found in the sources checked", with the source and its date.

## Glossary
- **List item:** one entry of the request (`items[i]`), a product or an ingredient found by name; the same items
  and order as `POST /cascades/evaluate`.
- **Ingredient key:** the cross-region key of drug resolution (a Wikidata QID or a Janus key).
- **Checked ingredient:** an ingredient of a list item that resolved to a key (mapped, or ambiguous with a
  choice). Ingredients of homeopathic products, unmapped and unchosen ambiguous ingredients are not checked and
  are listed as such.
- **ATC chemical subgroup:** the first five characters of an ingredient-level ATC code (4th level, e.g. `C09AA`).
- **Residual subgroup:** a chemical subgroup whose fourth-level letter is `X` (the WHO convention for "other"
  substances of a pharmacological subgroup, e.g. `N06AX`). Not a chemical class.
- **Form confirmed:** the ingredient's codes were selected for the product's form by drug resolution; an
  ingredient found by name carries all its codes and is not form confirmed.
- **Label:** one US prescription or OTC drug label of the openFDA drug label dataset, identified by its SPL set
  id, with its version and effective date.
- **Ingredient label:** the one label Janus keeps per ingredient: a label whose only active substance is that
  ingredient (design DP-S7 says which one).
- **Passage:** a sentence or table row of a label's "Drug Interactions" section.
- **Scale:** a published list of drugs with anticholinergic scores. Only scales published under CC BY with the
  scored list inside the paper are used.
- **Burden total:** per scale, the sum of the published scores of the distinct checked ingredients on the list
  that the scale lists.

## Requirements

### Requirement 1: One route, one input
1. THE API SHALL offer `POST /safety/check` as a medical route (JSON body only, `no-store`, nothing of the
   request logged or stored, read-only).
2. THE body SHALL be the body of `POST /cascades/evaluate` (`dataset_version`, 1-50 `items`, each a product
   candidate id or an ingredient key, optional choices and start month), validated strictly; unknown keys are
   refused. The client never sends an ATC code, a name or a label text.
3. A malformed body SHALL get 422 `invalid_request` with field paths only (never a value); another dataset
   version 409 `dataset_version_mismatch`; a missing resolution dataset 503 `safety_unavailable`.
4. THE answer SHALL carry one block per part (`duplication`, `interactions`, `burden`), the list's
   `not_checked` ingredients, the dataset version and the disclaimer. A part whose data is not installed SHALL
   answer `status: "unavailable"` and SHALL NOT fail the other parts.
5. EVERY sentence the API returns in English SHALL be a fixed statement or a quotation of a source; the client's
   own texts come from its catalogues.

### Requirement 2: Duplication (pure)
1. A `same_ingredient` finding SHALL be reported for an ingredient key IF AND ONLY IF checked ingredients with
   that key stand in two or more different list items; once per key, naming every such item.
2. A `same_group` finding SHALL be reported for an ATC chemical subgroup IF AND ONLY IF the subgroup is not
   residual and two checked ingredients with different keys, in different list items, each carry an
   ingredient-level code of that subgroup; once per subgroup, naming every member (item, key, the codes of that
   subgroup).
3. Ingredients of one list item SHALL never form a finding on their own: a combination product alone gives no
   finding.
4. A combination product's ATC code SHALL never be compared; only ingredient-level codes read through
   `rule_input` are.
5. A `same_group` finding SHALL say whether every member is form confirmed; a finding with a member that is not
   SHALL be labelled "product form not confirmed".
6. THE result SHALL be the same for any order of the items (item numbers aside) and SHALL be ordered:
   same-ingredient findings by key, then same-group findings by subgroup code.
7. WHEN there is no finding, THE answer SHALL carry the statement `no_duplication_found`, which names what was
   compared and ends with "This does not mean your medicines are free of problems."
8. THE answer SHALL name the sources and snapshot dates of the codes it compared.

### Requirement 3: Label interaction text — source and pipeline
1. THE source SHALL be recorded in `pipelines/sources.toml` as `openfda_label_interactions` (openFDA drug label
   dataset, CC0 1.0, FDA credit line, "Not an FDA endorsement", region US, storage `cache`); NOTICE SHALL be
   generated from it and `.kiro/steering/data-sources.md` SHALL list it.
2. THE pipeline SHALL read the openFDA bulk download (no API key, no paged API calls), one partition at a time
   with bounded memory, with the shared timeouts and retry rule, and SHALL keep no downloaded partition after
   the run and commit no label data.
3. THE pipeline SHALL keep only labels that have a "Drug Interactions" section and exactly one active
   substance, and of those one label per substance name; per kept label: substance name as published, set id,
   version, effective date, product type, and the section text as published.
4. EVERY run SHALL record source addresses, licence, export date, hashes, row counts and exclusions with
   reasons in its manifest, and SHALL fail when the parsed record count differs from the download index.

### Requirement 4: Label interaction text — matching (pure)
1. A finding SHALL be reported for an ordered pair (label ingredient A, named ingredient B) IF AND ONLY IF A and
   B are different checked ingredients standing in different list items, an ingredient label of A exists, and a
   passage of its "Drug Interactions" section contains a name of B as whole words.
2. THE names of B SHALL be the English label of its ingredient key and the English aliases Janus holds for it,
   after the exclusions of design DP-S9 (short names, names shared by two keys, names that are also A's names);
   no pharmacological class is inferred and no name is guessed.
3. EVERY finding SHALL quote the passage as published (cut to a fixed length with a flag) and SHALL carry the
   name that was matched; the quoted text SHALL contain that name.
4. EVERY finding SHALL carry the label's set id, version, effective date, the DailyMed address of the label and
   the data date of the download.
5. NO finding SHALL carry a severity, a grade, a recommendation or a classification by Janus.
6. WHEN A has no ingredient label, THE answer SHALL list A under `labels_not_found`; WHEN nothing is found, THE
   answer SHALL say which labels were read and their data date, and that this does not mean no interaction
   exists.
7. THE result SHALL not depend on the order of the items and SHALL be bounded (design §7).

### Requirement 5: Anticholinergic burden — source and licence
1. ONLY scales published under CC BY with the scored drug list inside the paper SHALL be used. Before a scale
   is added, the paper SHALL be opened, the licence line read and the list located; licence, citation, address
   and the date of that check SHALL be recorded in `pipelines/sources.toml` (and so in NOTICE).
2. THE names "ACB", "Anticholinergic Cognitive Burden", "ARS" and "ADS" SHALL NOT be used for anything Janus
   computes, and no list of those scales SHALL be copied. Beers, STOPP/START and ISMP lists SHALL NOT be
   reproduced.
3. THE scored lists SHALL be committed as `data/anticholinergic_scales.csv` with, per row: scale id, drug name
   as published, published score, locator in the paper, and the ingredient key Janus maps the name to (or the
   reason it maps to none).

### Requirement 6: Anticholinergic burden — computation (pure)
1. A contribution SHALL be reported for (scale, ingredient key) IF AND ONLY IF the key is a checked ingredient
   of the list and the scale lists a drug mapped to that key with a score above zero; once per key and scale,
   naming the list items that contain it.
2. THE burden total of a scale SHALL equal the sum of the scores of the contributions shown for that scale.
3. Scales SHALL be reported side by side, each with its own total; scores of different scales SHALL never be
   added or averaged.
4. THE answer SHALL NOT carry a threshold, a category ("high", "low") or a statement about the person.
5. WHEN a scale lists no ingredient of the list, THE answer SHALL say so for that scale, with the number of
   drugs the scale lists, and that this does not mean the medicines have no such effect.
6. THE result SHALL not depend on the order of the items.

### Requirement 7: Web
1. THE results screen SHALL show a section "More checks on this list" with one block per part, after the
   cascade findings. The section asks `POST /safety/check` with the body of the evaluation.
2. EVERY block SHALL handle loading, nothing found, findings, unavailable and error (with retry), and long
   content (long names, many findings, long quotations) without horizontal scroll at 375 px.
3. A duplication finding SHALL name the medicines by their box names and the ingredient, say that this can be
   intended, and refer to a pharmacist or doctor.
4. A label passage SHALL be shown as an English quotation, marked as such, with the label's date and a link to
   the label at DailyMed, the matched name, and the sentence that Janus quotes the label and does not judge it.
5. THE burden block SHALL show, per scale, the contributing medicines with their published scores, the total,
   and the citation with a link; no colour or word that grades the total.
6. EVERY block SHALL state what was checked, the data date where there is one, "automated", and "Expert review
   has not yet been done".
7. Texts SHALL exist in en, tr, de, fr, es; follow `.kiro/steering/medical-safety.md` (no forbidden phrase, no
   reassurance word, no "AI"); both themes; WCAG AA; touch targets of 44 px.
8. THE section SHALL NOT run in demo mode (design DP-S4); one line says so.

### Requirement 8: Quality
1. Property tests (Hypothesis, fast-check) SHALL cover Req 2, 4 and 6 (design §9); unit and route tests the
   rest; Playwright with axe the section in five languages, two themes, 375 px and 1280 px.
2. THE safety-auditor and localization-reviewer agents SHALL each make a read-only pass; findings are fixed or
   recorded. These are automated passes: expert review has not yet been done.
