# Kiro usage log

A dated log of how Kiro was used to build Janus: what specs caught, what property tests
found, what hooks blocked. Three to five lines per day.

## 2026-11-07 — Phase 0: repository skeleton

- Kiro (Vibe session, Autopilot) read the six steering files and the private planning
  documents, then proposed a plan for the Phase 0 skeleton. I approved it with changes
  (planning documents kept private in a gitignored folder) before any file was created.
- Kiro created the monorepo from `.kiro/steering/structure.md`: Next.js 16 web app
  (TypeScript strict, Tailwind v4, next-intl with EN/TR/DE/FR/ES, standalone output) and
  a FastAPI app (Python 3.12, uv, pytest, Hypothesis, ruff, pyright strict). The API has
  only empty modules and `/health`.
- Following `medical-safety.md`, Kiro added a test that checks every translation file for
  the forbidden phrases in all five languages, plus a key-parity check across languages.
- While wiring Docker Compose, Kiro found another local service already on port 3000 and
  moved the web port to 3100 (configurable) instead of stopping that service.
- CI (GitHub Actions) runs lint, type checks and tests, and fails if `.kiro/` is
  gitignored, a TİTCK list file is tracked, or a private planning document is tracked.

### Agent hooks

- Added hooks in `.kiro/hooks/`: `medical-language-guard`, `log-guard`, `license-guard`
  (+ `-create`) and `translation-completeness` run shell commands (no credits);
  `kiro-log` (PostTaskExec) and `kiro-log-stop` (Stop) are agent prompts that write this log.
- Each guard was tested against a planted violation: the medical-language guard flagged
  `"gereksiz ilaç"` and `"stop taking"` with path:line; log-guard flagged
  `logger.info(..., ingredients)` and an `atc_code` in `extra`; license-guard flagged a
  renamed CSV by its TİTCK column headers (BARKOD, ÜRÜN ADI, ETKİN MADDE, ATC KODU).
- Testing the translation hook showed the key-parity test did not say which key was
  missing; it now names missing and extra keys (`Home.status` in `de.json`).
- The phrase scan of `apps/` is a vitest test (`source-scan.test.ts`), so CI enforces it too:
  Node here is built without TypeScript stripping, so a standalone script couldn't reuse the
  phrase list.

- `kiro-log-stop` is disabled (`"enabled": false`): it fires an agent prompt at the end of
  every run, which costs credits even when it decides there is nothing to log. The
  `kiro-log` hook on spec-task completion stays on and is now the only automatic log writer.

### Custom agents

- Added five workspace agents in `.kiro/agents/` (Markdown with YAML front matter):
  `pharmacologist`, `statistician`, `historian` (can write, no web), `safety-auditor` and
  `localization-reviewer` (read-only: `read` tool only, no write or shell).
- Each agent loads the steering files for its area through `resources`.

## 2026-11-07 — Phase 1: data-pipelines spec and the first pipelines

- Refined `data-pipelines` requirements into EARS form (scope: pipc, titck,
  wikidata_ingredients, us_ndc, retractions), then wrote design.md with 16 Hypothesis
  properties traced to requirements, and tasks.md. The owner confirmed that a run flagged for
  review is not promoted until a maintainer promotes it.
- Before the design, the live sources were checked: Europe PMC Table 1 has the statin cascade
  split across two table rows, so a naive parser finds 64 cascades; the design merges split
  rows and fails unless exactly 65 are found. The real run found 65.
- Property test P12 found a counterexample in the TİTCK ingredient splitter: for `", ve "` the
  comma pattern swallowed the space before "ve", so "x, ve y" came out as "ve y". Fixed by
  treating a run of separators as one split point; a regression test was added.
- The local run of `titck` (live download, 06.11.2026 list) gave 22,982 products, 99.5% with
  ATC, 4,355 multi-ingredient products; AMLIPIN (C09BB03) splits into amlodipine and
  lisinopril. `us_ndc` gave 138,262 records, matching the openFDA index.
- NOTICE is now generated from `pipelines/sources.toml` and checked in CI.
- Contact for Wikidata/Crossref: the owner chose a public URL and no email anywhere. Checked
  first: the Wikimedia User-Agent policy accepts a website as contact, and Crossref allows the
  anonymous public pool (5 single-record requests/s, 1 concurrent). `JANUS_CONTACT` replaced
  `JANUS_CONTACT_EMAIL`; Crossref gets `mailto` only for an email contact.
- `wikidata_ingredients` gave 3,766 items with ATC codes (2,422 with RxCUI; labels: en 3,757,
  fr 2,813, de 2,284, es 2,284, tr 1,269), no query split needed. `retractions` checked the PIPC
  DOI: status `corrected` (publisher notice 10.1007/s41999-025-01378-7, 2025-12-18). The notice
  only moves the article to CC BY 4.0 on 30 Sep 2025; Table 1 is unchanged.

### Open items

- **arm64 image build not verified.** Images currently build and run on amd64 only; base
  images and lockfiles support arm64, but no arm64 build has run (no QEMU emulation set up,
  by decision). The Oracle Cloud shape (Ampere arm64 or x86) is decided at the end of
  Phase 3; if arm64 is chosen, verify with `docker buildx build --platform linux/arm64`
  before Phase 5.
- **Hooks not yet seen firing in the IDE.** Hook files load at session start; the command
  hooks were run by hand with a sample event, and the `kiro-log` prompt was followed by hand.
  Confirm in the next session; watch `kiro-log-stop` for repeated no-op runs (credit cost).
- **155 TİTCK rows excluded as `invalid_barcode`** (06.11.2026 list): 83 are 13 digits with a
  wrong check digit, the rest are empty, 12, 14 or 16-17 characters (e.g. a leading `:`). They
  are kept out of the lookup, not repaired; whether to recover any is a `drug-resolution` decision.
