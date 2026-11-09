# Janus public read-only API

The routes below take no request body, carry no personal data in or out, and only read precomputed or
released data. The machine-readable description, with examples, is [`openapi-public.json`](openapi-public.json)
(OpenAPI 3.1), generated from the API's own schema by `python -m janus.open.openapi`; CI fails when it drifts.

Base URL: `/api` on a Janus deployment (same origin as the web app). Nothing is deployed before Phase 5; locally,
`uv run uvicorn janus.main:app` serves the same routes without the `/api` prefix.

| Route | What it returns | When it is not available |
|---|---|---|
| `GET /health` | service status | — |
| `GET /privacy/storage` | where donated data would be stored (region) | — |
| `GET /memory/snapshot` | the FAERS counts snapshot: build id, snapshot date, quarters, freshness | 503 `memory_unavailable` |
| `GET /seance/catalogue` | the séance pairs (Canon substance × condition) | 503 `seance_unavailable` |
| `GET /light/overview`, `/light/validation`, `/light/export` | light-face repurposing candidates (researcher-facing; "candidate worth investigating — not a treatment"), validation cases, export | 503 `light_unavailable` |
| `GET /timemachine/catalogue` | remedy and cascade ids, the validation block, sources | 503 `time_machine_not_installed` |
| `GET /timemachine/substance/{id}` | one Canon remedy: molecules, predictions, measured activity, exposure | 404 `unknown_substance`, 422 `invalid_request` |
| `GET /timemachine/cascade/{id}` | one cascade: FAERS time to onset, published timing, populations | 404 `unknown_cascade` |
| `GET /open/outcomes` | the open outcome dataset as JSON ([`open-data.md`](open-data.md)) | 503 `open_data_unavailable` |
| `GET /open/outcomes.csv` | the same cells as CSV | 503 `open_data_unavailable` |
| `GET /open/data-quality` | the weekly data-quality report: findings with class and status against the previous run ([`open-data.md`](open-data.md) §3) | 503 `data_quality_unavailable` |
| `GET /open/data-quality.csv`, `/open/data-quality.md` | the same findings as CSV; the readable summary | 503 `data_quality_unavailable` |
| `GET /open/faers-onset` | the FAERS onset table for the 65 PIPC rows ([`open-data.md`](open-data.md) §4) | 503 `onset_table_unavailable` |
| `GET /open/faers-onset.csv` | the same rows as CSV | 503 `onset_table_unavailable` |
| `GET /open/faers-onset/{position}` | one PIPC row (1-65) with the caveats | 404 `unknown_position`, 422 `invalid_request` |
| `GET /open/cascade-package/pipc` | the 65 PIPC rows (CC BY 4.0) with Janus's class mapping (Apache-2.0), package version and citation; also used by the [MCP server](mcp.md) | 503 `package_unavailable` |
| `GET /cds-services` | the CDS Hooks discovery document ([`cds-hooks.md`](cds-hooks.md)) | — |

## Rules every route follows

- **Errors are codes**: `{"error": "<code>"}` (a 422 also names `fields`, never their values). No route sends a
  user-facing sentence; texts are translated in the web app.
- **Medical routes are `no-store`** and log only an access line (route, status, latency); never ingredients,
  codes or events (`privacy.md`).
- **Counts are reports, never people.** FAERS is spontaneous reporting: not incidence, not deduplicated across
  cases. Donated and outcome counts are released only as described in [`open-data.md`](open-data.md).
- **Onset table** rows are descriptive, not causal and not incidence; a row with too few reports or dominated by
  one identical date pair publishes counts only (`status`).
- **Time machine** answers are in silico and exploratory, "expert review has not yet been done"
  (`meta.review_status`); a concentration or dose in them is never a dose a person could take.

## Examples

```sh
curl -s https://<host>/api/open/outcomes | jq '.version, .snapshot_date, (.cells | length)'
# "open-outcomes-1+…"  "2026-11-09"  0        (no released cells yet)

curl -s -D - https://<host>/api/open/outcomes.csv -o outcomes.csv
# content-type: text/csv; charset=utf-8
# x-janus-dataset-version: open-outcomes-1+…
# dataset_version,snapshot_date,layer,ingredients,event,direction,region,value

curl -s https://<host>/api/timemachine/cascade/amlodipine_oedema_diuretic | jq '.cascade.onset.reports'
# 35
```

The POST routes of the API (resolution, cascade check, notes, donations, outcomes, the CDS Hooks service) are not
public API: they carry a person's medicines or answers. The web app uses them; the [MCP server](mcp.md) uses the
resolution and cascade-check routes; EHR sandboxes use `POST /cds-services/janus-cascade`
([`cds-hooks.md`](cds-hooks.md)).
