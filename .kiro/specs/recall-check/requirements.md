# Requirements: Recall check (US, FDA enforcement reports)

> Owner request 2026-11-10. A new bounded area: `pipelines` job `us_recalls`, `apps/api/janus/recalls/`, and a
> notice in `apps/web` on the confirm screen (the scan result) and on the medicine list. It reads one new source,
> the openFDA drug enforcement reports (CC0 1.0). It changes no cascade, memory or resolution logic.

## Introduction
When a person scans or lists a US medicine, Janus looks the product's NDC up in the FDA enforcement report
records (recalls of drug products; report dates from June 2012 in the current download) and says whether a record names that product code and, when the
box's GS1 code carried a lot, whether the record's lot text lists that lot. Janus quotes the record (recall number,
dates, classification, status, reason) and links to it. It says nothing about the medicine beyond the record, and
it never presents the absence of a record as a statement that the medicine is fine: it says which records were
checked, their date, and that they are US records only.

FDA publishes two limits with this data, and both shape the feature: the enforcement reports are not meant as a way
to issue alerts to the public, and FDA does not update a recall's status after it is classified. The notice is
therefore a record lookup with the record's own words, not an alert, and the status is shown as published.

## Glossary
- **Record:** one row of the openFDA drug enforcement dataset (one recalled product of one recall event), identified
  by its recall number (usually `D-nnnn-yyyy`).
- **Record NDCs:** the NDCs written in the record's own text (`product_description`, `code_info`,
  `more_code_info`): hyphenated package NDCs, hyphenated product NDCs after the word NDC, and 11-digit package NDCs
  after the word NDC. openFDA's added `openfda` block is not used (design DP-R2).
- **Package key / product key:** the canonical 11-digit (5-4-2) and 9-digit (5-4) forms of
  `janus.resolution.ndc`.
- **Lot codes of a record:** the tokens of the record's lot text (`code_info`, `more_code_info`) after
  normalisation, that have at least three characters and a digit.
- **Normalised lot:** the ASCII letters and digits of a lot, upper-cased; every other character is dropped.
- **NDC match:** `package` when the query's package key is a record NDC; `product` when only the product key
  matches (the record names the product code, or another package of the same product).
- **Lot match:** `listed` (the normalised lot is one of the record's lot codes), `not_listed` (a lot was given and
  is not one of them) or `not_given`.
- **Data date:** the export date of the openFDA download the current run was built from.

## Requirements

### Requirement 1: Source and licence
1. THE source SHALL be recorded in `pipelines/sources.toml` as `openfda_enforcement` with licence CC0 1.0, the
   terms address, the FDA credit line, "Not an FDA endorsement", FDA's two published limits (not an alert service;
   status not updated after classification), region US, storage `cache` and a weekly cadence; NOTICE SHALL be
   generated from it and `.kiro/steering/data-sources.md` SHALL list it.
2. THE pipeline SHALL download the dataset from the openFDA bulk download (no API key, no paged API calls), with
   connect and read timeouts, the existing per-host rate limit and retry rule, and SHALL keep no secret.
3. EVERY run SHALL record source addresses, licence, data date, source and content hashes, row counts and
   exclusions with reasons in its manifest, like every other pipeline.

### Requirement 2: Records
1. THE pipeline SHALL write one row per record with: recall number, event id, status and classification as
   published, product description, lot text (`code_info`, `more_code_info`), reason for recall, recalling firm,
   and the initiation, classification, report and termination dates as ISO dates.
2. A record without a recall number (empty, `N/A`, or not a letter followed by 2-19 letters, digits or hyphens),
   or repeating one, SHALL be excluded with a reason and counted; irregular numbers are kept as published.
3. Text fields SHALL be kept as published (only surrounding whitespace removed; an empty text is null).
4. WHEN the number of parsed records differs from the number the download index lists, THE run SHALL fail.
5. A date that is not a valid `YYYYMMDD` date SHALL be stored as null and counted in the run's metrics.

### Requirement 3: Matching (pure)
1. A record SHALL be reported for a query IF AND ONLY IF the query's package key or product key is among the
   record's NDC keys; no record is reported on a name, a firm, or openFDA's added fields.
2. THE NDC match SHALL be `package` when the package key matches and `product` otherwise.
3. THE lot match SHALL be `listed` IF AND ONLY IF a lot was given and its normalised form equals one of the
   record's lot codes; matching SHALL NOT use prefixes, substrings, ranges or similarity.
4. A lot that is not listed SHALL NOT remove the record from the answer: the answer keeps the product-level match
   and says the lot was not found in the record's lot text.
5. A record whose published status is `Terminated` SHALL be returned with `terminated = true`, its termination
   date and its status; a record with another status SHALL have `terminated = false`.
6. THE answer SHALL NOT depend on the order of the records, and SHALL be ordered: lot listed first, then package
   before product, then the newer report date, then the recall number.
