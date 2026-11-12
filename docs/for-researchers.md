# Janus for researchers

Janus is an open-source research prototype, not a medical device. It provides information, not medical advice. Nothing
on this page is guidance for a person, and every number is a count of reports, never of people. **Expert review has
not yet been done.** This page is also available in the app at `/research/for-researchers` (en, tr, de, fr, es, pt).

Public site: <https://janusmeds.org> (API under `/api`). Source: <https://github.com/mikailustuner/janus>. Status of
this page: 2026-11-10; dataset versions below change with each release.

## Start in ten minutes

1. Pick a source below (the FAERS onset table is a good first one).
2. Run one request with `curl` (section 2).
3. Run the worked example (section 3): one file, standard library only.
4. Read the limits (section 9) before you use a number.

## 1. Open data

Files are under `data/open/` in the repository (Frictionless `datapackage.json` with a SHA-256 hash and row count per
file) and are served by the API. Details: [open-data.md](open-data.md).

| Package | Files | Licence | Version (2026-11-10) |
|---|---|---|---|
| `data/open/cascade-package/` | `pipc.csv` (65 PIPC rows), `pipc_rules.csv`, `cascade_classes.csv`, `atc_code_exclusions.csv`, `ingredient_synonyms.csv`, `anion_acid_forms.csv`, `dose_form_groups.csv` | `pipc.csv` CC BY 4.0 (Rochon et al. 2025); the Janus mappings Apache-2.0 | 1.0.0, created 2026-11-09 |
| `data/open/faers-onset/` | `faers_onset_pipc.csv`, `faers_onset_pipc.json` | CC BY 4.0 (FAERS-derived counts, CC0 source; MedDRA notice included) | `faers-onset-pipc-1+b1df201877b1`, FAERS snapshot 2026-10-28 |
| `data/open/data-quality/` | `report.json`, `findings.csv`, `summary.md` | CC BY 4.0 | `data-quality-1+f75ead99e56f` |
| Open outcome dataset (API only) | `GET /open/outcomes`, `.csv` | CC BY 4.0 | `open-outcomes-1+...`; no released cells yet (valid empty file) |

Cite a dataset by its version string and snapshot date (section 10).

## 2. Public read-only API

Base URL `https://janusmeds.org/api`. Locally, `uv run uvicorn janus.main:app` in `apps/api` serves the same routes
without the `/api` prefix. Machine-readable description: [openapi-public.json](openapi-public.json); route table and
rules: [open-api.md](open-api.md). Errors are `{"error": "<code>"}`.

| Route | Returns |
|---|---|
| `GET /open/cascade-package/pipc` | the 65 PIPC rows with Janus's class mapping, version, citation |
| `GET /open/faers-onset`, `/open/faers-onset.csv` | FAERS time-to-onset table for the 65 PIPC rows |
| `GET /open/faers-onset/{position}` | one row (1-65) with the caveats |
| `GET /open/data-quality`, `.csv`, `.md` | weekly ingredient data-quality findings |
| `GET /open/outcomes`, `.csv` | open outcome dataset (released cells only) |
| `GET /memory/snapshot` | FAERS counts snapshot: build id, date, quarters, freshness |
| `GET /timemachine/catalogue`, `/timemachine/cascade/{id}` | in silico time machine data (exploratory) |
| `GET /simulate/compounds` | the allow-list of the exploratory simulations |
| `GET /cds-services` | CDS Hooks discovery document |

One request each (outputs from 2026-11-10; they change with each release):

```sh
curl -s https://janusmeds.org/api/open/faers-onset/5 | jq '.row | {status, median_days, reports_with_interval}'
# {"status": "small_sample", "median_days": 29.0, "reports_with_interval": 23}

curl -s https://janusmeds.org/api/open/data-quality | jq '.version, .summary.by_class'
# "data-quality-1+f75ead99e56f"
# {"benign_difference": 106, "confirmed_error": 12, "needs_pharmacist": 102}

curl -s https://janusmeds.org/api/open/cascade-package/pipc | jq '.version, (.rows | length)'
# "1.0.0"
# 65

curl -s https://janusmeds.org/api/simulate/compounds | jq '.version, .server_runs'
# "simulation-allowlist-3"
# true
```

