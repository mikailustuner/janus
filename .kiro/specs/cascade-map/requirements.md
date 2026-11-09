# Requirements: Cascade Map ("Constellation of the 65 PIPC patterns")

> Owner-approved enhancement (item 6 of 6), 2026-11-09. Client-only feature in `apps/web`; no API
> change. Criteria use EARS form. "The client" is the Janus web app. The words of the screen live
> in the new `CascadeMap` namespace (five languages); the clinical names come from the generated
> vocabulary (experience design §8.3, DP17).

## Introduction
The results scope card says "Janus checked 63 of the 65 patterns of the PIPC list", but a person
cannot see the list. The cascade map shows all 65 prescribing-cascade patterns of the PIPC list
(Rochon et al., Eur Geriatr Med 2025, CC BY 4.0) as an explorable constellation: the drug classes
are stars, every pattern is a directed line from the first class to the second, labelled with the
side effect. A table view shows the same patterns for screen readers and for anyone who prefers
reading. When the person's current list (or the demo patient) has findings returned by the API,
the lines of those patterns are highlighted. The map shows literature patterns, never verdicts,
and computes nothing medical (experience DP3).

## Glossary
- **Pattern / rule:** one row of PIPC Table 1 (`data/pipc.csv`), rule id `pipc:<row>`, with its
  Janus classes in `data/pipc_rules.csv`.
- **Class node (star):** a drug class (or individual drug) of the rule base: the `index_class` or
  `marker_class` of a rule with the role suffix (`_index`, `_index_eye`, `_marker`) removed, so one
  class is one star. A rule whose marker has no class (rows 27, 57) gets its own node
  `row<N>:marker`.
- **Edge (line):** one rule, directed from its index node to its marker node, labelled with the
  rule's adverse event (the Janus event key whose `pipc_positions` holds the row).
- **Matched edge:** an edge whose rule id appears in `findings[].rule_id` of the current
  `CascadeResult` (API or recorded demo fixture).
- **Cannot be checked:** a rule listed in `rules.not_matchable` or `rules.disabled` of the current
  result; without a result, the rules with an `unmatchable_role` in `data/pipc_rules.csv`.

## Requirements

### Requirement 1: The graph model
**User story:** As a person, I want every PIPC pattern on the map exactly once, so that the map is
a faithful picture of the list Janus checks.
#### Acceptance criteria
1. THE generator SHALL build the graph from `data/pipc.csv` and `data/pipc_rules.csv` only, with one
   edge per rule row and one node per class (Glossary).
2. THE client SHALL show every one of the 65 rules exactly once in the map and exactly once in the
   list view.
3. THE star label SHALL be the shortest published name of that class among the rows where it
   appears, in the interface language (generated vocabulary); the rule's own published names SHALL
   be shown unchanged in the panel and the list.
4. WHEN a data file changes THE committed graph file SHALL be regenerated; a test SHALL fail when the
   committed file differs from the generator output.

### Requirement 2: Layout
**User story:** As a person on a phone, I want a calm, readable map that does not jump around.
#### Acceptance criteria
1. THE layout SHALL be computed once at generation time by a deterministic algorithm (same input,
   same coordinates) and committed with the graph.
2. Every node SHALL lie inside the canvas with a margin, and no two nodes SHALL be closer than the
   minimum distance (design §4), so that at the phone's fit zoom the 24 px spacing circles of
   neighbouring stars never overlap (WCAG 2.5.8).
3. WHEN the user prefers reduced motion THE map SHALL show the static layout without any animated
   settle or animated zoom; without that preference the button zoom MAY ease in at most 200 ms using
   transform only.

### Requirement 3: Filters
**User story:** As a person, I want to find the patterns of one medicine class or one side effect.
#### Acceptance criteria
1. THE client SHALL offer a filter by drug class (a select of all class nodes, by label), by event
   (a select of the events of the rule base) and a text search over class and event names.
2. WHEN a filter is set THE client SHALL show only the edges whose rule satisfies all active filters
   and only the nodes touched by a shown edge; filters SHALL only remove, never add or move anything.
3. THE client SHALL announce the number of patterns shown ("12 of 65 patterns shown") in a polite
   live region, and SHALL show an empty state with a "Clear filters" action when nothing is left.

