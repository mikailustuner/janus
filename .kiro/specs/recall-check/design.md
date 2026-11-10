# Design: Recall check (US, FDA enforcement reports)

> Scope: `pipelines/janus_pipelines/jobs/us_recalls.py`; `apps/api/janus/recalls/` (`codes.py` pure text reading,
> `match.py` pure matching, `store.py` the current run in memory, `router.py` the route); `apps/web/src/recall/`
> (`lot.ts`, `query.ts`, `model.ts`, `client.ts`, `useRecall.ts`), `apps/web/src/components/recall/RecallCheck.tsx`,
> the lot path in `scan/gs1.ts`, `flow/pending.ts`, `store/list.ts`; one step in `deploy/titck-refresh.sh`.
> Decisions DP-R1-DP-R10, properties P1-P9 (API) and W1-W7 (web). Automated review passes:
> `review-safety-auditor.md`, `review-localization.md`. Expert review has not yet been done.

## 1. Overview
```mermaid
flowchart LR
  FDA[openFDA download index<br/>drug/enforcement zip] --> J[us_recalls job<br/>one row per record, text as published, ISO dates]
  J --> A[artifacts/us_recalls/runs/&lt;run&gt;<br/>rows.parquet + manifest]
  A -->|sync-data.sh / weekly job| S[server data dir]
  A --> H[RecallsHolder<br/>index by product key]
  H --> R[POST /recalls/check {ndc}]
  BOX[GS1 code on the box] -->|01, 17| RES[POST /resolve/scan]
  BOX -->|10 lot, stays in the browser| L[list item .lot]
  RES --> Q[recallQuery: package or product NDC]
  Q --> R --> V[RecallCheck notice]
  L --> V
```

## 2. Source and licence (Req 1)
- openFDA drug enforcement reports, from the FDA Recall Enterprise System. Terms (https://open.fda.gov/terms/,
  read 2026-11-10): "Unless otherwise noted, the content, data, documentation, code, and related materials on
  openFDA is public domain and made available with a Creative Commons CC0 1.0 Universal dedication." Credit is
  asked, not required: "Data provided by the U.S. Food and Drug Administration (https://open.fda.gov)". The
  enforcement dataset carries no third-party-rights warning.
- FDA's limits (https://open.fda.gov/apis/drug/enforcement/): "This data should not be used as a method to collect
  data to issue alerts to the public, nor should it be used to track the lifecycle of a recall"; "FDA does not
  update the status of a recall after the recall has been classified"; "Do not rely on openFDA to make decisions
  regarding medical care." These are responsible-use statements, not licence terms. They are recorded in
  `sources.toml` (and so in NOTICE) and shape the wording (DP-R8).
- Download: `https://api.fda.gov/download.json` → `results.drug.enforcement.partitions[]` (one zip, 3.8 MB,
  18,076 records on 2026-11-10, export date 2026-11-03). Two requests per run; no API key; `core/http.py` gives the
  timeouts (10 s connect, 60 s read, 300 s bulk), the 4 req/s limit for the FDA hosts and the GET-only retry rule.

## 3. Pipeline `us_recalls` (Req 2)
Schema `us_recalls-1`, source `openfda_enforcement`, storage `cache`, cadence 7 days. Reuses `us_ndc`'s
`iter_results`, `partition_text` and `parse_index` (now with a dataset name).

| Column | From | Rule |
|---|---|---|
| `recall_number` | `recall_number` | as published; a letter then 2-19 letters, digits, hyphens; else excluded `invalid_recall_number`; a repeat excluded `duplicate_recall_number` |
| `event_id`, `status`, `classification`, `product_description`, `code_info`, `more_code_info`, `reason_for_recall`, `recalling_firm` | same names | stripped; empty → null |
| `recall_initiation_date`, `center_classification_date`, `report_date`, `termination_date` | same names | `YYYYMMDD` → ISO; anything else null and counted (`invalid_dates`) |

