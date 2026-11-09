# Design: Research tools (Phase 1)

## 1. Routes and files
| Route | Component | Data |
|---|---|---|
| `/research/data-quality` | `components/research/DataQuality.tsx` | `GET /open/data-quality` (+ `.csv`, `.md` downloads) |
| `/research/faers-onset` | `components/research/OnsetTable.tsx` | `GET /open/faers-onset` (+ `.csv`) |
| `/research/faers-onset/row#<n>` | `components/research/OnsetRowView.tsx` | `GET /open/faers-onset/{n}` |
| `/research/developers` | `components/research/Developers.tsx` | static |

Models (decoders, clients, pure view rules): `src/research/dataQuality.ts`, `src/research/onset.ts`. Recorded
answers: `src/research/data-quality.recorded.json`, `src/research/faers-onset.recorded.json`
(`scripts/record-research.mjs`, from the real local API). All screens use the card primitives, the `StateView`
states, the `useCall` hook and a shared `useDemoClient` hook; the wide layout (1,120 px) like the time machine.

## 2. Decisions
| # | Decision | Why |
|---|---|---|
| DP-R1 | The decoders keep only the fields the screens show | Nothing else (e.g. a future product string) can reach the page |
| DP-R2 | Presentation rules of the onset table in `onset.ts` (`showsStatistics`, `showsShape`), not in components | One tested place for "never a number from a count-only row" |
| DP-R3 | Evidence links only on the two hosts the report uses | A link from data cannot become `javascript:` or another site |
| DP-R4 | English source texts (how to find, caveats in full, row notes, MedDRA terms, attribution) shown verbatim with `lang="en"`; translated short caveats and codes | Translations of reviewed English methods text would be a new, unreviewed text |
| DP-R5 | Onset row detail on its own route with the position in the fragment | Same pattern as the time machine; a code, not personal data |
| DP-R6 | Rows without a median sort last in both directions | No invented number to compare |

## 3. Properties (`src/research/research.test.ts`, fast-check)
| # | Property |
|---|---|
| R1 | Class × status counts sum to the report's `by_class` and `by_status` |
| R2 | A filter keeps exactly the matching findings, independent of input order; class filters partition the list |
| R3 | Evidence links only on https Wikidata / WHOCC; no TİTCK barcode in the recorded file; decoded finding keys are exactly the documented ones |
| R4 | 65 rows, positions 1-65, fixed framing fields, interval count ≤ candidates |
| R5 | Statistics only for described / small-sample rows; shape only for described |
| R6 | Sorting is a permutation, independent of input order, rows without a median last |

Rendered checks: `e2e/research-tools.spec.ts` (four pages × two themes × five locales × 375/1280 px with axe,
horizontal scroll, touch targets, forbidden phrases, no barcode; filters, sorting, presentation rules, 503, 404,
demo mode without requests, copy button, Research entries).

## 4. Reviews
Safety auditor, localization reviewer and statistician (read-only agents): `review-*.md` in this folder.
