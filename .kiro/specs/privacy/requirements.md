# Requirements: Privacy and Consent

> Refined 2026-11-07 for Phase 1; owner decisions of 2026-11-07 applied (adults only, consent
> version stored, 24-month retention, demo donations rejected). See `.kiro/steering/privacy.md`.
> **Phase 1 scope is the server side (`apps/api`):** Requirement 2, Requirement 4, the server
> parts of Requirements 1 and 3, and the API part of Requirement 5.
> Criteria tagged **[Client: experience spec]** stay here as requirements but are implemented in
> the `experience` spec (Phase 3). They are not part of this spec's tasks.
> QR tokens (note id + HMAC + expiry, no personal data) are specified in `doctor-loop` Req 2.
> *(2026-11-08, owner decision in `doctor-loop`.)* The token also carries the note's finding codes (PIPC rows, ingredient keys and ATC codes, Janus event keys, direction, language, region, issue week, expiry, key id, consent version) in a signed payload in the URL fragment; no personal data. The server stores only SHA-256 hashes of used or withdrawn note ids until expiry (`used_note_tokens`) and the outcomes (`outcomes`: report week, region, codes, answers, consent version, deletion hash). `privacy.md` is unchanged.

## Introduction
Health data is the biggest risk in Janus. Privacy is a product feature: on-device processing, stateless APIs, explicit consent, k-anonymity and differential privacy — designed to GDPR (EU), KVKK (Türkiye) and US consumer-health-data expectations at the same time.

## Glossary
- **API:** the FastAPI service in `apps/api`.
- **Client:** the Next.js PWA in `apps/web`, running in the user's browser.
- **Medical endpoint:** any API route that receives or returns medication, product-code,
  ingredient, event, date or note data. Every route is a medical endpoint unless it is on the
  operational allowlist.
- **Operational endpoint:** a route on a fixed allowlist that carries no health data
  (`/health`, `/privacy/storage`, the OpenAPI schema and docs).
- **Donation endpoint:** the medical endpoints that store or delete a donation (Req 3). They are
  the only medical endpoints allowed to write to storage.
- **Donation:** one anonymous record a user chooses to share, made only of the allowed fields.
- **Allowed fields:** 5-year age band, optional sex, region (TR, EU or US), ingredients, event,
  direction (adverse or benefit), report week, consent version.
- **Retention period:** 24 months; a donation is kept at most this long after its report week.
- **Demo mode:** the client's judge/demo mode with synthetic data (`experience` spec).
- **Report week:** the ISO week, in UTC, in which the API received the donation, stored as the
  date of that week's Monday.
- **Deletion token:** a secret returned once to the donor; presenting it deletes that donation.
- **Consent version:** the identifier of the consent text the client showed the user.
- **Route template:** the path pattern a request matched (e.g. `/resolve/{code}`), never the
  concrete path or query string.
- **Request id:** an identifier the API generates for each request.
- **Access log line:** the one log line the API writes per request.
- **Aggregate:** a set of cells, each a count from user data (donations or doctor-confirmed
  outcomes), plus any totals derived from them.
- **Contributor count:** the number of donations (or outcomes) a cell is computed from. Donations
  are anonymous, so the same person donating twice counts twice.
- **Released cell:** a cell whose value is shown; every other cell is suppressed.
- **k:** the suppression threshold, 20.
- **ε (epsilon):** the privacy parameter of the noise; noise scale is 1/ε.
- **Data version:** an identifier that changes whenever the donations behind an aggregate change.
- **EU storage region:** a hosting region located in an EU member state.

## Requirements

### Requirement 1: On-device processing
**User story:** As a user, I want images of my medicine boxes and my medication list to stay on my device, so that nobody else holds them.

#### Acceptance criteria
1. THE client SHALL decode barcodes and run OCR in the browser and SHALL NOT upload images. **[Client: experience spec]**
   - *(Added 2026-11-08, `drug-resolution` DP19 as extended by the owner.)* From a decoded GS1 code THE client SHALL send the API only the Application Identifiers (01) GTIN, (17) expiry and, if the code carries it, (712) national product reimbursement number. THE serial number (21) identifies a single box and SHALL never leave the device; the lot (10) SHALL NOT be sent either. THE API SHALL reject any request that carries AI (21) (HTTP 422, code `gs1_serial_not_accepted`) without looking anything up or echoing it, and SHALL drop a lot value it still receives. **[Client: experience spec]** for the sending side.
2. THE client SHALL keep the medication list in browser storage by default and SHALL work without an account. **[Client: experience spec]**
3. THE client SHALL render the doctor note PDF in the browser. **[Client: experience spec]**
4. *(Added in refinement, server side of 1.1.)* THE API SHALL NOT offer any endpoint that accepts an image or file upload.
   - IF a request to a medical endpoint has a body whose content type is not `application/json` THEN THE API SHALL reject it with HTTP 415 and SHALL NOT read the body into a file.

### Requirement 2: Stateless medical endpoints and logging
**User story:** As a user, I want the server to forget my medicines as soon as it has answered, so that nothing about my health is kept by accident.

