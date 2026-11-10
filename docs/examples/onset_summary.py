"""Summarise the Janus FAERS onset table for the 65 PIPC cascades (standard library only).

    python3 onset_summary.py                         # public site, one request
    JANUS_API_URL=http://127.0.0.1:8000 python3 onset_summary.py   # a local API

Counts are reports, never people. Descriptive only: not causal, not incidence.
"""

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
