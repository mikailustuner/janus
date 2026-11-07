# Data pipelines

ETL jobs, one per source (spec: `.kiro/specs/data-pipelines/`). A separate uv project so ETL
dependencies stay out of the API image. Research prototype, not a medical device.

Phase 1 jobs: `pipc`, `titck`, `wikidata_ingredients`, `us_ndc`, `retractions`.
Later phases: `eu_fr_bdpm`, `eu_es_cima`, `onsides`, `faers`, `canon`.

## Commands

```sh
cd pipelines
uv sync
uv run janus-pipelines run pipc                 # Europe PMC → data/pipc.csv (committed)
uv run janus-pipelines run titck                # newest TİTCK list, fetched at runtime
uv run janus-pipelines run titck --input FILE.xlsx [--snapshot-date YYYY-MM-DD]
uv run janus-pipelines run us_ndc               # openFDA NDC bulk download
uv run janus-pipelines run wikidata_ingredients # needs JANUS_CONTACT_EMAIL
uv run janus-pipelines run retractions          # needs JANUS_CONTACT_EMAIL; run after pipc
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
| `JANUS_CONTACT_EMAIL` | Contact address in the User-Agent (and Crossref `mailto`). Required by `wikidata_ingredients` and `retractions`; never set from a personal default. |
| `JANUS_CODE_VERSION` | Overrides the git commit recorded in manifests. |
| `HYPOTHESIS_PROFILE` | `dev` (default, 100 examples) or `ci` (300, derandomised). |
| `JANUS_TITCK_LIST` | Optional local TİTCK list for the integration test (skipped when unset). |

## Data directory

```
.data/artifacts/<pipeline>/runs/<run_id>/   rows.parquet, manifest.json, evidence_source.json
.data/artifacts/<pipeline>/current          symlink to the promoted run (atomic switch)
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
