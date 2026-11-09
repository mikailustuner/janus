# Design: Cascade Map

> Scope: the generator `apps/web/scripts/gen-cascade-map.mjs` and its output
> `apps/web/src/cascade-map/graph.json`, the pure view model `src/cascade-map/model.ts`, the screen
> `/cascades` (`src/components/cascade-map/`), its styles `src/theme/cascade-map.css`, the
> `CascadeMap` namespace and three entry links (results scope card, Research, footer). No API
> change. Decisions DP1–DP13 (§9), properties P1–P8 (§8).

## 1. Overview

```mermaid
flowchart LR
  P[data/pipc.csv] --> G[gen-cascade-map.mjs<br/>nodes, edges, layout]
  R[data/pipc_rules.csv] --> G
  E[memory_events.csv<br/>pipc_positions] --> G
  G --> J[src/cascade-map/graph.json<br/>committed, parity test]
  V[src/vocabulary/*.json<br/>names in 5 languages] --> M[model.ts<br/>labels, filters, matches, keyboard]
  J --> M
  A[CascadeResult<br/>API or demo fixture] -->|findings[].rule_id,<br/>rules.not_matchable/disabled| M
  M --> S[/cascades: Map or List + panel/]
```

Three things are kept apart:
1. **The graph** is data: it is generated from the reviewed rule-base files and committed. The
   client never derives a class, an edge or a position at run time.
2. **The overlay** is the API's answer: matched edges are the rows of `findings[].rule_id`; "cannot
   be checked" is `rules.not_matchable` + `rules.disabled`. The model only maps ids to rows
   (experience DP3).
3. **The view** draws, filters and navigates. Pan and zoom never re-render React.

## 2. Code layout

```
apps/web/scripts/gen-cascade-map.mjs     generator + deterministic layout (node, pure functions exported)
apps/web/src/cascade-map/graph.json       generated (prettier-ignored, parity test)
apps/web/src/cascade-map/model.ts         pure: labels, filterEdges, touchedNodes, matchedRows, matchedEdges,
                                          cannotCheck, move, byLabel, edgeGeometry, starField
apps/web/src/cascade-map/{graph,model}.test.ts   P1–P8
apps/web/src/components/cascade-map/
  CascadeMap.tsx   screen: framing, matches line, Map | List, filters, count, panel slot
  MapView.tsx      SVG constellation, pan/zoom engine, roving tabindex
  ListView.tsx     table alternative
  RulePanel.tsx    pattern / class panel (bottom sheet on phones, beside the map from 1024 px)
apps/web/src/theme/cascade-map.css        tokens-only styles for both themes
apps/web/src/app/[locale]/cascades/page.tsx
apps/web/e2e/cascade-map.spec.ts          map, list, keyboard, panel, axe, themes, locales, demo network, performance
```

## 3. Graph model (Req 1)

- **Node id** = rule class id without the role suffix `_index`, `_index_eye`, `_marker` (DP3). This
  merges exactly three cases: `beta_blocker_index_eye` (row 3), `beta_blocker_index` (row 4) and
  `beta_blocker_marker` (row 17) into `beta_blocker`; `nsaid` (rows 51–54) and `nsaid_marker`
  (row 40) into `nsaid`. A rule without a marker class (rows 27 bismuth subsalicylate, 57 saliva
  substitute, both `no_atc_code`) gets the node `row<N>:marker`. Result: **65 nodes, 65 edges**, no
  parallel and no opposite pair.
- **Edge** = `{row, from, to, event, supporting, unmatchable}`; `event` is the one Janus event key
  whose `pipc_positions` contains the row (the generator throws otherwise; all 65 rows have one).
- **Names** are not in the graph. `nodeLabel` takes, in the interface language, every published
  name of the class (`drug_a` of its index rows, `drug_b` of its marker rows) and shows the
  shortest one (ties: index rows first, then by row). Examples (EN): `statin` → "HMG Co-A
  reductase inhibitor" (rows 9–12 publish both the long and the short name), `nsaid` → "NSAID",
  `beta_blocker` → "Beta-blocker". The search matches every published name, so "statin" still finds
  rows 9–12. The panel and the list always show the row's own published wording.
