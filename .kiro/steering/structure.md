---
inclusion: always
---

# Repository structure

```
.kiro/              steering, specs, hooks, agents, settings/mcp.json  (never gitignored)
apps/web/           Next.js PWA (i18n: en, tr, de, fr, es)
  src/scan/           zxing-wasm decoding, tesseract.js OCR (on-device)
  src/note/           doctor note PDF (in the browser)
  src/demo/           judge/demo mode: sample codes, synthetic patients
apps/api/           FastAPI service
  janus/regions/      RegionAdapter + adapters: tr/, us/, eu_fr/, eu_es/, eu_name/ (DE and others by name/OCR)
  janus/resolution/   code → product → ingredients → ATC → RxCUI (+ Wikidata QID)
  janus/cascades/     cascade engine (pure functions)
  janus/memory/       PRR/ROR, k-anonymity, differential privacy
  janus/integrity/    retraction and freshness checks for every evidence record
  janus/passport/     cross-region ingredient equivalents
  janus/light/        inverse signals, side effect → indication, retrospective validation
  janus/seance/       three-witness synthesis
  janus/notes/        note content model + signed QR tokens + outcomes
  janus/agents/       narrator, auditor (LLM wrappers)
  janus/observability/ allowlist log formatter, access-log middleware, error handler
  janus/http_policy/  route kinds (operational / medical / donation), body policy (JSON only, 64 KiB)
  janus/db/           PostgreSQL pool; read-only and write transactions
  janus/contributions/ donations: model, report week, deletion tokens, retention purge, repository, router
  janus/privacy/      storage-region guard and endpoint
  janus/cds/          CDS Hooks 2.0 service (discovery, order-select / order-sign cards)
  janus/recalls/      recall check: US product code (and lot) against FDA enforcement report records
  janus/plaininfo/    plain medicine information: fixed group sentences in five languages, the US label's indications as a quotation, FR/ES product page links
  migrations/         Alembic migrations (forward-only, each with a downgrade)
  tests/              pytest + Hypothesis (property tests next to the module they test)
apps/mcp/           MCP server (janus-mcp): a thin client of the API for AI assistants
pipelines/          ETL jobs: titck, us_ndc, us_recalls, us_labels, eu_fr_bdpm, eu_es_cima, wikidata_ingredients, onsides, faers, pipc, retractions, canon (OpenITI)
data/               small, redistributable files only (e.g. PIPC table, CC BY; curated mappings)
docs/               public English docs: docs/kiro-usage.md now; architecture and data-source docs in Phase 5
  internal/           PRIVATE Turkish planning docs (idea, architecture, plan, research notes) — gitignored, never committed, never linked from public files
LICENSE, NOTICE     code license; data attributions (OpenITI, OnSIDES, PIPC, NLM, WHOCC, openFDA, BDPM, AEMPS CIMA, Wikidata, Crossref/Retraction Watch)
```

## Conventions
- Medical logic lives in pure modules with no I/O; adapters (DB, HTTP, LLM, region data) are separate.
- One spec per bounded area under `.kiro/specs/<area>/`.
- Downloaded third-party files with unclear redistribution terms (e.g. TİTCK lists) are fetched at runtime and are **not** committed. Files with open licences (BDPM, CIMA extracts) may be cached but must keep source attribution and update date.
