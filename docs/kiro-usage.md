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

## 2026-11-07 — Phase 1: privacy spec (server side)
- Refined `privacy` requirements into EARS form, client-side criteria kept and tagged for the
  `experience` spec; design.md has 16 Hypothesis properties and 21 decisions. Owner decisions:
  adults only (age bands from 20), consent version stored, 24-month retention purge,
  `"demo": true` rejected, placeholder event vocabulary until `collective-memory`.
- Built in `apps/api`: an allowlist log formatter for every logger, an access-log middleware
  (request id, route template, status, latency), route kinds with a fail-safe "medical unless
  allowlisted" rule, JSON-only 64 KiB bodies, read-only transactions for medical routes, the
  `contributions` migration with CHECK constraints, donation and deletion endpoints, the
  EU-region guard, the retention purge, and the shared k = 20 / discrete Laplace module.
- Statistical test S1 (chi-square fit of the noise sampler) found that the discrete Laplace
  sampler used scale ε instead of 1/ε (the two integers of CKS20 Algorithm 2 were swapped);
  at ε = 1 both are the same, so only the ε = 0.1 case showed it. Fixed in
  `janus/memory/noise.py`.
- Property test P7 found that the donation model accepted `"explicit": 1` and
  `"age_band": 65.0`: Pydantic's `Literal` compares by equality even in strict mode. Fixed with
  strict `bool`/`int` fields plus explicit checks.
- The manual check in docker compose found that uvicorn still emitted an access record per
  request (reduced to a `suppressed` line by the formatter); the `uvicorn.access` logger is now
  disabled. The `log-guard` hook flagged `event` in `log_event()`; it is the log-event name,
  so the call was restructured rather than suppressed.
### Open items
- Phase 5: daily purge schedule; rate limiting at Caddy without storing or logging IPs (one
  source can still submit many donations until then); database roles; production Postgres
  log settings; Caddy access logs; backups and their retention; production EU region.
- `collective-memory`: replace the placeholder event vocabulary.
- `experience`: consent screen, privacy page (region, 24-month retention, what is stored), no
  donations in demo mode.
## 2026-11-07 — Phase 1: drug-resolution spec (Türkiye and United States)
- Refined `drug-resolution` requirements into EARS form; EU criteria kept and tagged for Phase 2.
  design.md has 24 Hypothesis properties and 23 decisions. Owner decisions: invalid-barcode
  TİTCK rows are not repaired and stay findable by name only; duplicate barcodes return every
  candidate; the client sends only GS1 AI (01) and (17), and the API still drops serial and lot;
  US products get route-based ATC selection.
- Built: GS1 and NDC parsers; `titck-2` (name-only rows, no split inside parentheses) and
  `us_ndc-2` (route, dosage form); name folding, salt stripping and a TR/INN spelling key; the
  combination-code classifier with a reviewed rule file and a route → ATC-group map (both drafted
  by the pharmacologist agent, owner-reviewed, uncertain rows checked against the WHOCC index);
  load-time preparation; a loader with a content-hash check and one-transaction switch; TR and
  US adapters; four POST-only medical routes.
- AMLIPIN (`C09BB03`) resolves to amlodipine `C08CA01` and lisinopril `C09AA03`; a topical US
  betamethasone keeps `D07AC01` and drops `H02AB01`.
- Measured coverage (DP22, reported): TİTCK 83.9 % of ingredient occurrences (target 85 %, not
  met; the gap is mostly parenteral-nutrition amino acids, electrolytes and vaccine strain
  fragments with no single-substance code); openFDA Rx 92.6 % of products fully mapped (target
  92 %, met); Wikidata/TİTCK group agreement 93.9 % (98.2 % if same-3-character disagreements
  are WHO re-codings; not individually documented).
- Counterexamples found by property tests:
  - P17: sorting ATC codes failed when one code had no product reference (`None` vs `str` in
    dataclass ordering); fixed with an explicit sort key.
  - P5: the TİTCK ATC bridge matched a salt form on a single product ("x hidroklorür") but not
    the plain name in a combination product; the bridge is now keyed by the salt-normalised name.
- Real-data checks found Wikidata aliases that made common names ambiguous (esomeprazole lists
  "omeprazole"); label hits now win over alias hits within a step. The pharmacologist review
  added a guard so that salt stripping cannot merge substances (sodium vs potassium
  bicarbonate, zinc acetate vs zinc gluconate, sodium calcium edetate vs edetate disodium).
