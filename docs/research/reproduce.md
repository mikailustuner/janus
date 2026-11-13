# Reproducing the validation numbers

Every number in [cascade-validation.md](cascade-validation.md) and [faers-calibration.md](faers-calibration.md)
follows from committed files by one command.

```bash
scripts/reproduce.sh          # every number from the committed tables and raw answers (no data download)
scripts/reproduce.sh --full   # also rebuild the tables: FAERS counts from a local data directory, cascade
                              # answers from the public API; then compare with the committed numbers
```

| Study             | Committed inputs                                                    | Committed outputs                                                    | Rebuilt by                                                                                         |
| ----------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Cascade detection | `data/validation/cascades/*.csv` (reference set, `MANIFEST.sha256`) | `data/validation/cascades/results/`                                  | `pipelines/tools/cascade_validation.py` (public API), `cascade_validation_errors.py` (error table) |
| FAERS calibration | `data/validation/faers/*.csv` (reference sets)                      | `data/validation/faers/results/` (`pairs.csv` holds every 2×2 table) | `pipelines/tools/faers_calibration.py` (needs the FAERS counts build named in the results)         |

The check mode needs only Python 3.12 and the standard library. The full FAERS rebuild needs the counts build
named in the results file, made by the `faers` pipeline (`docs/for-researchers.md`, "Reproducible pipelines").

`.github/workflows/reproduce.yml` runs the check every week and re-runs the cascade validation against the
public API. It fails, and GitHub notifies, when a committed number no longer follows from the committed files, or
when the live engine now answers the reference set differently (for example after a data update). A changed
answer is then reported as a new, dated result; the original result stays as published.