**Rate limits.** The repository states limits only for the queued simulations (`POST /simulate`, `GET
/simulate/jobs/{id}`): 3 submissions per 30 seconds and 5 per 10 minutes per client, 120 submissions per 10 minutes
in total, 120 polls per minute per client; the answer is HTTP 429 `rate_limited` or `queue_full` with `Retry-After`.
The read-only routes state no limit: be gentle, and for bulk use download the files in `data/open/` instead of
paging the API. The public site refuses the default Python `User-Agent` (HTTP 403): send your own.

The POST routes (resolution, cascade check, notes, donations, outcomes) carry a person's medicines and are not
public API.

## 3. Worked example: the FAERS onset table in 20 lines

[`docs/examples/onset_summary.py`](examples/onset_summary.py), standard library only, one request:

```python
import json
import os
import urllib.request

base = os.environ.get("JANUS_API_URL", "https://janusmeds.org/api").rstrip("/")
# The public site refuses the default Python user agent; send your own.
request = urllib.request.Request(
    f"{base}/open/faers-onset", headers={"User-Agent": "janus-onset-example/1.0"}
)
with urllib.request.urlopen(request, timeout=30) as response:
    table = json.load(response)

rows = table["rows"]
with_median = [r for r in rows if r["median_days"] is not None]
print(table["version"], "snapshot", table["faers_snapshot_date"], table["license"])
print("rows:", len(rows), "| rows with a median time to onset:", len(with_median))
print("rows with a median under 7 days:", sum(r["median_days"] < 7 for r in with_median))
print("by status:", table["summary"]["by_status"])
for r in sorted(with_median, key=lambda r: -r["reports_with_interval"])[:3]:
    print(
        f"PIPC row {r['pipc_position']}: {r['pipc_drug_a']} -> {r['pipc_adverse_event']}: "
        f"median {r['median_days']} days from {r['reports_with_interval']} reports ({r['status']})"
    )
```

Output on 2026-11-10 (run against the public site; the file in the repository has a docstring and the same code):

```
faers-onset-pipc-1+b1df201877b1 snapshot 2026-10-28 CC BY 4.0
rows: 65 | rows with a median time to onset: 32
rows with a median under 7 days: 19
by status: {'cluster_dominated': 3, 'count_only': 19, 'described': 21, 'no_candidate_reports': 2, 'no_interval': 9, 'small_sample': 11}
PIPC row 2: Antihypertensive -> Orthostatic hypotension/dizziness: median 2.0 days from 276 reports (described)
PIPC row 15: Anticonvulsant -> Rash: median 13.0 days from 226 reports (described)
PIPC row 9: Hydroxymethylglutaryl-coenzyme A (HMG Co-A) reductase inhibitor (statin) -> Myalgia/myositis: median 35.0 days from 216 reports (described)
```

Read it as description only: a median is published only for rows with enough reports, with a complete start and event
date; zero-day and day-01 dates are heaped; the numbers are neither causal nor incidence.

## 4. MCP server

`apps/mcp` is a thin read-through client of the API for MCP clients (Claude, Kiro, others): seven tools,
`janus_resolve_code`, `janus_resolve_ndc`, `janus_search_medicines`, `janus_check_cascades`,
`janus_cascade_package_rows`, `janus_time_machine_catalogue`, `janus_time_machine_cascade`. Every result is
`{"janus_safety": {...}, "result": <the API's JSON>}`. Nothing is logged or kept between calls. Full guide:
[mcp.md](mcp.md).

```sh
cd apps/mcp
uv sync
JANUS_API_URL=http://127.0.0.1:8000 uv run janus-mcp      # stdio
```

Kiro (`.kiro/settings/mcp.json`, shipped in the repository):

```json
{
  "mcpServers": {
    "janus": {
      "command": "uv",
      "args": ["run", "--directory", "apps/mcp", "janus-mcp"],
      "env": { "JANUS_API_URL": "http://127.0.0.1:8000" },
      "disabled": false,
      "autoApprove": ["janus_cascade_package_rows", "janus_time_machine_catalogue", "janus_time_machine_cascade"]
    }
  }
}
```

## 5. CDS Hooks service