7. Matching SHALL be pure functions with no I/O and no clock.

### Requirement 4: API
1. THE API SHALL serve `POST /recalls/check` with a JSON body `{ndc, lot?}`; codes travel in the body only.
2. `ndc` SHALL be a hyphenated package NDC, a hyphenated product NDC or an 11-digit package NDC; ten digits
   without hyphens (three possible layouts) SHALL be refused with 422 `ndc_malformed`.
3. `lot`, when present, SHALL be 1-20 characters of the GS1 character set with at least one letter or digit;
   otherwise 422 `invalid_request` naming the field. A 422 SHALL never echo input.
4. THE answer SHALL give: the source (id, run, data date, licence, record count, count of records with an NDC),
   region `US`, whether a lot was given, the matches (at most 20, with the total and a truncation flag), fixed
   notice codes for the limits, and the standard disclaimer.
5. EACH match SHALL give the recall number, classification and status as published, `terminated`, the four dates,
   the reason, product description and lot text quoted from the record (lot text cut at 2,000 characters with a
   flag), the recalling firm, the NDC match, the lot match, the record's lot codes, and the address of the record
   at openFDA.
6. WHEN no current run is installed or it cannot be read, THE route SHALL answer 503 `recalls_unavailable`.
7. THE route SHALL be a medical route: `no-store`, nothing logged but the access line; the NDC and the lot SHALL
   never be logged or stored.
8. WHEN the data date is more than 14 days old, THE answer SHALL carry the notice `snapshot_outdated`.
9. THE API SHALL read a newly promoted run without a restart.

### Requirement 5: The lot stays on the device
1. THE web app SHALL read AI (10) of a scanned GS1 code, keep it in memory until the medicine is confirmed and
   then with the list item in the browser's storage, and SHALL NOT send it to any server (this narrows experience
   Req 10.2, which dropped the lot; the serial (21) is still dropped).
2. THE web app SHALL ask the API by NDC only and SHALL compare the lot with the record's lot codes on the device,
   with the same normalisation as the API.
3. THE content sent to `POST /resolve/scan` SHALL stay (01), (17), (712) only.

### Requirement 6: Notice in the web app
1. FOR a US product candidate chosen on the confirm screen and for every US product item of the medicine list,
   THE web app SHALL show the recall check: loading, a notice per matching record, the checked-and-nothing-found
   line, or an error with a retry.
2. A notice SHALL say "This product appears in an FDA recall record" (or "This product and lot appear…" when the
   lot is listed), and SHALL show the recall number, the report date, the classification, the status as published
   (with the termination date when terminated), the reason quoted from the record marked as a quotation in
   English, a link to the record and a link to FDA's recall search.
3. WHEN a lot is known and is not listed, THE notice SHALL say that the automated reading did not find the lot in
   the record's lot text, SHALL show that text, and SHALL NOT say that the lot is not concerned.
4. EVERY notice SHALL advise checking with a pharmacist, SHALL NOT recommend stopping, starting or changing a
   medicine, and SHALL NOT state anything about the medicine's safety beyond the record.
5. WHEN no record matches, THE web app SHALL say that the FDA recall records up to the data date were checked,
   that they are US records only, how many of them state no product code, and that finding no record does not
   mean the medicine has no problem; it SHALL NOT use "safe", "no problems" or "all clear" in any language.
6. THE notice SHALL say that the status is as published and that FDA does not update it after classification, and
   that the check is automated; where a review status is shown it SHALL read "Expert review has not yet been
   done".
7. THE check SHALL NOT run for non-US items, for items found by ingredient name, or in demo mode (demo products
   are invented); in demo mode the list SHALL say so once.
8. `--risk` SHALL NOT be used for a recall notice (design.md: red is for emergencies and retracted evidence);
   the notice uses `--warn`, an icon and text.
9. Texts in en, tr, de, fr, es with the same meaning; both themes; 375 px and 1280 px without horizontal scroll;
   WCAG AA; touch targets of 44 px; long record text wraps and is folded.

### Requirement 7: Deployment data path
1. THE run SHALL reach the server by the existing `deploy/sync-data.sh` (it copies every `artifacts/*` run) with
   no change to that script and no database load.
2. THE weekly server job SHALL also run `us_recalls`; a failed recall refresh SHALL keep the previous run and
   SHALL NOT stop the TİTCK reload.

### Requirement 8: Quality
1. Hypothesis properties for Requirement 3 and the text reading (design §8); pipeline tests on synthetic
   openFDA-shaped files with no network; route tests (200, 422, 503, medical route).
2. fast-check properties for the on-device lot rule and the query builder; unit tests of the notice in five
   languages; Playwright with axe for the notice in both themes at 375 px and 1280 px.
3. THE medical-language word lists SHALL hold for every recall text in five languages.
4. Automated read-only passes of the safety-auditor and localization-reviewer agents; findings and fixes recorded
   in this spec. Expert review has not yet been done.
