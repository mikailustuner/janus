# Open data: safety-auditor review

**Date:** 2026-11-09 · **Reviewer:** safety-auditor (`.kiro/agents/safety-auditor.md`), a separate read-only agent
pass against `medical-safety.md`, `privacy.md`, `product.md`, `data-sources.md`. No files edited.

| # | Finding | Action |
|---|---|---|
| O1 | **Blocking:** the donation and outcome consent texts (2026-11-v2) name Collective Memory and research, not publication under CC BY; deletion cannot reach downloaded copies | Fixed in code (DP10): a layer is published only when every stored row has a consent version in `OPEN_RELEASE_CONSENT_VERSIONS` (empty); otherwise it is withheld whole and named. Proposed v3 consent sentence (five languages, in the review) goes to the owner and legal review (checklist) |
| O2 | "Asking again does not average the noise away" overclaims: the noise is redrawn when a cell's reports change | Reworded in `OpenData.rule.noise` (five languages) and `docs/open-data.md` |
| O3 | The empty text claimed "no group has reached 20", untrue once the sibling rule hides a group of 20+; direction missing | Reworded in five languages |
| O4 | Differencing across snapshots and against `/memory/shared` {a,b,c} can narrow a count | Documented in `docs/open-data.md`; a noisy threshold or a two-ingredient sibling rule inside `release_cells` is left to the owner (checklist) |
| O5 | "No TİTCK string" too absolute (codes and row counts in notes; the name hashes are reversible because the names are in `data/ingredient_synonyms.csv`) | Reworded: "no TİTCK list row, product name or barcode; some notes state codes or row counts"; the hashes are described as letting CI repeat the check. Whether `data/ingredient_synonyms.csv` itself conflicts with `data-sources.md` is an owner item (checklist) |

**What holds:** one release path; hidden cells never listed; outcomes filtered on `confirmed`; 503 without database
or noise key; version over released content only; no true count, age, sex or week in the CSV; nothing logged;
licences per file correct; "pseudonymous", never "anonymous"; no differential-privacy claim; reports not people;
nothing submitted upstream; honest empty state.
