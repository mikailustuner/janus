# Requirements: Evidence Integrity ("No Zombie Evidence")

> Refined 2026-11-07 for Phase 1. Requirements 1–3 are the original ones; every original
> criterion keeps its number and wording, with refinements as sub-bullets. Requirements 4–8 were
> added in the refinement. Criteria tagged **[Client: …]** describe what a screen or document
> shows; this spec provides the data for them and the UI is built in the named spec.
> Phase 1 scope: the `evidence` table and its integrity status, the status rules, freshness, the
> API data for the doctor note and the evidence view, and the rule gate that the cascade engine
> consumes. Not in scope: the screens (`experience`), the note layout (`doctor-loop`), the rule
> base itself (`cascade-engine`).

## Introduction
Retracted papers keep being cited for years (on English Wikipedia, citations to retracted papers persisted for a median of 3.68 years — Shi et al., 2026). Janus must never warn a patient, brief a doctor or propose a hypothesis on the basis of retracted or outdated evidence. Every evidence record is checked for retraction and freshness, and the result is visible.

This is a trust layer inside Janus, not a standalone retraction checker (those exist: scite Reference Check, Feet of Clay Detector, RetractionBot, Zotero alerts). Janus's difference is that the check sits in front of patient-facing medical statements.

## Glossary
- **Evidence record:** a row in `evidence` (rule source paper, statistic snapshot, label, ancient text locator, outcome, or a dataset snapshot).
- **Integrity status:** `ok`, `corrected`, `expression_of_concern`, `retracted`, `unknown`.
- **Freshness:** the age of the data snapshot behind the record compared with its expected update cadence.
- **Evidence id:** the stable text key of an evidence record, e.g. `dataset:pipc` or `rule:pipc:12`. Notes and API calls carry evidence ids, never the record content.
- **DOI-bearing record:** an evidence record with a DOI. Only these are checked against Crossref.
- **Basis:** the evidence records another record rests on (a rule rests on its source paper). Records form a directed acyclic graph.
- **Check status:** the result of the latest Crossref check of a DOI. **Effective status:** the status Janus uses, which differs from the check status only when a failed check must not undo a retraction (`data-pipelines` Req 9.5).
- **Notice:** a Crossref update notice of a work (type, source, notice DOI, date), e.g. a correction.
- **Citable:** an evidence record that may back a patient-facing finding, a note sentence or a hypothesis card (Requirement 5).
- **Root source:** the DOI-bearing record, or the record without basis, that a citable record ultimately rests on through citable links only.
- **Integrity snapshot:** the immutable, in-memory copy of all evidence records, statuses, notices and source cadences that the pure functions work on. **Integrity version:** a hash of that snapshot.
- **Rule gate:** the pure function that tells the cascade engine whether a rule is enabled, given the rule's source evidence ids.
- **Cadence:** `cadence_days` of a source in `pipelines/sources.toml`. **Freshness limit:** twice the cadence.

## Requirements

### Requirement 1: Retraction check
#### Acceptance criteria
1. WHEN an evidence record has a DOI THE system SHALL query Crossref for update notices (retraction, correction, expression of concern, including Retraction Watch data) and store the status with the check date.
   - The query is made by the `retractions` pipeline (`data-pipelines` Req 9). THE integrity loader SHALL store, for each DOI-bearing record, the effective status, the status of the latest check, the reason when that check failed, the check date, the run id of the check, and every notice (type, source, notice DOI, date).
   - WHERE an evidence record has no DOI THE system SHALL store no integrity status for it and SHALL report its DOI check as `not_applicable`. `not_applicable` SHALL NOT be shown as `ok`.
