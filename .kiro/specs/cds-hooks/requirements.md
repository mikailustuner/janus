# Requirements: CDS Hooks service

## Introduction
Owner goal 2026-11-09: clinicians should be able to see Janus's prescribing-cascade check where they prescribe. This
feature adds an **HL7 CDS Hooks 2.0 service** to the API: a discovery endpoint and one service, `janus-cascade`, for
the `order-select` and `order-sign` hooks. An electronic health record (EHR, the CDS client) sends the draft
medication orders and the patient's active medications as FHIR R4 resources; Janus maps their codes to its
ingredient keys with the existing resolution layer, runs the existing cascade engine and answers with CDS Hooks
cards.

Janus is a research prototype, not a medical device and **not for clinical use**. A CDS service used in a clinic is
regulated clinical decision support (FDA CDS guidance; EU MDR Annex VIII Rule 11); this feature exists so that the
integration can be tried in sandboxes and evaluated, not to be connected to a live EHR (pre-launch checklist).

## Glossary
- **CDS client:** the EHR or sandbox that calls the service. **Hook:** the workflow event (`order-select`,
  `order-sign`). **Card:** one unit of guidance in the response.
- **Draft orders:** `context.draftOrders`, a FHIR Bundle of unsigned orders. **Selections:** `context.selections`,
  the ids of the newly selected orders (`order-select` only).
- **Prefetch:** FHIR data the client fetched for the service: `medicationRequests` and `medicationStatements`.
- **Focus items:** the medicines a card must involve: the selected orders (`order-select`) or all draft medication
  orders (`order-sign`).

## Requirements

### Requirement 1: Discovery
1. THE API SHALL serve `GET /cds-services` with one entry per hook (`order-select`, `order-sign`), both with id
   `janus-cascade`, a title, a description that states "research prototype, not a medical device, not for clinical
   use" and "no card does not mean the medicines are free of problems" (safety review S1), the prefetch templates
   for active and on-hold MedicationRequest and MedicationStatement resources, and `usageRequirements`.
2. THE discovery response SHALL take no body, carry no personal data and be listed in the public OpenAPI document.

### Requirement 2: The service request
1. THE API SHALL accept `POST /cds-services/janus-cascade` with the CDS Hooks request fields only (`hook`,
   `hookInstance`, `fhirServer`, `fhirAuthorization`, `context`, `prefetch`, `extension`); an unknown top-level or
   context field SHALL be rejected with 422 naming the field path, never its value.
2. WHEN `hook` is not `order-select` or `order-sign`, THE service SHALL answer 422.
3. WHEN `hook` is `order-select` and `context.selections` is missing, THE service SHALL answer 422.
4. THE body limit of the service SHALL be 256 KiB (FHIR bundles are verbose); a larger body SHALL be rejected with
   413 before it is parsed. Bundles SHALL hold at most 200 entries each.
5. WHEN neither prefetch key is present, THE service SHALL answer 412 `prefetch_missing` (it never calls the client's
   FHIR server). A key with value `null` means "no data" and SHALL be accepted.
6. THE service SHALL never read `fhirAuthorization` and never call `fhirServer` or any other external service.

### Requirement 3: Mapping codes to Janus ingredients
1. THE service SHALL read medication codes from `medicationCodeableConcept.coding` or from a referenced `Medication`
   (contained, or in the same Bundle).
2. THE service SHALL map, through the existing resolution layer: an NDC (`http://hl7.org/fhir/sid/ndc`) to the
   openFDA product; an RxNorm code (`http://www.nlm.nih.gov/research/umls/rxnorm`) to the US products that carry it,
   or to the one ingredient key that carries it; an ATC code (`http://www.whocc.no/atc`) to the one ingredient key that
   carries it at ingredient level.
3. A combination ATC code SHALL never be matched (tech.md); a code that maps to more than one different ingredient
   set SHALL not be guessed; an ATC code whose ingredient key carries codes of more than one anatomical group SHALL
   not be matched (the order's dose form would be lost; pharmacologist review P1); all SHALL count as "not checked".
4. Codings SHALL be tried in the order NDC, RxNorm, ATC; the first that maps SHALL be used.
5. A resource whose `subject` (or `patient`) names another patient than `context.patientId` SHALL be ignored.
6. Only draft orders with status `draft`, `active`, `on-hold` or `unknown`, and prefetched resources with status
   `active` or `on-hold`, SHALL be used.
7. WHEN more than 50 distinct medicines remain after mapping, THE service SHALL answer 422 `too_many_medications`.

### Requirement 4: Cards
1. THE service SHALL run the existing cascade engine (`cascades.service.derive`) on the mapped medicines, without
   start dates, in one read-only transaction.
2. THE service SHALL return one card per finding that involves at least one focus item, and no card otherwise; WHEN
   there is no such finding THE response SHALL be `{"cards": []}`.
3. EACH card SHALL have `indicator` `info` (never `warning` or `critical`; safety review S3), a `summary` shorter than 140 characters
   that says "Possible prescribing cascade" and names the PIPC row, a Markdown `detail` that cites the PIPC row (table
   locator, published text, citation, evidence id) and the BMJ 2026 priority figure with its confidence interval when
   the engine returns one, and `source.label` "Janus (research prototype, not a medical device)".
4. THE detail SHALL describe the finding as a pattern in the published list, not a clinical assessment; SHALL say
   that Janus did not read start dates and cannot tell which medicine came first; SHALL carry "Do not stop this
   medicine suddenly." for every abrupt-stop side the engine names; SHALL carry the disclaimer and "Not for clinical
   use."; SHALL say when a side was matched by ingredient only ("Dose form not confirmed"), which prefetch keys the
   EHR did not provide, and that FAERS is spontaneous reporting when FAERS is among the evidence; and SHALL contain
   no forbidden phrase (medical-safety rule 2).
5. Cards SHALL carry no `suggestions` with actions and no `systemActions`: Janus never changes an order.
6. Cards SHALL carry one absolute link to the PIPC article and no SMART link.

### Requirement 5: Privacy and statelessness
1. THE service SHALL store nothing and log nothing but the access line (route, status, latency); no code, id, name
   or date of a request SHALL reach a log or an error body.
2. THE routes SHALL be medical routes (`no-store`, access line only).
3. CORS SHALL be off by default and allowed only for the origins in `JANUS_CDS_CORS_ORIGINS`, only on
   `/cds-services` paths.
4. JWT authentication of the CDS client (CDS Hooks "Trusting CDS Clients") is not implemented; it SHALL be documented
   as an open item and on the pre-launch checklist.

### Requirement 6: Documentation and tests
1. `docs/cds-hooks.md` SHALL explain the service, its limits, the mapping, the security status and a demo against the
   public CDS Hooks sandbox (no test calls an external service).
2. Contract tests SHALL check the discovery document and the card schema; property tests SHALL check that lists
   without a cascade give no card, that every card cites a PIPC row, that summaries are shorter than 140 characters,
   and the code mapping.
