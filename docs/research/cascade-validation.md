# Cascade detection validation: results

Protocol: [`cascade-validation-protocol.md`](cascade-validation-protocol.md), registered in commit `d7a0b1f`
(2026-11-13, SHA-256 of the file at registration `fb58529bf1135ebbc7a3c3ae534fdf3c2fe3b7f6071afad3031061177d735bb0`);
amendment 1 in commit `4191eb3` before the reference set was complete and before any run on it (file SHA-256 after
the amendment `6b664b5f529910acf4f5fe8fbe81f4c9e43d8595a28b73ac065a600a44247503`).

Reference set: `data/validation/cascades/` (built blind to the rule base, engine and output; pushed in commit
`38ef35c` before the evaluation; checksums in `MANIFEST.sha256`; method in its `README.md`).

Index test: the public API at <https://janusmeds.org/api> (release `963f9109fbb1`, dataset
`a8ae53c225ee…`) with the rule base frozen at registration. SHA-256 of the rule base files at registration and at
the run (unchanged): `data/pipc.csv` `2030ae28…`, `data/cascade_classes.csv` `dbccf32b…`,
`data/cascade_priority.csv` `b4758a8d…`; no commit touched `apps/api/janus/cascades/` in between.

Scripts: `pipelines/tools/cascade_validation.py` (run), `pipelines/tools/cascade_validation_errors.py` (error
table). Raw answers and metrics: `data/validation/cascades/results/` (the 22 MB cache of API answers is not kept;
the scripts rebuild it).

## Summary

- **When Janus flags a cascade it is usually right**: specificity 0.975 (95 % CI 0.955–0.986) on 432 constructed
  negative pairs. Hypothesis H2 is met.
- **It finds about a third of the cascades published outside its own source list**: sensitivity 0.364
  (0.303–0.430) on 217 positive pairs. Hypothesis H1 (lower bound ≥ 0.80) is **not met**.
- **The engine is not the limit; the rule base is.** All 77 positive pairs whose drug classes are linked by a rule
  of the rule base were flagged (77/77). Of the 138 missed pairs, 75 are cascades the rule base does not contain, 59
  involve a drug outside its classes, and 4 failed name resolution.
- In older patients' full medication lists from case reports that describe no cascade, **half (26/50) receive at
  least one cascade notice**, mostly statin → pain reliever and NSAID → antihypertensive. A notice is a pattern to
  discuss, not a diagnosis; this is the screening burden of a rule list on polypharmacy, not an error rate.

Plainly: Janus checks for 65 listed prescribing cascades and does that reliably. It does not find cascades outside
that list, and published cascades are much broader than any one list.

## Primary outcomes (pair level, Wilson 95 % intervals)

| Measure | Result | 95 % CI | Hypothesis |
| --- | --- | --- | --- |
| Sensitivity | 79 / 217 = 0.364 | 0.303–0.430 | H1 (lower bound ≥ 0.80): not met |
| Specificity | 421 / 432 = 0.975 | 0.955–0.986 | H2 (lower bound ≥ 0.90): met |

Unresolved names: 4 positive pairs (counted as missed) and 2 negative pairs (left out of the specificity
denominator, amendment 1).

## Secondary outcomes

| Measure | Result | 95 % CI |
| --- | --- | --- |
| PPV at the designed 1 : 2 ratio | 79 / 90 = 0.878 | 0.794–0.930 |
| NPV at the designed 1 : 2 ratio | 421 / 559 = 0.753 | 0.716–0.787 |
| Case-level detection (cascade case reports) | 17 / 57 = 0.298 | 0.195–0.427 |
| Alert rate, comparison cases (no cascade described) | 26 / 50 = 0.520 | 0.385–0.652 |
| Sensitivity within the rule base's scope (exploratory, uses the rule base) | 77 / 77 = 1.000 | 0.953–1.000 |
| Sensitivity, one pair per cascade (protocol §6; lowest pair id per A class → B class) | 74 / 203 = 0.365 | 0.301–0.433 |

PPV and NPV depend on the 1 : 2 ratio fixed by design and are not clinical predictive values.

### Error table: missed positive pairs (138)

| Category | Pairs |
| --- | --- |
| Cascade not in the rule base (both drugs in its classes, no rule links them) | 75 |
| A drug outside the rule base's classes | 59 |
| Name not resolved | 4 |
| A rule links the classes but the engine did not report it | 0 |

