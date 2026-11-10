---
inclusion: fileMatch
fileMatchPattern: "{pipelines/**,apps/api/janus/**,data/**}"
---

# Data sources (verified 2026-11-06 / 2026-11-07)

## Product identification by region
| Source | Region | Use | License / terms | Notes |
|---|---|---|---|---|
| TİTCK Ruhsatlı Beşeri Tıbbi Ürünler Listesi (weekly .xlsx) | TR | barcode → product → ingredient(s) → ATC | **Unclear — do not commit; fetch at runtime** | 23,113 rows (2026-11-06), 99.5% with ATC. **Combination products carry one combination ATC (e.g. AMLIPIN amlodipine+lisinopril = C09BB03)** — decompose to ingredients |
| TİTCK SKRS e-reçete list | TR | on-market flag | Unclear — do not commit | weekly |
| İTS DataMatrix (GS1) | TR | box scan | — | (01) GTIN-14 = "0" + 13-digit barcode; (21) serial; (17) expiry YYMMDD; (10) lot |
| DSCSA product identifier (GS1 DataMatrix) | US | box scan | — | GTIN encodes the NDC (FDA DSCSA product-identifier guidance). Most US patients receive pharmacy vials: support NDC from label text (OCR) and name search |
| openFDA NDC directory | US | NDC → product → ingredients | CC0 | API key |
| openFDA drug enforcement reports (recalls) | US | NDC (+ lot on the device) → recall records | CC0 1.0 (open.fda.gov/terms, verified 2026-11-10); credit FDA; not an FDA endorsement | Bulk download, no key; weekly; 18,076 records (export 2026-11-03), 55 % state an NDC in their text. **FDA: not a way to issue alerts to the public; status is not updated after classification.** Read NDCs from the record text only, never from the added `openfda` block |
| openFDA drug label, "Drug Interactions" sections | US | active substance → label passage that names another ingredient on the list | CC0 1.0 (open.fda.gov/terms); credit FDA; not an FDA endorsement | Bulk download (14 partitions, ~1.8 GB, streamed, not kept), no key; monthly; one label per single-substance name (latest effective date). Quoted as published with set id, date and DailyMed link; never graded. Whole-word name matching only |
| BDPM — Base de données publique des médicaments | EU-FR | CIP13 → CIS → composition (substances) | Licence ouverte: cite source and update date; do not alter data; no implied endorsement | Monthly files: CIS_bdpm, CIS_CIP_bdpm, CIS_COMPO_bdpm … GTIN ↔ CIP13 layout to confirm in design |
| AEMPS CIMA REST API + nomenclátor | EU-ES | national code (CN) → medicine → active ingredients + ATC | Reuse with attribution (Ley 37/2007) | JSON, no auth; daily; pages of 200. GTIN ↔ CN layout to confirm in design |
| AIFA open data: `confezioni.csv` + `PA_confezioni.csv` (Liste dei farmaci) | EU-IT | AIC (pack code) → pack → active ingredients (+ ATC, form) | CC BY 4.0 (aifa.gov.it/open-data, verified 2026-11-10): cite the source; no login | Semicolon CSV, refreshed daily; 160,015 packs (2026-11-10), of which 74,313 homeopathic registrations and 33 suspended (not authorised) packs are left out. Quantity and unit only for part of the ingredient lines; strength otherwise only in the pack description text (not parsed). **No GTIN column: Italian boxes are found by name, never by scan.** Names are Italian; no Italian word list exists, so names map by label or through the pack's own ATC code |
| Health Canada Drug Product Database (DPD), marketed extract | CA | DIN → product → ingredients (+ ATC, form, route, strength) | Open Government Licence – Canada 2.0 (Open Government Portal record of the dataset, verified 2026-11-10): attribution statement; no official status or endorsement | `allfiles.zip` (1.5 MB), UTF-8 tables joined on `DRUG_CODE`; 13,379 marketed products (extract of 2026-11-02), 11,487 of class Human (the others are veterinary, disinfectant, radiopharmaceutical: left out). **The `UPC` column is empty in all 7,617 packaging lines: no barcode lookup.** Canada is outside the regions TR / EU / US, so its products are a Passport target only (not a scan or name-search candidate) |
| Germany (PZN) | EU-DE | — | **No open PZN → product database found** | Resolve by OCR + name search; PZN can be parsed but not resolved |
| Wikidata | all | multilingual ingredient names → ATC (P267), RxNorm CUI (P3345) | CC0 | Cross-region ingredient key; cache a filtered extract |

