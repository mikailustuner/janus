# Requirements: The Time Machine

> Owner-approved feature, written 2026-11-09. Four layers (L1 molecules, L2 targets and today's
> drugs, L3 ADMET and body simulation, L4 exposure versus potency) plus the digital twin of the
> cascade. Criteria tagged **[Client: experience]** describe what the web app shows; this spec
> provides the data and the contract (design §10), and `apps/web` builds the screens.
>
> Everything here is **in silico**: results are hypotheses, never treatments and never doses
> (medical-safety rules 7–8). No claim in this spec may be shown to a patient as advice. The
> human `reviewed` status is reserved for the experts; until then every output carries
> "AI-reviewed, pending expert review".

## Introduction
Take a substance named in Ibn Sina's Canon, Book 2, and follow it forward in time: its
constituents (L1), the protein targets those constituents are measured on and the drugs used
today for the same condition (L2), what an open model predicts about their fate in the body and
what a simulation says about plasma concentration over time (L3), and whether the concentration
a historical dose would produce reaches the concentration at which an activity was measured
(L4). Separately, build a *digital twin of a prescribing cascade*: a virtual older population,
the time to onset reported in FAERS, and a comparison with the timing windows published in the
cascade literature.

The Time Machine is researcher-facing. The only patient-facing output is one cautious sentence
about a timing window (Requirement 9).

## Glossary
- **Constituent:** a chemical compound reported to occur in the plant or preparation a Canon
  entry names.
- **Occurrence statement:** a Wikidata "found in taxon" (P703) statement with a reference,
  matched on the compound's full InChIKey (P235). LOTUS uploads such statements.
- **Potency:** a measured concentration at which an activity was observed (IC50, EC50, Ki, Kd,
  AC50, MIC), in µmol/L.
- **Public-domain depositor:** a PubChem depositor whose records are US-government works. Only
  these supply values Janus stores.
- **Curated target:** a protein, named in `data/time_machine/potency_targets.csv` with a reason,
  that is relevant to the condition of the pair. A potency on any other target may not carry a
  verdict.
- **PBPK:** the physiologically based model of the httk package (US EPA). Used only where httk
  has human parameters for the drug.
- **Compartmental model:** Janus's one-compartment model with first-order absorption and cited
  parameters. **Never called PBPK.**
- **Credibility:** the verdict of the validation rule (Requirement 5) on a drug.
- **Time to onset:** the interval from the therapy start date to the event date in one FAERS
  report. What a reporter wrote down, not a measured latency.
- **Risk window:** the central 80 % of the reported times to onset.
- **Elderly population:** ages 65–79. HTTK-Pop resamples NHANES records and holds no ages above
  79, so 80+ cannot be simulated and is never claimed.

## Requirements

### Requirement 1: Verified sources, tools and licences
#### Acceptance criteria
1. THE spec SHALL record, for every dataset, tool and model used, its source, version, licence
   and the date it was verified, before any of its output enters the repository.
2. WHEN a value's licence permits storage only under a share-alike or unverified licence THE
   pipeline SHALL NOT store the value.
   - 1.2a WHERE such a record concerns a drug-metabolism target THE pipeline SHALL keep a
     *pointer* (assay id, target, depositor, licence class) without the value, so the finding is
     not lost.
3. THE repository SHALL NOT contain a number or a reference that cannot be traced to a fetched
   source; every DOI cited SHALL be verified through Crossref and its retraction relations
   checked.
4. WHERE a tool must be installed to produce an artifact THE installation SHALL live under
   `.data/tools` and SHALL NOT be committed.
5. WHEN a required local tool is absent THE job SHALL be refused with the "refused" exit code
   and SHALL NOT fail the test suite; THE continuous-integration run SHALL NOT need R or any
   model environment.

### Requirement 2: L1 — molecules of a Canon substance
#### Acceptance criteria
1. THE build SHALL cover 3–5 substances that the séance package identifies, chosen with the
   historian and pharmacologist passes, and SHALL record why each was chosen.
