# Implementation Plan: Light Face

> Scope: `pipelines/janus_pipelines/jobs/{onsides,openfda_label}.py`, `data/light/`, `data/evidence_papers.csv`,
> `pipelines/sources.toml` (+ NOTICE), `apps/api/janus/light/`, the `/light/*` routes, `apps/web/src/light/`,
> `apps/web/src/components/light/`, the `/research/*` routes, the `Light` namespace, `docs/light-face-validation.md`,
> `docs/pre-launch-checklist.md`. Requirement numbers refer to requirements.md; P1–P16 and DP1–DP20 to design.md.
> No owner stop (Phase 4 brief): reviews are agent passes with sheets, marked "AI-reviewed, pending expert review".
> No health data in logs, fixtures or test output.
> **Checkpoints** (every step): `uv run ruff check .`, `uv run ruff format --check .`, pyright strict, pytest with
> `HYPOTHESIS_PROFILE=ci` including database tests after `alembic upgrade head` on `janus_test`; web `npm test`,
> `npm run lint`, `npm run typecheck`; commit in the worktree branch (the manager merges).

- [x] 1. Sources, licences and citations
  - Verify the OnSIDES licence and release (done in design §1.1), openFDA label (CC0, registry), every DOI in Crossref.
  - `sources.toml`: cadence for `onsides` (91) and `openfda_label` (30); one `cited_only` source per paper; NOTICE
    regenerated. `data/evidence_papers.csv`: the papers of design §8.1 and DP6. _Requirements: 2.1, 2.4, 5.1, 6.1_
- [x] 2. `onsides` pipeline (design §3.1)
  - [x] 2.1 Tests: pinned hash refusal, parse of a synthetic zip, accounting, side tables. _Requirements: 6.1_
- [x] 3. `openfda_label` pipeline (design §3.2)
  - [x] 3.1 Tests: query building, generic-name filter, synthetic responses. _Requirements: 6.2_
- [x] 4. Curated files and loaders (`curation.py`, design §4)
  - [x] 4.1 Property test P10 (committed files load; injected defects named). _Requirements: 2.1, 5.1_
- [x] 5. Pure signals: `keys.py`, `labels.py`, `inverse.py` (design §5)
  - [x] 5.1 P5, P6, P12, P2 (label part). _Requirements: 1.1, 2.2, 2.3_
- [x] 6. Ranking and candidates (`ranking.py`, `candidates.py`, design §6)
  - [x] 6.1 P7, P9, P15, P2 (merge part). _Requirements: 1.3, 4.4_
- [x] 7. Validation (`validation.py`, `report.py`, design §8)
  - [x] 7.1 P4, P11 on synthetic data. _Requirements: 5.1–5.3_
- [x] 8. Build CLI and store (`build.py`, `store.py`)
  - [x] 8.1 P4 end to end on a synthetic input set (byte-identical, order-independent). _Requirements: 6.3, 6.4_
- [x] 9. **Checkpoint: real data.** Run both pipelines and the build on the dev data; record facts and the validation
  table in design §14; generate `docs/light-face-validation.md`.
- [x] 10. Review passes (design §12): pharmacologist sheet, statistician sheet; apply changes; rebuild; record in §14.
- [x] 11. Cards, patient layer, messages (`cards.py`, `benefit.py`, `messages.py`)
  - [x] 11.1 P1, P3, P8 (database test with synthetic donations on `janus_test`). _Requirements: 3, 4.1, 4.5_
- [x] 12. API (`schemas.py`, `service.py`, `router.py`, `export.py`, app wiring)
  - [x] 12.1 P13, P14 (database tests for integrity filtering). _Requirements: 4.2, 6.4, 6.5_
- [x] 13. Web: `Light` namespace (five languages), client and pure view logic, screens
  - [x] 13.1 vitest + fast-check P16; message tests; source scan. _Requirements: 4, 5.2, 5.3_
  - [x] 13.2 Playwright: routes, states, axe, 375/1280, both themes; screenshots. _Requirements: 4.3, 5.2, 5.3_
- [x] 14. Final checkpoint: all suites green; pre-launch checklist item; decisions for the experts listed.