## Clinical knowledge
| Source | Use | License / terms | Notes |
|---|---|---|---|
| PIPC list (Rochon et al., Eur Geriatr Med 2025;16(5):1573–1584, PMC12712104) | **Primary cascade rule base (65 cascades)** | CC BY 4.0 | Table 1 machine-readable from Europe PMC XML |
| ThinkCascades (McCarthy et al., Drugs Aging 2022) | 9 cascades, secondary | Restricted PMC terms — cite only | |
| BMJ 2026;394:e100499 (Rochon) | 24 high-priority cascades | Paywalled | prioritisation for those named in the abstract |
| OnSIDES v3.1.1 (data, 2026-04-22) | drug → side effects (US/EU/UK/JP labels) | Data CC BY 4.0, code MIT | Replaces SIDER (unmaintained since 2015, CC BY-SA 4.0) |
| openFDA drug label | indications text (US) | CC0 | for exploratory mode and light face |
| RxNav / RxClass (NLM) | ATC ↔ RxCUI | Free; attribution sentence required | 20 req/s |
| WHO ATC/DDD | classification | **Restricted** (no commercial copy/modify; index is paid) | Take ATC codes from TİTCK / CIMA / RxClass / Wikidata; attribute WHOCC |

## Adverse events and statistics
| Source | Use | License / terms | Notes |
|---|---|---|---|
| openFDA / FAERS | Collective Memory, PRR/ROR | CC0 | 21,054,159 reports (2026-10-28); API key required; not deduplicated; quarterly ASCII files for local DuckDB; reporter country field allows TR/EU/US filtering |
| EudraVigilance (adrreports.eu) | EU reports | Public access with reuse limits | **Link out only; do not ingest** |

## Evidence integrity
| Source | Use | License / terms | Notes |
|---|---|---|---|
| Crossref REST API (incl. Retraction Watch data since Jan 2025) | retraction / correction status of every cited DOI | Open metadata | |
| Europe PMC / PubMed | citation metadata, full text where OA | Open APIs | |

## Séance
| Source | Use | License / terms | Notes |
|---|---|---|---|
| OpenITI `0428IbnSina.QanunFiTibb` | Canon Book 2 (844 headings) | **CC BY-NC-SA 4.0** — derived data keeps same license, attribute OpenITI | Typos/missing passages flagged by OpenITI |
| Hamdard 1998 Canon Book 2 translation | plant identifications | © Jamia Hamdard — cite only, never republish text | |
| PMC3941892 tables | Canon remedy identifications (burns/wounds) | CC BY | gold set for the wounds/burns theme |
| Ottoman texts (theses, TTK editions) | 10–20 hand-picked samples | Copyright with authors — short cited quotes only | |
| AncientBiotics (mBio 2020) | medieval remedies | CC BY (Data Set S1 PDF) | no downloadable DB |

## Pitch statistics (verified)
- WHO Medication Without Harm: medication errors cost an estimated US$42 billion a year.
- Oscanoa 2017 meta-analysis: 8.7% of hospital admissions in older adults due to adverse drug reactions.
- Daunt 2025 (PMC12149247): 39.4% of 385 hospitalised older patients had ≥1 potential cascade.
- EMPOWER (JAMA Intern Med 2014): a patient-directed brochure led 27% of long-term benzodiazepine users to discontinue — evidence that informing patients can start deprescribing conversations.
- Lancet 2024 GRAM: AMR 1.14M attributable / 4.71M associated deaths (2021).

Every row inserted into `evidence` must store `source_url`, `license`, region (if any) and snapshot date/version.