2. THE system SHALL re-check every DOI at least weekly and after every rule-base update.
   - THE `retractions` pipeline SHALL collect DOIs from the evidence source records of the current artifacts and from the curated paper list `data/evidence_papers.csv`, so a rule-base update that adds a paper is covered by the next pipeline run.
   - WHEN a DOI-bearing record has no row in the current `retractions` artifact THE integrity loader SHALL store it as `unknown` with reason `not_yet_checked` and SHALL report how many records are in that state.
   - WHEN the latest check of a record is older than twice the cadence of the `crossref` source THE system SHALL show the notice `integrity_check_may_be_out_of_date` with that record. The status itself SHALL NOT change.
   - **[Phase 5: scheduling]** The weekly schedule is a deployment task (`data-pipelines` DP11). Until then the check runs when a maintainer runs the pipeline, and the notice above makes a missed week visible.
3. WHEN a record is `retracted` THE system SHALL exclude it from patient-facing findings, doctor notes and hypothesis cards, and SHALL disable any cascade rule whose only source is retracted.
   - `retracted` includes partial retractions, withdrawals and removals, as mapped by the `retractions` pipeline.
   - The exclusion and the rule gate follow Requirements 5 and 6.
4. WHEN a record is `corrected` or `expression_of_concern` THE system SHALL show the notice next to the evidence.
   - THE system SHALL return every notice of the record with its type, date, source and a link to the notice DOI (`https://doi.org/<notice doi>`), newest first.
   - THE system SHALL show the notice as published and SHALL NOT describe what the notice changed, because Crossref metadata does not say. (Owner note: the correction to the PIPC paper only changed its licence to CC BY 4.0; Crossref lists CC BY 4.0 on the notice from 2025-12-18 but does not describe the change, so Janus shows type, date and link only.)
   - A `corrected` or `expression_of_concern` record SHALL remain citable and SHALL carry the notice wherever it is cited (Requirement 5.3).
5. WHEN the check cannot be completed THE system SHALL mark the record `unknown` and show it; it SHALL NOT silently treat it as `ok`.
   - THE system SHALL keep the reason of the failed check (`check_failed`, `not_found`, `unreadable_response`, `http_<status>`, `not_yet_checked`).
   - IF a check cannot be completed and the last completed check of that DOI was `retracted` THEN THE system SHALL keep the effective status `retracted` (`data-pipelines` Req 9.5). This SHALL also hold across integrity loads: a stored `retracted` status SHALL change only when a later completed check reports another status.
   - WHEN the current `retractions` artifact has no row for a DOI that is already stored THE integrity loader SHALL keep the stored state unchanged.

### Requirement 2: Freshness
#### Acceptance criteria
1. Every data source SHALL declare its expected update cadence (e.g. TİTCK weekly, BDPM monthly, FAERS quarterly).
   - THE cadence SHALL be the `cadence_days` already declared in `pipelines/sources.toml`. THE system SHALL NOT keep a second list of cadences; the integrity loader SHALL read the registry file and store the cadence it finds with the source.
   - IF an evidence record names a source whose storage rule is `runtime_only`, `cache` or `commit` and that source declares no `cadence_days` THEN THE integrity loader SHALL refuse the record and name the source.
   - Records of `cited_only` and `separate_package` sources (published papers, licensed packages) have no update cadence; their freshness SHALL be reported as `not_applicable`.
2. WHEN a source snapshot is older than twice its cadence THE system SHALL show a "data may be out of date" notice on the affected results.
   - THE age SHALL be counted in whole UTC days from the record's snapshot date to the current UTC date. THE snapshot SHALL be stale if and only if its age is greater than `2 × cadence_days`. An age of exactly `2 × cadence_days` is not stale. A snapshot date in the future SHALL give age 0.
   - THE notice code SHALL be `source_may_be_outdated`, and the data SHALL name the source, its snapshot date, its age and the limit in days.
   - WHERE a result rests on several sources THE notice SHALL be attached for each stale source.
   - A stale snapshot SHALL NOT change an integrity status and SHALL NOT make a record non-citable. The notice informs; it does not remove evidence.

### Requirement 3: Visibility
**User story:** As a doctor, I want to see that the sources behind the note are current and not retracted, so that I can trust it.