2. WHEN a constituent is curated for a substance THE pipeline SHALL confirm an occurrence
   statement for the substance's taxon, matched on the full InChIKey, and SHALL record the
   compound item and the reference items of that statement.
   - 2.2a WHEN no such statement exists THE constituent SHALL be excluded and counted, never
     carried forward on the strength of its name.
   - 2.2b WHERE the substance is a preparation rather than an organism (e.g. vinegar) THE
     constituent SHALL be recorded without a taxon and the reason SHALL be stated.
3. THE structure used for any prediction SHALL be fetched from PubChem **by name or by curated
   CID and verified against the curated InChIKey**; a mismatch SHALL fail the run.

### Requirement 3: L2 — targets and today's drugs
#### Acceptance criteria
1. THE pipeline SHALL record, per constituent, the activities measured on protein targets that
   come from a public-domain depositor, each with its assay id, target, measure and value.
2. THE pipeline SHALL record the drugs used today for the same condition and SHALL confirm the
   condition on each drug's US label, storing the label's set id, version date and the matched
   term.
   - 3.2a WHEN the condition term is not found on any label of that drug THE drug SHALL be
     excluded and counted.
   - 3.2b THE bridge from a Canon condition to a modern indication SHALL be stated as
     interpretive wherever it is one.
3. THE pipeline SHALL report the overlap and the difference between the targets of the
   constituents and the targets of today's drugs.
4. WHEN a constituent has a measured activity on a drug-metabolism target THE pipeline SHALL
   raise an interaction flag.
   - 3.4a An interaction flag SHALL be marked `established` only WHEN the pair (compound,
     target) is curated with its own cited evidence; every other flag SHALL say it is a
     screening-panel record and not an established interaction.
   - 3.4b THE hyperforin–PXR flag behind St John's wort CYP3A4 induction SHALL be found by the
     pipeline and SHALL cite its evidence.

### Requirement 4: L3 — ADMET and the body simulation
#### Acceptance criteria
1. THE build SHALL record structure-based ADMET predictions for every constituent and
   comparator drug from an open model, with the model version, and SHALL label them predictions,
   not measurements.
2. THE simulation of plasma concentration over time SHALL use httk's PBPK model WHERE httk has
   human parameters for the drug, and Janus's compartmental model otherwise.
   - 4.2a THE compartmental model SHALL be called "minimal compartmental model with cited
     physiological parameters" in the spec, the field names, the contract and the product copy,
     and SHALL NOT be called PBPK anywhere.
   - 4.2b Every parameter of the compartmental model SHALL cite its source; a parameter that is
     an assumption SHALL say so and SHALL carry a wider spread.
3. THE simulation SHALL report an uncertainty band (5th, 50th, 95th percentile), SHALL be
   seeded, and SHALL give the same output for the same input.
4. THE virtual population SHALL be described as ages 65–79 with its source, and the build SHALL
   NOT present a simulated result for ages above 79.

### Requirement 5: Validation before trust
#### Acceptance criteria
1. THE credibility rule SHALL be fixed before the predictions are compared with observations
   and SHALL be recorded in the artifact.
2. THE build SHALL validate each simulation model against published human pharmacokinetics for
   at least two drugs, citing each observed value and its verified DOI.
3. THE build SHALL report the fold error on Cmax and on AUC for every validation drug, and SHALL
   mark the outcome `credible`, `borderline` or `failed`.
4. WHEN a drug is not `credible` THE build SHALL NOT produce an exposure-versus-potency verdict
   for it, and its card SHALL say that the model is not validated for that drug.
5. WHERE an observed AUC is derived from the same source as a model parameter THE build SHALL
   say that the AUC comparison is not independent.

### Requirement 6: FAERS time to onset
#### Acceptance criteria
1. THE pipeline SHALL derive the time to onset per (report, drug) from the therapy start date
   and the event date in the quarterly FAERS files, without changing the existing `faers`
   artifact or its contract.
2. THE pipeline SHALL use only complete dates, SHALL exclude partial dates, missing dates,
   negative intervals and implausibly long intervals, and SHALL count every exclusion by reason.
3. THE pipeline SHALL report the share of reports with a usable interval.
4. THE analysis SHALL fit a Weibull distribution and SHALL classify the hazard from the 95 %
   interval of the shape parameter, citing the method paper.
   - 6.4a WHEN fewer than 10 reports carry a usable interval THE fit SHALL be omitted with its
     reason.
   - 6.4b WHEN fewer than 30 reports carry a usable interval THE result SHALL be marked a small
     sample and SHALL still be shown with its count and interval.
