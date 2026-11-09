# Requirements: Simulation service (research tools, Phase 2)

> Owner decisions 2026-11-09:
> 1. On-demand model runs are allowed with **2 concurrent jobs**, a **queue of at most 10**, **rate limits** and
>    strong security and abuse prevention.
> 2. **No individualised simulation.** No body weight, age, sex, kidney or liver function or any other
>    person-specific input: the user picks a predefined virtual population ("typical adult", "typical adult
>    ≥ 65") defined from cited physiology or HTTK-Pop; dose, interval and number of doses may be set within hard
>    bounds; every result is a distribution over the virtual population (median and interval band), never one
>    person's value. The simulation screens do not link to or read the medicine list, findings or any patient
>    screen. Every result carries: "Virtual population, for research. Not about any person and not a dose
>    recommendation." The browser explorer follows the same rule. Rationale: software that computes doses for an
>    individual patient is a medical device (EU MDR Annex VIII Rule 11; FDA CDS guidance) regardless of
>    disclaimers, and medical-safety.md forbids dose advice.
> 3. Resource budget: deploy Req 7.4 amended (`.kiro/specs/deploy/requirements.md`): long-running services
>    together ≤ 4.5 CPU and ≤ 6 GB (caps are ceilings, not reservations, on a 4-core host); the simulator ≤ 2.0
>    CPU and ≤ 1.5 GB. Measured on a development PC: httk single run 3.5 s, 1000-person HTTK-Pop 4.5 s, R ≈ 400 MB.
>
> Everything here is in silico, exploratory research and teaching material (medical-safety.md; time-machine rule:
> no "reaches an active level" wording, no exposure-versus-potency verdict).

## Glossary
- **Virtual population:** a predefined set of virtual individuals: for the minimal compartmental model, the
  cited parameters of `data/time_machine/compartmental_pk.csv` (clearance scaled by a cited factor) drawn with
  their cited spreads; for httk, HTTK-Pop virtual individuals of an age range (NHANES 2013-2018, 20-50 or 65-79).
- **Allow-list:** `data/simulation/compounds.json`: the only compounds, populations, dose bounds, scenarios,
  httk chemical names, validation verdicts and limits the service accepts.
- **Job:** one queued model run; **slot:** one worker thread running a job.

## Requirement 1: In-browser explorer
1. THE explorer SHALL run the time machine's minimal compartmental model entirely in the browser; no input or
   output SHALL be sent to a server.
2. THE explorer SHALL offer only the allow-listed compartmental compounds (amlodipine, rhein) and their virtual
   populations, a dose within the allow-list's fixed bounds (with the cited scenarios as quick picks), and single
   or repeated doses at the compound's listed intervals only (amlodipine every 24 h; rhein every 12 or 24 h), at
   most 14 doses; a schedule that does not fit the simulated time SHALL be refused, never cut short.
3. THE explorer SHALL show the concentration-time distribution (5th, 50th, 95th percentile) as a chart with a
   table, and the bands of the peak and of the single-dose AUC; it SHALL NOT show a single-person curve or value.
4. THE validation status of the model for the compound (credible / borderline / failed, the fold errors with
   their direction, and what was checked) SHALL always be visible next to the result; a run outside the validated
   scenario (another dose, repeated doses) SHALL be labelled an extrapolation.
5. EVERY result SHALL carry "Virtual population, for research. Not about any person and not a dose
   recommendation." and the in-silico label; no text SHALL say a level is reached or effective.
6. THE TypeScript port SHALL produce the same numbers as the Python model on shared fixtures (Python's random
   generator reproduced), within 1e-9 relative.

## Requirement 2: Queued server runs
1. THE API SHALL accept `POST /simulate` for the allow-listed compartmental compounds and the httk population
   run for the three httk drugs of the time machine's population layer. The httk run SHALL compare both
   predefined HTTK-Pop age ranges (20-50, 65-79) at 1 mg/kg/day and SHALL report the older-to-younger ratio of
   medians as its result; absolute concentrations SHALL be labelled not validated and not a level anyone has.
2. A request SHALL contain only a kind, allow-listed ids and bounded integers or finite numbers; unknown fields
   SHALL be rejected (422 naming `<unknown>`, never the field's name or a value); the body SHALL be JSON of at
   most 1 KiB.
3. No request text SHALL reach R or Python model code: model arguments SHALL be built from the allow-list and
   from validated numbers; no shell SHALL be used.
4. THE queue SHALL hold at most 10 queued or running jobs; WHEN full, THE API SHALL answer 429 `queue_full` with
   `Retry-After`.
5. AT most 2 jobs SHALL run at once, enforced in the database.
6. EACH job SHALL be killed after 30 s and recorded as `timeout`.
7. AN identical normalised input SHALL reuse the queued, running or finished job (cache); a failed job SHALL
   NOT be reused.
8. Results SHALL expire after 24 h, failures after 1 h, queued jobs after 10 min; expired rows SHALL be deleted.
9. `GET /simulate/jobs/{id}` SHALL give the state, the queue position and the result; 404 when unknown or
   expired; 422 when the id is not a UUID.
10. EVERY answer of the simulation router SHALL carry the disclaimer of Req 1.5 (the generic body-policy
    rejections 413/415 happen before the router and are codes only); job answers SHALL carry the validation
    status of the model for the compound, and the screen SHALL show the status the job carries.

## Requirement 3: Abuse prevention and privacy
1. THE API SHALL rate-limit submissions per client (3 per 30 s, 5 per 10 min: one client cannot fill the queue)
   and in total (120 per 10 min), and polls per client (120 per minute), answering 429 `rate_limited` with
   `Retry-After`.
2. THE rate limiter SHALL NOT store an address: only a keyed hash (HMAC with a per-process random secret) in
   memory, expiring after the longest window, with a bounded table. An IPv6 client SHALL count as its /64
   network. `CF-Connecting-IP` SHALL be trusted only when the deployment says the API sits behind Cloudflare
   (`JANUS_BEHIND_CLOUDFLARE=on`); otherwise the socket peer counts.
3. THE queue SHALL store no address, header or other request metadata.
4. Logs SHALL hold route, status and latency (API) and states, counts and durations (worker) only.
5. A Cloudflare rate-limiting rule for `/api/simulate*` SHALL be documented for the deployer.

## Requirement 4: Worker isolation
1. THE worker SHALL run in its own image with pinned R and httk, buildable for linux/arm64 and linux/amd64.
2. THE worker container SHALL be attached to the internal network only (no route out, no published port), run
   as a non-root user with a read-only root file system, a size-limited `noexec,nosuid,nodev` tmpfs, all
   capabilities dropped, `no-new-privileges` and at most 128 processes, within 2.0 CPU and 1.5 GB.
4. THE worker SHALL connect with its own database role that may only read, update and delete queue rows.
3. THE deploy checks SHALL prove from inside the running worker that the internet, package mirrors, the metadata
   service and the host are unreachable, and run one small cached job in the smoke test.

## Requirement 5: Screens
1. THE simulation page SHALL offer a form (compound, virtual population, bounded inputs), show the queue state,
   and show the result as a chart and a table with the validation status and the disclaimer; 429, 503 and
   timeout states SHALL be shown with their meaning.
2. THE explorer and the simulation page SHALL NOT import or read the medicine list, findings or any patient data
   and SHALL NOT link to a patient screen.
3. BOTH SHALL work in both themes, five languages, at 375 and 1280 px, axe-clean, with loading, empty, error and
   long-content states; demo mode SHALL answer from a recorded result with no request.

## Requirement 6: Measured model error (owner decision 2026-11-09)
1. EVERY httk result SHALL state its measured error against Obach 2008 human data: the number of drugs, the
   retrieval date, the geometric bias and its direction, the share within 2-fold and the geometric mean fold
   error (httk half-life: n = 205, 2.1-fold too high, 30.7 % within 2-fold, GMFE 3.83).
2. FOR half-life only, THE result SHALL carry a split-conformal 80 % interval from that calibration, labelled
   "calibrated on Obach 2008, n = 205; covers the true value about 80 % of the time in held-out drugs".
3. Cmax, AUC and concentration outputs SHALL get no calibrated interval and SHALL say they are not validated
   against measured data (the compartmental model: beyond its one validation study).
4. ADMET-AI half-life and VDss values of zero or below SHALL never be shown as numbers; they are marked "the model
   returned an invalid value".
5. EVERY result for the older virtual population SHALL carry: HTTK-Pop's age effect is nearly the same for every
   drug; FDA labels report a median exposure increase of about 35 % in older adults (Janus research note,
   `docs/research/httk-pop-older-adult-exposure.md`, linked).
6. THE calibration constants SHALL be a versioned data file with provenance and no label text
   (`data/simulation/calibration.json`).

## Requirement 7: Quality
1. Property tests: no person-specific field; every answer carries the disclaimer; the calibrated interval only
   for half-life; the bias text on every httk result; invalid ADMET values never rendered; validation (bounds, strict
   types, unknown fields); cache key; queue limit and slots; rate limits; parity of the TypeScript port; expiry.
2. Reviews: safety auditor (wording; security and abuse of the endpoint), pharmacologist (inputs, bounds,
   populations, wording), localization reviewer (new texts).