#### Acceptance criteria
1. THE doctor note SHALL carry an integrity line: number of sources, date checked, and "no retracted sources used" — or the exceptions.
   - THE API SHALL return the data for this line for any set of evidence ids: number of distinct sources, how many of them were checked by DOI, counts per status, the oldest and newest check date, the stale sources, the evidence ids that were excluded with their reasons, and a flag `no_retracted_used`.
   - THE flag `no_retracted_used` SHALL be true if and only if no root source of any citable record is `retracted`. THE exceptions (`corrected`, `expression_of_concern`, `unknown`, stale sources, excluded ids) SHALL be returned as data, not folded into the flag.
   - THE line SHALL state nothing about the person's medicines; it describes the sources only (`medical-safety.md` rules 3 and 9).
   - **[Client: doctor-loop / experience]** Wording in the five languages and the layout in the PDF.
2. THE evidence view SHALL show each source's integrity status and check date.
   - THE API SHALL return, for each requested evidence id, the status, the check status, the check date, the age of the check, the notices (Requirement 1.4), the freshness (Requirement 2.2), the reason when excluded, and the root sources the record rests on with the same fields.
   - WHEN a record is `corrected` or `expression_of_concern` THE notice SHALL appear in the data of that record and of every record that rests on it. For the PIPC evidence this means the correction notice 10.1007/s41999-025-01378-7 (type `correction`, source `publisher`, date 2025-12-18) appears with the PIPC list and with each PIPC rule record.
   - THE API SHALL never return `ok` for a record whose status is `unknown` or that has not been checked.
   - THE API SHALL return `retracted` records too, marked as excluded, so that the evidence view can show why a source was left out.
   - **[Client: experience]** The status labels, the zombie stamp for `retracted`, and the layout.
3. THE researcher area SHALL list any evidence that changed status since the last snapshot.
   - THE system SHALL record every change of an effective status with the previous status, the new status, the date it was observed and the run id of the check.
   - THE API SHALL list the changes since a given date, newest first, and by default those observed on the most recent day on which any status changed.
   - A first sighting of a record (no previous status) SHALL be stored but SHALL NOT be listed as a change.
   - **[Client: experience]** The researcher screen.

### Requirement 4: Evidence records (added in refinement)
**User story:** As the narrator and auditor agents, I need one place that knows every source Janus can cite, with its licence and date, so that a sentence without a registered source can be removed.

#### Acceptance criteria
1. EVERY evidence record SHALL have: an evidence id, a kind (`dataset`, `rule`, `faers_stat`, `paper`, `label`, `ancient`, `chembl`, `outcome`), a source id from the source registry, a source URL, a licence, a snapshot date (and whether it is the retrieval time), and optionally a region, a DOI, a locator and a title.
   - IF a record lacks a source URL, a licence or a snapshot date, or names a source that is not in the registry, THEN THE loader SHALL refuse it, name the field, and change nothing.
2. THE evidence id of a record SHALL be derived from its kind, source id and a key (for example the table row of a rule) and SHALL NOT depend on run ids, load order or time. THE same source, loaded again, SHALL keep its ids.
   - THE loader SHALL NOT delete evidence records. A note issued earlier can still resolve its ids; a record that is no longer produced keeps its last state.
3. THE loader SHALL create records from: the evidence source record of every current pipeline artifact (kind `dataset`, id `dataset:<source id>`, with the DOI the pipeline emitted, e.g. `pipc`), and the curated paper list `data/evidence_papers.csv` (kind `paper`). Other specs SHALL register their records (rules, statistics, labels, outcomes) through the same validated function.
4. A record MAY list basis records. THE loader SHALL refuse a basis that does not exist, a record that rests on itself directly or indirectly, and a `rule` record without basis.
5. A DOI SHALL be stored in normalised form (lower case, without URL or `doi:` prefix; `data-pipelines` Req 9.1) and SHALL match `10.<4–9 digits>/<suffix>`.

