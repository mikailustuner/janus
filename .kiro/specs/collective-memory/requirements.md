# Requirements: Collective Memory

> **Refined 2026-11-08 for Phase 2**, after the FAERS count builder (`janus.memory.faers_build`,
> `data-pipelines` Requirement 15, DP31–DP33) was built and run on the 2025Q4–2026Q3 window.
> Every criterion of the first seed is kept; additions and changed wording are marked
> *(Added in refinement)* or *(Refined)*. Criteria tagged **[Client: experience spec]** are
> requirements on screens and are implemented there; this spec provides the data, the codes and the
> message catalogue. Decisions and measurements are in `design.md`; the statistician agent's review
> of the statistics is in `statistics-review.md`.
> **Statistics review (2026-11-08): approved with changes; all changes are applied below and marked *(Statistics review Qn)*.**
> **Phase 2 scope (`apps/api` and the message files):** the FAERS layer (Requirements 1–3, 6–11),
> the contributions layer (Requirements 4–5) and the interface for the outcomes layer. The outcomes
> data itself arrives with `doctor-loop`.

## Introduction
Show how often the same medicines and events appear together in public adverse-event **reports** (FDA FAERS from day one), plus consented Janus contributions and doctor-confirmed outcomes, with standard pharmacovigilance statistics and strong privacy. Counts are always described as reports, never as people.

