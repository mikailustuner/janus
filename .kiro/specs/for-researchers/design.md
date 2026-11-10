# Design: Janus for researchers

## 1. Files
| File | Role |
|---|---|
| `apps/web/src/app/[locale]/research/for-researchers/page.tsx` | route |
| `apps/web/src/components/research/ForResearchers.tsx` | the page (static, no request) |
| `apps/web/src/research/forResearchers.ts` | code snippets and the route table (also read by tests) |
| `apps/web/src/components/research/Developers.tsx` | exports `Snippet` (copy button) for reuse |
| `apps/web/messages/*.json` | new namespace `ForResearchers` plus `Research.tools.forResearchers`; keys only added |
| `docs/for-researchers.md`, `docs/examples/onset_summary.py` | English twin and the example |

## 2. Decisions
| # | Decision | Why |
|---|---|---|
| DP-F1 | Route under `/research/`, listed first among the Research tools | the researcher area is the natural entry |
| DP-F2 | Reuse `Snippet` from `Developers.tsx` (export it) | one copy-button component, no second one |
| DP-F3 | Prose translated, code/URLs/identifiers verbatim | as the developers page |
| DP-F4 | Only GET routes of `docs/open-api.md` plus `GET /simulate/compounds` are listed; POST routes carry a person's medicines and are not public API | matches `open-api.md` |
| DP-F5 | The example uses the standard library only, sends its own User-Agent, one request | runnable anywhere; the public site returns 403 to the default agent |
| DP-F6 | Citation text is built from NOTICE's copyright holder and version strings; no DOI, no ORCID | not inventing authorship metadata |
| DP-F7 | Status line "Expert review has not yet been done" copied from the research notes | owner wording rule |

## 3. Page order
Ten-minute path → data → API → worked example → MCP → CDS Hooks → pipelines → research notes → limits and reporting → cite.

## 4. Tests
Unit (`src/research/forResearchers.test.tsx`): five-language key parity, wording rules, snippet equals
`docs/examples/onset_summary.py`, route table equals the markdown twin, rendered page contains the status line.
Playwright (`e2e/for-researchers.spec.ts`): 5 locales × 2 themes, axe, no horizontal scroll, 44 px targets,
forbidden phrases, copy button; the route is also in `routes.spec.ts` `PLAIN`.