### Requirement 5: Status rules and citability (added in refinement)
#### Acceptance criteria
1. THE severity order of statuses SHALL be `ok` < `corrected` < `expression_of_concern` < `retracted`. `unknown` SHALL stand outside this order and SHALL never be treated as `ok`.
2. A record SHALL be citable according to these rules, and no others:
   - a record that is not in the evidence table is not citable (`not_registered`);
   - a DOI-bearing record is citable unless its effective status is `retracted` (`retracted`);
   - a record without DOI that has basis records is citable if and only if at least one basis record is citable (`no_citable_basis`);
   - a record without DOI and without basis is citable.
3. THE system SHALL treat `corrected`, `expression_of_concern` and `unknown` records as citable and SHALL return their notices or their `unknown` status with them. **[Owner to confirm: DP4]**
4. WHEN a finding, a note sentence, a hypothesis card or a Séance witness cites a set of evidence ids THE system SHALL keep only the citable ids; IF none is left THEN the finding, sentence or card SHALL be removed. The API SHALL return the kept and the excluded ids with the reason for each.
5. WHEN a record's effective status changes from any other status to `retracted` THE set of citable records, of kept outputs and of enabled rules SHALL only shrink; no output SHALL appear that was absent before.
6. THE citability of a record SHALL be a function of the integrity snapshot only; THE system SHALL NOT store an "excluded" or "disabled" flag that could outlive the status that caused it.

### Requirement 6: Rule gate for the cascade engine (added in refinement)
**User story:** As the cascade engine, I need one pure function that tells me whether a rule may be used and why not, so that a rule backed only by a retracted paper never produces a finding.

#### Acceptance criteria
1. THE system SHALL provide a pure function `rule_gate(sources, snapshot)` that takes the evidence ids of a rule's sources and returns: whether the rule is enabled, the reason when it is not, the sources that remain citable, and the sources that were removed with the reason for each. It SHALL do no I/O.
2. A rule SHALL be disabled if and only if it has no source, or none of its sources is citable. A rule with at least one citable source SHALL stay enabled, and its non-citable sources SHALL be left out of the evidence ids of its findings.
3. THE reason SHALL be `no_source` (empty list), `all_sources_retracted` (every source removed because `retracted`) or `no_citable_source` (any other mix), together with the removed sources and, for retracted ones, their notices, so that the cascade engine can "disable the rule and report why" (`cascade-engine` Req 1.5).
4. THE gate SHALL depend only on the snapshot passed in. A rule disabled by a retracted source SHALL be enabled again as soon as a snapshot in which a source is citable is used.
5. THE gate SHALL not depend on the order of the sources or on repeated ids.
6. THE cascade engine SHALL read the snapshot once per request through one function (`load_snapshot`) and pass it to its pure functions; THE gate SHALL NOT read the database.

### Requirement 7: API data (added in refinement)
**User story:** As the client, I need the integrity data for the evidence ids of a note or a finding, without sending any medicine list to the server.

#### Acceptance criteria
1. THE API SHALL offer `POST /evidence/resolve` with a JSON body of 1 to 200 distinct evidence ids and SHALL return: the integrity version, the date used as "today", one item per id (Requirement 3.2), the citable and excluded ids with reasons, and the integrity line (Requirement 3.1).
2. THE API SHALL offer `POST /evidence/changes` with an optional `since` date and an optional limit, and SHALL return the status changes (Requirement 3.3), the dates on which changes were observed, and the current count per status.
3. THE responses SHALL contain fixed codes for statuses, reasons and notices, and data (dates, ids, URLs, counts). They SHALL contain no sentences for the patient; the wording belongs to the note and the client. Every response SHALL carry the research-prototype disclaimer (`medical-safety.md` rule 9).
4. IF no evidence has been loaded THEN THE API SHALL answer 503 `integrity_unavailable`, and no id SHALL count as citable. WHEN evidence is loaded, an id that is not registered SHALL be returned as `not_registered` and not citable, with status 200.
5. THE responses SHALL be identical for the same request, snapshot and date, whatever the order or repetition of the ids.
6. WHEN a body is invalid THE API SHALL answer 422 `invalid_request` naming the failing fields only, and SHALL NOT echo any input value.