Not carried: the firm's address, distribution pattern, quantity, and the whole `openfda` block (DP-R2). Metrics:
records, counts by status and classification, first and last report date. The run fails when the parsed count
differs from the index. First run: 18,074 rows, 2 excluded (one empty number, one `N/A`), 0 invalid dates, report
dates 2012-06-20 to 2026-10-28; Terminated 14,814, Ongoing 2,822, Completed 438; Class I 1,753, II 14,601,
III 1,720. `rows.parquet` 1.9 MB.

## 4. Reading the record text (`codes.py`, pure)
- **NDC keys** from `product_description`, `code_info`, `more_code_info`: a hyphenated package NDC anywhere
  (`dddd[d]-ddd[d]-d[d]`, not next to another digit or hyphen, and only in a published layout 4-4-2, 5-3-2, 5-4-1
  or 5-4-2) → 11-digit key; after the word NDC a hyphenated product NDC → 9-digit key, or 11 plain digits → package
  key. Ten plain digits are not read (three layouts). Every package key also gives its product key.
- **Lot codes** from `code_info` and `more_code_info`: split at whitespace and `, ; : ( ) [ ] # &`; drop a token
  written as a date (`8/2025`, `02/28/2026`, `12-13-16`); normalise (ASCII letters and digits, upper case); keep
  3-20 characters with at least one digit. A hyphen, a slash or an `@` stays inside one code (`37-883948`,
  `CC/004/24-25`, `07282026@2`).
- On the first run 9,878 of 18,074 records (55 %) give at least one NDC key (8,445 distinct product keys; at most 26
  records for one product), and 9,289 of those give a lot code. 3,441 records say "all lots" in some form.

## 5. Matching (`match.py`, pure; Req 3)
`Query(product, package?, lot?)` from `query_from_input`: `parse_ndc_input` of drug resolution must give exactly
one key (so ten plain digits are refused); a package key also sets its product part; the lot is normalised.
`Index.by_product` maps a product key to its records. `find` returns one `Match(recall, ndc_match, lot_match)` per
record under the query's product key: `package` iff the query's package key is one of the record's package keys,
else `product`; `listed` iff the normalised lot is one of the record's lot codes, `not_listed` when a lot was given,
else `not_given`. Order: lot listed, package, newer report date, recall number. The lot never filters.

## 6. Store (`store.py`; Req 4.6, 4.9, 7.1)
`RecallsHolder(data_dir)` reads `artifacts/us_recalls/current` (manifest: succeeded, or needs_review with a
promotion; source and schema as expected; rows by DuckDB `read_parquet`) into an `Index`, under a lock, on first use
and whenever `current` resolves to another run directory. 1.3 s for the real run; about 15 MB in memory. No
database table, no migration, no loader: the records are public reference data, and `deploy/sync-data.sh` already
copies every `artifacts/*` run and switches `current` atomically. The integrity loader records the run's source,
licence and data date in the evidence tables like any other artifact.

## 7. API contract **[Client: experience, MCP]**
`POST /recalls/check`, medical route (no-store, access line only). Body `{"ndc": str(1-32), "lot"?: GS1 set, 1-20}`.
- 422 `{"error": "invalid_request", "fields": [...]}` (bad body, unknown field, bad lot); 422 `ndc_malformed`;
  503 `recalls_unavailable`. No answer echoes input.
- 200 `RecallCheckOut`: `region` ("US"), `source` {`source_id`, `run_id`, `snapshot_date`, `license`, `url`,
  `terms_url`, `search_url`, `records`, `records_with_ndc`}, `ndc_level`, `lot_given`, `matches[]` (≤ 20),
  `total_matches`, `truncated`, `notices[]`, `disclaimer`.
- `RecallMatchOut`: `recall_number`, `event_id`, `classification`, `status`, `terminated`,
  `recall_initiation_date`, `center_classification_date`, `report_date`, `termination_date`, `reason_for_recall`,
  `product_description`, `code_info` (lot text, both fields, ≤ 2,000 characters), `code_info_truncated`,
  `recalling_firm`, `ndc_match`, `lot_match`, `lot_codes[]` (all of them, normalised), `record_url`.