### Open items
- TİTCK coverage below the 85 % target; more curated synonyms (`data/ingredient_synonyms.csv`)
  or a parenteral-nutrition decision would close part of the gap.
- `cascade-engine`: read codes only through `rule_input`; decide how `all_codes` findings are
  labelled; decide whether index-drug classes include systemically acting non-oral codes (e.g.
  timolol eye drops `S01ED`) — recorded in its requirements.
- Re-review both curated ATC files when WHOCC publishes a new ATC version.
- 12-digit NDC (FDA rule, effective 2033) not accepted yet.
- Phase 2: `eu_fr`, `eu_es`, `eu_name` adapters; de/fr/es labels in the name index.

## 2026-11-07 — Phase 1: evidence-integrity spec and build
- Refined `evidence-integrity` requirements into EARS form (original criteria and the four
  properties kept, Requirements 4-8 added), wrote design.md with 20 Hypothesis properties and 21
  decisions, then built it. The owner confirmed that only retracted evidence is excluded
  (`corrected`, `expression_of_concern`, `unknown` stay citable with their notice or status),
  that notices are shown as published, and that drug-resolution's hard-coded 14 days is replaced
  by the shared freshness rule (twice the cadence in `pipelines/sources.toml`).
- The PIPC paper is `corrected` in Crossref (a publisher correction notice of 2025-12-18). The
  API returns that notice next to the PIPC evidence and with every rule that rests on it; the
  record stays citable. Janus does not say what the notice changed, because Crossref does not.
- Spec check before building found that the `retractions` pipeline only reads DOIs of datasets,
  so a paper cited by a rule would never be checked; a curated paper list became a second input.
- The sticky-retraction rule is repeated in the loader against the database: a failed check row
  carries no notices, so without it a retracted record would lose its notice.
- Property test P9 disagreed with the code at first. The path-based reference followed the
  basis of a retracted DOI-bearing record; the requirement judges such a record by its own
  status, so the reference was wrong and was fixed.
- The rule gate (`rule_gate`) is a pure function over an immutable snapshot, ready for the
  cascade engine; its contract is recorded in the cascade-engine requirements.
## 2026-11-07 — Phase 1: cascade-engine spec and build
- Refined `cascade-engine` requirements into EARS form (all original criteria and the seven
  properties kept, Requirements 5-10 added), wrote design.md with 22 Hypothesis properties and 21
  decisions, and generated tasks.md with a stop after the curated mapping was drafted.
- Before citing the window paper (Hendrix 2024) and the eye-drop paper (Vander Zanden 2001), their
  DOIs were checked in Crossref. BMJ 2026 data is used only for the six cascades its abstract
  names with a number, described as "named in the abstract", never as "one of the 24".
- The pharmacologist agent drafted the PIPC-to-ATC mapping (66 classes, 202 patterns) and a
  review sheet; the validator was built first, so the draft was checked mechanically. The owner
  reviewed it with AI assistance: row 49 narrowed to B12, magnesium and oral iron; ten extra
  abrupt-stop groups confirmed; no eye-drop extension for row 4 (only a letter as source); every
  code first taken from Wikidata re-checked by hand on the WHOCC index. A pharmacist or physician
  review is still needed before any public claim.
- Decision on non-oral forms that act systemically: ophthalmic beta-blockers (`S01ED`) start
  row 3 only, as a cited form extension; PIPC has no bronchospasm or bradycardia row.
- Gate 1 passes on real data: AMLIPIN (`C09BB03`) gives the CCB → diuretic cascade from its
  amlodipine through the API, with the PIPC correction notice; logs hold no request values.
- The PIPC coverage report showed which rules cannot fire per region (midodrine, quinine and
  rosiglitazone have no TİTCK product; flunarizine has none in the US) and gave 102 synonym
  proposals, pending owner review. The first hint threshold (0.5) mostly matched unrelated salts;
  0.6 on salt-stripped names kept the true variants.
- Property tests found no engine defect. One generator mistake (P17) was fixed; one P20 failure
  in development did not reproduce in seven later runs and is recorded as unexplained.
- Follow-up for drug-resolution: give imipenem an ingredient-level code (today only the
  combination code `J01DH51`, so row 58 cannot see imipenem).

