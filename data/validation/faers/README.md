# FAERS calibration reference sets

Drug–outcome pairs with a known answer (`groundTruth` 1 = positive control, 0 = negative control), used
by the pre-registered FAERS calibration (`docs/research/faers-calibration-protocol.md`).

| File | Pairs | Source |
| --- | --- | --- |
| `omop_reference_set.csv` | 399 (165 positive, 234 negative) | Ryan PB et al., Drug Saf 2013;36(Suppl 1):S33–S47, doi:10.1007/s40264-013-0097-8 |
| `euadr_reference_set.csv` | 93 (43 positive, 50 negative) | Coloma PM et al., Drug Saf 2013;36(1):13–23, doi:10.1007/s40264-012-0002-x |

Both come from the OHDSI MethodEvaluation R package (Apache License 2.0), `data/omopReferenceSet.rda`
and `data/euadrReferenceSet.rda` at commit `d7305910f6c6`, converted to CSV with pyreadr 0.5.2 and
otherwise unchanged. SHA-256 of the source files: `omopReferenceSet.rda`
`8d0964fce92c557d98cb751ec2aea7c1e3e1643696231a177128579a5662fa15`, `euadrReferenceSet.rda`
`5cea251e7ab03a232f871abfb448655b8474ffab325bb19b4fbae8d139203c32`.
