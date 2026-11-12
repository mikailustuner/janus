"""Build `data/modelkit/ctgov_study_ids.csv`: the sponsor study codes of the ClinicalTrials.gov
records in the model kit evidence (milestone M5, study identity across sources).

For every NCT id of the current `modelkit_ctgov` artifact the record is read from the official bulk
file (the same file the job reads; one member per record, nothing else is opened) and its
organisation study id and secondary ids are written. Research use only.

python tools/build_modelkit_ctgov_ids.py CTGOV_ROWS_PARQUET BULK_ZIP OUT_CSV"""

from __future__ import annotations

import csv
import json
import sys
import zipfile
from pathlib import Path

import polars as pl

from janus_pipelines.modelkit.study_identity import norm_code


def main(rows_path: Path, bulk: Path, out: Path) -> None:
    ncts = sorted(set(pl.read_parquet(rows_path, columns=["study_id"])["study_id"].to_list()))
    written = 0
    with zipfile.ZipFile(bulk) as zf, out.open("w", newline="", encoding="utf-8") as fh:
        names = set(zf.namelist())
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["nct_id", "codes"])
        for nct in ncts:
            member = f"{nct[-2:]}/{nct}.json"
            if member not in names:
                continue
            ident = json.loads(zf.read(member))["protocolSection"]["identificationModule"]
            raw = [ident.get("orgStudyIdInfo", {}).get("id", "")]
            raw += [s.get("id", "") for s in ident.get("secondaryIdInfos", [])]
            codes = sorted({c for c in (norm_code(x) for x in raw if x) if c})
            w.writerow([nct, "|".join(codes)])
            written += 1
    print(f"{written} records, {len(ncts)} NCT ids in the artifact")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