## 2026-11-08 — Phase 2: BDPM, CIMA and FAERS pipelines, FAERS count builder
- Refined `data-pipelines` for Phase 2 (Requirements 11-15, 24 new properties P17-P40, decisions
  DP14-DP33) and checked the sources first. Findings that changed the design: FDA now calls
  FAERS "AEMS"; the quarterly page links `2025Q4` and `2026q3` with different letter case and has
  a commented-out row and a wrong posting year for 2025 Q4; EU and EEA reports carry the single
  country code `EU`; the BDPM files use three encodings (two Windows-1252, one UTF-8); the AEMPS
  Nomenclátor already holds national code, ingredients, ATC, NTIN and GTIN, so the REST API is
  not crawled; the AEMPS host rejected a generic command-line User-Agent.
- `drug-resolution/eu-code-encodings.md` records, with sources, how the DataMatrix carries the
  French CIP13 (GTIN-14 = `0` + CIP13) and the Spanish national code (NTIN `0847000` + code +
  check digit, or GTIN + AI 712), and what is not verified (the Spanish code's check-digit
  algorithm; AI 710 to 714 other than 712). No French or Spanish box was seen.
- Owner decisions applied: region = occurrence country, else reporter country, US territories
  count as US, EU means EU-27 only; N for the 2x2 tables = reports with a mapped ingredient
  (all-reports total kept as a sensitivity figure); the FAERS name rules wait as a follow-up in
  `drug-resolution`, with their coverage impact logged; MedDRA terms only as published in FAERS,
  with the ICH trademark notice and a Phase 5 checklist item (`docs/pre-launch-checklist.md`).
- Core change (approved): a bounded-memory content hash with the same result as the in-memory
  rule, file-backed output and side tables. A first FAERS design would have needed 4 to 5 GiB;
  the real run peaks at 2.5 GiB.
- Real runs: BDPM 20,914 presentations; CIMA 30,900 presentations; FAERS 1,626,375 reports read,
  1,510,804 kept (111,604 superseded versions, 3,967 deleted cases); builder: 1,252,900 reports
  with a mapped ingredient, 84.0 % of ingredient occurrences mapped, 6.2 million pair rows.
- Property tests found: the builder crashed when no report in the artifact named an ingredient
  (P33 counterexample, empty mapping table; fixed). Generator mistakes fixed in my own tests:
  too many malformed BDPM lines made the file-level column check fail (P22), and a line-end
  check assumed that a report with a quote character survived deduplication (P31). Real data
  found two defects the generated data did not: a Polars expression used as a number in the
  FAERS parser, and the commented-out row and posting-date typo on the FDA page.
- The `api` suite needs `alembic upgrade head` on the test database before the database tests
  (otherwise 14 failures and 10 errors that are not code faults).

## 2026-11-08 — Phase 2: Collective Memory spec and first build steps

- Refined `collective-memory` (requirements, design with 31 properties and 22 decisions, tasks) from
  what `data-pipelines` actually built, and measured first on the real counts file: pair lookup
  p95 14 ms as built, 5.9 ms for one statement after physically sorting the tables (the file also
  shrank from 120 MB to 80 MB; an ART index gave no gain and made it 2.6 times larger); 372,863 pairs
  with at least 3 reports, 65 % of them meet the Evans criteria (Yates-corrected chi-squared), so the
  criteria hardly discriminate; the N = mapped-reports choice changes the five-class assessment of
  2.5 % of pairs against N = all reports.
- The statistician agent reviewed the statistics (approved with changes): Yates chi-squared,
  `disproportionate` needs at least 5 reports, no multiple-comparison correction but wording and
  ordering by report count, five-class sensitivity flag, and a sibling rule for user-layer cells
  because two nested cells, each at least 20, differ by 0 to ±4 within the noise and would reveal a
  smaller group.
- Owner decisions applied: FAERS is cited through one dataset record (`dataset:faers`) with a
  deterministic locator, no per-pair evidence records (decision recorded in `collective-memory`,
  `cascade-engine` and `evidence-integrity`); donations will accept Janus keys `J<n>`; Evans,
  Waller and Davis 2001 verified in Crossref and added to the evidence papers (Yates form cited from
  secondary use, full text paywalled).
