# Data pipelines

ETL jobs, one per source (spec: `.kiro/specs/data-pipelines/`). A separate uv project so ETL
dependencies stay out of the API image. Research prototype, not a medical device.

Phase 1 jobs: `pipc`, `titck`, `wikidata_ingredients`, `us_ndc`, `retractions`.
Phase 2 jobs: `eu_fr_bdpm`, `eu_es_cima`, `faers`.
Later phases: `onsides`, `canon`.

## Commands

```sh
cd pipelines
uv sync
uv run janus-pipelines run pipc                 # Europe PMC → data/pipc.csv (committed)
uv run janus-pipelines run titck                # newest TİTCK list, fetched at runtime
uv run janus-pipelines run titck --input FILE.xlsx [--snapshot-date YYYY-MM-DD]
uv run janus-pipelines run us_ndc               # openFDA NDC bulk download
uv run janus-pipelines run wikidata_ingredients # needs JANUS_CONTACT
uv run janus-pipelines run retractions          # run after pipc
uv run janus-pipelines run eu_fr_bdpm           # France: BDPM files (Licence Ouverte)
uv run janus-pipelines run eu_fr_bdpm --input DIR --snapshot-date YYYY-MM-DD   # local copies
uv run janus-pipelines run eu_es_cima           # Spain: AEMPS Nomenclátor de prescripción
uv run janus-pipelines run faers                # FDA AEMS (FAERS) latest four quarters, ~250 MB
uv run janus-pipelines run faers --quarters 2026Q3,2026Q2   # named quarters (back-fill)
uv run janus-pipelines status                   # current artifact per pipeline
uv run janus-pipelines promote NAME RUN_ID --by NAME   # promote a needs_review run
uv run janus-pipelines notice [--check]         # NOTICE from sources.toml
```

Exit codes: 0 succeeded, 1 failed, 3 needs review (not promoted), 4 refused (licence rule or
unknown source).

## Environment

| Variable | Use |
|---|---|
| `JANUS_DATA_DIR` | Artifacts directory (default `<repo>/.data`, git-ignored). Relative paths are relative to the repo. |
| `JANUS_CONTACT` | Operator contact in the User-Agent: an http(s) URL or an email. Required by `wikidata_ingredients`. Crossref gets `mailto` only for an email contact, otherwise the public pool. Never derived from git or the system. |
| `JANUS_CODE_VERSION` | Overrides the git commit recorded in manifests. |
| `HYPOTHESIS_PROFILE` | `dev` (default, 100 examples) or `ci` (300, derandomised). |
| `JANUS_TITCK_LIST` | Optional local TİTCK list for the integration test (skipped when unset). |

## Phase 2 notes
- `eu_fr_bdpm`: the three files use different encodings (Windows-1252, UTF-8, Windows-1252) and
  are decoded strictly; text is kept exactly as published (the licence forbids altering it).
  The snapshot date is the oldest of the three file dates.
- `eu_es_cima`: one 16 MB archive, XML read as a stream. The AEMPS host refused a generic
  command-line User-Agent on 2026-11-08; the pipelines send their own.
- `faers`: one row per deduplicated report (latest version per case, DELETE files applied);
  removed reports are in `removed.parquet` next to `rows.parquet`. Ingredient names stay as
  published; `python -m janus.memory.faers_build` (in `apps/api`) maps them and writes the
  DuckDB count tables for Collective Memory under `memory/faers_counts/` (outside `artifacts/`, which the loaders scan).
- Large outputs: a job may write its rows to Parquet itself; the core then hashes them in a
  bounded-memory stream (same hash as the in-memory rule) and records side tables in the manifest.
- Spill files go to `staging/<pipeline>/_scratch`, removed after every run.

## Data directory

```
.data/artifacts/<pipeline>/runs/<run_id>/   rows.parquet, manifest.json, evidence_source.json
.data/artifacts/<pipeline>/current          symlink to the promoted run (atomic switch)
.data/artifacts/<pipeline>/runs/<run_id>/<name>.parquet   side tables (e.g. faers removed.parquet)
.data/raw/<pipeline>/<run_id>/              downloads of cache-rule sources (never TİTCK)
```

Every manifest records source URLs, licence, snapshot date, source and content hashes, row
counts, exclusions with reasons, and the code version. A run whose row count changes by more
than 10% ends as `needs_review` and is not promoted until `promote` is run.

## Rules

- Sources, licences and storage rules live in `sources.toml`; NOTICE is generated from it.
- TİTCK lists (`runtime_only`) are never written to `data/` or any git-tracked path; tests build
  TİTCK-shaped workbooks in memory and no fixture is committed.
- External calls use timeouts, retry only GET/HEAD on connection errors, timeouts, 429 and 5xx
  (at most 3 times), and keep per-host rate limits.
- Logs carry run id, pipeline, outcome and counts only.

## Tests

```sh
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```

Tests make no network calls.