- Notices (fixed codes): `us_records_only`, `absence_is_not_clearance`, `status_as_published`,
  `records_without_ndc_not_searched`, `lot_text_read_automatically`, `not_an_alert_service`, and
  `snapshot_outdated` when the data date is older than twice the cadence (the evidence-integrity freshness rule).
- `record_url`: `https://api.fda.gov/drug/enforcement.json?search=recall_number.exact:"<number>"&limit=1`, checked
  to return the one record. `search_url`: FDA's recall search (DP-R9).
- `apps/web/src/recall/fixtures/check.json` is this API's answer for three invented records; an API test fails
  when it differs, and the web decoder and renderer are tested on it.

## 8. Properties
| # | Property | Req | Test |
|---|---|---|---|
| P1 | a record is reported iff it names the query's product or package key; each once | 3.1 | Hypothesis, brute-force oracle |
| P2 | `package` only when the package key is in the record | 3.2 | Hypothesis |
| P3 | `listed` iff the normalised lot is one of the record's lot codes | 3.3 | Hypothesis |
| P4 | the lot never adds or removes a record | 3.4 | Hypothesis |
| P5 | terminated iff the published status says so; status and date carried; never dropped | 3.5 | Hypothesis |
| P6 | same answer for any record order; the documented order | 3.6 | Hypothesis, shuffled |
| P7 | a written package NDC is read with its product; no digits, no key; every key stands in the text; the `openfda` block is never read | 3.1, DP-R2 | Hypothesis + examples |
| P8 | lot normalisation is ASCII upper alphanumeric and idempotent; case and separators do not matter; a lot is listed iff it is a whole token; a longer or shorter code is another lot; dates are not lots | 3.3 | Hypothesis + shared examples |
| P9 | ≤ 20 matches with total and flag; lot text cut and flagged while the lot still matches; `snapshot_outdated` after 14 days; only unambiguous NDCs accepted | 4.2-4.8 | Hypothesis |
| W1 | the device's lot rule equals the API's (shared example table, same properties) | 5.2 | fast-check |
| W2 | the lot is beside the scan content, never in it; stored only when well-formed; the request body is `{ndc}` | 5.1-5.3 | fast-check + unit |
| W3 | the query is the named package or the single product code; none for other regions, ingredients, mixed products; always an NDC the API accepts | 6.1, 6.7 | fast-check |
| W4 | the decoder accepts the API's answer and refuses changed ones; errors map to catalogue keys | 4 | unit |
| W5 | every Recall text in five languages: same keys and parameters, no forbidden, reassurance or "AI" word, also when rendered | 6.4, 6.6, 8.3 | fast-check |
| W6 | nothing found: data date, US only, not a clearance, no lot echoed | 6.5 | render, 5 languages |
| W7 | a notice: record number, quoted reason, status (terminated with date), lot line by case, advice, both links, English marked, no `--risk` | 6.2-6.4, 6.8 | render, 5 languages |
Plus: pipeline tests (as published, exclusions, count mismatch, schema, dates), route tests (medical POST, 200,
422 without echo, 503, reload without restart, the real run when present), Playwright (`e2e/recall.spec.ts`: five
languages × two themes × 375 px and 1280 px, axe, touch targets, no horizontal scroll, the lot in no request,
nothing found, error and retry, the scan flow, demo mode).

## 9. Web (Req 5, 6)
- `scan/gs1.ts`: `outbound()` still builds `(01)…(17)…(712)…`; it now also returns `lot` (AI (10) when well-formed).
  `ScanPage` puts it in `Pending.lot` (memory), `ConfirmPage` in `Item.lot` (browser storage, optional field of
  `janus.v1.list`; older lists stay valid). `Reconfirm` keeps it.
- `recall/query.ts`: only `kind = product`, `region = US`, with packages. The package the person holds is the
  candidate package whose key is one of the layouts of the scanned NDC GTIN or equals the typed NDC; then the
  11-digit key is asked. Otherwise the hyphenated 9-digit product code, when all packages share one.