- Built: the count file schema `faers_counts-2` (sorted tables, `mapped` flag, region-basis table;
  rebuilt in 421 s at 2.7 GiB peak, all unchanged table hashes identical), the pure statistics
  (`janus.memory.stats`, exact integer and `Fraction` arithmetic for the decisions), and the event
  vocabulary loader with a first proposal of 34 adverse and 5 benefit keys, all `proposed`.
  The pharmacologist agent reviewed the PT mappings (approved with changes, applied to the
  proposal). **Stop:** nothing uses the mappings until the owner reviews
  `.kiro/specs/collective-memory/event-mapping-review.md`.
- Property tests: P1–P6, P9 (pure part), P15, P28, P29. No counterexample beyond my own test
  mistakes (a wrong expected PRR in an example; the Haldane correction adds 0.5 to all four cells).
- Checkpoint 1: `apps/api` 409 passed (CI profile, PostgreSQL 16 after `alembic upgrade head`), ruff,
  pyright strict, `pipelines` 138 passed, web lint, types and tests green.

## 2026-11-08 — Phase 2: Collective Memory, FAERS layer built
- Owner review of the event mapping: all 34 adverse and 5 benefit keys accepted with changes
  (arrhythmia gains Torsade de pointes and ventricular tachycardia/fibrillation; balanoposthitis
  stays out). For `peripheral_oedema` I computed the assessment with and without "Peripheral
  swelling" for amlodipine, nifedipine, gabapentin and pregabalin: no class changed, so the key was
  activated. All 39 keys are `active`; the vocabulary is the package file
  `apps/api/janus/memory/memory_events.csv` (the API image build context is `apps/api`), the
  placeholder list is removed, and donations read the same file. The whole mapping still needs a
  pharmacist or physician before any public claim (pre-launch checklist).
- Built: `CountsReader` (read-only DuckDB, 1 GB memory limit, 4 threads, no external access),
  `POST /memory/pair`, `/memory/combination`, `/memory/regions`, `/memory/shared` and
  `GET /memory/snapshot`; the combination view with a pairwise fallback; the sibling rule and
  `release_table` for the user layers (k = 20, Laplace noise); migration `0007` so donations can
  name Janus keys `J<n>`; the dataset-level citation `dataset:faers` with a deterministic locator
  and a small cascade-engine hook; the `Memory` message catalogue in EN, TR, DE, FR and ES with a
  word-list guard (forbidden phrases, people nouns, causal, risk and reassurance words). One exact
  sentence ("not evidence that the medicine causes the event") is allow-listed in all five
  languages, and a test checks that only that exact sentence passes.
- Reviews: localization-reviewer (labels, then messages), safety-auditor and pharmacologist. Applied:
  number-first crisis and urgent-care lines (depression, severe skin reactions, arrhythmia) attached
  to every row that includes those events, citations on every object that carries a count, a notice
  that Turkish reports are few and self-selected, "not verified" wording in EN and DE, and a set of
  TR, FR and DE wording fixes. Not applied, owner decides: further safety lines (GI bleeding,
  seizures, heart failure), native-speaker check, EN-US spelling of "oedema/diarrhoea", crisis-line
  numbers per region. All are in `docs/pre-launch-checklist.md`.
- Counterexamples found by tests: a region with no reports has no `faers_totals` row, so the pair
  query lost it (fixed with a LEFT JOIN); a 422 response echoed an unknown field name from the
  request (now never echoed); the Spanish subjunctive "cause" was missing from the causal word
  list; plus mistakes in my own generators and expected values.
- Measured on the real counts file (build `20261108T020842Z-7445632a-f55a79cf-4714`, 1,510,804
  reports, 1,252,900 mapped): pair lookup p95 6.7 ms in the database and 11.7 ms through the route;
  regions 7.1 / 14.6 ms; a key over 6 PTs 73 ms; a 20-ingredient combination p95 196 ms (target
  250 ms); 8 concurrent clients p95 60 ms. Two threads were slower than four. The pairwise fallback
  lists events for the 5 pairs with the most reports and sets `events_omitted`.
- Open items for the owner are in design §12 and the pre-launch checklist: pharmacist review of the
  mapping, native-speaker check, extra safety lines, crisis-line numbers, the EudraVigilance public
  address, MedDRA notice wording (IFPMA), optional `faers_mapping_gap` table.
