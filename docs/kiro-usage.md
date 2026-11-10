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

## 2026-11-08 — Phase 2: Collective Memory, owner decisions on the open items
- Three more safety lines: `urgent_care_gi` (`gastric_ulcer_bleed`), `urgent_care_seizure` (`seizures`),
  `urgent_care_breathing` (`heart_failure`), recorded in `experience` Requirement 7 beside the first three
  and in the vocabulary CSV (six lines in total).
- Regional numbers moved out of the sentences into the `Memory` catalogue, keyed by the user's region
  (`emergency` and `crisis` tables in all five languages, `EMERGENCY` and `CRISIS` in `messages.py`): US 911
  and 988 (call or text), TR 112, EU 112 plus the local crisis service, OTHER and UNKNOWN the local emergency
  number. Tests check that no safety sentence holds a number and that both tables have all five regions.
- EudraVigilance link is `https://www.adrreports.eu` (link only). MedDRA notice: short form on screen
  ("MedDRA® trademark is registered by IFPMA on behalf of ICH."), long form in NOTICE, `sources.toml` and
  the builder metadata of new builds; responses take the short form from the code, so the existing counts
  file needs no rebuild. English labels and messages use US spelling (edema, diarrhea, recognize); MedDRA PT
  strings and the permanent keys are unchanged.
- `faers_mapping_gap` is deferred to the `drug-resolution` EU and name-rules work (recorded there).
- Still on `docs/pre-launch-checklist.md`: pharmacist or physician review of the mapping, native-speaker check,
  re-check of every number and of the link, MSSO terms for PT display.
## 2026-11-08 — Phase 2: drug-resolution EU and name rules, tasks 15–19 and the review stop (task 20)
- Spec refined (requirements, design §11–§19, tasks 15–28) and owner decisions applied: imipenem option (b)
  (one reviewed component-code pair, DP43; `J01DH51` counts for a curated imipenem key only), AI (712) approved
  (DP19 extended; the API now **rejects** AI (21) with 422 `gs1_serial_not_accepted` instead of dropping it, test
  P50), `faers_mapping_gap` not built (DP36).
- Built, with no rule data enabled: coverage snapshot tool with `compare` and a `--rules` what-if option; region
  `EU` and key groups in the adapter interface; AI 712 in the parser; migration `0008`; language-aware name
  functions (`name_lists`, `names`, `matching`) with the anion-acid and biologic-suffix steps; rule-impact report.
  The dataset built with the new code maps every name of the five sources as before (0 changed names).
- Counterexamples and findings: the first Spanish vowel rule replaced the keys of Spanish labels and unmapped 5 TİTCK
  names on real data (fixed: French and Spanish labels get their own and the neutral keys; property P34 monotonic);
  `ruff check .` in CI also covers `migrations/` (two unused `noqa` failed the first push). 585 API tests green
  locally, CI green after the lint fix.
- Pharmacologist agent wrote `name-rules-review.md`. Accepted-set what-if: BDPM 67.6 → 81.9 %, Nomenclátor
  48.1 → 86.1 %, FAERS 84.0 → 86.6 %, TİTCK 84.6 % unchanged. Stopped at task 20 for the owner's review; ten
  decisions listed in the sheet (Section 10). WHOCC has no code for imipenem alone (only J01DH51).
- Tasks 21–28 (same day, after the owner accepted the sheet): the accepted rule data is enabled (word lists,
  connectors, the seven anion-acid rows, 24 French route rows, 26 synonym rows, biologic suffix and acid word order on;
  Spanish final vowel off; aceponate removed from the salt words as its own commit; `anhydre` a hydrate word). Measured
  after, key level: BDPM 67.6 → 82.2 % of occurrences, Nomenclátor 48.1 → 86.1 %, FAERS 84.0 → 86.6 %, TİTCK 84.6 %
  unchanged, openFDA Rx 91.7 → 92.4 %; with the ATC requirement of the loader BDPM is 80.5 %. The Istanbul gate and the
  counts build were re-run: the cascade result is unchanged, FAERS reports with a mapped ingredient grew by 28,844 and
  three keys lost reports for accepted reasons (hydrocortisone salts moved from the aceponate item to hydrocortisone;
  `alginate` and `pidolate` salts no longer map to the bare acid).
