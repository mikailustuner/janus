# Requirements: Drug model starter kit ("Model kit")

> Status: experimental. Milestones M0 and M1 are built (M1 did not reach its precision target, see `reviews.md`);
> M2 onwards are open tasks (`tasks.md`). Research use only, not for
> clinical decisions. Expert review has not yet been done. All reading, confirmation and checking in this feature
> is automated; nothing in it has been reviewed by a person.

## Purpose
For a drug name, give a researcher (1) a pharmacokinetic (PK) parameter set in which every value is traceable to a
quoted source sentence or table cell, (2) model files that run in the researcher's own tool (Janus engine JSON,
R/mrgsolve in M0; PK-Sim in M4), and (3) an honest validation report: does the set predict a measurement from a
study it was not built from. It is not clinical decision support, does not compute a dose for any person, and is
not a PBPK simulator.

## Glossary
- **Evidence row:** one measured or stated fact (a PK parameter or an observation) with its source locator, the
  quoted text, the verdict of two readers, and a `confirmed` flag.
- **Reader:** an automated reading pass over the quoted source text. Reader A and reader B are separate passes;
  neither sees the other's output. Agreement is decided by code, not by the readers.
- **Parameter set:** the chosen value of each model parameter with its confidence class, the evidence used and
  the evidence left out with the reason.
- **Held-out study:** a study whose observations are used only to test a set, never to build it.
- **Release:** one versioned evidence artifact (`rows.parquet` + `manifest.json`, a `current` link).

## Requirement 1: Evidence store
1. THE evidence store SHALL keep one row per fact with: drug key, analyte and analyte class, parameter, value as
   stated, value in canonical units, unit, dose and dose unit, route, regimen and interval, population, number of
   subjects, formulation, co-administration flag, study id, source id, source locator, source version, the quote,
   reader A and reader B verdicts, `confirmed`, the confirmation reason, extraction time and pipeline version.
2. A row SHALL be `confirmed` if and only if both readers agree with its value, unit, analyte (the parent drug)
   and context (no restriction such as one sex, a special population, fed state, dose dependence, a per-kg basis
   or a bound). Disagreement rule (owner decision 2026-11-11): if the two readers agree on the value but differ on
   its context (a study-arm restriction such as the test or reference arm of a crossover study,
   co-administration, formulation, food state, population), that IS a disagreement and the value is not
   confirmed. Rows where the readers disagree SHALL stay in the store, flagged, and SHALL NOT reach the builder.
3. THE store SHALL be a versioned artifact built by a pipeline job from committed small source files, with the
   same run, manifest and `current` link rules as the other artifacts; the API SHALL load a new release without
   a restart.
4. Every source SHALL be in `pipelines/sources.toml` and `NOTICE`. ClinicalTrials.gov rows SHALL carry the
   attribution, the date the record was processed and the statement of modification (units converted, values
   re-typed, rows filtered). FDA label and review text is public domain; PubMed Central rows are used only from
   articles licensed CC BY or CC0, with per-article attribution.
5. No raw bulk download and no file larger than 1 MB SHALL be committed.
6. (M1) The store SHALL keep non-parent analytes (named metabolite, enantiomer, unbound, total, prodrug,
   combination partner, unknown code) as separate analytes: they never feed a parent parameter set. A study arm that
   gives another active drug is interaction evidence only. Species other than human are not stored as evidence.
7. (M1) Units SHALL be checked by dimension: a value is converted only if its unit has the dimension of its
   parameter; a per-kg value keeps its per-kg parameter (`cl_per_kg`, `vd_per_kg`) and is never converted to an
   absolute value or read as CL/F without an explicit body weight; molar units are refused without a molar mass.
   The mean type (arithmetic, geometric, median) and the dispersion (SD, CV %, range, interval) are separate fields.
   A dose SHALL come only from an arm definition, a table, a footnote or the methods, never from an abstract.