### Requirement 8: Loading, storage and privacy (added in refinement)
#### Acceptance criteria
1. THE integrity loader (`python -m janus.integrity.load`) SHALL read the current `retractions` artifact and the evidence source record of every other current artifact from the data directory, verify each artifact's outcome and content hash against its manifest (as the resolution loader does), and write all changes in one transaction. IF anything fails THEN the stored state SHALL be as before the load.
2. WHEN the loader is run again on unchanged artifacts THE stored data SHALL be unchanged and no status change SHALL be recorded.
3. THE tables SHALL be created by a forward-only Alembic migration with a downgrade. THE tables SHALL hold no user data: only public evidence, statuses and notices.
4. THE integrity version SHALL be a hash of the snapshot content and SHALL change if and only if a record, a basis link, a status, a notice or a cadence changes.
5. THE two routes SHALL be medical routes (JSON body only, `no-store`, read-only transactions): an evidence id can reveal which finding a person has. THE routes and the loader SHALL log no evidence id and no DOI; the loader SHALL log counts and the integrity version only.
6. THE only code allowed to write the evidence tables SHALL be `janus/integrity/load.py` and the validated registration function that other specs call inside their own loaders (the import-boundary test of the privacy spec is extended).

## Properties to test (PBT candidates)
- No patient-facing finding, note sentence or hypothesis card is ever backed only by `retracted` evidence. (Req 1.3, 5.2, 5.4)
- An `unknown` status is never displayed as `ok`. (Req 1.5, 3.2, 5.3)
- Changing a record's status from `ok` to `retracted` removes it from every output and never adds new findings. (Req 1.3, 5.5, 6.2)
- Re-running the check with unchanged Crossref responses produces identical statuses (idempotence). (Req 1.1, 8.2, 8.4)
- Added in refinement:
  - A failed check or a missing row never un-retracts a stored `retracted` record, and `unknown` never becomes `ok`. (Req 1.5)
  - A snapshot is stale exactly when its age exceeds twice its cadence; freshness never changes a status or citability. (Req 2.2)
  - The cadence the loader uses is the `cadence_days` of the registry file; a data source without cadence is refused. (Req 2.1)
  - Citability follows the DOI status for DOI-bearing records and the basis for the others, whatever the order of the data, and the computation ends on any graph. (Req 5.2)
  - A rule is disabled exactly when it has no citable source; more retracted sources never enable a rule, more citable sources never disable one; there is no memory between snapshots. (Req 6.2–6.5)
  - The integrity line equals an independent recount, and `no_retracted_used` is true exactly when no root source is retracted. (Req 3.1)
  - Every notice of a `corrected` or `expression_of_concern` record appears in its data and in the data of every record that rests on it, newest first. (Req 1.4, 3.2)
  - Invalid evidence records (missing field, bad id or DOI, missing basis, cycle, `rule` without basis, unknown source, no cadence) are refused with a specific code and nothing is stored; evidence ids are deterministic and unique. (Req 4)
  - The status-change log has exactly one row per real change and none for unchanged statuses. (Req 3.3)
  - A failed or refused load leaves the previous state complete. (Req 8.1)
  - With nothing loaded, nothing is citable and the route answers 503; unregistered ids are never citable. (Req 7.4)
  - The resolve response does not depend on the order or repetition of ids, and the integrity version changes if and only if content changes. (Req 7.5, 8.4)
  - The routes are stateless, log no evidence id or DOI, never echo input, and use closed vocabularies for codes. (Req 7.3, 7.6, 8.5)