- Built: EU product builders and optional BDPM and Nomenclátor artifacts in the loader (213,213 products in the development
  database); France, Spain and no-open-database adapters with ordered key groups; EU name search; 503 instead of a false
  "not found" when a needed source is missing; coverage report EU bucket and `member_name_part` hints (hints 343 → 905, of
  which 271 come from the EU names and 294 from the new kind); imipenem as a reviewed component-code pair (`J2`,
  `J01DH51`) with migration `0010`, the engine guard and a row 58 example; migration `0009`.
- Counterexamples and findings: the loader's cleanup of old datasets ran for more than 50 minutes on the development
  database because deleting a product scanned `res_product_code` without an index (migration `0009`, now about 2 minutes);
  a French GTIN on a dataset without the BDPM used to give a "region adapter not available" notice and now gives 503
  (test changed); the route rule keeps the iodine of iodinated contrast agents and intravenous glutamic acid from taking
  the antiseptic and digestive codes (465 BDPM occurrences stay unmapped on purpose); the whole-word-part residual in FAERS
  re-measured at 0.30 % (2.48 % with the Phase 1 ladder; the earlier 0.13 % came from a narrower scan); an unquoted comma in
  a note broke the cascade rule-base loader for one row (refused loudly, fixed by quoting); a Turkish synonym string had
  reached the sheet and a test and was removed in a follow-up commit (it stays in the history of one commit).
- Tests: 672 API tests (0 skipped) including property tests for the EU builders (P29, P41–P47), adapters (P27, P30–P33), name rules,
  FAERS builder suffix counting and the component pair (P48), with the real-data tests run locally against the
  development database. Decisions and numbers: `.kiro/specs/drug-resolution/design.md` §19.

## 2026-11-08: doctor-loop (doctor note and outcome loop, server side)
- Spec refined in Kiro (EARS requirements, design with 34 properties and 31 decisions, tasks). Owner decisions applied
  before building: re-derive findings on the server; the QR token carries the finding codes in a signed payload in the URL
  fragment, so the server keeps only used note-id hashes and the outcomes (a pending server record was rejected); English
  INN with "name not translated" where a translation is missing; expiry on the Monday five weeks after the issue week.
- Built (tasks 1–14): binary token with 128-bit truncated HMAC, key rotation and a QR size rule (version 25, level M;
  the realistic worst case, 20 medicines and 18 findings, needs version 21); five-language glossary mechanism, builder,
  auditor and `POST /notes/document`; outcome store (migration `0011`), `/notes/token`, `/outcomes/form`, `/outcomes`,
  `/notes/withdraw`; the outcomes layer of Collective Memory; one disclaimer constant for all API responses. 785 API tests.
- Property tests found: a ratio of 0.005 printed as 0.00 and 99.95 as 100,0 (rounding fixed); month numerals split
  differently per language (the auditor now removes rendered parameters before looking for digits); the dev database had
  no `dataset:faers` record, so notes had no statistics until the integrity loader was rerun.
- Stopped at task 15: the pharmacologist and localization-reviewer agents reviewed the glossary drafts; twelve decisions in
  `.kiro/specs/doctor-loop/glossary-review.md`. The pharmacologist also found wrong Wikidata ATC codes on a few
  ingredient keys (for example ketoconazole with ketoprofen's code), a `drug-resolution` matter.

## 2026-11-08: wrong ATC codes (drug-resolution) and the doctor-loop glossary decisions
- The owner's glossary decisions came with one correctness bug that had to go first: ingredient keys carrying another
  substance's ATC code (ketoconazole with ketoprofen's code, mefenamic acid with tramadol's, esomeprazole with a former
  pregabalin code). Fixed in `drug-resolution` as its own change: a curated per-key exclusion file
  (`data/atc_code_exclusions.csv`, twelve rows), loader and builders threaded with it, properties P49–P50, DP45, and a
  review sheet (`.kiro/specs/drug-resolution/atc-code-review.md`) with the cross-check (RxClass, shared codes, WHOCC group
  pages checked by hand) and the measured effect. Seven of the twelve codes came from TİTCK single-ingredient products,
  not Wikidata as the pharmacologist agent had assumed. The dataset and the FAERS counts were rebuilt: three keys lost their
  counts (45 mapped reports), gate 1 of the cascade engine is unchanged.
