# Changelog

All notable changes to Janus. Versions follow [Semantic Versioning](https://semver.org/); while the version is
below 1.0 a minor version may change public API answers. Each release is a git tag `vX.Y.Z` and is the commit the
public server runs ([docs/releasing.md](docs/releasing.md)). Research use only; expert review has not yet been done.

## [Unreleased]

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
- Validation studies page for researchers with the cascade detection and FAERS calibration results, and the
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
