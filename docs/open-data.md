# Janus open data

Janus publishes two kinds of open data. Both are research material, not medical advice. Janus is a
research prototype, not a medical device.

1. **The open outcome dataset**: counts of donated reports and of doctor-confirmed outcomes, released only
   through the same rule as Collective Memory (groups of at least 20, noise added, sibling rule).
2. **The open cascade data package**: the prescribing-cascade rule base Janus uses, with Janus's
   mappings, as versioned files with a licence per file.

The read-only API that serves the dataset (and the other public routes) is described in
[`open-api.md`](open-api.md) and [`openapi-public.json`](openapi-public.json).

## 1. The open outcome dataset

| | |
|---|---|
| Name | `janus-open-outcomes` |
| Where | `GET /api/open/outcomes` (JSON) and `GET /api/open/outcomes.csv` (CSV); the **Open data** page of the web app shows the same cells and links both files |
| Licence | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Attribution: "Janus open outcome dataset (released cells of donated reports and doctor-confirmed outcomes), CC BY 4.0." |
| Version | `version` (JSON) and the `x-janus-dataset-version` header (CSV): `open-outcomes-1+<hash>`, the rule version and a hash of the released cells. Same stored data → same file. |
| Snapshot | `snapshot_date`: the UTC day the file was produced |
| Today | **No released cells yet.** Janus has not launched, so no group has reached 20; the files are valid and empty, and the page says "no released cells yet". There are no example numbers anywhere in the product. |

### What is in it, and what never is

- **Layers.** `contributions`: reports people donated with explicit consent (pseudonymous, never anonymous:
  `privacy.md`). `outcomes`: answers of doctors who read a Janus note and said a pattern was a prescribing
  cascade (`assessment = confirmed`), given without an account through the note's QR code. Outcomes are not
  verified by Janus.
- **Cells.** One cell is (layer, a set of one or two ingredient keys, Janus event key, direction, region). Its
  value counts the stored reports of that layer that name all the ingredients, the event and the direction in
  that region.
- **Release rule** (the existing Collective Memory code path, `apps/api/janus/memory/shared.py`):
  - a cell is released only when its **true** count is at least **k = 20**;
  - the **sibling rule** hides a cell when a nested cell (the same set plus one more ingredient) would reveal,
    by subtraction, a group of 1 to 19;
  - released values carry **discrete Laplace noise** (scale 1/ε, ε = 1 by default), deterministic per cell and
    per version of its contributors: asking again about the same stored reports gives the same value; the noise is
    drawn again only when the reports in the group change;
  - **hidden cells are not listed at all**, not even as "hidden": their existence would say that 1 to 19 reports
    exist;
  - **consent:** a layer is published only when every stored report of it was given under a consent text that
    names this open dataset (`OPEN_RELEASE_CONSENT_VERSIONS` in `apps/api/janus/open/outcomes.py`). The current
    consent texts (2026-11-v2) name Collective Memory and research, not open publication, so today any stored
    donation or outcome withholds its whole layer (`withheld_layers` in the JSON). A layer is never published in
    part: a partial count next to the Collective Memory count would allow differencing.
- **Never in it:** a true count, an age band, a sex, a week, a country, a city, a deletion token, free text, a
  note id or anything that identifies a person.

### Data dictionary

| Field (JSON `cells[]` / CSV column) | Type | Meaning |
|---|---|---|
| `dataset_version` (CSV) / `version` (JSON) | string | `open-outcomes-1+<12 hex>`; changes whenever a released value changes |
| `snapshot_date` | date `YYYY-MM-DD` | UTC day the file was produced |
| `layer` | `contributions` \| `outcomes` | donated reports, or doctor-confirmed outcomes |
| `ingredients` | 1–2 keys (CSV: joined with `\|`) | ingredient keys: Wikidata items (`Q…`, CC0) or curated Janus keys (`J…`, `data/janus_ingredients.csv`) |
| `event` | string | Janus event key (`apps/api/janus/memory/memory_events.csv`; lay labels in five languages in the web vocabulary) |
| `direction` | `adverse` \| `benefit` | the person or doctor reported a harm or an improvement |
| `region` | `TR` \| `EU` \| `US` | the only geography Janus stores |
| `value` | integer ≥ 0 | number of **reports** (never people) in the cell, with noise added |

JSON only: `withheld_layers` (layers not published for lack of an open-release consent), `release_rule` (`k`, `epsilon`, `noise`, `sibling_rule: true`, `hidden_cells_listed: false`),
`license`, `license_url`, `attribution`, `dictionary_url` (this page) and `notices`:
`counts_are_reports_not_people`, `not_verified`, `not_incidence`, `noise_added`.

### How to read it

- Counts are **reports**, not people, and not incidence: there is no denominator. A donated report is a donation,
  not a person; one person may donate more than once, and the cells of one and two ingredients overlap.
- Outcomes are what a doctor answered, not a verified diagnosis or a cause.
- Because suppression uses the true count, the release as a whole is not claimed to be formally differentially
  private (collective-memory DP14). Comparing several cells, or versions over time, can narrow a count; the rules
  reduce this but do not exclude it.
- Cite: "Janus open outcome dataset, version `<version>`, snapshot `<snapshot_date>`, CC BY 4.0."

## 2. The open cascade data package

`data/open/cascade-package/` (Frictionless [`datapackage.json`](../data/open/cascade-package/datapackage.json),
README, seven CSV files). Generated by `python -m janus.open.package` from `data/`; CI fails when the committed
package differs from the builder's output.

| File | Licence | Content |
|---|---|---|
| `pipc.csv` | CC BY 4.0 (Rochon et al. 2025) | the 65 cascades of the PIPC list, Table 1, cell text as published |
| `pipc_rules.csv` | Apache-2.0 | each PIPC row → Janus index and marker class, or why it cannot be matched |
| `cascade_classes.csv` | Apache-2.0 | class → ATC prefix patterns, scope and basis |
| `atc_code_exclusions.csv` | Apache-2.0 | ATC codes a source gives an ingredient wrongly (see [`contributing-corrections.md`](contributing-corrections.md)) |
| `ingredient_synonyms.csv` | Apache-2.0 | ingredient name → Wikidata item (name rules), without any row that cites or matches the TİTCK list |
| `anion_acid_forms.csv` | Apache-2.0 | anion → acid forms (name rules) |
| `dose_form_groups.csv` | Apache-2.0; names CC0 (openFDA) and Licence Ouverte 2.0 (BDPM, shown as published) | published dose form → Janus dose-form group |

- **Version:** `datapackage.json` `version` (semantic; 1.0.0) and `created` (the day it was rebuilt); every
  resource has its `sha256` hash and row count.
- **No TİTCK list row, product name or barcode.** TİTCK lists have no clear redistribution terms and are fetched
  at runtime only. The package leaves out every synonym row whose evidence cites TİTCK or the coverage report built
  on it, and every name whose SHA-256 occurs in `apps/api/janus/open/titck_name_hashes.txt` (names found in the
  local TİTCK list; the hashes let CI repeat the check without the list). Some notes state codes or row counts
  observed in the TİTCK list.
- **ATC codes** were checked by hand on the WHOCC ATC/DDD index; no index text is copied. The WHO index is not
  open data.
- **Status:** reviewed by the project owner with AI assistance; not yet reviewed by a pharmacist or physician
  (`docs/pre-launch-checklist.md`).