- Glossary: all rows `accepted` after the owner's edits (wrong non-English ingredient cells cleared, English INN fixes,
  case, curated keys, template rewording, row 49, combination-code label, one outcome action per finding). New properties
  P35–P38; a test loads the committed glossary. Example notes for a synthetic patient in five languages were generated
  from the real glossary and read; they exposed three wording defects that no property test sees (a Turkish and a French
  sentence that started with a lower-case or an elided ingredient name, a German pronoun that did not match its noun).
- A CSV edit by string replacement broke a row (an unquoted comma); the glossary loader refused it loudly, and the edit was
  redone through the `csv` module.
- Still open: native-speaker and pharmacist or physician review (pre-launch checklist), merging the duplicate product keys.

## Phase 3 (2026-11-08)

Kiro credits ran out halfway through. Phase 3 (experience and medication-passport) was built with Kiro and Claude Opus 5.5 subagents, following the same Kiro specs (requirements → design → tasks, EARS, numbered DPs, property tests), the `.kiro/steering` files and the `.kiro/agents` definitions (localization-reviewer, safety-auditor, pharmacologist as separate review passes). The `.kiro/hooks` PostFileSave hooks ran after every file write through `.kiro/hooks/scripts/claude-dispatch.py`, which reads the same hook files and runs the same scripts. Home-page art (isometric night house, cabinet room, glass Janus mask) and the door transition video were generated with Google Gemini and Veo; ghosts, fireflies and motion are code.

## 2026-11-08 — experience tasks 1–12 (checkpoint 1)

- Built the client of `.kiro/specs/experience` tasks 1–12: same-origin `/api` transport with CSP and no-referrer headers, strict response decoders and request builders, the two themes (Two Faces, Glass) from the steering tokens, self-hosted fonts, the browser store, the shell, the demo (three synthetic patients recorded from the real local API), medicine list, timeline, results, finding detail with evidence and the FAERS pair, Collective Memory panels and the doctor note with a PDF made in the browser.
- Property tests (fast-check) found: a `record` entry treated as required by the decoder mutation test (P19); `γ`/`Δ` in reviewed ingredient names missing from every PDF font (3.3, fixed with a Noto Sans fallback); the 2020 Atkinson Hyperlegible lacking `İ` (switched to Atkinson Hyperlegible Next).
- Playwright checks found: an abrupt-stop line shown twice for one item on the results screen (C6) and a `GET /api/memory/snapshot` sent in demo mode after a reload, before demo mode was read (C4). Both fixed; C1–C3 pass with axe on 14 routes × 5 languages × 2 themes × 2 viewports.
- The `.kiro/hooks` medical-language and translation-completeness hooks ran after every write (through `claude-dispatch.py`); while drafting Turkish they flagged nothing, the catalogue tests caught "tanı" and "olasılık" before commit.
- All three owner demo cases reproduced on the real engine (Istanbul row 5 probable at 5 months; Cologne rows 1 and 51 form-unconfirmed; Ohio rows 24 and 31).

## 2026-11-08 — experience tasks 13–22, built with Claude Code