## Glossary
- **2×2 table** for drug D and event E: a = reports with D and E; b = D without E; c = E without D; d = neither.
- **PRR** = (a/(a+b)) / (c/(c+d)). Signal (Evans): PRR ≥ 2, χ² ≥ 4, a ≥ 3. *(Refined: the Evans criteria with Yates-corrected χ², 1 df; Evans SJW, Waller PC, Davis S, Pharmacoepidemiol Drug Saf 2001;10(6):483-486, DOI 10.1002/pds.677, verified in Crossref 2026-11-08, no retraction or correction. The full text is paywalled, so the Yates form is cited from its use in the pharmacovigilance literature.)*
- **ROR** = (a·d)/(b·c); 95% CI = exp(ln ROR ± 1.96·√(1/a+1/b+1/c+1/d)); signal if lower bound > 1.
- **Layers:** `faers` (public), `contributions` (Janus users), `outcomes` (doctor-confirmed). Never mixed into one number.
- **Region (of a FAERS report):** one of TR, EU, US, OTHER, UNKNOWN. *(Owner decision 2026-11-08, `data-pipelines` DP16.)* It is derived from the occurrence country; when that is empty, from the reporter country; a value that is empty or `COUNTRY NOT SPECIFIED` counts as missing. `TR` is TR; `US` and the US territories PR, GU, VI, AS, MP, UM are US (as FDA treats them); the FAERS pseudo-code `EU` and the 27 EU member-state codes are EU, and EU means EU-27 only (GB, CH, NO, IS, LI are OTHER); everything else present is OTHER; missing is UNKNOWN. FAERS cannot tell EU member states apart. Each report records which field was used. `ALL` is the sum of the five regions.
- *(Added in refinement.)* **Report:** one deduplicated FAERS case report. Deduplication is by case version only (latest version of each case; cases listed in FDA's deleted-case files removed). Different case ids describing the same event are not matched, so duplicates across cases may remain (`data-pipelines` DP15).
- *(Added.)* **Mapped report:** a report with at least one drug ingredient that the `drug-resolution` name ladder mapped to an ingredient key. **Primary N** = the number of mapped reports (`reports_mapped`) in the region asked for (`data-pipelines` DP32). **Sensitivity N** = all reports (`reports_all`).
- *(Added.)* **Scope:** `suspect` (the ingredient is the primary suspect, secondary suspect or interacting drug in some drug line of the report: roles PS, SS, I) or `any` (also concomitant, role C). Under `suspect`, a report where D appears only as concomitant counts as not exposed.
- *(Added.)* **Ingredient key:** a Wikidata item id (`Q…`) or a Janus key (`J<n>`, `data/janus_ingredients.csv`), the same key `drug-resolution` returns.
- *(Added.)* **Event (FAERS):** a MedDRA Preferred Term (PT) string as published in FAERS. **Janus event key:** a key of the Janus event vocabulary (Requirement 6) naming one or more PTs; a report has the event when it has any of them.
- *(Added.)* **Pair:** one ingredient with one event. **Combination:** two or more ingredients; a report belongs to it when it names all of them (in the chosen scope). **Pairwise:** every two-ingredient subset of a combination.
- *(Added.)* **Display threshold:** the smallest report count that is shown as a result instead of "insufficient data": `MIN_REPORTS` = 3 (the same number as the minimum a of the Evans criteria; confirmed in the statistics review).
- *(Added.)* **Snapshot:** the FAERS window (four quarters), its posting date, and the counts build id.
- *(Added.)* **Data version (user layers):** an identifier that changes whenever the donations or outcomes behind an aggregate change (`privacy` Glossary).
- *(Added.)* **Hidden cell:** a user-layer cell whose true contributor count is below k = 20. A hidden cell is reported as hidden, never as zero.

## Requirements

### Requirement 1: Statistics
#### Acceptance criteria
1. WHEN asked for (D, E) THE system SHALL return a, b, c, d, PRR, ROR with 95% CI, χ², the snapshot date and the layer.
   - *(Added.)* THE result SHALL also state the region, the scope, the primary N, the build id and that N counts mapped reports only.
   - *(Added.)* THE cells SHALL be computed from the count tables as `data-pipelines` Requirement 15.5 defines them: a = pair count; b = ingredient count − a; c = event count over mapped reports − a; d = N − ingredient count − event count + a, all in the asked region, with the ingredient and pair counts in the asked scope.
   - *(Added.)* IF any cell is negative, or a exceeds the ingredient or event count, THEN THE system SHALL fail with an internal error that names no medicine or event; it SHALL NOT clamp or repair counts.
2. WHEN any cell is zero THE system SHALL apply the Haldane correction (+0.5) and mark the result as corrected.
   - *(Added.)* THE correction SHALL add 0.5 to all four cells, and PRR, ROR and the interval SHALL be computed from the corrected cells. χ² SHALL be computed from the uncorrected table. The result field is `haldane_applied` (it is not called "corrected", so it is not confused with the continuity correction of χ², Requirement 1.6). WHEN it is set THE result SHALL carry the notice `estimate_uses_continuity_correction`. *(Statistics review Q2.)*
   - *(Added.)* IF a margin of the raw table (a+b, c+d, a+c, b+d) is zero THEN χ² SHALL be 0.0 (no division); the function is total.
   - *(Added.)* WHEN a = 0 THE system SHALL return the four counts and `no_reports`, and SHALL NOT return PRR, ROR or an interval. *(Statistics review.)*
3. WHEN a < 3 THE system SHALL label the result "insufficient data" and SHALL NOT call it a signal.
   - *(Added; owner-approved evidence rule, Requirement 10.3.)* FOR a < 3 THE API SHALL return the four cells (so the report count) and the assessment, and SHALL NOT return PRR, ROR, an interval or χ²; no sentence states a number derived from such a cell.
   - *(Added.)* THE threshold SHALL apply to every cell separately, so a regional cell with fewer than 3 reports is "insufficient data" even when the pooled cell is not.
4. *(Refined.)* THE system SHALL state on every FAERS result that it is spontaneous reporting, not incidence, and that reports are deduplicated by case version only, so the same event can still appear under different cases.
   - The first seed said "not deduplicated". The builder does remove superseded case versions and deleted cases (`data-pipelines` DP15), so the statement is made exact and keeps the limit: duplicates across different cases may remain. The medical-safety rule 6 wording "not deduplicated" is met by "not deduplicated across cases".
   - Canonical sentence (statistics review Q11b): "Reports are sent voluntarily and are not checked. The counts do not show how often an event happens. Only repeated versions of the same case are merged, so one event can still appear in more than one case."
5. All user-facing text SHALL describe counts as "reports" (e.g. "2,300 reports"), never as "people" or "people like you".
   - *(Added.)* THE same SHALL hold for API field names (`reports`, never `people`, `patients` or `persons`) and in all five languages (Requirement 8).
6. *(Added.)* THE system SHALL compute the 95% interval of the ROR as exp(ln ROR ± 1.96·√(1/a+1/b+1/c+1/d)) on the (possibly corrected) cells and SHALL return one `assessment` from a closed set: `insufficient_data` (a < 3), `no_reports` (a = 0), `not_disproportionate`, `weak`, `disproportionate`. The Evans-type criteria (PRR ≥ 2, χ² ≥ 4, a ≥ 3) and "ROR lower bound > 1 with a ≥ 3" SHALL be returned as separate booleans `evans_met` and `ror_signal` (each false when a < 3). *(Statistics review Q3, Q5.)*
   - χ² SHALL be Pearson's χ² with Yates' continuity correction on the raw table, and the result SHALL say so (`chi2_form: "yates"`). The first seed's "χ² ≥ 4" is kept as the threshold. In copy the criteria are called "Evans criteria (Yates-corrected χ²)" and the note says the Yates form is cited from secondary use (owner decision 2026-11-08).
   - THE rule SHALL be: `a = 0` → `no_reports`; `0 < a < 3` → `insufficient_data`; otherwise `disproportionate` when both criteria are met and a ≥ 5 (`WEAK_BELOW`), `weak` when at least one criterion is met but not both with a ≥ 5, else `not_disproportionate`. WHEN the class is `weak` THE result SHALL carry the sentence "Few reports; treat as a weak pattern."
   - THE result SHALL carry `interval_method: "woolf_log"` and `interval_level: 0.95`. WHEN a < 5 or `haldane_applied` THE result SHALL carry the notice `interval_approximate`.
   - THE decisions PRR ≥ 2 and χ² ≥ 4 SHALL be made with integer arithmetic (exact), not floats.
   - THE system SHALL NOT return an assessment, PRR or ROR without its interval, its report count a and its primary N.
7. *(Added.)* THE system SHALL return a sensitivity table with N = all reports (`reports_all`, event counts over all reports) beside every result, SHALL state which figure is primary, and SHALL set `denominator_sensitive` when the five-class assessment differs between the two (same region and scope; `data-pipelines` DP32). The sensitivity part SHALL carry the full cells, PRR, ROR with interval, χ² and assessment, validated like the primary cells. *(Statistics review Q1.)*
   - THE result SHALL state that "other reports" in the comparison include reports where the medicine is only concomitant (scope `suspect`), and that unrecognised spellings of the medicine put some of its reports into the comparison group, which hides patterns more often than it creates them; a `not_disproportionate` answer is the least reliable answer. *(Statistics review Q1; measured: in every scenario of a leak the assessment moved toward `disproportionate`.)*
8. *(Added.)* THE system SHALL state in every result that these criteria are a screening statistic and that most examined pairs meet them, so meeting them is common and is not evidence that the medicine causes the event (the exact sentence of `design.md` §8.1, the single exception of Requirement 8.4). Lists of events SHALL be ordered by report count and SHALL NOT be ordered or cut by PRR, ROR or assessment. *(Statistics review Q6. No formal multiple-comparison correction and no 99% level: 65% of examined pairs reject the null, so it is not calibrated. Owner decision 2026-11-08: the sentence ends "not evidence that the medicine causes the event" and is the only allow-listed exception to Requirement 8.4.)*
   - **[Client: experience spec]** In event lists the client SHALL show the report count and the interval first and SHALL NOT use a badge, colour or icon for `disproportionate`; the label belongs to the detail view with the screening sentence.
9. *(Added.)* THE statistics SHALL be pure functions (no I/O) over four integer counts and the thresholds; floats are IEEE double and are not rounded by the server (formatting by locale is the client's job).

### Requirement 2: Combination view
**User story:** As a caregiver, I want to see how often these same medicines appear together in reports so that I know this pattern has been seen before.

#### Acceptance criteria
1. WHEN given a set of ingredients THE system SHALL return the count of FAERS reports containing all of them and the top reported events with their statistics.
   - *(Added.)* THE set SHALL have 2 to 20 distinct ingredient keys; THE default scope SHALL be `any` (a combination often includes a concomitant medicine); the caller MAY ask for `suspect`, which then applies to every ingredient of the set.
   - *(Added.)* A report SHALL count once however many drug lines name its ingredients. THE top events SHALL be at most 50 (default 20), ordered by reports descending, then by PT ascending, and SHALL each carry the statistics of Requirement 1 for the combination as the exposure.
2. WHEN the combination count is below the display threshold THE system SHALL fall back to pairwise results and say so.
   - *(Added.)* THE fallback SHALL be a ladder, in this order: the combination; every two-ingredient subset whose count reaches the display threshold; each single ingredient. THE response SHALL name the `level` it shows and, for each skipped level, a reason code `below_display_threshold`.
   - *(Added.)* FOR a two-ingredient set whose count is below the threshold THE fallback SHALL be the two single ingredients.
3. *(Added.)* THE view SHALL say that the medicines were reported together, and SHALL NOT say or imply that they interact, that the combination causes an event, or that the combination is unusual or safe.
   - *(Statistics review Q8.)* THE response SHALL state `exposure: "all_of_set"` and `comparison: "all_other_mapped_reports"`, SHALL give for each top event also the report count of each member medicine alone (same scope and region), and SHALL carry the caveat that the comparison group includes reports naming only some of the medicines, so a pattern may come from one of them and does not show an effect of taking them together. WHEN the shown level is a fallback the statistics SHALL refer to that level and the response SHALL say which.
   - THE response SHALL say that counts of a set are lower bounds of the reports that name them, because a report counts only if every ingredient was recognised.
4. *(Added.)* IF an ingredient has no reports at all in the window THEN THE response SHALL list it as `no_reports` and the combination count SHALL be 0.

### Requirement 3: Regional view
#### Acceptance criteria
1. *(Refined.)* WHERE the occurrence country or, failing that, the reporter country is present THE system SHALL let the user filter FAERS results by region (TR, EU, US, OTHER) and SHALL show how many reports have no country (UNKNOWN), as a count and as a share of all reports. *(The first seed said "reporter country" and "reporter region"; the owner rule of 2026-11-08, `data-pipelines` DP16, is occurrence country first.)*
   - *(Added; safety review S8.)* FOR TR the response SHALL carry the notice `tr_reports_small_self_selected` ("Reports from Türkiye are few and are sent by choice. They do not show how medicines are used in Türkiye."), on `pair` and `combination` with region TR and always on `regions`.
   - *(Added.)* THE system SHALL also show how many reports got their region from the reporter country because the occurrence country was empty.
2. THE system SHALL link to EudraVigilance public reports (adrreports.eu) for EU users and SHALL NOT ingest EudraVigilance data.
   - *(Added.)* THE link SHALL be a fixed address of the public site, carrying no medicine, event or user value. **Owner decision 2026-11-08:** the address is `https://www.adrreports.eu`; the pre-launch checklist re-checks that it still works.
3. *(Added.)* THE regional breakdown SHALL return TR, EU, US, OTHER, UNKNOWN and ALL, each with its own N and its own 2×2 table (without an event: the report counts only, and the notice `absence_is_not_reassurance` whenever a region shows 0 reports; safety review S6); counts of the five regions SHALL add up to ALL.
4. *(Added.)* THE system SHALL state that a report's region is the country where the event is said to have happened or, when that is missing, where the reporter is, and does not tell where the patient lives or where the medicine was bought; that EU is 27 states pooled and FAERS cannot tell member states apart; that the regions' numbers are not comparable as rates, because reporting habits differ; that a different label in two regions can come from different numbers of reports, not a different pattern; and that each region is compared only with the other reports from the same region. FOR TR it SHALL add that the reports are a small, self-selected set and no picture of medicine use in Türkiye. *(Statistics review Q7, Q11c.)*
5. *(Added.)* WHEN a region filter is chosen THE system SHALL use that region's N, ingredient counts and event counts for every cell; it SHALL NOT subtract regional counts from pooled figures.

### Requirement 4: Contributions and outcomes
#### Acceptance criteria
1. WHEN a user donates with explicit consent THE system SHALL store only the fields allowed by the privacy spec and return a deletion token.
   - *(Added.)* Implemented by the `privacy` spec (Requirement 3). This spec adds the event vocabulary donations use (Requirement 6) and the read side below.
2. Doctor-confirmed outcomes SHALL be reported separately from patient reports.
3. *(Added.)* THE `contributions` and `outcomes` layers SHALL be returned as separate objects. THE system SHALL NOT output any number computed from more than one layer (no sum, share, ratio or "total across layers"), and no sentence SHALL compare a number of one layer with a number of another.
4. *(Added.)* THE user layers SHALL show counts only. THE system SHALL NOT compute PRR, ROR, χ² or any rate from them, because donations and outcomes have no comparison group.
5. *(Added.)* A user-layer cell SHALL be (ingredient set, Janus event key, direction, region) with region TR, EU or US. Its true contributor count is the number of stored donations (or outcomes) that name all the ingredients of the set, the event and the direction in that region. A donation is a donation, not a person (`privacy` DP13).
6. *(Added.)* THE system SHALL read user layers from the live stores in one read-only transaction, so a deleted donation is absent from the next response (`privacy` Requirement 3.3).
7. *(Added.)* THE `outcomes` layer SHALL be defined as an interface (a source of cells with true contributor counts) and SHALL answer `not_available` until `doctor-loop` provides the outcome store. THE answer SHALL NOT be an empty or zero count.
   - *(Closed 2026-11-08 by `doctor-loop` task 12.)* `OutcomesSource` (`janus/notes/source.py`) is registered: a cell counts doctor-reported outcomes with assessment `confirmed` whose ingredient pair contains the set; release is the same `release_table`, k = 20, noise and sibling rule; `GET /memory/snapshot` reports `outcomes: ok | unavailable`.
8. *(Added.)* Demo data SHALL never reach the user layers (`experience` Requirement 4.3); the API has no way to mark a read as demo, so this holds because the client sends no donations in demo mode and the donation endpoints reject `"demo": true`.

### Requirement 5: Privacy of aggregates
#### Acceptance criteria
1. THE system SHALL NOT display any aggregate from `contributions` or `outcomes` for a group smaller than k = 20.
   - *(Added.)* THE system SHALL use the shared `release_table` (`privacy` Requirement 4): suppression is decided on the true contributor count before any noise; totals are sums of released values only; k comes from configuration and cannot be below 20.
2. THE system SHALL add Laplace noise (configured ε) to counts from `contributions` and `outcomes`, clamp at zero and round to integers.
   - *(Added.)* ε is the configured value (default 1), the noise is the exact discrete Laplace of scale 1/ε, the result is a non-negative integer, and the same cell for the same data version returns the same value.
3. FAERS counts SHALL be shown without noise.
4. *(Added.)* A hidden cell SHALL look the same whether its true count is 0 or 19: the response says `hidden` and carries no value, no count bound and no hint of the true count.
5. *(Added.)* IF the noise key is not configured THEN THE system SHALL answer the user layers with `layer_unavailable` and SHALL NOT release a count without noise.
6. *(Added.)* THE system SHALL describe the protection as "hidden under 20, noise added" and SHALL NOT claim formal differential privacy for the release as a whole (`privacy` DP14).
7. *(Added.)* THE system SHALL NOT log ingredients, events, regions, counts or the data version of a user-layer request; the access log carries request id, route template, status and latency only (`privacy` Requirement 2).
8. *(Added; statistics review Q9.)* **Sibling rule.** Before `release_table`, THE system SHALL set the count of a cell S (n = donations naming all of S, the event, direction, region) to 0, so it is hidden, unless n ≥ k and, for every ingredient X not in S, the donations of S that also name X number m_X with n − m_X = 0 or n − m_X ≥ k. Hence for any two released cells S ⊂ T of the same event, direction and region, n_S − n_T is 0 or at least 20, and subtracting nested cells never reveals a group smaller than 20 to within the noise. An ineligible cell SHALL be answered exactly like a hidden one.
9. *(Added.)* THE privacy page text SHALL state the residual limits: two-step differencing (A) − (A,B) − (A,C) + (A,B,C) is not covered; and until rate limiting exists (Phase 5, `privacy` Requirement 3.7) someone who can add donations can pad a cell and re-draw its noise. The protection holds against ordinary readers, not against someone who can add donations. **[Client: experience spec]**
10. *(Added.)* THE counted thing in these layers is "donated reports" (k counts donations, `privacy` DP13), never "people". `privacy` Requirement 4.1 says "fewer than k = 20 people"; the wording of this spec follows DP13.

### Requirement 6: Event terms and the Janus event vocabulary *(Added in refinement)*
**User story:** As a caregiver, I want the side effect a finding names to be looked up in the reports, and as a donor I want to choose from the same list of side effects.

#### Acceptance criteria
1. THE system SHALL show FAERS events only as MedDRA Preferred Term strings as published in FAERS. It SHALL NOT store, ship or show any MedDRA hierarchy (SOC, HLT, LLT) (`data-pipelines` DP33).
   - Wherever a PT is shown THE notice "MedDRA® trademark is registered by IFPMA on behalf of ICH." SHALL accompany it; NOTICE and exports carry the long form "MedDRA® the Medical Dictionary for Regulatory Activities terminology is the international medical terminology developed under the auspices of ICH. MedDRA® trademark is registered by IFPMA on behalf of ICH." *(owner decision 2026-11-08; the MSSO terms check stays on the pre-launch list)*. **[Client: experience spec]** (the API carries the short notice in every response that has a PT).
   - THE term drift between quarters is not corrected (`data-pipelines` DP20); a PT is matched as an exact string after Unicode NFC normalisation.
2. THE system SHALL provide the Janus event vocabulary as a curated file `apps/api/janus/memory/memory_events.csv`: a key (`^[a-z0-9][a-z0-9_.-]{0,39}$`), a label in each of en, tr, de, fr, es, a direction (`adverse` or `benefit`), and for `adverse` keys the list of PTs it covers. `benefit` keys cover no PT, so the FAERS layer answers `not_available` for them.
   - THE adverse keys SHALL be derived from the adverse events of the 65 PIPC rows (41 phrasings in `data/pipc.csv`); THE benefit keys SHALL be the improvement terms.
   - A key SHALL keep its meaning once released; removal is a deprecation flag, never a deletion, because stored donations hold keys.
   - THE vocabulary replaces `contributions/placeholder_events.txt`; the placeholder's keys SHALL stay valid.
3. THE PT lists are clinical judgement. THEY SHALL be proposed in a review file, reviewed by the owner (with the pharmacologist agent's check), and the status line "reviewed by the project owner with AI assistance; needs review by a pharmacist or physician before any public claim" SHALL be kept (same rule as the cascade mapping).
4. WHEN an event is given as a Janus key THE system SHALL count a report as having the event when it has any of the key's PTs, once per report.
5. EVERY PT in the vocabulary SHALL exist in the PT list of the current counts file; the build report SHALL list the ones that do not. A PT that is absent is reported, not dropped silently.
6. THE vocabulary file SHALL be validated at load: unique keys, regex, five labels, no empty PT list for `adverse`, no PT in two keys of the same PIPC row group when that would change a union, direction in the set.

### Requirement 7: API contracts *(Added in refinement)*
**User story:** As the `experience` and `medication-passport` specs, I need stable endpoints with response contracts for a pair, a combination and a regional breakdown.

#### Acceptance criteria
1. THE API SHALL offer these routes (contracts in `design.md` §5):
   - `POST /memory/pair`: one ingredient, one event (a PT or a Janus key), a region (default `ALL`), a scope (default `suspect`).
   - `POST /memory/combination`: 2 to 20 ingredients, a region, a scope (default `any`), a limit for top events.
   - `POST /memory/regions`: 1 to 20 ingredients and an optional event; the breakdown of Requirement 3.3.
   - `POST /memory/shared`: the user layers (Requirement 4–5): layer, ingredients, Janus event key, direction.
   - `GET /memory/snapshot`: operational; snapshot facts and notices (no medicine or event data).
2. EVERY route except `/memory/snapshot` SHALL be a medical route: JSON body only, at most 64 KiB, `Cache-Control: no-store`, no medicine, event or region value in the URL or a query string, read-only access, and no logging of the body (`privacy` Requirement 2). Hence the lookups are `POST`.
3. THE API SHALL validate input at the boundary and reject, with 422, an unknown field, an ingredient key outside `^(Q[1-9][0-9]{0,9}|J[1-9][0-9]{0,5})$`, duplicate ingredients, more than 20, an unknown region, scope, layer or direction, a PT longer than 200 characters, and a request with both or neither of `pt` and `key`.
4. THE same request against the same build SHALL give a byte-identical response.
5. EVERY FAERS response SHALL carry: `snapshot` {build id, snapshot date, window, FAERS run id, resolution dataset version, whether it equals the served resolution dataset, stale flag}, `notices` (codes from a closed set), the one-line disclaimer of medical-safety rule 9, `meddra_notice` when a PT appears, and `citation` {evidence id `dataset:faers`, locator}.
6. IF the counts file is missing, unreadable or fails its metadata check THEN THE FAERS routes SHALL answer 503 `memory_unavailable` with no numbers (fail closed); THE `shared` route SHALL be independent of the counts file.
7. WHEN the counts were built against a resolution dataset other than the one now served THE API SHALL still answer, with the notice `counts_built_against_other_dataset`: ingredient keys are Wikidata items or Janus keys, which do not change with the dataset. *(Resolves the open item "Staleness"; DP7.)*
8. WHEN the snapshot is older than twice the FAERS cadence (2 × 91 days; the freshness rule of `evidence-integrity`) THE API SHALL answer with `stale = true` and the notice `source_may_be_outdated`.
9. THE routes SHALL be classified by the route-kind check (`/memory/snapshot` is added to the operational allowlist with a test), and the access log SHALL contain route template, status, latency and request id only.
10. THE routes SHALL open the counts file read-only and SHALL NOT write to disk, spill to a temporary directory or cache a result (`privacy` Requirement 2.1).

### Requirement 8: Language and safety of every string *(Added in refinement)*
#### Acceptance criteria
1. THE API SHALL return codes, numbers and the English canonical sentence for each code; THE client renders the words. THE message catalogue (namespace `Memory`) SHALL exist in en, tr, de, fr and es in `apps/web/messages/`, with every code of the closed set present in every language and no empty value (`experience` Requirement 2 property).
2. NO user-facing string of this spec, in any of the five languages, in API sentences, message files, LLM prompts or templates, SHALL contain a forbidden phrase of `medical-safety.md` rule 2. The existing guard (`src/i18n/forbidden-phrases.ts`, `source-scan.test.ts`) SHALL cover the new files.
3. NO string of this spec SHALL name the counted thing as people: the words for people, persons and patients are forbidden in the `Memory` namespace and in API sentences, in each of the five languages (list in `design.md` §7). The counted thing is "reports", "donated reports" or "doctor-confirmed outcomes".
4. NO string SHALL say or imply causation, incidence, probability, risk to the reader, safety, or that something is "normal" or "unusual"; the words for these are forbidden in the `Memory` namespace (list in `design.md` §7). The allowed pattern is: "reported together", "reported more often than in the other reports", "worth discussing with your doctor".
   - *(Owner decision 2026-11-08.)* ONE exception: the screening sentence of Requirement 1.8, in the exact wording of `design.md` §8.1 in each of the five languages, as the complete value of the single message `Memory.screening` and as the English canonical sentence of the code `screening_statistic`. A test SHALL show that only that exact string passes: the same sentence with any change, inside a longer string, or under another key fails the causal-word check.
5. NO string SHALL recommend starting, stopping or changing a medicine. WHEN a result is shown next to a medicine of an abrupt-stop class the screen carries "Do not stop this medicine suddenly" **[Client: experience spec]**; this spec's strings never add advice.
6. EVERY screen and note that shows a FAERS result SHALL carry the one-line disclaimer (rule 9), the FAERS limits sentence (Requirement 1.4), the snapshot date and window sentence (Requirement 10.2), and the source attribution ("Source: FDA AEMS, formerly FAERS. Not an FDA endorsement.").
7. WHEN nothing is found (no pattern, `no_reports`, `insufficient_data`) THE sentence SHALL follow rule 3: it SHALL NOT reassure ("no reports" does not mean "no problem"), and SHALL say that absence of reports in this window does not mean absence of an association.
8. EVERY sentence that states a statistic SHALL name its evidence id; a sentence whose id is not citable (`cite` removes it) SHALL be dropped (medical-safety rule 5).
9. THE emergency notice ("Call emergency services", 112 / 911) comes first on any screen that lists events such as chest pain or breathing difficulty **[Client: experience spec]**.

### Requirement 9: Performance *(Added in refinement)*
**Basis:** measured 2026-11-08 on the dev machine (AMD Ryzen 5 1500X, 4 cores / 8 threads, 15 GiB, SSD) with the real counts file (`faers_pair_counts` 6,195,095 rows, file 121 MB), DuckDB read-only, warm cache. Details in `design.md` §1.

#### Acceptance criteria
1. A pair lookup (totals, ingredient, event and pair counts for one region and scope, plus the statistics) SHALL take at most **10 ms at the 95th percentile** inside the process (database part) and at most **25 ms at the 95th percentile** through the HTTP route in-process (ASGI client), single client, warm file. *(Measured: 14 ms as built; 6.7 ms with the physical sort of Requirement 11; route 11.7 ms.)*
2. A regional breakdown for a pair SHALL take at most 15 ms (database) and 40 ms (route) at p95.
3. A pair with a Janus event key (union of PTs, report-level) SHALL take at most 100 ms at p95 for a key with up to 6 PTs. *(Measured worst case: 74 ms with 6 of the commonest PTs and the largest ingredient.)*
4. A combination request with up to 20 ingredients, including the top events and the pairwise fallback, SHALL take at most 250 ms at p95. *(Measured on the 20 largest ingredients, the worst case: 196 ms p95 after filtering first and listing events for the 5 pairs with the most reports; 1.06 s before. A pair that is not among them is returned with its count and `events_omitted`.)*
5. The file open and first query after process start SHALL take at most 100 ms (measured 26 ms + 15 ms).
6. A request SHALL use a bounded number of database statements (pair at most 6, regions at most 8, combination at most 12 + the number of pairs examined in one statement), so no request scans per ingredient or per event in a loop.
7. THE benchmark SHALL be a script that runs against the real counts file, prints the percentiles, and is skipped when no file exists; its results are recorded in the checkpoint notes. CI does not assert latency (shared runners); CI asserts the statement counts (6) and the stateless property.
8. 8 concurrent clients SHALL give no error and a p95 at most 5 times the single-client target.

### Requirement 10: Snapshot, freshness and evidence *(Added in refinement)*
#### Acceptance criteria
1. EVERY FAERS result SHALL carry its snapshot (Requirement 7.5) and every number SHALL state its source and snapshot date (statistician agent rule).
2. THE system SHALL state the window as "reports received or updated in the four quarters <first>–<last>, including follow-up versions of cases first received earlier", wherever dates are shown (`data-pipelines` §10).
3. *(Owner decision 2026-11-08, DP12.)* THE system SHALL NOT create evidence records per statistic. The FAERS snapshot has one dataset-level evidence record, `dataset:faers` (written by the evidence-integrity loader from the `faers` artifact, with source URL, licence and snapshot date). A statistic cites it with a **deterministic locator** naming the ingredient, the event, the region and the scope: `faers:ingredient=<key>;event=<janus key or pt:<percent-encoded PT>>;region=<ALL|TR|EU|US|OTHER|UNKNOWN>;scope=<suspect|any>`.
   - THE locator SHALL be built by one pure function, SHALL parse back to its parts (round trip), and SHALL depend on no run id, date or build id.
   - THE sentences of Requirement 8.8 SHALL cite `dataset:faers` plus the locator; the id passes the same `cite` filter as rules and papers (`cascade-engine` Requirement 2.7, Phase 2).
   - A sentence that states a number from a cell with fewer than 3 reports SHALL NOT be produced: that cell is shown as `insufficient_data` or `no_reports` (Requirement 1.3), and these coverage sentences (including the nothing-found sentence of Requirement 8.7) cite `dataset:faers` without a number.
   - No per-pair record and no loader that writes records SHALL exist. The kind `faers_stat` of `evidence-integrity` stays valid and unused.
4. THE `cascade-engine` SHALL add `dataset:faers` and the locator `faers:ingredient=<index key>;event=<janus key>;region=ALL;scope=suspect` to a finding whose rule has a Janus event key, through the same `cite` call (so a snapshot that is not registered drops both). The change SHALL be minimal: one optional field on the finding and one optional mapping on the rule base; no change to evidence-integrity code.
5. THE API SHALL return, with every FAERS statistic and every count, `citation: {evidence_id: "dataset:faers", locator}`; the route does not write. A figure nested in an object that has its own citation (for example `members_alone` inside an event row) inherits it. *(Safety review S7.)*
6. THE system SHALL NOT ingest EudraVigilance, and SHALL NOT use any data other than the FAERS counts file and the consented layers.

### Requirement 11: Changes to the count file *(Added in refinement; `data-pipelines` Requirement 15 is the builder's spec)*
#### Acceptance criteria
1. THE builder SHALL write the count tables physically sorted by their lookup keys (`faers_pair_counts` by ingredient key, PT, scope, region; `faers_ingredient_counts` by ingredient key, scope, region; `faers_event_counts` by PT, region; `faers_report_ingredient` by ingredient key, report id; `faers_report_event` by report id, PT), so a point lookup reads few row groups.
2. THE physical order SHALL NOT change any table hash (hashes are computed on rows in sorted order); the hashes of unchanged tables SHALL equal those of the first build (only `faers_report` changes, by its new column), and a rebuild from the same artifact SHALL give the same hashes.
3. THE builder SHALL also write the share of reports by region and region basis (`faers_region_basis`: region, basis, reports), for Requirement 3.1.
4. THE builder SHALL record in the metadata the schema version `faers_counts-2` for these changes, and the reader SHALL refuse a file with another schema version (fail closed, Requirement 7.6).

## Properties to test (PBT candidates)
- PRR and ROR are always positive and finite after correction; ROR's CI lower bound ≤ ROR ≤ upper bound.
- Swapping the roles of "exposed" and "unexposed" inverts ROR (ROR' = 1/ROR) for tables without zero cells. *(Refined, statistics review Q12: this is the row swap a↔c, b↔d, and the interval bounds swap and invert; the transposition b↔c leaves ROR, its interval and χ² unchanged.)*
- Scaling all four (non-zero) cells by the same factor k > 1 leaves PRR and ROR unchanged and narrows the ROR CI.
- Regional counts sum to the total (TR + EU + US + other + unknown = all).
- No output from user layers ever represents a group with fewer than 20 people. *(Read as "donated reports", `privacy` DP13: k counts donations.)*
- Noised counts are never negative and never non-integer.
- The result for (D, E) does not depend on the order in which reports were loaded.
- No rendered sentence uses "people" for a FAERS count.
- *(Added in refinement.)*
  - Transposition (b↔c) leaves ROR, its interval and χ² unchanged; scaling by k > 1 multiplies Pearson χ² by exactly k and raises Yates χ² by at least k; PRR, ROR and the ROR lower bound and the assessment class do not decrease with a (b, c, d ≥ 1 fixed). (Req 1.6)
  - The PRR ≥ 2 and χ² ≥ 4 decisions equal the exact integer inequalities for counts up to 1.6 million; PRR and ROR agree with a `Fraction`/50-digit reference to relative 1e-12; no NaN or infinity for any valid table, including zero cells and a zero margin. (Req 1.2, 1.6)
  - `haldane_applied` is true exactly when a raw cell is zero; with a = 0 no estimate field exists; the booleans re-evaluated from the serialised numbers equal the returned booleans. (Req 1.2, 1.6)
  - Sibling rule: any two released user-layer cells S ⊂ T (same event, direction, region) have n_S − n_T = 0 or ≥ 20; an ineligible cell is answered exactly like a hidden one. (Req 5.8)
  - Combination: the member-alone count of an event is never below the combination count for that event (same scope and region). (Req 2.3)
  - The cells computed from the count tables equal a direct recount from the report facts; a ≤ min(drug, event), b, c, d ≥ 0 and a+b+c+d = primary N. (Req 1.1)
  - A result is `insufficient_data` exactly when 0 < a < 3, and `no_reports` exactly when a = 0, in every region; the Haldane flag is set exactly when a cell of the raw table is zero. (Req 1.2, 1.3)
  - χ² is computed from the raw table and is the same with and without correction; correction changes PRR, ROR and the interval only. (Req 1.2)
  - The assessment equals a direct evaluation of the criteria on the cells; it never says `disproportionate` or `weak` with a < 3. (Req 1.6)
  - Sensitivity: with no unmapped-only reports (reports_all = reports_mapped) the sensitivity table equals the primary; adding reports that have no mapped ingredient never changes a, b, and changes c, d as the formulas say. (Req 1.7)
  - A list of events is ordered by reports descending, then PT, whatever the assessments. (Req 1.8, 2.1)
  - The combination count equals the number of reports naming all ingredients; adding an ingredient to the set never raises the count; the single-ingredient combination equals the precomputed pair (differential test SQL vs tables). (Req 2.1)
  - The fallback ladder returns the highest level whose count reaches the threshold; a level is shown only if its count reaches the threshold; the response names the level. (Req 2.2)
  - Combination results do not depend on the order of the ingredients in the request or on duplicate drug lines in a report. (Req 2.1)
  - Regional cells add up to ALL for a, the ingredient count, the event count and N; filtering by a region uses only that region's counts. (Req 3.3, 3.5)
  - The share of UNKNOWN plus the other regions is 1; the reporter-fallback count never exceeds the report count of its region. (Req 3.1)
  - A Janus event key's count equals the number of reports with any of its PTs; a key with one PT equals the PT result. (Req 6.4)
  - No output combines numbers of two layers; the response of a request has no field equal to a sum over layers. (Req 4.3)
  - User-layer cells: a hidden cell looks identical for true counts 0 to 19; changing a suppressed cell does not change any released value or total; released values are non-negative integers; the same cell and data version give the same value; the data version changes after a deletion. (Req 5.1, 5.2, 5.4)
  - Without a noise key, the user layers answer `layer_unavailable` and no count is released. (Req 5.5)
  - The user-layer routes write nothing and log no ingredient, event, region or count. (Req 5.7, 7.2)
  - The same request against the same build gives a byte-identical response; request ingredient order does not change the response. (Req 7.4)
  - Invalid input of every kind (unknown field, bad key, duplicate, too many, both/neither `pt` and `key`) gets 422 and no database statement runs. (Req 7.3)
  - A missing or tampered counts file gives 503 and no numbers. (Req 7.6)
  - Every code of the closed set has a non-empty message in all five languages; no message contains a forbidden phrase, a word for people/patients, or a causal, probability or reassurance word. (Req 8)
  - Every sentence that states a statistic carries an evidence id; a statistic with a < 3 has no evidence id. (Req 8.8, 10.3)
  - The evidence-record loader is idempotent and deterministic; ids do not depend on run ids or dates; every record has basis `dataset:faers`. (Req 10.3, 10.4)
  - The vocabulary loader accepts a valid file and rejects each defect (duplicate key, bad key, missing label, empty PT list for an adverse key, unknown direction). (Req 6.6)
  - A request uses at most the stated number of database statements. (Req 9.6)
  - The builder's sorted layout gives the same table hashes as the unsorted layout. (Req 11.2)

## Resolved open items *(from the first seed's two sections, 2026-11-07 and 2026-11-08)*
- **FAERS statistics in findings** (cascade-engine Req 2.7): Requirement 10.3 and `design.md` §6.
- **Region:** Requirement 3.1 and the glossary (DP16 of `data-pipelines`). The UNKNOWN share is shown (3.1).
- **Denominator:** Requirement 1.1 and 1.7 (DP32 of `data-pipelines`); the statistician agent's verdict is in `statistics-review.md` and summarised in `design.md` §8 (DP2).
- **Window:** Requirement 10.2.
- **Exposure scope:** `suspect` for the pair view, `any` for the combination view (Requirements 1.1, 2.1; DP4).
- **Staleness** (counts built against another resolution dataset): Requirement 7.7 (DP7).
- **MedDRA:** Requirement 6.1 (DP33 of `data-pipelines`).
- **`mapping_gap_possible` (2026-11-08):** not added. The optional `faers_mapping_gap` table is not built (`drug-resolution` DP36, `data-pipelines` DP34): after the Phase 2 name rules the measured leak is 0.30 % of occurrences (163 ingredient keys; 2.48 % with the Phase 1 ladder, same scan), and the limit stays in the `denominator_mapped_reports` message and the unmapped list. Reopened only if the owner rejects the biologic-suffix or acid-form rules; then the response would carry `mapping_gap_possible` per ingredient from that table. The counts file was rebuilt with the Phase 2 ladder on 2026-11-08 (`drug-resolution` task 25: reports with a mapped ingredient 1,252,900 → 1,281,744); responses keep working across the rebuild (Requirement 7.7).
