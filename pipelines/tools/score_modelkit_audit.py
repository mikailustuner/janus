"""Score filled answer sheets of the model kit expert sample audit (milestone M6, plan 12.3).

    python tools/score_modelkit_audit.py KEY_CSV FRAME_SIZES_JSON OUT_JSON SHEET_CSV:ROLE [...]
        [--record RECORD_JSON --date YYYY-MM-DD --release RUN_ID]

KEY_CSV is the private key of the draw (item_id, frame, stratum, ...); FRAME_SIZES_JSON maps each
stratum to its frame size N_h. Each sheet is a filled `audit_items.csv`; ROLE is the reviewer's
role (pharmacometrician, clinical_pharmacologist or pharmacist; never a name). OUT_JSON gets the
result per reviewer and for the strict consensus, kappa between reviewers and the criterion of plan
12.3. With --record the `expert_audit` record the evidence job reads is written too (normally
`data/modelkit/expert_audit.json`; the owner decides when to commit it). Research use only.
"""

from __future__ import annotations

import argparse
import csv
import json
from itertools import combinations
from pathlib import Path

from janus_pipelines.modelkit.audit import (
    ROLES,
    check_record,
    consensus,
    kappa,
    make_record,
    read_answers,
    score,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score the model kit expert sample audit.")
    ap.add_argument("key", type=Path)
    ap.add_argument("frame_sizes", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("sheets", nargs="+", help="SHEET_CSV:ROLE")
    ap.add_argument("--record", type=Path)
    ap.add_argument("--date")
    ap.add_argument("--release")
    a = ap.parse_args(argv)
    key = list(csv.DictReader(a.key.open(encoding="utf-8", newline="")))
    sizes = {str(k): int(v) for k, v in json.loads(a.frame_sizes.read_text("utf-8")).items()}
    sheets: list[tuple[str, dict[str, str]]] = []
    for spec in a.sheets:
        path, _, role = spec.rpartition(":")
        if role not in ROLES or not path:
            ap.error(f"{spec}: give SHEET_CSV:ROLE with a role of {sorted(ROLES)}")
        rows = list(csv.DictReader(Path(path).open(encoding="utf-8", newline="")))
        sheets.append((role, read_answers(rows, Path(path).name)))
    per = [(role, score(ans, key, sizes)) for role, ans in sheets]
    cons = score(consensus([ans for _, ans in sheets]), key, sizes)
    reviewers_met = all(r["criterion"]["met"] for _, r in per)  # type: ignore[index]
    result = {
        "n_items": len(key),
        "reviewers": [{"role": role, **r} for role, r in per],
        "consensus": cons,
        "kappa": {
            f"{i}-{j}": kappa(sheets[i][1], sheets[j][1])
            for i, j in combinations(range(len(sheets)), 2)
        },
        "criterion_met": bool(cons["criterion"]["met"]) and reviewers_met,  # type: ignore[index]
    }
    a.out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", "utf-8")
    if a.record:
        if not (a.date and a.release):
            ap.error("--record needs --date and --release")
        record = make_record(
            cons, date=a.date, release=a.release, roles=[r for r, _ in sheets],
            n_items=len(key), reviewers_met=reviewers_met,
        )  # fmt: skip
        check_record(record)
        a.record.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", "utf-8")
    o = cons["overall"]
    print(json.dumps({"consensus": o, "criterion_met": result["criterion_met"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
