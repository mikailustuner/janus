# Automated review passes (2026-11-09)

Three read-only automated review passes, run separately on the code, the data and the new messages. Expert review
has not yet been done.

## Safety auditor (`.kiro/agents/safety-auditor.md`): wording, security and abuse
Clean: no request text reaches R, Python argv, a shell or SQL (strict schema, allow-list ids, argv from
allow-list values and integers, R re-checks every argument, parameterised SQL); 1 KiB body; advisory lock on
submit and claim; failed jobs never cached; cache key includes the allow-list version; limiter keeps only an HMAC
with a per-process secret; no address in the database; worker logs states, counts and durations only; container
non-root, read-only, no capabilities, `no-new-privileges`, internal only; wording in five languages (no forbidden
phrase, nothing "reached", "effective" or "therapeutic", no dose advice); the sentence on every page and result;
no patient data read or linked.

| # | Finding | Severity | Resolution |
|---|---|---|---|
| F1 | Worker connects as the database owner; a compromised R package could use it | advisory (strong) | Own role `janus_simulator` (migration 0014): SELECT, UPDATE, DELETE on `simulation_jobs` only; password from `.env` set by `python -m janus.simulation.dbrole` in `deploy.sh`; test Q5 |
| F2 | IPv6 address rotation inside a /64 escapes per-client limits | advisory | IPv6 counted per /64; global window kept; property test |
| F3 | `CF-Connecting-IP` trusted unconditionally | advisory | Trusted only with `JANUS_BEHIND_CLOUDFLARE=on` (deploy compose); else the socket peer |
| F4 | Cloudflare rule only in the design | advisory | In `deploy/README.md` (simulation section) with the Free-plan trade-off |
| F5 | Result could sit next to another compound's verdict after a change of the form | advisory | The result card shows the validation status the job carries |
| F6 | One client could fill the queue (10 per 10 min = queue size) | advisory | 5 per 10 min per client |
| F7 | Simulator can reach `api:8000` on the shared internal network | advisory | Declined: the API is the same surface the internet reaches; a separate network needs a new firewall subnet (open item) |
| F8 | `/tmp` executable | minor | `noexec,nosuid,nodev`; self-test passes with it |
| F9 | `check_compose.py` did not check the simulator's pids limit and tmpfs | minor | Checked |
| F10 | Migration allowed the dropped `httk_single` kind | minor | Removed (0014 not yet applied anywhere) |
| F11 | 413/415 body-policy answers carry no disclaimer | minor | Req 2.10 scoped to the router's answers (the body policy answers codes only, before any route) |
| F12 | `/simulate/` with a trailing slash missed the 1 KiB limit | minor | Path normalised for the limit |
| F13 | An oversized or malformed result could crash a slot | minor | Size (200 kB) and shape checked before storing; a refused result fails the job only |
| F14 | `poll_after_s` of 0 would poll in a tight loop | minor | Clamped to at least 1 s |

## Pharmacologist (`.kiro/agents/pharmacologist.md`): inputs, bounds, populations, wording
| # | Finding | Severity | Resolution |
|---|---|---|---|
| P1 | Schedules longer than the 336 h horizon were silently cut short | blocking | Horizon 360 h; a schedule that does not fit is refused (422, and in the browser); 14 doses every 24 h fit exactly |
| P2 | httk run showed absolute concentrations of a model that failed validation, one age group per job | blocking | One job runs both HTTK-Pop age ranges; the older-to-younger ratio of medians is the result; absolute bands only in a disclosure "not validated, not a level anyone has"; 1 mg/kg/day stated as far above usual doses |
| P3 | Interval 6-48 h allowed 4 × the usual amlodipine exposure and untested rhein schedules | advisory | Per-compound intervals: amlodipine 24 h; rhein 12 or 24 h; extrapolation label outside the validated scenario |
| P4 | "Credible" read as general | advisory | Scope shown: what was checked (one dose, healthy volunteers; rhein only the peak independent) |
| P5 | Fold errors without direction | advisory | Directions in the allow-list (checked against the time-machine table by a test) and shown ("model peak 2.37-fold lower") |
| P6 | Population labels and the double use of the CL spread | advisory | Labels name the sources ("Young healthy adults (Faulkner 1986)", "Older adults (Abernethy 1990: hypertensive, mean age 68)", "Healthy adults (Magnard 1993)"); basis says the shift is on top of a spread that already covers the difference, and 80+ is not covered |
| P7 | Canon 480 mg scenario lost its caveats | advisory | "mg rhein equivalent"; the scenario note (upper estimate, one historical dose, machine translation) shown with the input |
| P8 | "Cited bounds" not cited for amlodipine | minor | "Fixed bounds of this model" |
| P9 | Rhein F drawn 0.8-1.0 although parameters are apparent | minor | F fixed at 1 for apparent parameters (allow-list `f_fixed`), in Python and the browser port |
Checked fine: dose ranges themselves, leaving out a ≥ 65 rhein population, peak capture on the grid, superposition,
units, single-dose AUC label, disclaimers, no dosing wording.

## Localization reviewer (`.kiro/agents/localization-reviewer.md`)
Clean: key parity, placeholders, no forbidden phrase or reassurance word, the fixed sentence faithful in TR, DE,
FR, ES.

| # | Finding | Resolution |
|---|---|---|
| L1 | TR "on kişilik sıra" (people, not runs) | "sırada en fazla on" |
| L2-L6 | TR terms aligned with the time machine (konsantrasyon, medyan, simüle edilen, persentil, AUC), "Sıraya alınan", "Sanal birey sayısı", "{at}. saatte" | Fixed |
| L7 | FR "une personne seule" | "une personne en particulier" |
| L8 | ES double negation | Fixed |
| L9 | DE "Steady State", "mg/l" as in the time machine | Fixed |
Pending: a native-speaker check of the PK terms before launch.
