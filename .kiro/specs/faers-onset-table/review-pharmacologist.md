# Pharmacologist review (agent `.kiro/agents/pharmacologist.md`, read-only), 2026-11-09

Two passes on the class → ingredient mappings, event terms and output. AI review; a pharmacist has not reviewed
this yet.

## First pass
| # | Finding | Severity | Resolution |
|---|---|---|---|
| O1 | "FAERS does not give the route" is false; local forms counted through any code | blocker | `faers_onset` keeps `DRUG.route`/`dose_form` (`pairs` side table); local routes dropped (`routes.py`); caveat rewritten |
| O2 | Systemic corticosteroids count eye, skin, inhaled forms; cortisol includes replacement doses | blocker | Route filter; row notes 59-61 |
| O3 | NSAIDs: low-dose aspirin and carbaspirin dominate; topical and eye forms | blocker | Both keys excluded (`data/onset_key_exclusions.csv`); route filter |
| O4 | Antihypertensive/diuretic: theobromine, diazoxide; minoxidil topical; eye beta-blockers | should-fix | Theobromine and diazoxide excluded; topical/eye lines removed by the route filter |
| O5 | Row 3 inconsistent (S01ED-only keys missing, eye drops via C07) | should-fix | S01ED extension on and eye route allowed for row 3; row note |
| O6 | Laxatives: naloxone, mannitol, sorbitol, glycerol, magnesium sulfate; bowel prep day 0 | blocker | Five keys excluded; rectal route kept; row note 47 |
| O7 | Iron: iron(III) citrate is a phosphate binder | should-fix | Excluded; IV iron sucrose confirmed not a member (second pass) |
| O8 | Cabergoline/bromocriptine prolactin use | should-fix | Row note 30 |
| O9 | Row 23: midazolam, "Amnesia" captures acute effects | should-fix | Midazolam excluded; row note 23; term change is an open item |
| O10 | Event terms that do not match drug B (rows 2, 5, 11, 21-22, 26-27, 31, 48, 50, 56, 63) | should-fix | Row notes; vocabulary unchanged (shared with Collective Memory, owner-reviewed) — open items |
| O11 | Row 49 mixes B12, magnesium, iron | should-fix | Row note |
| O12-O14 | Rows 48 and 3 long medians; zero-day medians rows 6 and 52 | notes | Cluster rule (rows 3, 6, 48 now counts only); per-member counts published |
| O15 | Heroin; codeine not a member; doxepin; levomilnacipran | note | Heroin excluded; codeine row note 55; doxepin see below |
| O16 | Dedup wording, review status, receipt window | should-fix | Reworded |

## Second pass
- **Blocker remaining — doxepin:** plain "DOXEPIN" maps to Q71704041 ((E/Z)-doxepin, only D04AX01), so those reports
  never reach the tricyclic class (rows 33-35), and the cascade engine may give US doxepin products only the
  topical code. Not fixed here: it is a drug-resolution change (a curated code or a key merge). Row notes 33-35 and
  an open item record it.
- Joint and lesion injections of systemic corticosteroids were dropped → allowed for `corticosteroid_systemic`.
  **Fixed.**
- Nasal and inhaled systemic products (butorphanol, fentanyl nasal; inhaled levodopa; inhaled loxapine; diazepam
  nasal) were dropped → allowed for opioids, dopaminergic antiparkinsonians, antipsychotics and benzodiazepines.
  **Fixed.**
- Row 23 note on "Amnesia"; row 65 note on unmapped oral iron names; rows 59-61 note on cortisone with no intervals.
  **Added.** Duplicate lactulose key receives no FAERS name: closed.
