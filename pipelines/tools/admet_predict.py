"""Run ADMET-AI on a CSV of (name, smiles) and write the predictions (time-machine design §6.3).

Run with the pinned environment, never the project venv:
    .data/tools/admet-ai-env/bin/python -I pipelines/tools/admet_predict.py IN.csv OUT.csv
CPU only. Not imported by Janus code; outside pyright's include list on purpose (its
dependencies live only in the tool environment)."""

import csv
import sys

import torch
from admet_ai import ADMETModel

torch.set_num_threads(4)


def main(src: str, dst: str) -> None:
    with open(src, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    model = ADMETModel(num_workers=0)
    preds = model.predict(smiles=[r["smiles"] for r in rows])
    cols = list(preds.columns)
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["name", "smiles", *cols])
        for r, (_, p) in zip(rows, preds.iterrows(), strict=True):
            w.writerow([r["name"], r["smiles"], *[p[c] for c in cols]])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