#### Acceptance criteria
1. Medical API endpoints SHALL NOT persist request bodies.
   - THE API SHALL treat every route as a medical endpoint unless the route is on the operational allowlist.
   - WHEN a medical endpoint other than a donation endpoint handles a request THE API SHALL NOT write any part of the request or response to the database, files, caches or any other store.
   - WHEN a medical endpoint other than a donation endpoint uses the database THE API SHALL use a read-only transaction.
   - IF a request body to a medical endpoint exceeds 64 KiB THEN THE API SHALL reject it with HTTP 413 without storing it.
   - THE API SHALL send `Cache-Control: no-store` on every medical-endpoint response.
2. Logs SHALL contain only request id, route, status and latency; THE system SHALL NOT log ingredients, product codes, events, dates or note content.
   - WHEN a request finishes, with any status including an unhandled error, THE API SHALL write exactly one access log line containing only: request id, route template, HTTP status code and latency in milliseconds (plus the log line's own timestamp and level).
   - WHEN a request matches no route THE API SHALL log the route as a fixed placeholder, not the requested path.
   - THE API SHALL generate the request id itself for every request, SHALL ignore any request id sent by the caller, and SHALL return it in the `X-Request-ID` response header.
   - THE API SHALL NOT log query strings, request or response bodies, headers, IP addresses or user agents.
   - THE API SHALL pass every log record, from its own code and from libraries (e.g. uvicorn, FastAPI, HTTP clients), through one allowlist; IF a record carries content outside the allowlist THEN THE API SHALL drop that content and keep only the logger name, level and a fixed marker.
   - IF a request raises an unhandled exception THEN THE API SHALL log only the exception's class name with the request id (no message, traceback or variable values) and SHALL return HTTP 500 with the request id and no exception details.
3. *(Added in refinement.)* THE local database configuration SHALL NOT write statement text, parameters or failing row contents to the database server's log.

### Requirement 3: Consent and donation
**User story:** As a user, I want to choose exactly what I share and be able to take it back.

#### Acceptance criteria
1. WHEN a user chooses to donate THE client SHALL show a specific consent screen, in the user's language, listing every field to be shared and the legal basis (explicit consent). **[Client: experience spec]**
   - *(Server side, Phase 1.)* IF a donation request does not confirm explicit consent for a known consent version THEN THE API SHALL reject it with HTTP 422 and store nothing.
   - WHEN a donation is stored THE API SHALL store the consent version the user accepted with it (owner decision: documents consent, GDPR Art. 7(1); not personal data).
2. THE system SHALL store only: 5-year age band, optional sex, region (TR / EU / US), ingredients, event term, direction (adverse/benefit), week.
   - *(Owner decision.)* The consent version is also stored (3.1); `privacy.md` lists it among the allowed fields.
   - THE API SHALL accept a donation only with these fields and SHALL reject, with HTTP 422 and nothing stored, a request that has any other field, a missing required field or a value outside its domain:
     - age band: the lower bound of a 5-year adult band (20, 25, …, 85) or 90 meaning "90 and over"; IF a lower band is sent THEN THE API SHALL reject it (no donations for minors: there is no parental-consent flow);
     - sex: `female` or `male`, or absent;
     - region: `TR`, `EU` or `US` (no country, city or postcode);
     - ingredients: 1 to 20 distinct ingredient keys (Wikidata item ids, e.g. `Q18216`);
     - event: one key from the configured Janus event vocabulary (derived from the PIPC adverse events plus improvement terms for `benefit`, defined in `collective-memory`; a small placeholder vocabulary until then; no MedDRA dependency);
     - direction: `adverse` or `benefit`.
   - THE API SHALL set the report week itself from the time of receipt; the request SHALL NOT contain any date or time.
   - THE donation record SHALL contain no free-text field, no exact timestamp, no name, email, IP address, user agent, location or device identifier.
   - THE donation's record id SHALL be random, so that ids do not reveal the order of donations.
   - THE database schema SHALL enforce the allowed fields and their domains, independently of the API's own validation.
   - IF a donation request carries `"demo": true` THEN THE API SHALL reject it with HTTP 422 and store nothing. (The client never sends donations in demo mode; **[Client: experience spec]**.)
3. THE system SHALL return a deletion token; WHEN it is presented THE system SHALL delete the donation completely and confirm.
   - WHEN a donation is stored THE API SHALL return a deletion token of at least 128 random bits from a cryptographically secure source, exactly once, and SHALL store only a one-way hash of it.
   - THE API SHALL accept a deletion token only in a request body, never in a URL.
   - WHEN a valid deletion token is presented THE API SHALL delete the donation in one transaction and confirm the deletion; after that no query SHALL return the donation, and no aggregate computed afterwards SHALL include it.
   - IF a presented token matches no stored donation (never issued or already used) THEN THE API SHALL respond with HTTP 404 and delete nothing.
   - WHEN a donation is deleted THE API SHALL leave every other donation unchanged.
4. THE system SHALL store donations in an EU hosting region and SHALL state the hosting region on the privacy page.
   - THE API SHALL read the donation storage region from configuration and SHALL enable the donation endpoints only WHEN that region is on an explicit list of EU storage regions, or is `local` for development.
   - IF donations are not enabled THEN the donation endpoints SHALL respond with HTTP 503 and store nothing.
   - THE API SHALL expose the configured donation storage region, and whether it is in the EU, at an operational endpoint for the privacy page.
   - THE privacy page SHALL state the hosting region. **[Client: experience spec]**
5. *(Added in refinement.)* THE database schema for donations SHALL be created by a forward-only, reversible migration: every migration has an upgrade and a downgrade, and applied migrations are never edited.
6. *(Owner decision.)* THE system SHALL keep a donation at most 24 months and then delete it automatically.
   - WHEN the purge runs on a given day THE API SHALL delete every donation whose report week starts on or before the date 24 months earlier, and SHALL leave every newer donation unchanged.
   - THE purge SHALL be a function and a command that can be run repeatedly with the same result; scheduling it daily is done in Phase 5.
   - THE privacy page SHALL state the retention period. **[Client: experience spec]**
7. *(Owner decision, known limit.)* Rate limiting of the donation endpoints is done in Phase 5 at the Caddy reverse proxy, without storing or logging IP addresses. Until then one source can submit many donations (see Req 4.1, contributor count).

### Requirement 4: Aggregate protection
**User story:** As a donor, I want any number shown from donations to hide whether I am in it, so that sharing cannot single me out.

#### Acceptance criteria
1. THE system SHALL suppress any aggregate from user data representing fewer than k = 20 people.
   - THE API SHALL decide suppression on each cell's true contributor count, before any noise: a cell is released only IF its contributor count is at least k.
   - THE API SHALL compute any total or other derived value only from released cells, so that no output depends on a suppressed cell.
   - THE suppression and noise functions SHALL be pure (no I/O; randomness passed in), in one module shared with the `collective-memory` spec.
   - THE configuration SHALL NOT allow k below 20.
2. THE system SHALL add Laplace noise with a configured ε to user-data counts.
   - WHEN a cell is released THE API SHALL add noise from the discrete Laplace distribution with scale 1/ε (sensitivity 1), and SHALL release a non-negative integer.
   - WHEN the same cell is requested again for the same data version THE API SHALL return the same noisy value.
   - THE configuration SHALL accept ε only within a fixed valid range and SHALL refuse to start otherwise.
   - THE API SHALL NOT add noise to FAERS counts, which are public data.

### Requirement 5: Transparency
#### Acceptance criteria
1. THE privacy page SHALL explain, in all supported languages, what stays on the device, what is sent, what is stored, for how long, and how to delete it. **[Client: experience spec]**
2. THE product SHALL NOT claim certifications or audits that have not been performed.
   - *(Server side, Phase 1.)* API responses, including the storage-region endpoint, SHALL NOT contain compliance or certification claims.
   - The README, privacy page, video and Devpost text follow the same rule. **[Client: experience spec; write-ups in Phase 5]**

## Properties to test (PBT candidates)
- For any request to a medical endpoint, the captured log line contains none of the request's medical values. (Req 2.2)
- For any stored donation, the stored record contains only allowed fields. (Req 3.2)
- After deletion with a valid token, no query returns the donation. (Req 3.3)
- Suppression: for any dataset, no output cell is derived from fewer than 20 contributors. (Req 4.1)
- Added in refinement:
  - For any log record from any logger, the formatted line has only allowlisted keys and none of the record's other content. (Req 2.2)
  - For any request, there is exactly one access log line; its route is the route template, never the concrete path or query, and its request id equals the `X-Request-ID` header. (Req 2.2)
  - For any request to a non-donation medical endpoint, the database and the file system are unchanged afterwards, and the response carries `Cache-Control: no-store`. (Req 2.1)
  - For any non-JSON or oversized body to a medical endpoint, the request is rejected and nothing is stored. (Req 1.4, 2.1)
  - For any payload with an extra field, a missing field, a value outside its domain (including an age band under 20), no explicit consent or `"demo": true`, the donation is rejected and nothing is stored. (Req 3.1, 3.2)
  - For any set of donations and any purge day, the purge deletes exactly the donations with a report week on or before the 24-month cutoff, and running it again changes nothing. (Req 3.6)
  - For any receipt time, the report week is the Monday of that UTC ISO week, and no client input changes it. (Req 3.2)
  - The deletion token is not recoverable from the database; any other token deletes nothing; a token works only once; other donations are unchanged. (Req 3.3)
  - For any region value, donations are enabled exactly when the region is on the EU list or is `local`. (Req 3.4)
  - No output of an aggregate changes when suppressed cells change (while they stay below k). (Req 4.1)
  - Noised counts are never negative and never non-integer. (Req 4.2)
  - The same cell and data version always give the same noisy value. (Req 4.2)
  - Configuration never accepts k below 20 or ε outside the valid range. (Req 4.1, 4.2)