- **Generated, committed, checked**: `node scripts/gen-cascade-map.mjs` writes `graph.json` with the
  sha256 of its three inputs; the parity test regenerates in memory and compares (P1), like the
  vocabulary (experience P13).

## 4. Layout (Req 2, DP2)

Fruchterman–Reingold in the generator: start on a golden-angle spiral over the sorted ids,
700 steps with linear cooling, edge attraction, all-pairs repulsion and a gravity of 2 (the rule
base has many small components; a weak gravity of 0.06 left a dense core with small components
flung to the corners, looked at and rejected), then the bounding box is scaled to the canvas and a collision
pass pushes pairs apart to the minimum distance and clamps to the margin. Coordinates are rounded
to integers. Same input → same output (P4). Each star also gets a preferred **label side**
(left or right: the side with fewer stars in a 260 × 90 unit band), used first by the label
placement of §6.

Canvas 1000 × 1250 units (4:5, the phone map's aspect), margin 70, **minimum distance 80**. At
375 px the map is 343 px wide, so the fit zoom is 0.343 px per unit and two stars are at least
27 px apart: the 24 px spacing circles of WCAG 2.5.8 never overlap (P5). Committed layout:
minimum distance 81 units, edge lengths 81–417 (mean 171).

## 5. View model (Req 3–6)

- `filterEdges(graph, {classId, event, query})` keeps graph order and only removes (P2). The query
  is folded (locale lower case, no diacritics, Turkish dotless i → i) and every word must occur in
  a published name of either class, the row's three texts, the event label or the row number.
- `touchedNodes(edges)` = nodes shown. Positions never change with a filter.
- `matchedRows(result)` = row → finding positions, from `findings[].rule_id` only; `matchedEdges` is
  the graph's edges with such a row (P3).
- `cannotCheck(graph, result)` = the result's `not_matchable` and `disabled` lists when there is a
  result; else the rule base's static `unmatchable` rows (27, 57). Integrity-disabled rules are
  therefore only known after an evaluation, as on the results scope card.
- `move(nodes, visible, current, dir)` = the visible star in that half-plane with the smallest
  `along + 2 × sideways` (ties by id), else stay (DP7, P6). `byLabel` gives Home / End and the class
  select order (`Intl.Collator` of the locale).

## 6. Screen (Req 3–8)

Order: title, intro, the framing line (a card, `role="note"`), the matches line (`role="status"`),
the segmented control Map | List (`aria-pressed` buttons in a labelled group), the filters (search,
class select, side-effect select in a fieldset), the polite count ("12 of 65 patterns shown") and
"Clear filters", then the map or the list, the keyboard hint, the legend; the panel to the right
from 1024 px (a hint + legend card when nothing is selected), a bottom sheet on phones.

**Matches line** states: evaluating (`aria-busy`); no list → "Add medicines …" + Scan; too many or
needs confirmation → the Medicines messages; error or `rule_base_unavailable` → "cannot be shown
right now. The map still shows every pattern." (+ retry for network/timeout); no finding → the
rule-3 sentence `Findings.noPattern`; else "N patterns match findings for your list. They are
drawn thicker and dashed." The map itself never waits for the evaluation.

**MapView** (DP4): one `<svg>` whose user units are CSS pixels; a `<g>` carries
`translate(x y) scale(k)` written from a `requestAnimationFrame`; `--inv = 1/k` on the svg keeps
stars, labels and arrowheads at screen size (`.cm-glyph { transform: scale(var(--inv)) }`), lines use
`vector-effect: non-scaling-stroke`. During a gesture `--inv` follows the zoom in 8 % steps and is
set exactly when the gesture ends (it restyles every star, label and arrowhead; §7).
**Label placement** (greedy, when the zoom settles or a drag ends, never per pan frame): labels are
taken in priority order — the focused, selected and selected-neighbour stars (always shown), then
the person's matches, then by number of patterns — and a label is shown on its preferred side, else
on the other side, only where its box overlaps no star and no label already placed and lies inside
the map box. Far out the map names the busy and the matched classes; close in, every class. Labels
longer than 26 characters are cut with "…" on the map only (full name in the accessible name, the
panel and the list). Labels sit in their own `aria-hidden` layer, outside the star buttons (axe
`label-content-name-mismatch`).
- Pointer: drag pans (4 px slop), two pointers pinch, Ctrl/⌘ + wheel zooms (a plain wheel scrolls
  the page), a tap (< 6 px) opens the nearest visible star within 26 px, else the line under the
  finger (an 18 px invisible hit stroke). `touch-action: none` on the map only.
- Buttons zoom in, zoom out, show the whole map (44 px round, bottom right). The button zoom eases
  for 180 ms with transform only; with `prefers-reduced-motion: reduce` it jumps. There is no
  animated settle: the layout is static (Req 2.3).
- Keyboard: stars are `<g role="button">` with a roving tabindex; arrows `move`, Home/End,
  Enter/Space open, + / − zoom; a keyboard move pans the star into view. Escape anywhere on the
  screen closes the panel and focus returns to the opener (the star, the list button or the class
  panel's star). Accessible name: "Statin: first medicine in 4 patterns, second medicine in 0
  patterns." plus "Part of a finding for your list." when matched. Lines are `aria-hidden`: the
  list view is their text alternative (Req 6.1).
- Draw order: plain lines, cannot-check lines, matched lines (on top); a selected star or line dims
  the rest (opacity) and the selected line shows its side effect at its midpoint.

**Theme** (Req 8.1, DP6): Night Pharmacy = the map box on `--bg` (midnight), a fixed field of 110
tiny `--fg` dots behind (static, `aria-hidden`, not panned), ivory stars with a teal edge and a soft
teal glow, teal lines; Glass Janus = the frosted card, no star field, no glow, white-filled stars
with a teal ring, `--muted` lines and teal matched lines. Matched = 4 px, dash 9/5, full accent;
cannot check = 2 px dotted `--muted`; legend in text in both themes. `--risk` is not used.

**Panel** (Req 4): eyebrow "Row N", title "A → event → B" (`Findings.cascade`), "Janus cannot check
this pattern: {reason}" with the scope card's reason words, a definition list (first class, side
effect, second medicine, published wording), `Findings.row49` for row 49, `Findings.supporting`
when a ThinkCascades id exists, the source line `Findings.source`, the evidence ids
(`rule:pipc:N`, `dataset:pipc`, supporting ids) in mono as in the evidence fallback of the finding
page, and — only with a result — "Your list": per matching finding the roles sentence
`Findings.medicinesRoles` with box names, the abrupt-stop line when an item is warned
(medical-safety rule 4), `Findings.discuss` and a link "Evidence and reports" to
`/results/finding#<position>`; else "None of the findings for your list uses this pattern." — or,
for a pattern Janus cannot check, the cannot-check line again (safety S2). When a matching finding's
event has a safety line (e.g. Cologne row 51 → `urgent_care_gi`) the panel starts with the
emergency notice and shows the safety line next to the finding, as the Results screen does (DP10).
Class panel: its patterns as first and as second medicine (buttons), the row-49 note for the
"deficiency" star, and "Show only this class".
The panel is a non-modal `role="dialog"`; its heading receives focus.

## 7. Performance (Req 7, DP2, DP4)

65 stars and 65 lines are small enough for SVG without culling: a pan frame changes one transform
attribute; a zoom frame also changes `--inv`, in 8 % steps (exact at the end). Filters run as a
transition (`useDeferredValue`): the urgent render updates the inputs, the map (a `memo` component
with stable props) re-renders afterwards in React's time slices. Accessible names are computed once
per filter. Experiments (same build, 375 px, CPU 4×, 60 frames each): panning by the transform alone
gave no long task and 16.7 ms frames; per-frame `--inv` updates were the only source of long tasks
when the host was busy, hence the stepping. The focus ring element exists only on the focused or
selected star.

Measured by `e2e/cascade-map.spec.ts` ("performance"): production build, Chromium, 375 × 812, CPU
throttling 4× (CDP `Emulation.setCPUThrottlingRate`), long tasks by `PerformanceObserver`
(`longtask`), frame intervals by `requestAnimationFrame` during: a 40-step pointer drag, six zoom
button presses, a pinch-free Ctrl + wheel zoom, and three filter changes.

### 7.1 Results

The test records the host's 1-minute load average with every run. On this 8-core machine, shared
with two other agents' builds, the load varied from 4 to 20 during the work; CPU throttling
multiplies whatever else runs, so the budget is asserted only when load / cores ≤ 0.75 and the
numbers are recorded either way (annotation `performance`).

| Run (2026-11-09, after the fixes) | Host load | Long tasks > 50 ms | Frames | Median frame | p95 frame |
|---|---|---|---|---|---|
| 1 | 4.6 | **0** | 224 | 16.7 ms | 33.3 ms |
| 2 | 4.6 | **0** | 219 | 16.7 ms | 33.3 ms |
| 3 | 4.0 | **0** | 221 | 16.7 ms | 33.3 ms |
| busy host (not asserted) | 12.9–15.2 | 2–4 (50–80 ms, zoom or wheel) | 201–211 | 16.7 ms | 50.0 ms |
| saturated host (not asserted) | 19.8–20.5 | 25–30 (50–225 ms) | 305–319 | 16.7 ms | 66.7 ms |

After merging into main (coordinator, 2026-11-09) the zoom buttons still gave 5 long tasks of 50–66 ms at load
4.6: `placeLabels` ran on every 8 % zoom step of the tween and read `getComputedTextLength()` between attribute
writes (a forced layout per label). Fix (DP14): text widths are read once, all before any write (they do not depend
on the zoom because labels are counter-scaled) and read again after `document.fonts.ready`; labels are placed only
when the zoom settles. Two runs at host load 6.0 and 8.8: **0** long tasks, median 16.7 ms, p95 33.2–33.3 ms.

Before the fixes (per-frame `--inv`, labels inside the star buttons, no deferred filter) the same
test at load 6–11 gave 10–19 long tasks of 50–110 ms, all in the zoom and wheel phases. A check on
a real mid-range phone is on the pre-launch checklist.

## 8. Correctness properties

| # | Property | Validates | Test |
|---|---|---|---|
| P1 | The committed `graph.json` equals the generator output; every PIPC row is exactly one edge from its index node to its marker node; every node lists exactly its edges' rows and has at least one. | Req 1.1, 1.2, 1.4 | `graph.test.ts`, example-based over the 65 rows |
| P2 | Filters only remove: for any filter the shown edges are a subsequence of the graph's edges; adding a filter never adds an edge; every shown edge satisfies each active filter; shown nodes are exactly the nodes of shown edges. | Req 3.2 | fast-check over class × event × query (incl. random strings) |
| P3 | Matched edges ⊆ edges, and equal the graph edges whose row is in `findings[].rule_id` (rule ids outside the graph ignored); finding positions point back at findings with that rule id. | Req 5.1 | fast-check over `cascadeResultArb` + random extra rule ids |
| P4 | The layout is deterministic: the same ids and links give the same coordinates. | Req 2.1 | fast-check over random graphs of 2–70 nodes |
| P5 | Every node is inside the canvas margin and no two nodes are closer than the minimum distance (committed layout and random graphs). | Req 2.2 | as P4 + the committed file |
| P6 | Keyboard: from any visible star, the arrow moves reach every visible star, for random filters and for every single class or event filter; a move stays on a visible star and goes in the pressed direction. | Req 6.2 | fast-check (60 runs) + exhaustive single filters (100 filters) |
| P7 | Names: every node has a vocabulary name (never its id); the label is the shortest published name; it follows the interface language. | Req 1.3 | examples EN/TR |
| P8 | "Cannot be checked" = the result's lists, else the static unmatchable rows. | Req 4.2 | examples |

## 9. Decisions

| # | Decision | Alternatives | Why |
|---|---|---|---|
| DP1 | Route **`/cascades`**, a wide page (1120 px from 1024 px); entries: the results scope card ("Explore all 65 patterns"), a card on the Research page, a footer link. Not in the bottom tab bar or the header navigation. | `/research/cascades`; `/results/patterns`; a tab. | It is reference material for patients and researchers alike; the scope card is where the "65" is mentioned; the tab bar stays at five places (design.md). |
| DP2 | **Layout precomputed** in the generator (force-directed + collision), committed as integers; **SVG** rendering without culling. | Client-side force simulation; canvas/WebGL; d3. | 65 nodes / 65 edges: SVG is cheap and gives real focusable elements, text and crisp lines; no settle animation (reduced motion for free); no new dependency; deterministic and testable (P4, P5). Measured in §7.1. |
| DP3 | **One star per class**: the role suffixes `_index`, `_index_eye`, `_marker` are removed; unmatchable markers get `row<N>:marker`. Other class ids are kept as they are (e.g. `antiparkinsonian` vs `dopaminergic_antiparkinsonian`, `pioglitazone_rosiglitazone` vs `rosiglitazone`, `vitamin_supplement` vs `ppi_deficiency_supplement`). | One star per published name; one star per class id. | Published names differ in wording for the same class (rows 9 vs 10–12); class ids differ only by role or form extension for the beta-blocker and NSAID cases. Merging more would claim equivalences the rule base does not make (pharmacologist pass). |
| DP4 | Pan/zoom writes the `transform` attribute and `--inv` from rAF; no React state per frame; counter-scaled glyphs keep 44 px hit circles and fixed label size. | CSS `transform` on a wrapper div (blurry when scaled, no counter-scaling); React state per move. | Crisp at every zoom, layout-free frames, smallest work per frame. |
| DP5 | Matches come only from `findings[].rule_id`; cannot-check from the result's lists; without a result the static unmatchable rows. The map calls `useEvaluation` like Results (cached result reused; no list → no request; demo → fixture). | Recompute matches from the list's ATC codes; a new API route. | Experience DP3: the client computes no cascade. Reusing the same hook keeps one source of truth and the demo offline. |
| DP6 | Theme looks as §6; matched = thicker + dashed + legend text; cannot-check = dotted + legend; never `--risk`; all wording theme-neutral (no paired `twoFaces`/`glass` keys needed). | Colour-coded classes or systems; a "ghost" metaphor. | WCAG 1.4.1 (colour never the only cue); red only for real risk; Glass forbids theme-device words. |
| DP7 | Arrow keys move to the **nearest star in that direction** (all visible stars), not "graph neighbours first". | Neighbour-first with a 60° cone (first draft). | The neighbour-first rule left stars unreachable by arrows (P6 failed: 63 of 65 reachable). Graph neighbours are listed in the class panel instead. |
| DP8 | The panel is a **bottom sheet on phones** (fixed, 72 svh, non-modal dialog) and a sticky aside from 1024 px. | Panel below the map in the flow. | In the list view the panel would land below 65 rows; a sheet keeps it next to the tapped item. Non-modal: the map stays usable. |
| DP9 | The list view is a two-column table (row, pattern as a button with its status), not five columns. | Five columns; card list. | Fits 343 px without horizontal scroll and keeps table semantics (`th scope=row`). |
| DP10 | Literature patterns show no emergency notice or urgent-care line; a pattern **with a finding for the person's list** whose event has a safety line shows the emergency notice first in its panel and the safety line next to the finding, as Results does. The abrupt-stop line is shown next to the person's medicines. | A `SafetyLine` for every event; none at all (first draft). | Rule 10 and experience Req 7 are about what is shown for the person; urgent-care lines for 65 literature events would make every visit alarming. The first draft (none) was changed by the safety-auditor pass (S4). |
| DP11 | Labels are placed greedily by priority with a side fallback (§6) instead of a zoom threshold. | Show minor labels only above 1.7 × the fit zoom (first draft). | The threshold version overlapped hub labels in the dense core and cut labels at the map edge (looked at in the 375 and 1440 screenshots). |
| DP12 | The performance budget is asserted only when the host is not saturated (load / cores ≤ 0.75); the numbers are always recorded. | Always assert; never assert. | CPU throttling multiplies the host's own load; on a saturated shared host the test measured the other agents, not the map (§7.1). |
| DP13 | `/cascades` is in the DEMO list of `e2e/routes.spec.ts` only; its plain (no list) state runs the same checks in `cascade-map.spec.ts`. | Also in PLAIN. | The plain-routes test has a 30 s budget for all its routes; one more route with 65 buttons pushed it over on a busy host. |
| DP14 | Label text widths cached (read in one pass before writes, refreshed after web fonts load); labels re-placed only when a zoom settles, not per tween step. | Re-measure per step; hide labels during zoom. | The per-step measuring forced a layout per label (50–66 ms at 4× CPU); widths are zoom-independent. Measured in §7.1. |
