# FHIR R4 JSON schema (test fixture)

`fhir.schema.json.gz` is the official FHIR R4 (4.0.1) JSON schema, `http://hl7.org/fhir/R4/fhir.schema.json`
(the same file as in `http://hl7.org/fhir/R4/fhir.schema.json.zip`, dated 2019-11-01 inside the zip),
downloaded on 2026-11-09, gzipped (`gzip -9 -n`) because it is 3.4 MB. SHA-256 of the uncompressed file:
`2230406893b4cf002a4ee1e5e2bbeca22ac5d2d4931b3e9ef7b9594bbc376a01` (checked by `bundle.test.ts`).
Licence: HL7 FHIR is published under Creative Commons "No Rights Reserved" (CC0),
`http://hl7.org/fhir/R4/license.html`. HL7® and FHIR® are trademarks of Health Level Seven International;
their use here implies no endorsement. Used by the tests only (`validate.ts`); never shipped to the browser.