- Built scanning (GS1 outbound filter keeping only (01), (17), (712); zxing-wasm reader and camera; demo codes caught before any request), on-device label OCR with tesseract.js (models fetched with pinned SHA-256, never committed), the confirm screen, re-resolution after a dataset change, the outcome loop (QR opt-in, 28-day in-app reminder, withdrawal), the doctor page /o with its own small layout, donation with explicit consent and deletion, the privacy page, a hand-written service worker for the offline demo, and a bundle-budget script.
- Property tests found: an OCR selection index past the recognised words still sent a shorter query (P22); a decoder mutation test treating optional record entries as required (P19, test fix). Playwright found: a stale preview server serving an old build (test harness), and against the real local API, a donation form whose region default was read before the settings loaded.
- Checked end to end against the real local API: QR token → doctor page → answer stored → withdrawal; donation stored → deletion by token. Doctor page form ready in a median 2.1 s on a throttled 4G phone profile.
- Owner review polish applied: unslashed zero in Atkinson Hyperlegible Next, compact result cards, visible Glass colour fields, safe-area padding, and a small `web-e2e` CI job (en + tr) that runs beside the API job without adding wall time.
- Task 22: localization-reviewer, safety-auditor and pharmacologist passes run as separate agents from their `.kiro/agents` definitions; sheets in `.kiro/specs/experience/`.

## Desktop layout (owner decision 2026-11-08, Req 27 / DP41)
- Added Requirement 27 and DP41 to the experience spec before building; built before the task 22 stop.
- Shell: header nav + theme toggle from 768 px, bottom tab bar phone only; wide routes get 1,120 px main.
- Results grid (72ch findings column + sticky aside), medicines rows + timeline aside (desktop only, phone unchanged), Memory two columns, note paper at A4 proportions with actions aside, settings two columns, website home (mask halves link to both faces in Two Faces; colour fields in Glass).
- Caught by e2e: privacy link on home under 44 px target (now a button link); duplicate box names from the timeline aside broke a getByText (test uses the heading role; aside hidden on phone).
- no-hex test forced mask colours into tokens.css (--mask-shadow/--mask-light).

## Task 23 (owner decisions on the wording review)
- Applied ten decisions across web catalogues, note glossary (API), memory_events.csv, steering privacy/product, specs (Req 28, DP42–45, doctor-loop DP40–41, collective-memory DP25).
- Ran localization-reviewer and safety-auditor as separate read-only agents on the changed rows: 6 blocking found (lost ES sentence from a truncated dump; TR "bildirim" still meaning notice/answer; ES outcome heading; "Order not confirmed" keyed to status `possible`, which also covers after-window). All fixed; third order label added for the owner.
- Lessons: printing values truncated at 200 chars and rewriting from that dump silently dropped a sentence; a memory word-list test caught "olasılık"; e2e caught digits in a research empty state.
- Fixtures re-recorded (Ohio oral products by NDC); real-API e2e green with consent v2; API 861 passed with JANUS_TEST_DATABASE_URL set (earlier run without it skipped 223).

## Task 24 (cinematic homes)
- Native sticky + rAF scrubbing instead of GSAP (no dependency); video re-encoded with GOP 6, no audio; AVIF via ffmpeg libaom.
- Mid-task asset swap (isometric cabinet room + new door video) handled by re-encoding and moving the ghost anchors.
- Flaky e2e found: the layout's Suspense fallback keeps a hidden copy of the page until React reveals the shell (~300 ms throttle); locators scoped to #content.
- Reviews: localization 5 advisory, safety 8 advisory, all applied.
- Owner screenshot review: full-viewport hero with header overlay, slim emergency bar (measured header offset), whole-house framing via container-query math, misty ghosts, scene-3 ghosts as linked pointer shortcuts; a reviewer suggestion (ES "su número…") was rejected because the same value is substituted into "llame al {emergency}".

## 2026-11-08 — medication-passport tasks 9–11 (Claude Code)
- Built the Passport client list logic in `apps/web/src/passport/` (identity, merge, duplicate groups, presence request builder with fan-back, memory keys, typed strength entry) with fast-check properties P1, P2, P18, P20, P21; a Python test exports the server's literal sets and 500 typed-entry cases as fixtures the web tests read.
- Writing the entry-parity fixture showed that "40,680 mg" was read as 40.68 mg: an amount like "1,000" / "1.000" is a thousands group in one language and a decimal in another, so both implementations now refuse it (DP25). Reviewing the request builder showed that a box with one unrecognised ingredient would have been sent with its other keys only and could read "present"; such items are no longer sent (DP24).
- Drafted the `Passport` namespace (124 keys) in five languages with substitution and removal word lists; the rendered-message property (every plural branch) and the existing placeholder-parity test caught two branches whose argument lists differed between languages (TR, DE `not_in_source`), rewritten.
- Wording review stop (task 11): localization and safety passes found the Spanish salt/base caveat contradicting itself ("dosis" for both), the French BDPM line reading as disapproval and the Turkish openFDA line reading as "not FDA approved"; fixed. Ten decisions left for the owner.

