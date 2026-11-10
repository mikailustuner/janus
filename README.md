# Janus

**Live: [janusmeds.org](https://janusmeds.org)** · English, Türkçe, Deutsch, Français, Español

> Janus provides information, not medical advice. Research prototype — not a medical
> device (not FDA-cleared, not CE-marked). Expert review has not yet been done.

Janus reads the medicines in a person's home — from the code on the box, a photo of the
label or the medicine's name — and looks for **prescribing-cascade patterns**: cases where
a side effect of one medicine may have been mistaken for a new condition and treated with
another medicine. Each pattern is linked to its published source and turned into a short
note the person can take to their doctor, in the doctor's language.

Janus never tells anyone to start, stop or change a medicine, and never says a medicine is
safe. When it finds nothing, it says which sources it checked and when.

Built for the Kiroween 2026 hackathon with the Kiro method (steering, specs, hooks and
review agents in [`.kiro/`](.kiro)); the development log is
[docs/kiro-usage.md](docs/kiro-usage.md).

## What it does

| Feature | What the person gets |
| --- | --- |
| Cascade check | Patterns from the published PIPC cascade list that match the medicine list, with sources and a doctor note |
| Ways in | Barcode / GS1 code, label photo (read on the device) or the ingredient name — works for a box from any country when the ingredient name is printed in Latin letters |
| Safety check | Same ingredient or same ATC subgroup twice; US label "Drug Interactions" passages that name another medicine on the list (quoted, no grading); three openly licensed anticholinergic burden scales, cited |
| Recall check | Whether a US product or lot appears in an FDA recall (enforcement) record, quoted from the record |
| Medication passport | Products with the same active ingredient in another country (France, Spain, United States, Canada, Italy), with strength and form shown as same / different / unknown — never "equivalent" |
| Medicine information | What kind of medicine it is, in plain words in five languages, plus the official label text quoted untranslated |
| Research tools | Time machine (evidence over time), séance (evidence synthesis), FAERS onset table, data-quality report, population simulation with measured model error |

Product data: Türkiye (TİTCK), France (BDPM), Spain (CIMA), United States (openFDA),
Canada (Drug Product Database) and Italy (AIFA). Every source, licence and attribution is
listed in [NOTICE](NOTICE).

## For researchers

Open data packages, the public read-only API, the MCP server, the CDS Hooks service, the
pipelines and a worked example, in one place:
[docs/for-researchers.md](docs/for-researchers.md) (also at
[janusmeds.org/en/research/for-researchers](https://janusmeds.org/en/research/for-researchers)).

- [Open data](docs/open-data.md) · [Public API](docs/open-api.md) · [MCP server](docs/mcp.md) · [CDS Hooks](docs/cds-hooks.md)
- Research notes: [HTTK-Pop and older-adult exposure](docs/research/httk-pop-older-adult-exposure.md),
  [negative results](docs/research/negative-results.md)
- Errors we found in open sources: [docs/contributing-corrections.md](docs/contributing-corrections.md)

## Status and limits

- Expert review has not yet been done: medical wording, translations and mappings were
  checked by automated review passes only. Open expert reviews are listed in
  [docs/pre-launch-checklist.md](docs/pre-launch-checklist.md).
- Cascade patterns come only from published, cited lists; Janus does not invent rules.
- The simulation uses virtual populations only — no individual dosing.

## Repository layout

| Path         | Contents                                                       |
| ------------ | -------------------------------------------------------------- |
| `apps/web/`  | Next.js web app (PWA), five languages                          |
| `apps/api/`  | FastAPI service (Python 3.12), PostgreSQL                      |
| `apps/mcp/`  | Read-only MCP server over the public API                       |
| `pipelines/` | Data ETL jobs, one per source                                  |
| `data/`      | Small, redistributable data files and open data packages      |
| `deploy/`    | Hardened self-hosted deployment ([deploy/README.md](deploy/README.md)) |
| `docs/`      | Documentation and research notes                               |
| `.kiro/`     | Kiro steering, specs, hooks and review agents                  |

## Local development

Requirements: Docker with Compose, or Node 24 + pnpm 12 and
[uv](https://docs.astral.sh/uv/).

With Docker:

```sh
cp .env.example .env    # set POSTGRES_PASSWORD
docker compose up --build
```

- Web: http://localhost:3100
- API health check: http://localhost:8000/health

Without Docker:

```sh
pnpm install
pnpm dev                          # web on http://localhost:3000

cd apps/api
uv sync
uv run uvicorn janus.main:app --reload
```

Checks (the same ones CI runs):

```sh
pnpm lint && pnpm typecheck && pnpm test
cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

The demo needs no sign-up: three synthetic patients with invented product names.

## Privacy

Images and label text never leave the device; barcode decoding and OCR run in the
browser. Medication lists (including a lot number read from the box) stay in the browser;
the API receives only what a check needs, such as an ingredient or product code, and does
not store lists. No account, no tracking cookies. Details:
[janusmeds.org/en/privacy](https://janusmeds.org/en/privacy).

## License

Code: [Apache License 2.0](LICENSE). Copyright 2026 Mikail Üstüner.

Third-party data sources keep their own licenses and terms; see [NOTICE](NOTICE).