### Missed cascade cases (40 of 57)

| Category | Cases |
| --- | --- |
| Cascade not in the rule base | 25 |
| A drug outside the rule base's classes | 11 |
| Expected drug not resolved from the case's list | 4 |

### Flagged negative pairs (11 of 432)

Every one matches a cascade class pair of the rule base: felodipine → indapamide and phenylbutazone or rofecoxib →
bisoprolol, ivabradine, eplerenone or spironolactone (calcium channel blocker → diuretic, NSAID → antihypertensive
or heart failure agent), omeprazole → magnesium oxide, fluvastatin → morphine, phenobarbital → betamethasone,
prochlorperazine → metformin, rivastigmine → trazodone, simvastatin → tasimelteon. The negative-pair rule
(protocol §3.2) excludes a pair only when an OnSIDES adverse event of A is a label indication of B′; indapamide's
label names hypertension, not oedema, so the rule kept pairs that are recognised cascades. Most of these "false
positives" are therefore errors of the constructed reference standard, not of the engine. The primary estimate is
not changed; read it as a lower bound.

### Comparison cases: notices by rule (cases with at least one)

| Rule | Cases |
| --- | --- |
| Statin → pain reliever (PIPC 9) | 14 |
| NSAID → antihypertensive (PIPC 53) | 12 |
| Calcium channel blocker → diuretic (PIPC 5) | 5 |
| NSAID → gastroprotective agent (PIPC 51) | 5 |
| NSAID → heart failure agent (PIPC 54) | 3 |
| Others (seven rules) | 1–2 each |

## Deviations

1. **Case medication lists (found after the first results).** The first run split each case's medication list on
   every semicolon, including semicolons inside bracketed notes, so names such as "ropinirole [started …" did not
   resolve. The parser was corrected (split outside brackets, drop bracketed and parenthesised notes, split "X and
   Y"), and the run was repeated. Both results are reported: case-level detection 7 / 57 = 0.123 (0.061–0.232) with
   the first parser, 17 / 57 = 0.298 (0.195–0.427) corrected. Pair-level results, the primary outcomes, do not use
   this parser and are identical in both runs; the comparison alert rate is unchanged (26 / 50). The first run's
   files are kept (`metrics_v1.json`, `cases_*_v1.json`).
2. **Late sensitivity analysis.** The pre-specified analysis counting one pair per cascade (protocol §6) was computed
   after the first version of this report, with the pair chosen by a fixed rule (the lowest pair id of each A
   class → B class group, 203 groups): 74 / 203 = 0.365 (0.301–0.433), the same as the primary estimate.
3. **Reference-set builder choices beyond the protocol text** (recorded by the builder before any run, see
   `data/validation/cascades/README.md`): a negative B′ was redrawn when it had no single-ingredient US label (the
   label check cannot run without one); study signals from untargeted screens of all drugs, and rows without a
   positive association, were not used as positive pairs.

## Limits

- The positive pairs come from three reviews and two other sources whose study pools overlap; the source count is
  a count of papers, not independent evidence. Class-level cascades were reduced to one ingredient by a fixed rule,
  which sometimes chose old or withdrawn drugs (for example alprenolol, phenylbutazone, zimelidine).
- The negative pairs are constructed; the 11 flagged ones show the construction is imperfect.
- Only 10 of the 57 cascade cases are aged 65 or over, and psychiatric drugs dominate. Eight lists are partial;
  in eleven cases drug A was stopped before drug B.
- The comparison cases come from case reports on other topics; a report that does not describe a cascade does
  not prove there is none, so their alert rate is not a specificity.
- Every step was automated; no clinician checked the reference set. Expert review has not yet been done; the
  reference set is part of the expert validation packet.

## What follows for the product

- The scope statement must stay explicit: Janus checks a fixed list of 65 cascades (PIPC); "no notice" never means
  "no cascade".
- The 59 pairs with a drug outside the rule base's classes and the 75 cascades not in it are a ready list for
  extending the rule base, each with its sources. Adding rules is a clinical decision for the expert panel, not
  something tuned on this reference set.
- Half of older patients' full lists receive a notice; the patient flow should present notices as questions for
  the doctor and keep their number manageable.