8. (M1) Reader B SHALL be an implementation independent of reader A (a different parsing strategy, no shared
   extraction code, run without seeing A's output). The runtime has no language model; reader code is build-time
   only. Confirmation = same value (+-1 %), unit, analyte, dose and context (Requirement 1.2).
9. (M1) CL/F = dose / AUC(0-inf) (CL for an intravenous dose) SHALL be derived only where one study arm gives both,
   and the row SHALL be labelled derived with its derivation.

## Requirement 2: Parameter-set builder
1. THE builder SHALL be pure and deterministic: the same rows in any order give the same set.
2. IT SHALL use only confirmed rows of the parent drug, not co-administered, of an immediate-release or solution
   formulation, not a bound and not per-kg.
3. WHEN intravenous clearance and volume exist, the set SHALL be built from them (oral bioavailability from a
   confirmed bioavailability row); otherwise from apparent oral values (CL/F, V/F) labelled "apparent".
4. A per-kg value SHALL NOT be converted to a person-sized value; the builder has no body-weight input.
5. WHEN several studies give a value, the builder SHALL report the sample-size weighted geometric mean and the
   between-study spread; one value per study (arms of one study are pooled first).
6. THE absorption rate SHALL be derived from the time of peak concentration and the elimination rate only, and
   labelled derived; WITHOUT a confirmed peak time the set SHALL be marked incomplete (no concentration-time
   export, no peak prediction).
7. A two-compartment model SHALL be chosen only when the evidence contains a central and a steady-state volume
   that differ; otherwise one compartment, with the reason stated.
8. Each parameter SHALL carry a confidence class: A (two or more independent confirmed studies that agree within
   2-fold), B (one confirmed study, or studies that disagree), C (derived from other parameters or from a stated
   range). Class D (a screening-model fallback) is not produced in M0.
9. Held-out rule: THE studies used to test a set SHALL be chosen before building by a rule that looks only at
   which parameters a study reports for the parent drug; a study that reports any building parameter is never a
   test study; the same study never builds and tests; arms of one study stay on one side. A clearance derived from
   dose and AUC is not "reported" by its study; when a drug has no stated clearance, one study (the first in sorted
   order among those with derived rows) is designated to build and never tests.

## Requirement 3: Validation report
1. FOR each drug with a set, the report SHALL compare the set's predicted Cmax and AUC with the observations of
   the held-out studies: ratio predicted/observed, per study, then the geometric mean over studies; the
   geometric mean fold error (GMFE), the share within 2-fold, the number of points and of studies.
2. STATUS (strict rule, owner decision 2026-11-11): **Validated** only if both AUC and Cmax were tested and EVERY
   held-out observation point (each AUC point and each Cmax point, in every study) is within 2-fold; **Failed** if
   any tested point is outside 2-fold (the report SHALL show which point and name the suspect parameter);
   otherwise **Not validated**, with the reason (no independent observation, no parameter set, Cmax or AUC not
   testable). The geometric mean ratio and the GMFE are still reported but never decide the status.
3. Observations of another formulation class, co-administered arms, unconfirmed rows, and AUC to the last
   sampling time (the time is not in the evidence) SHALL NOT be used; each exclusion SHALL be listed with its
   reason.
4. THE report SHALL show n everywhere and SHALL NOT show an interval it cannot support: a conformal interval is
   shown only with at least 20 independent held-out studies; otherwise the report says that n is too small.
5. A system report SHALL aggregate over drugs (counts by status, pooled GMFE and share within 2-fold with a
   Wilson interval) and state whether n reaches the pre-registered minimum (10 drugs for interpretation).

## Requirement 4: Exports
1. FOR a drug with a complete set THE service SHALL export: Janus engine JSON (the compartmental schema of the
   simulation service, a point model), and R/mrgsolve (`model.cpp`, an example R script); each with
   `provenance.json` (every parameter to its evidence rows, quotes, licences, derivations, exclusions, the
   validation summary), `references.bib`, `LICENSES.txt` and the research-use statements.
2. THE mrgsolve model SHALL load and simulate in R and SHALL reproduce the Janus engine curve within 1 %; a test
   SHALL prove it, with the mrgsolve version pinned and its licence recorded.
3. An incomplete set or a drug without a set SHALL NOT export a model (409 `incomplete_set` / 404-type code).
4. Every export file that is text SHALL carry "Research use only. Not for clinical decisions." and "Expert review
   has not yet been done".
5. PK-Sim, NONMEM and Monolix exports are later milestones (M4, v1.1).

## Requirement 5: API
1. READ-ONLY routes: `GET /modelkit/drugs`, `/modelkit/drugs/{key}`, `/modelkit/drugs/{key}/evidence`,
   `/modelkit/drugs/{key}/export/{target}` (`janus`, `mrgsolve`), `/modelkit/validation`; optional `release`.
2. INPUT SHALL be validated at the boundary (key pattern, target allow-list); errors are codes; 404
   `unknown_drug`, `unknown_release`; 422 `invalid_request`; 503 `modelkit_unavailable`.
3. RESPONSES SHALL be computed once per release and kept in memory; no request starts a simulation or a job.
4. Routes are medical-policy routes (no-store, access line only); the public API document SHALL list them.

## Requirement 6: Web
1. `/[locale]/research/model-kit` SHALL list the drugs with an "Experimental" badge and a status badge.
2. A drug page SHALL show: the badges and the research-use text; the parameter table (value, unit, confidence
   class, number of sources); for each value the quote, the source link and both reader results; the validation
   chart (observed against predicted with the 2-fold band) and its table; the excluded evidence with reasons;
   the download buttons.
3. THE UI SHALL work in en, tr, de, fr, es, in both themes, at 375 px and desktop, meet WCAG AA, and handle
   loading, empty, error and long-content states.
4. THE researchers page and `docs/for-researchers.md` SHALL link to it as experimental.
5. NO text SHALL say a medicine or dose is safe, advise any person, or say "AI"; no text SHALL imply a person
   reviewed anything.

## Requirement 7: MCP
1. THE MCP server SHOULD offer read-only `modelkit_search`, `modelkit_get`, later `modelkit_evidence`, with the
   same statements and no dose advice.

## Requirement 8: Production criteria (not met by M0)
Coverage of at least 150 drugs with confirmed sets and 40 validated; AUC within 2-fold in at least 80 % and Cmax in
70 % of validated drugs with minimum n of 30; sampled accuracy of confirmed values at least 0.95 by an expert
sample audit; three export targets tested in CI; at least one pharmacometrician and one clinical pharmacologist
have reviewed the method; method write-up, user guide, limits page, change log; every source's terms met.
Until then the product stays "experimental".

## Owner decisions
- **2026-11-11 (a) Strict validation rule.** A drug is Validated only if every held-out observation point (each
  AUC and each Cmax point, every study) is within 2-fold. If any point is outside 2-fold the status is Failed,
  with the point and the suspect parameter shown. The earlier drug-level geometric-mean ratio rule is withdrawn.
  Sunitinib (one Cmax point at ratio 0.499) is therefore Failed.
- **2026-11-11 (b) Context disagreement.** Agreement on the value alone is not confirmation; a difference in
  context (arm restriction, co-administration, formulation, food, population) is a disagreement (Requirement 1.2).
