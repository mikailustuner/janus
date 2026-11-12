# API metrics (private)

The api container serves Prometheus text format on its own port, `JANUS_METRICS_PORT` (9464 in
`deploy/compose.yml`). It is unset (no listener) by default, so development and tests open no port. The
port is not part of the public API: it is absent from `docs/openapi-public.json`, there is no `/metrics`
route in the app, and `deploy/README.md` ("Metrics") describes how it is scraped and why the public site
cannot reach it.

## Privacy and cardinality

Label values come from fixed sets only: a route template of the app (or `<unmatched>`), an HTTP method
from a fixed list (or `OTHER`), a status class, a job state, a dataset name from a fixed list, a
quantile. A request's path values, query string, headers, address and body are never read into a label.
Largest label sets: `route` (about 60 templates) x 8 methods x 5 status classes, only for combinations
that occurred; 31 datasets; 4 job states. Total well under 5,000 series.

## Series

| Metric | Labels | Meaning |
| --- | --- | --- |
| `janus_http_requests_total` | `route`, `method`, `status_class` | Finished HTTP requests. `status_class` is `1xx` to `5xx`; an unhandled error counts as `5xx`. |
| `janus_http_request_duration_seconds` (histogram: `_bucket`, `_sum`, `_count`) | `route`, `method`, `status_class` | Latency from request start to the end of the response. Buckets 5 ms to 30 s. |
| `janus_http_requests_in_flight` | none | Requests being handled now. |
| `janus_simulation_queue_readable` | none | 1 when the queue table could be read at the last refresh, 0 when the database did not answer (the other queue series are then absent). |
| `janus_simulation_jobs` | `state` = `queued`, `running`, `done`, `failed` | Jobs in `simulation_jobs` now. Rows leave the table when they expire (results 24 h, failures 1 h), so these are gauges, not counters. |
| `janus_simulation_oldest_queued_age_seconds` | none | Age of the oldest queued job; 0 when none is queued. Rising values mean the simulator is stuck or slower than the load. |
| `janus_simulation_recent_jobs_done` | none | Jobs that finished successfully in the last hour. |
| `janus_simulation_recent_job_duration_seconds` | `quantile` = `0.5`, `0.95` | Run time (start to finish) of the jobs counted by `recent_jobs_done`. Absent when there were none. Computed from the table, because the simulator is a separate container. |
| `janus_dataset_present` | `dataset` | 1 when the dataset has a current run, 0 when it has none (some datasets are optional). |
| `janus_dataset_loaded_timestamp_seconds` | `dataset` | Modification time (Unix seconds) of the dataset's current run. Absent when not present. |
| `janus_dataset_age_seconds` | `dataset` | Seconds since that time. Absent when not present. |
| `janus_dataset_snapshot_age_seconds` | `dataset` | Seconds since the `snapshot_date` of the current run's manifest (source data age). Absent when there is no manifest or date. |
| `janus_db_pool_max`, `janus_db_pool_size`, `janus_db_pool_in_use`, `janus_db_pool_waiting` | none | Database pool: configured maximum, open connections, connections handed out, requests waiting for one. |
| `process_*`, `python_*` | as `prometheus_client` defines them | Standard process (CPU, memory, file descriptors, start time), garbage-collector and interpreter series. |

`dataset` is one of the pipeline jobs (`ca_dpd`, `canon`, `canon_gold`, `eu_es_cima`, `eu_fr_bdpm`,
`eu_it_aifa`, `faers`, `faers_onset`, `modelkit_*`, `onsides`, `openfda_label`, `pipc`, `retractions`,
`titck`, `tm_*`, `us_*`, `wikidata_ingredients`: runs under `<data dir>/artifacts/<name>/current`) or one of
`faers_counts`, `light`, `data_quality`, `onset_table` (their own `current` links). The list is
`ARTIFACT_DATASETS` and `BUILT_DATASETS` in `apps/api/janus/observability/metrics.py`; a test keeps it equal
to the pipeline jobs.

The queue, dataset and pool series are read when a scrape arrives and cached for 15 seconds; one scrape
costs three small queries on `simulation_jobs` (statement timeout 2 s) and a few `stat` calls.
