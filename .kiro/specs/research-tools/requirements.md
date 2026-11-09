# Requirements: Research tools (Phase 1 — data screens)

> Owner request 2026-11-09: turn the Research area into tools researchers actually use. Phase 1 builds web screens
> on APIs that already exist: the data-quality report (`.kiro/specs/data-quality/` design §9), the FAERS onset
> table (`.kiro/specs/faers-onset-table/` design §7) and a page for developers and clinicians (docs/mcp.md,
> docs/cds-hooks.md, docs/open-api.md, data/open/). Phase 2 (model explorer, queued simulations) is its own spec,
> `.kiro/specs/simulation-service/`. Everything here is researcher-facing; nothing here is guidance for a person.

## Requirement 1: Data-quality report screen
1. THE screen SHALL show the latest run (date, version, first run or compared with the previous run) and the
   number of findings per class (confirmed error, needs pharmacist, benign difference) and per class × status
   (new, persisting, resolved).
2. THE screen SHALL list the findings with a filter by class, by status and a search over the English label, the
   key and the codes; a long list SHALL be shown in pages of 30 with "show more".
3. EACH finding SHALL show its check, the compared codes, the product count, the translated reasons, its upstream
   status and evidence links (Wikidata item, WHOCC group pages). Links SHALL only point to `https://www.wikidata.org`
   and `https://atcddd.fhi.no`.
4. THE screen SHALL explain how to report a finding upstream (a pharmacist checks it first; Wikidata, TİTCK, CIMA,
   Janus's own files) and SHALL say that Janus sends nothing itself.
5. THE screen SHALL offer the CSV, JSON and Markdown downloads with the version, licence and attribution.
6. THE screen SHALL NOT show any TİTCK product name, list row or barcode (the API carries none; the decoder keeps
   only the documented fields).

## Requirement 2: FAERS onset table screen
1. THE screen SHALL show all 65 PIPC rows in one table sortable by row, reports, reports with an interval, median
   and status, with `aria-sort` on the sorted column.
2. A median SHALL be shown only for `described` and `small_sample` rows, always with its exact 95 % interval; a
   `count_only`, `cluster_dominated`, `no_interval` or `no_candidate_reports` row SHALL show no statistic.
3. EACH row SHALL open a detail view with the counts first, the status in words, then (where allowed) the median,
   the exact interval and its coverage, the interquartile range as a chart with a table, the day-01 sensitivity, the
   Weibull shape only where published with its caveat, the date-quality counts, the row definition, the PIPC text
   as published, the row notes and the caveats.
4. EVERY onset screen SHALL say: descriptive only, not causal, not incidence; FAERS is spontaneous reporting;
   counts are reports, not people. Small-sample and count-only rows SHALL be labelled.
5. THE screen SHALL offer the CSV and JSON downloads with the version, FAERS quarters, licence, attribution and the
   MedDRA notice.

## Requirement 3: For developers & clinicians
1. THE page SHALL describe the MCP server, the CDS Hooks service, the public read-only API and the open data
   packages, with copyable configuration snippets and links to the documents.
2. THE page SHALL say the service is a research prototype, not a medical device and not for clinical use.

## Requirement 4: Shared
1. THE Research index SHALL list the three screens.
2. EVERY screen SHALL work in both themes and five languages, at 375 and 1280 px, axe-clean, with loading, empty,
   error (503 with retry, 404) and long-content states.
3. Demo mode SHALL answer from files recorded from the real local API (`scripts/record-research.mjs`), with no
   request.
