# Cascade map: pharmacologist pass (2026-11-09)

Scope: the class nodes and edges of `apps/web/src/cascade-map/graph.json` (generator
`apps/web/scripts/gen-cascade-map.mjs`, design §3, DP3), the star labels in EN, TR, DE, FR, ES
(`nodeLabel`: shortest published name of the class), and the rule panel's wording
(`RulePanel.tsx`). One labelled AI pass in the role of `.kiro/agents/pharmacologist.md`; it read the
65 rows of `data/pipc.csv` and `data/pipc_rules.csv` against the generated graph and the list of
node labels in all five languages. Status: **AI-reviewed, pending expert review**
(`docs/pre-launch-checklist.md`).

## Checked
- **One edge per row, direction index → marker** for all 65 rows (P1 checks it mechanically). No
  parallel and no opposite pair exists, so no two patterns are drawn on top of each other.
- **Class merge (DP3)** is limited to the role suffixes: `beta_blocker_index_eye` (row 3, includes
  ophthalmic beta-blockers), `beta_blocker_index` (row 4) and `beta_blocker_marker` (row 17,
  systemic only) become one star "Beta-blocker"; `nsaid` (rows 51–54) and `nsaid_marker` (row 40,
  includes topical NSAIDs) become "NSAID". The star is the PIPC class concept; the matching scope per
  rule (eye drops, topical forms) stays in the rule base and is not claimed by the map. Acceptable.
- **Classes kept apart, correctly**: `antidepressant` (marker, rows 3, 36, 55) vs
  `tricyclic_antidepressant`, `ssri_snri`, `venlafaxine` (index rows); `antiparkinsonian` (marker)
  vs `dopaminergic_antiparkinsonian` (index row 30) vs `antimuscarinic_antiparkinsonian` (row 19);
  `pioglitazone_rosiglitazone` (row 43) vs `rosiglitazone` (row 44); `corticosteroid_systemic`
  (index) vs `topical_corticosteroid` (marker row 15); `vitamin_supplement` (row 48) vs
  `ppi_deficiency_supplement` (row 49). Merging any of these would claim an equivalence PIPC does not
  make.
- **Unmatchable markers** (rows 27 bismuth subsalicylate, 57 saliva substitute, `no_atc_code`) are
  their own stars and are labelled "cannot be checked" with the scope card's reason.
- **Labels** are the published names (glossary-accepted translations); the shortest one is used on
  the map, the row's own wording in the panel and the list. `statin` → "HMG Co-A reductase inhibitor"
  (rows 10–12 use it; row 9 the long form); search still finds "statin".

## Findings

| # | Item | Finding | Severity | Outcome |
|---|---|---|---|---|
| P1 | edge directions | All 65 index → marker, as published. | — | Passed |
| P2 | `ppi_deficiency_supplement` | Its star is named "Vitamin or Mineral Deficiency" because row 49 publishes the second medicine that way. On a map of medicine classes this reads like a condition. | advisory | **Applied**: the class panel of this star shows `Findings.row49` ("… Janus checks vitamin B12, magnesium and oral iron supplements for it"), as the pattern panel already did. The label stays as published. |
| P3 | `corticosteroid_systemic` | Star "Corticosteroid" (PIPC wording) while the rules check systemic corticosteroids only (DP8 of the rule base). | advisory | Kept: the map names the PIPC class; the matching scope is the rule base's and is not shown as a claim. For the experts. |
| P4 | `beta_blocker`, `nsaid` merges | Per-rule form extensions differ inside one star. | advisory | Kept (DP3); documented in design §3. |
| P5 | legend and intro | "The dots are the medicine classes": 14 stars are single medicines (digoxin, midodrine, lithium, metformin, …) and one is the published deficiency of row 49. | advisory | **Applied** in all five languages: "medicine classes or single medicines". |
| P6 | event filter | The side-effect select groups rows by the Janus event key (e.g. rows 2 and 56 under "Dizziness or low blood pressure on standing"); the panel shows the row's own published side effect. | — | Passed (same mapping as the finding cards, `memory_events.csv`). |
| P7 | matched edges | Only `findings[].rule_id` of the API result is used; no ATC or class logic in the client. | — | Passed (experience DP3, P3). |

Verdict: **pass** with P2 and P5 applied; P3 and P4 recorded for the experts.
