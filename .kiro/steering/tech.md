---
inclusion: always
---

# Tech stack and engineering rules

> The stack below is the **recommended** option. Alternatives and the decision record are in `docs/internal/PLAN.md` §6. If the decision changes, update this file first.
> `docs/internal/` holds private Turkish planning documents (idea, architecture, plan, research notes). It is gitignored and not part of the public repo; never link to it from public files. Public English docs (architecture, data sources, Kiro usage) are written in Phase 5.

## Stack
- **Web:** Next.js (App Router) + TypeScript, installable PWA, Tailwind CSS with in-repo components (no shadcn/ui, owner decision 2026-11-08; design system in `design.md`), `next-intl` for EN/TR/DE/FR/ES/PT. Barcode decoding in the browser with `zxing-wasm` (DataMatrix + GS1). OCR fallback on-device with `tesseract.js`. No images leave the device.
- **Doctor note PDF:** generated **in the browser** (the medication list never needs to reach the server to produce the note); only evidence ids and the note token are exchanged with the API.
- **API:** Python 3.12 + FastAPI + Pydantic v2. Property-based tests with **Hypothesis** (the documented Kiro PBT path); unit tests with pytest.
- **Storage:** PostgreSQL 16 (`pg_trgm`, `unaccent` for multilingual name search) for application data; DuckDB (read-only files) for FAERS-derived tables and OnSIDES.
- **ETL:** Python + DuckDB/Polars jobs under `pipelines/`, one per source, scheduled (GitHub Actions cron, or the Janus Kiro Crew app).
- **LLM:** Claude (`claude-sonnet-5-5` default; `claude-opus-5-5` for hard Arabic extraction). Used only for language (explaining, translating, writing the note) — never for medical decisions.
- **Deployment:** Oracle Cloud Infrastructure (OCI), EU region, one VM with Docker Compose (Caddy for HTTPS, Next.js `standalone`, FastAPI, PostgreSQL). **Nothing is deployed to any server before Phase 5 of `docs/internal/PLAN.md`;** until then everything runs locally with Docker Compose. Images must build for both arm64 and amd64.
- **External APIs:** openFDA (API key required, 240 req/min), RxNav/RxClass (20 req/s, NLM attribution required), Crossref REST (retractions), Wikidata Query Service, CIMA REST (Spain). All external calls have timeouts, retries only when idempotent, and cached results.

## Core principle: deterministic medicine, LLM language
- Whether a cascade, signal or hypothesis exists is decided by deterministic code (rules, time logic, statistics). This code must be pure and property-tested.
- LLM output must reference evidence ids; an auditor step removes any sentence without evidence.
- Rule matching always works on **ingredient-level** ATC codes. A combination product's ATC code (e.g. `C09BB03`) is never matched against rules directly; the product is first decomposed into its ingredients.

## Regional design
- Region-specific code lives behind one interface (`RegionAdapter`: parse code → product → ingredients). Adding a country must not touch the cascade engine, memory or notes.
- Every resolved field records its source, region and source version date.

## Engineering rules
- Validate input at the API boundary; fail loudly; no silent catch-alls.
- Secrets only from environment / secret store. Never in code, logs or commits.
- Parameterized SQL only. Forward-only, reversible migrations.
- Prefer boring, proven libraries already in the stack over new dependencies.
- Every data source has a recorded version/snapshot date and license in the `evidence` table.
- Accessibility: WCAG AA, keyboard navigation, visible focus, alt text; every data view handles loading, empty, error and long-content states. Mobile-first (check at 375px).
- Before building UI, choose the design system with the `ui-ux-pro-max` skill and record it in `.kiro/steering/design.md`.