### Requirement 4: Panel
**User story:** As a person, I want to read what a line means and where it comes from.
#### Acceptance criteria
1. WHEN the user activates an edge THE client SHALL open a panel with: the row number, the cascade in
   the interface language ("A → event → B"), the event, the source line "PIPC list (Rochon et al.,
   Eur Geriatr Med 2025), row N" as on the finding card, the evidence ids of the rule
   (`rule:pipc:N`, `dataset:pipc`, and the supporting paper ids of `pipc_rules.csv`) in mono, the
   ThinkCascades line when a supporting id exists, and the row-49 note for row 49.
2. WHEN the rule cannot be checked THE panel and the list SHALL label it "cannot be checked" with the
   same reason wording as the results scope card.
3. WHEN the user activates a node THE client SHALL open a panel with the class and the patterns that
   start and end at it, each one a button that opens that pattern.
4. WHEN the rule has a matched finding THE panel SHALL list the person's matching medicines (box
   names in the finding card's wording), the abrupt-stop line for warned items, and a link to the
   finding's evidence page (`/results/finding#<position>`).
5. WHEN the user presses Escape or the close button THE client SHALL close the panel and return focus
   to the star or control that opened it.

### Requirement 5: Matches from the API only
**User story:** As a person with a list, I want to see which literature patterns my findings belong
to, without the map deciding anything about my medicines.
#### Acceptance criteria
1. THE client SHALL derive matched edges only from `findings[].rule_id` of the `CascadeResult`
   returned by the API or the demo fixture; it SHALL NOT evaluate any rule, timing or class
   membership itself (experience DP3).
2. Matched edges SHALL differ from other edges by width, dash and a text legend, not by colour alone;
   red (`--risk`) SHALL NOT be used.
3. WHEN there is no list THE client SHALL show the map without highlights and a line inviting the
   person to add medicines; WHEN the evaluation is loading or fails THE map SHALL still work, with the
   matches' own loading or error line.
4. WHEN the demo is active THE client SHALL make no network request (experience Req 4).

### Requirement 6: Accessible alternative and keyboard
**User story:** As a keyboard or screen-reader user, I want the same information without a pointer.
#### Acceptance criteria
1. THE client SHALL offer a segmented control "Map | List"; the list view SHALL be a table of all
   shown patterns (row, first class, side effect, second class, status) with the same filters.
2. THE map SHALL use a roving tabindex: one star is in the tab order; arrow keys move to the
   neighbouring star in that direction (graph neighbours first, then the nearest star in that
   direction); Home and End go to the first and last star by label; Enter or Space opens the panel.
3. Every star SHALL have an accessible name (class, number of patterns as first and as second
   medicine, "in your list" when matched); the map SHALL have a name and keyboard instructions.
4. Focus SHALL be visible (3 px accent ring) on stars and controls; every control SHALL be at least
   44 × 44 px; zoom in, zoom out and reset SHALL be buttons.

### Requirement 7: Pan, zoom and performance
**User story:** As a person with a mid-range phone, I want the map to stay smooth.
#### Acceptance criteria
1. THE map SHALL pan by pointer drag and zoom by pinch, Ctrl/⌘ + wheel and the buttons, changing only
   SVG transforms (no layout per frame, no React render per pointer move).
2. WHILE panning, zooming or filtering at 375 px with 4× CPU throttling THE page SHALL have no long
   task over 50 ms; the measured numbers SHALL be recorded in design.md.

### Requirement 8: Theme, safety and wording
**User story:** As the owner, I want the map to fit both themes and every safety rule.
#### Acceptance criteria
1. THE map SHALL look like a constellation in Night Pharmacy (stars on midnight, teal lines) and like
   a clean light graph in Glass Janus, with tokens only and no theme-device word in Glass.
2. THE screen SHALL show the framing line ("Patterns described in the literature … something to
   discuss with your doctor, not a verdict.") and the disclaimer; no forbidden phrase in any
   language.
3. THE route `/cascades` SHALL be reachable from the results scope card ("What Janus checked"), the
   Research page and the footer.
4. Every new text SHALL exist in EN, TR, DE, FR, ES and pass the localization-reviewer and
   safety-auditor passes; class names and edges SHALL pass a pharmacologist pass.
