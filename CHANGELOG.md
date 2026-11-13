# Changelog

All notable changes to Janus. Versions follow [Semantic Versioning](https://semver.org/); while the version is
below 1.0 a minor version may change public API answers. Each release is a git tag `vX.Y.Z` and is the commit the
public server runs ([docs/releasing.md](docs/releasing.md)). Research use only; expert review has not yet been done.

## [Unreleased]

## [0.3.1] - 2026-11-13

### Added

- The expert validation protocol (`docs/research/expert-validation-protocol.md`, with amendment 1), registered before
  any expert sees the material, and the tools that draw its samples and score the answers
  (`pipelines/tools/validation_packet_sample.py`, `score_validation_packet.py`). Expert review has not yet been done.

### Fixed

- After a dataset change, the first name searches could fail while the API built the new name index; the data load
  now builds it before visitors search.

## [0.3.0] - 2026-11-13

### Added

- Two ways in on the home page (patients and families; researchers and clinicians). Patient pages show a patient
  menu (scan, medicines, results, doctor note, passport; settings in the header); researcher pages show their own
  menu (overview, validation, drug models, data, API and MCP) and a link back. The research hub lists its pages in
  five groups; hypothesis cards, the séance and the time machine are labelled experimental and are not in the
  patient menu. Addresses are unchanged.
- The result card reads in three parts: what Janus found, why it may matter, what you can do, with "do not stop or
  change a medicine on your own; talk to your doctor or pharmacist first".
- Every validation study can be downloaded as CSV and shows the citation of the release (from `CITATION.cff`).
- Portuguese ingredient names in the site and the doctor note (1,015 of 1,126 names, from Wikidata, CC0; review by
  a native speaker has not yet been done) and in the ingredient name index.
- CI checks the reading level of the patient texts (Flesch-Kincaid for English, Ateşman for Turkish) and that every
  message key used in the code exists.
- Keyboard and focus tests; a usability test protocol and an accessibility page (`docs/accessibility.md`).

### Fixed

- On a phone, a control focused from the keyboard could be hidden behind the bottom bar.
- Eight screens had no page heading while empty or failing.
- The model kit table on the validation page showed a message key instead of the interval.
- The glass theme no longer downloads the night theme's hero image.
- Stale browser tests (a barcode with a wrong check digit, the candidate order, ambiguous locators) fixed; the full
  browser suite is now a release step.

## [0.2.2] - 2026-11-13

### Fixed

- Migrations read the database URL from `DATABASE_URL_FILE` too (the staging check found that the migration step
  still expected the variable).

## [0.2.1] - 2026-11-13

### Fixed

- The staging check read the production database through the installed compose file, which during the release
  that moves secrets to files is still the previous one; it now finds the production database container by its
  labels.

## [0.2.0] - 2026-11-13

### Added

- Every release is first checked on an ephemeral staging stack: a fresh copy of the production database, the new
  release's migrations, the isolation probe and the smoke test, before production is touched.

### Changed

- Secrets reach the containers only as mounted files (`*_FILE`), never as environment variables.

## [0.1.0] - 2026-11-13

First tagged release: the public site at <https://janusmeds.org> on this date.

### Added

- Medication list check for the 65 cascades of the PIPC list, with sources and evidence for each notice; doctor
  note (PDF, built in the browser); medication passport; plain medicine information; safety, recall and national
  product checks (Türkiye, US, EU countries, Canada, Italy); label OCR and barcode scanning on the device; six
  languages.
- Research tools: FAERS onset table, data-quality reports, open data and public read-only API, MCP server, CDS Hooks
  sandbox, in-browser and queued simulations, experimental drug model starter kit.
- Pre-registered validation studies: cascade detection (specificity 0.975, sensitivity 0.364 against cascades
  published outside the rule list) and FAERS signal calibration (AUC 0.74; nominal intervals too narrow, calibrated)
  ([docs/research/](docs/research/)).
- Operations: daily and weekly backups pulled by a separate machine with a tested restore, private alerting,
  external uptime check, nightly five-fold test runs, pre-commit gate, coverage floors, weekly mutation testing,
  dependency, secret and image scans, CodeQL, hardened images.
- Model kit precision re-measured with study-level clustering (ClinicalTrials.gov still above the 0.90 bound);
  PubMed Central tables and Drugs@FDA reviews measured on fresh pre-registered samples and held back; EMA EPARs
  listed as a cited-only source.
- Model kit gate re-examined: not interpretable (0 of the 10 drugs it needs; limited by the data); the claim is
  narrowed to AUC within 2-fold in 3 drugs; a pre-registered cross-study unit check is implemented and switched off
  because it did not meet its own decision rule ([docs/research/modelkit-gate.md](docs/research/modelkit-gate.md)).
- Validation studies page for researchers with the cascade detection, FAERS calibration, model kit precision and
  model kit gate results, and the
  calibration line next to every FAERS reporting ratio.
- Known limitations in one place, STARD and READUS-PV reporting checklists, one-command reproduction of the
  validation numbers with a weekly check, `CITATION.cff` and Zenodo metadata.
- Architecture page and decision records ([docs/architecture.md](docs/architecture.md), [docs/adr/](docs/adr/README.md)).
- Service level objectives with burn-rate alerts and a dashboard; backup monitoring; runbook
  ([docs/operations.md](docs/operations.md)).

### Changed

- The light face's review status value is `automated_checks_pending_expert` (was `ai_reviewed_pending_expert`).

### Fixed

- The weekly evidence load stopped on the model kit artifacts, which named no source URL.
- The pipelines fetcher dropped a URL's own query string when given an empty parameter mapping.
