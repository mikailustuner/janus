# Janus CDS Hooks service

> **Research prototype, not a medical device, not for clinical use.** Janus provides information, not medical
> advice. Clinical decision support shown to clinicians can be regulated as a medical device (US FDA Clinical
> Decision Support guidance, revised 29 Jan 2026; EU MDR Annex VIII Rule 11, at least class IIa). This service
> exists so that the integration can be tried in sandboxes and evaluated. Do not connect it to a live EHR (see the
> [pre-launch checklist](pre-launch-checklist.md)).

The Janus API includes an [HL7 CDS Hooks 2.0](https://cds-hooks.hl7.org/) service (2.0.1, STU 2 Release 2) that
checks medication orders for **possible prescribing cascades** from the published PIPC list (Rochon et al., Eur
Geriatr Med 2025, CC BY 4.0). Spec: [`.kiro/specs/cds-hooks/`](../.kiro/specs/cds-hooks/).

## Endpoints

| Route | What it does |
|---|---|
| `GET /cds-services` | Discovery: the service `janus-cascade` for the hooks [`order-select`](https://cds-hooks.org/hooks/order-select/) and [`order-sign`](https://build.fhir.org/ig/HL7/cds-hooks-library/order-sign.html) (these two replace the older `medication-prescribe` hook) |
| `POST /cds-services/janus-cascade` | The service: FHIR R4 draft orders + prefetch in, cards out |

Prefetch templates:

```
medicationRequests:   MedicationRequest?patient={{context.patientId}}&status=active,on-hold
medicationStatements: MedicationStatement?patient={{context.patientId}}&status=active,on-hold
```

## What it does with a request

1. **Validates** the CDS Hooks fields strictly (an unknown top-level or `context` field → 422 naming the field
   path, never its value) and reads the FHIR resources leniently. Body limit 256 KiB, at most 200 bundle entries.
   No prefetch key at all → 412 `prefetch_missing` (Janus never calls the EHR's FHIR server; `fhirAuthorization`
   is never read). A key sent as `null` means "no data".
2. **Extracts medicines**: draft `MedicationRequest`s (status draft, active, on-hold or unknown) and prefetched
   active or on-hold `MedicationRequest` / `MedicationStatement` resources. A resource for another patient than
   `context.patientId` is ignored. **Start dates are not read**: `authoredOn` is when a request was written (often
   a renewal), not when the medicine was started.
3. **Maps codes** through the Janus resolution layer, in this order, first match wins:
   - NDC (`http://hl7.org/fhir/sid/ndc`) → the openFDA product;
   - RxNorm (`http://www.nlm.nih.gov/research/umls/rxnorm`) → the US products that carry the code (SCD/SBD), or
     the one ingredient key that carries it (IN);
   - ATC (`http://www.whocc.no/atc`) → the one ingredient key that carries the code at ingredient level, unless
     that key's codes span more than one anatomical group (e.g. timolol eye drops S01ED01 and oral timolol
     C07AA06): the engine would read every form's codes, so the order's form would be lost.
   A combination ATC code is never matched; a code that maps to products that read differently, to more than 500
   products, or to two ingredient keys, is not guessed. Such medicines are counted as "not checked" on the card.
4. **Runs the cascade engine** (the same one as `POST /cascades/evaluate`) in one read-only transaction.
5. **Answers with cards** only for findings that involve a **focus** medicine: the selected orders
   (`order-select`) or the draft orders (`order-sign`). No finding → `{"cards": []}`. Janus shows a card only when
   it finds a pattern from its rule list; **no card does not mean the medicines are free of problems** (the
   discovery document says so too). A medicine Janus could not map is counted on the cards it does show; when no
   card is shown, an unmapped selected order is not reported.

## Cards

```json
{
  "summary": "Possible prescribing cascade (PIPC row 5): amlodipine and furosemide",
  "indicator": "info",
  "detail": "**Possible prescribing cascade.** These medicines match a pattern in the published PIPC list ...",
  "source": {"label": "Janus (research prototype, not a medical device)", "url": "https://github.com/mikailustuner/janus/blob/main/docs/cds-hooks.md"},
  "links": [{"label": "PIPC list (Rochon et al. 2025)", "url": "https://doi.org/10.1007/s41999-025-01215-x", "type": "absolute"}]
}
```

- `summary` under 140 characters; `indicator` always `info` (a literature pattern without start dates is not an
  urgent alert); never `warning` or `critical`.
- `detail` (Markdown): the PIPC row as published (table locator, drug A → adverse event → drug B), which medicines
  matched and where they came from, the timing caveat ("the pattern applies only if B was started after A"), a
  "dose form not confirmed" line when a medicine was matched by ingredient only, the BMJ 2026 population figure
  with its 95% CI when the engine has one, "Do not stop this medicine suddenly." for abrupt-stop drug classes,
  "This may be worth considering in a medication review.", the not-checked count, the prefetch keys the EHR did
  not provide, the FAERS caveat when FAERS is among the evidence, the citation and evidence ids, the disclaimer and
  "Not for clinical use."
- No `suggestions`, no actions, no `systemActions`: Janus never changes an order.

## Privacy and security

- Stateless: nothing is stored. The routes are medical routes: `Cache-Control: no-store`, and the only log line is
  the access line (route, status, latency). Error bodies are codes and field paths; an unknown field is named
  `<unknown>`, because its name is the sender's text.
- **No client authentication yet.** CDS Hooks says services SHOULD authenticate clients with a signed JWT (ES384 /
  RS384, `iss`/`jku` allow-list, `aud` = the service URL, `jti` replay check). Janus does not verify it: this is an
  open item and the reason the service must not receive real patient data.
- CORS is off unless `JANUS_CDS_CORS_ORIGINS` lists origins (comma-separated `https://` origins, or
  `http://localhost[:port]`); it then applies to `/cds-services` paths only.

## Try it with curl

Start the API with a loaded dataset (README; locally `docker compose up`, the API listens on `127.0.0.1:8000`), then:

```sh
curl -s http://127.0.0.1:8000/cds-services | jq '.services[].hook'
# "order-select"  "order-sign"

curl -s -X POST -H 'content-type: application/json' \
  --data @docs/cds-hooks-example.json \
  http://127.0.0.1:8000/cds-services/janus-cascade | jq '.cards[].summary'
# "Possible prescribing cascade (PIPC row 5): amlodipine and furosemide"
```

[`cds-hooks-example.json`](cds-hooks-example.json) is a synthetic `order-select` request: an active amlodipine 5 mg
tablet (RxNorm 308135) and a selected furosemide 20 mg tablet order (RxNorm 310429).

## Demo with the public CDS Hooks sandbox

The [CDS Hooks sandbox](https://sandbox.cds-hooks.org) is a mock EHR in the browser; it calls the service from your
browser, so the API needs CORS for the sandbox origin. No patient data is involved: the sandbox uses its own test
FHIR server and synthetic patients.

1. Start the API locally with CORS for the sandbox:
   ```sh
   JANUS_CDS_CORS_ORIGINS=https://sandbox.cds-hooks.org docker compose up --build
   # or, in apps/api: JANUS_CDS_CORS_ORIGINS=https://sandbox.cds-hooks.org uv run uvicorn janus.main:app
   ```
2. Open the sandbox with Janus's discovery endpoint and the Rx View preselected (furosemide 20 mg tablet):
   ```
   https://sandbox.cds-hooks.org/?serviceDiscoveryURL=http%3A%2F%2Flocalhost%3A8000%2Fcds-services&screen=rx-view&hook=order-select&prescribedMedication=310429
   ```
   Or add it by hand: gear icon → **Add CDS Services** → `http://localhost:8000/cds-services`.
   Your browser may ask whether the page may reach a service on your own computer (local network access); allow it
   for the demo. If the browser blocks plain `http://localhost` from the https page, put the API behind a local
   https proxy. Do not expose it through a public tunnel: the service has no client authentication.
3. In **Rx View** choose a medicine; the sandbox calls `order-select`. Cards appear when the selected medicine and
   one of the sandbox patient's active medicines match a PIPC row (for example a diuretic selected for a patient on
   a calcium channel blocker). Use **Change Patient** to try another synthetic patient. The **CDS Developer Panel**
   shows the request and the cards.
4. Stop the API when you are done.

Tests never call the sandbox or any other external service.

## Tests

`apps/api/tests/test_cds_*.py`: contract tests for discovery and the card schema; property tests (no card without
a finding that touches a focus medicine; every card cites its PIPC row; summary length; code mapping order and
no guessing; other-patient and status filters; nothing of a request in logs, error bodies or the database).