## 2026-11-08 — medication-passport tasks 11 (answers) to 14 (Claude Code)
- Applied the owner's ten wording decisions and ran a pharmacologist pass: the "oral solid" group also holds effervescent and orodispersible tablets, so "to swallow" became "taken by mouth"; the Turkish "değiştirilmiş salımlı" (modified release) tripped the substitution word list and became "modifiye salımlı".
- Built the Passport screens (`/passport`, `/passport/item#id`), the nav entry, the medicine link and the duplicate notice slot; recorded the three demo patients' presence answers from the real local API (counts and codes only).
- The experience check C4 ("in demo mode nothing reaches the API") conflicted with the Passport's "demo calls the live endpoint first": the demo now uses only the recorded answers (DP26).
- Screenshot review showed "Strength: Strength not compared …" and "(as entered from the box)" on rows where the source had nothing to compare; both removed, and a render test now checks that the label appears exactly where a typed value was compared.
- Notes left in experience, drug-resolution and doctor-loop open items (origin label in the note slot not built yet).

## Phase 4 (2026-11-09) — light face and séance, built with Claude Code (Claude Opus 5.5)

- Same method as Phase 3: refined specs first (`light-face` DP1–DP20, P1–P16; `seance` DP1–DP16, P1–P21 and a web contract), then tasks, then separate review passes from `.kiro/agents`. Each spec was built on its own branch and merged with CI green.
- Light face: OnSIDES and openFDA label pipelines, curated goals and cases, a retrospective validation against 13 known repurposings. Only 2 of 13 reached the top 10, so the screens call it a **prototype**; the result is shown, not hidden.
- Séance: Canon Book 2 pipeline, a gold table from PMC3941892 (CC BY 3.0), an AI reader with two AI review passes. The best pairs reach 2 of 3 witnesses, so Gate 4 (three witnesses) was **not met** and the screen says so.
- The log-guard hook blocked 7 CLI prints of aggregate counts (false positives); they carry `# log-guard: ignore` pragmas now.
- Owner decisions applied to the experience spec before building: no light mode (DP48), and the home's "Step inside" button plays the door video once instead of scroll-scrubbing (DP49).

## Enhancements (2026-11-09) — built with Claude Code (Claude Opus 5.5)

Each item got its own spec under `.kiro/specs/` (requirements → design with DPs and properties → tasks), checkpoints, and pharmacologist, safety-auditor and localization-reviewer passes with fixes applied.
- **Card design** (experience Req 29, DP50–DP56): grouped lists, large titles, stat tiles and segmented controls across results, passport, memory, research, light face and séance; steering `design.md` gained the cards and layout system.
- **fhir-export:** R4 Bundle built in the browser and validated against the official schema fixture.
- **zombie-alert:** retraction check by date only, in-app alert, opt-in notification, note update, demo simulation.
- **cascade-map:** explorable map and table of the 65 PIPC patterns; label widths measured once (performance check).
- **janus-report:** one-glance summary and an opt-in share image made on the device (PNG 1080×1350, no request).
- **report-assistant:** on-device drafts for TÜFAM, MedWatch 3500B and EU national authorities with a cited channel table; owner decision: 3500B other medicines split into E10 (over the counter) and E11 (prescription) by product type.
- **time-machine:** Canon molecules (Wikidata/LOTUS CC0, PubChem), ADMET-AI, httk PBPK, a minimal compartmental model, FAERS time to onset and a cascade digital twin. The validation table shows the failures: httk was not credible for any of 4 drugs (haloperidol AUC off by 32×), so no "reaches an active level" sentence exists. Only amlodipine passed the gate for a patient timing sentence (35 reports, median 23 days).
- **open-data:** released outcome dataset (k = 20, noise, sibling rule), versioned cascade data package, OpenAPI document of public GET routes, and a corrections guide (5 Wikidata and 7 TİTCK errors listed, nothing submitted upstream).

