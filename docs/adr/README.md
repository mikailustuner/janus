# Architecture decision records

Decisions are recorded where they are made: each feature's design document under
`.kiro/specs/<feature>/design.md` keeps a table of design decisions numbered `DP1`,
`DP2`, … with the decision and its reason. Decisions that cut across features are
recorded here as short ADRs.

## Cross-cutting decisions

| ADR                                                  | Decision                                                                    |
| ---------------------------------------------------- | --------------------------------------------------------------------------- |
| [0001](0001-no-language-model-as-product-reader.md)  | No language model reads documents or answers people inside the product      |
| [0002](0002-pre-registered-measurements.md)          | Every scientific measurement is pre-registered before its results exist     |
| [0003](0003-backups-pulled-by-a-separate-machine.md) | Backups are pulled by a separate machine the server cannot reach            |
| [0004](0004-synthetic-test-fixtures.md)              | Behaviour tests use synthetic fixtures; recorded data has one contract test |

## Decisions by feature (467 in 32 design documents)

| Feature             | Design document                                                                                             | Decisions |
| ------------------- | ----------------------------------------------------------------------------------------------------------- | --------- |
| cascade-engine      | [Design: Cascade Engine ("Ghost Diseases"), Phase 1](../../.kiro/specs/cascade-engine/design.md)            | 23        |
| cascade-map         | [Design: Cascade Map](../../.kiro/specs/cascade-map/design.md)                                              | 14        |
| cds-hooks           | [Design: CDS Hooks service](../../.kiro/specs/cds-hooks/design.md)                                          | 14        |
| collective-memory   | [Design: Collective Memory, Phase 2](../../.kiro/specs/collective-memory/design.md)                         | 25        |
| data-pipelines      | [Design: Data Pipelines (ETL), Phase 1 and Phase 2](../../.kiro/specs/data-pipelines/design.md)             | 34        |
| data-quality        | [Design: Weekly data-quality report](../../.kiro/specs/data-quality/design.md)                              | 0         |
| deploy              | [Design: Deploy (Phase 5)](../../.kiro/specs/deploy/design.md)                                              | 11        |
| doctor-loop         | [Design: Doctor Note and Outcome Loop, Phase 2 (server side)](../../.kiro/specs/doctor-loop/design.md)      | 42        |
| drug-resolution     | [Design: Drug Resolution, Phase 1 (Türkiye and United States)](../../.kiro/specs/drug-resolution/design.md) | 45        |
| evidence-integrity  | [Design: Evidence Integrity, Phase 1](../../.kiro/specs/evidence-integrity/design.md)                       | 22        |
| experience          | [Design: Experience, Phase 3 (client)](../../.kiro/specs/experience/design.md)                              | 72        |
| faers-onset-table   | [Design: FAERS time to onset for all 65 PIPC cascades](../../.kiro/specs/faers-onset-table/design.md)       | 0         |
| fhir-export         | [Design: FHIR export of the medicine list](../../.kiro/specs/fhir-export/design.md)                         | 14        |
| for-researchers     | [Design: Janus for researchers](../../.kiro/specs/for-researchers/design.md)                                | 0         |
| janus-report        | [Design: Janus report (Summary screen and share image)](../../.kiro/specs/janus-report/design.md)           | 14        |
| light-face          | [Design: Light Face ("Dead Drugs Rise")](../../.kiro/specs/light-face/design.md)                            | 24        |
| mcp-server          | [Design: Janus MCP server](../../.kiro/specs/mcp-server/design.md)                                          | 10        |
| medication-passport | [Design: Medication Passport (cross-border list)](../../.kiro/specs/medication-passport/design.md)          | 33        |
| model-kit           | [Design: Drug model starter kit](../../.kiro/specs/model-kit/design.md)                                     | 0         |
| national-products   | [Design: National products, Canada (DPD) and Italy (AIFA)](../../.kiro/specs/national-products/design.md)   | 0         |
| ocr-first           | [Design: OCR first — a box from any country](../../.kiro/specs/ocr-first/design.md)                         | 0         |
| open-data           | [Design: Open data](../../.kiro/specs/open-data/design.md)                                                  | 10        |
| plain-medicine-info | [Design: Medicine information in your own language](../../.kiro/specs/plain-medicine-info/design.md)        | 0         |
| privacy             | [Design: Privacy and Consent, Phase 1 (server side)](../../.kiro/specs/privacy/design.md)                   | 21        |
| recall-check        | [Design: Recall check (US, FDA enforcement reports)](../../.kiro/specs/recall-check/design.md)              | 0         |
| report-assistant    | [Design: Report Assistant](../../.kiro/specs/report-assistant/design.md)                                    | 13        |
| research-tools      | [Design: Research tools (Phase 1)](../../.kiro/specs/research-tools/design.md)                              | 0         |
| safety-check        | [Design: Safety check of the medicine list](../../.kiro/specs/safety-check/design.md)                       | 0         |
| seance              | [Design: The Séance ("Three Witnesses"), Phase 4](../../.kiro/specs/seance/design.md)                       | 16        |
| simulation-service  | [Design: Simulation service](../../.kiro/specs/simulation-service/design.md)                                | 0         |
| time-machine        | [Design: The Time Machine](../../.kiro/specs/time-machine/design.md)                                        | 0         |
| zombie-alert        | [Design: Zombie Alert](../../.kiro/specs/zombie-alert/design.md)                                            | 10        |

This index is generated by `scripts/adr_index.py`; run it after adding a design decision.
