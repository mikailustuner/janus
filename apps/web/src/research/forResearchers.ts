/**
 * Code and route tables of "Janus for researchers" (spec for-researchers). Code is shown verbatim in
 * every language. ONSET_EXAMPLE is the body of docs/examples/onset_summary.py (a test compares them);
 * API_ROUTES is the route table of docs/for-researchers.md (a test compares them too).
 */
export const SITE = "https://janusmeds.org";
export const REPO = "https://github.com/mikailustuner/janus";

export const API_ROUTES = [
  { key: "cascade", routes: "GET /open/cascade-package/pipc" },
  {
    key: "onset",
    routes: "GET /open/faers-onset, /open/faers-onset.csv",
  },
  { key: "onsetRow", routes: "GET /open/faers-onset/{position}" },
  { key: "quality", routes: "GET /open/data-quality, .csv, .md" },
  { key: "outcomes", routes: "GET /open/outcomes, .csv" },
  { key: "memory", routes: "GET /memory/snapshot" },
  {
    key: "timemachine",
    routes: "GET /timemachine/catalogue, /timemachine/cascade/{id}",
  },
  { key: "compounds", routes: "GET /simulate/compounds" },
  { key: "cds", routes: "GET /cds-services" },
] as const;

export const DATA_PACKAGES = [
  { key: "cascade", path: "data/open/cascade-package" },
  { key: "onset", path: "data/open/faers-onset" },
  { key: "quality", path: "data/open/data-quality" },
] as const;

export const CURL_EXAMPLES = `curl -s ${SITE}/api/open/faers-onset/5 | jq '.row | {status, median_days, reports_with_interval}'
# {"status": "small_sample", "median_days": 29.0, "reports_with_interval": 23}

curl -s ${SITE}/api/open/data-quality | jq '.version, .summary.by_class'
# "data-quality-1+f75ead99e56f"
# {"benign_difference": 106, "confirmed_error": 12, "needs_pharmacist": 102}

curl -s ${SITE}/api/open/cascade-package/pipc | jq '.version, (.rows | length)'
# "1.0.0"
# 65

curl -s ${SITE}/api/simulate/compounds | jq '.version, .server_runs'
# "simulation-allowlist-3"
# true`;

export const ONSET_EXAMPLE = `import json
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
    )`;

export const ONSET_OUTPUT = `faers-onset-pipc-1+b1df201877b1 snapshot 2026-10-28 CC BY 4.0
rows: 65 | rows with a median time to onset: 32
rows with a median under 7 days: 19
by status: {'cluster_dominated': 3, 'count_only': 19, 'described': 21, 'no_candidate_reports': 2, 'no_interval': 9, 'small_sample': 11}
PIPC row 2: Antihypertensive -> Orthostatic hypotension/dizziness: median 2.0 days from 276 reports (described)
PIPC row 15: Anticonvulsant -> Rash: median 13.0 days from 226 reports (described)
PIPC row 9: Hydroxymethylglutaryl-coenzyme A (HMG Co-A) reductase inhibitor (statin) -> Myalgia/myositis: median 35.0 days from 216 reports (described)`;

export const MCP_RUN = `cd apps/mcp
uv sync
JANUS_API_URL=http://127.0.0.1:8000 uv run janus-mcp`;

export const PIPELINE_RUN = `cd pipelines
uv sync
uv run janus-pipelines run pipc
uv run janus-pipelines status
uv run janus-pipelines notice --check`;

export const CITATION = `Janus project (Copyright 2026 Mikail Üstüner). Janus FAERS onset table for the PIPC cascades, version faers-onset-pipc-1+b1df201877b1 (FAERS snapshot 2026-10-28), CC BY 4.0. ${REPO} (accessed YYYY-MM-DD).`;