What the checks caught:
- A property test showed the onset bootstrap interval depended on row order (9 vs 19 days for the same data); it is now order-independent.
- The medical-language hook flagged "diagnosis" in a curated time-machine note shown verbatim; reworded and rebuilt.
- The pharmacologist pass showed that the spec's patient timing sentence described the wrong interval; the spec was amended.
- The safety auditor blocked publishing donated data: the current consent texts do not cover a CC BY release, so stored cells stay withheld until a new consent version exists. The data package also leaves out 108 of 134 synonym rows that came from the TİTCK list.
- 12 wrong ATC codes stay excluded.

Process lessons:
- A chained merge command continued past a conflict. It was recovered from MERGE_HEAD and redone step by step; merges now run one step at a time.
- Subagents left unbounded polling loops; every brief now requires bounded waits.

State at the end: web 528 unit tests, Playwright 367 passed (axe, 375 and 1280 px, both themes, five languages), API 960 tests, CI green on all five jobs. Open items for experts are in `docs/pre-launch-checklist.md`.

## Phase 5 (2026-11-09) — public deploy, integrations and research data, built with Claude Code (Claude Opus 5.5)

Same method: a spec per item under `.kiro/specs/` (deploy, mcp-server, cds-hooks, data-quality, faers-onset-table), steering read first, the `.kiro/hooks` running after every write, and separate review passes from `.kiro/agents`.
- **deploy:** the public site at https://janusmeds.org on the owner's server behind a locally managed Cloudflare Tunnel: no inbound port, API and database on an internal Docker network, non-root read-only containers, host firewall rules that keep Janus containers away from the server and private ranges, build-on-host releases with health-gated swap, isolation probes and smoke tests, automatic rollback. A weekly timer fetches the TİTCK list on the server and rebuilds the data-quality report.
- **mcp-server:** seven read-only MCP tools over the public API (`.kiro/settings/mcp.json` starts it in Kiro).
- **cds-hooks:** CDS Hooks 2.0.1 `order-select` / `order-sign` service returning information cards from the cascade engine.
- **data-quality:** weekly comparison of ingredient codes across TİTCK, Wikidata, openFDA, BDPM and CIMA (220 findings in the first run: 12 confirmed errors, 102 for a pharmacist, 106 explained differences); upstream report drafts kept private.
- **faers-onset-table:** descriptive FAERS time-to-onset for all 65 PIPC rows (32 with usable intervals).
- **simulation service:** server-side virtual-population runs (R + httk) behind a database queue with two concurrent jobs, a queue cap, per-job time limit and a keyed-hash rate limit (no IP stored); no individual dosing, model error shown next to every result.
- **Clinical White:** Glass Janus became a light-only clinical theme (owner decision) with a new hero image.
- **Wording:** the "AI-reviewed, pending expert review" label was replaced by "Expert review has not yet been done" everywhere (owner decision).

What the checks caught:
- A local rehearsal of the deploy found that the API image could not start (repository-root paths at import), that the isolation probe passed without checking anything (`docker run` without `-i`), and that the stack shared the development compose project name; all fixed and now checked in CI.
- The first public release served no images, fonts or scanner files (`public/` missing from the standalone image); the smoke test now checks static files.
- A CDS Hooks property test generated an ingredient name ("SIN PROBLEMA") that tripped the medical-language list; the generator now excludes those words.
- The pharmacologist pass on CDS Hooks found three blocking mapping issues (e.g. eye-drop codes carrying oral codes); all fixed.
- The statistician pass on the onset table found zero-width bootstrap intervals on tied data and a date cluster that produced misleading medians; an exact interval and a cluster rule were added.

Research (not product): several pre-registered experiments on open data (cascade signals, PK timing, label divergence, label-based cascade discovery, older-adult exposure, label PK atlas). Most hypotheses were not supported; the results are written up honestly, and one note is public (`docs/research/httk-pop-older-adult-exposure.md`). Expert review has not yet been done.