5. Counts SHALL be called reports, never people, and the output SHALL state that FAERS is
   spontaneous reporting: not incidence, not deduplicated across cases.

### Requirement 7: L4 and the digital twin of the cascade
#### Acceptance criteria
1. WHEN a Canon entry states a dose THE build SHALL convert it to grams with a cited conversion
   and its spread, and SHALL propagate that spread into the constituent dose.
   - 7.1a THE conversion SHALL carry the range between sources, not a single value.
   - 7.1b WHERE no dose is stated for a substance THE build SHALL produce no exposure scenario
     for it rather than inventing one.
2. THE comparison of simulated concentration with measured potency SHALL be made on the unbound
   concentration WHERE an unbound fraction is available and on the total concentration
   otherwise, and the basis SHALL be named.
   - 7.2a THE verdict SHALL be one of "reaches", "overlaps" or "stays below" and SHALL be about
     concentrations in a model, never about an effect in a person.
   - 7.2b THE potency used SHALL be measured on a curated target relevant to the condition.
     WHEN none exists THE build SHALL record the gap and produce no verdict.
3. THE digital twin SHALL cover 3–5 documented cascades and SHALL state, per cascade, which
   method produced its exposure layer (PBPK, compartmental, or time to onset only).
4. THE twin SHALL compare its risk window with the published timing window and SHALL report
   agreement or disagreement honestly, including when they disagree.
   - 7.4a WHERE the published timing is qualitative THE comparison SHALL be reported as not
     comparable rather than forced.

### Requirement 8: Offline computation, read-only API
#### Acceptance criteria
1. Every result SHALL be computed offline into an artifact; no model and no simulation SHALL run
   while a request is served.
2. THE `/timemachine` routes SHALL be read-only, stateless and medical: GET only, `no-store`,
   and nothing logged but the access line.
3. WHEN the artifact is not installed THE routes SHALL answer 503; WHEN an id is unknown they
   SHALL answer 404; WHEN an id is invalid they SHALL answer 422 naming the field without
   echoing the value.
4. THE artifact SHALL record the run id, snapshot date, licence and tool versions of every
   source it was built from.

### Requirement 9: What a patient may see **[Client: experience]**
#### Acceptance criteria
1. THE patient-facing output of the Time Machine SHALL be limited to one cautious sentence about
   the timing window of a cascade, built from fixed codes, and SHALL never include a
   concentration, a dose, a potency or a molecular claim.
2. THE sentence SHALL say that the window comes from reports others have filed, SHALL use
   "reports" and not "people", and SHALL end by suggesting the person discuss it with their
   doctor.
3. THE sentence SHALL NOT appear WHEN the cascade's onset data is a small sample or its
   agreement with the literature is `disagrees`.
4. THE detailed curves, bands, potencies and validation tables SHALL appear only in the research
   area.
5. Every screen SHALL carry the disclaimer and "AI-reviewed, pending expert review".

### Requirement 10: Review and expert hand-over
#### Acceptance criteria
1. THE pharmacologist, statistician and historian agents SHALL each review this feature
   independently and record one labelled file each.
2. Every item an agent could not settle SHALL be added to `docs/pre-launch-checklist.md` for the
   experts.
3. No output SHALL be marked expert-reviewed by this build.

## Properties to test (PBT candidates)
- Unit conversion is linear in the amount and keeps low ≤ central ≤ high.
- The compartmental solver conserves mass, never returns a negative concentration, is linear in
  dose, and superposes repeated doses.
- Cmax and AUC from the closed form agree with numerical integration of the same curve.
- The Weibull fit recovers the shape and scale of synthetic data within the expected standard
  error, and its shape interval always contains the estimate.
- A potency value from a non-public-domain depositor never reaches the output; a pointer never
  carries a value.
- A model that failed validation never carries an exposure verdict.
- The witness of a cascade is never shown as a small sample when it has 30 reports or more, and
  always when it has fewer.
- An invalid id is never echoed back in a response.