HL7 CDS Hooks 2.0 service `janus-cascade` for the hooks `order-select` and `order-sign`. Discovery:
`GET https://janusmeds.org/api/cds-services`; service: `POST /api/cds-services/janus-cascade`. **Sandbox only, not for
clinical use**: try it in the public CDS Hooks sandbox with synthetic patients, never connect it to a live EHR. There
is **no client authentication (no signed JWT) yet.** Start dates are not read (a finding is a pattern in the PIPC
list; "no card" does not mean the medicines are free of problems). Details and a sandbox walk-through:
[cds-hooks.md](cds-hooks.md).

## 6. Reproducible pipelines

One job per source in `pipelines/` (a separate uv project). The source registry is `pipelines/sources.toml`; the
`NOTICE` file is generated from it.

```sh
cd pipelines
uv sync
uv run janus-pipelines run pipc            # Europe PMC -> data/pipc.csv
uv run janus-pipelines status              # current artifact per pipeline
uv run janus-pipelines notice --check      # NOTICE still matches sources.toml
```

Exit codes: 0 succeeded, 1 failed, 3 needs review (not promoted), 4 refused. Artifacts go to `JANUS_DATA_DIR`
(default `.data`, git-ignored). Some sources are large (FAERS about 250 MB, openFDA labels 1.8 GB). Lists with unclear
redistribution terms are fetched at runtime and never committed. See [pipelines/README.md](../pipelines/README.md)
and [NOTICE](../NOTICE).

## 7. Research notes

Draft notes, not peer reviewed. **Expert review has not yet been done.**

- [Do HTTK-Pop age-group simulations predict how drug exposure changes in older adults?](research/httk-pop-older-adult-exposure.md)
- [Negative and null results](research/negative-results.md): seven pre-registered hypotheses, most not supported.

## 8. Other reading

[open-data.md](open-data.md), [open-api.md](open-api.md), [mcp.md](mcp.md), [cds-hooks.md](cds-hooks.md),
[contributing-corrections.md](contributing-corrections.md).

## 8a. Drug model starter kit (experimental)

A few drugs with parameter sets whose every value links to a source quote, tested against held-out studies:
[/en/research/model-kit](https://janusmeds.org/en/research/model-kit) in the web app, routes under `/modelkit` in
[open-api.md](open-api.md). Each drug page also quotes what US labels state about the exposure of older adults and of people
with kidney or liver impairment (two automated readers agree on each statement; no extrapolation, no dose advice), and the
export holds the Janus engine file, an R/mrgsolve model and a PK-Sim compound (a compound building block only: the inputs PK-Sim
needs and the evidence lacks are marked missing, never invented). **Experimental.** Research use only. Not for clinical
decisions. It is not a dose calculator. **Expert review has not yet been done.**

## 9. Limitations and how to report errors

- Counts are **reports, not people**. FAERS is spontaneous reporting: not incidence, not deduplicated across cases.
- The onset table is descriptive, not causal. The time machine is in silico and exploratory; a concentration or dose
  in it is never a dose a person could take.
- Mappings and classifications are produced by automated rules and tests. **Expert review has not yet been done.**
- The CDS Hooks service has no client authentication yet and is for sandboxes only.
- Found a mistake in a file, a number or this page? Open an issue:
  <https://github.com/mikailustuner/janus/issues>. For an error in a source database (ATC codes and similar), see
  [contributing-corrections.md](contributing-corrections.md); report upstream only after a pharmacist has checked it.
  Do not put personal or patient data in an issue.

## 10. How to cite

There is no `CITATION.cff` yet. Until the owner publishes citation metadata, cite what you used, with its version:

> Janus project (Copyright 2026 Mikail Üstüner). Janus FAERS onset table for the PIPC cascades, version
> `faers-onset-pipc-1+b1df201877b1` (FAERS snapshot 2026-10-28), CC BY 4.0. https://github.com/mikailustuner/janus
> (accessed YYYY-MM-DD).

The PIPC list itself: Rochon PA et al. Potentially inappropriate prescribing cascades (PIPC) list. Eur Geriatr Med
2025;16(5):1573-1584. doi:10.1007/s41999-025-01215-x. Code: Apache-2.0 ([LICENSE](../LICENSE)).