- `recall/useRecall.ts`: one request per NDC, kept in memory for the session; retry on error.
- `RecallCheck`: loading line (`role=status`), error with retry (`role=alert`), the nothing-found line with the
  share of records that cannot be compared (method and status note folded under "About this check"), or one
  notice per record with the method line (data date, United States only, not an alert service, review status)
  and the status note visible under the list. A notice: title, recall number, report date,
  classification and status as published, the reason as an English quotation, the NDC line, the lot line, the
  pharmacist sentence, folded lot text and product description, the two links. `--warn` border and icon.
- Shown on the confirm screen once a candidate is chosen (the scan result) and in each US row of the medicine list.
  Not in demo mode: one line says the demo products are invented.

## 10. Decisions
| # | Decision | Alternatives | Why |
|---|---|---|---|
| DP-R1 | Bulk download of the whole dataset, weekly | Paged API queries per product at request time | No key, two requests, no rate-limit exposure, no user's NDC sent to FDA, works offline of FDA; 3.8 MB |
| DP-R2 | NDCs from the record's own text only | openFDA's `openfda.product_ndc` / `package_ndc` | The added block lists every product of the same label (up to 22 product codes for one record), so it would report records that do not name the product. Cost: 45 % of records state no NDC and cannot be found |
| DP-R3 | Text reading in the API next to the NDC rules; the pipeline keeps text as published | Extract in the pipeline | One definition of an NDC key (`janus.resolution.ndc`); same convention as `us_ndc`; a rule change needs no re-run |
| DP-R4 | In-memory index from the artifact, reloaded when `current` moves | PostgreSQL table with a loader and a migration | Public reference data of 18 k rows; no migration, no change to `sync-data.sh` or `load-data.sh`; a refresh needs no restart |
| DP-R5 | The lot stays in the browser; the web asks by NDC and compares on the device; the API still accepts an optional lot for other clients | Send the lot | experience Req 10.2 and the GS1 rule of drug resolution keep everything but (01), (17), (712) on the device. Keeping the lot in the browser's list narrows that rule (it was dropped before); it is never sent |
| DP-R6 | Lot match by equality of normalised whole tokens | Substring, prefix, fuzzy, range expansion | A false "your lot is listed" is the worse error; "not found" keeps the notice and shows the text |
| DP-R7 | A lot that is not listed keeps the product-level notice | Hide the record | Lot texts say "all lots", ranges, dates; Janus cannot conclude the box is outside the recall |
| DP-R8 | A record lookup with the record's words, FDA's limits and a pharmacist sentence; terminated recalls shown and labelled; `--warn`, not `--risk` | An alert; hiding terminated recalls | FDA's responsible-use statement; medical-safety rules 1 and 3; design.md keeps red for emergencies and retractions |
| DP-R9 | Link to the record at openFDA (exact recall number) and to FDA's recall search | A deep link into FDA's search application | The openFDA address is verified to return the record; a per-record address of the search application could not be verified |
| DP-R10 | No check in demo mode | A recorded or invented answer | Demo products are invented; an invented FDA record must not be shown as real |

## 11. Limits and open items
- 45 % of the records state no NDC in their text (older records, compounded products, "all NDCs"); they are never
  found. The nothing-found line says how many.
- A `product` match can be about another package size of the same product code.
- Lot codes: a lot written with spaces inside, a range ("lots 100 to 120"), a slash-separated list, or a lot shaped
  like a date is not read; "all lots" is not interpreted. The notice then says the lot was not found and shows the
  text. A date written without separators can be read as a lot code.
- NDC shapes not read: ten plain digits, NDCs with spaces, `5-5` product forms.
- Status is as published and may be stale (FDA). Recalls before June 2012 and recalls not yet classified are not
  in the data. Only US records: no TİTCK, EMA or national EU recall source is checked.
- The record link opens openFDA's data format (JSON), not a readable page.
- Items found by ingredient name, pharmacy vials without an NDC, and non-US products are not checked.
- The weekly server step is untested on the server (nothing was deployed in this work); it needs outbound access
  to `api.fda.gov` and `download.open.fda.gov` from the jobs network.
- MCP tool for the route; the product NDC of FDA's own recall press releases; expert review of the wording.
