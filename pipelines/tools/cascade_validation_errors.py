"""Error table and within-scope sensitivity of the cascade validation (protocol §4, secondary).

Reads the raw answers written by `cascade_validation.py` and the frozen rule base (built from the
repository files by the engine's own loader). Runs in the API environment:

    cd apps/api && uv run python ../../pipelines/tools/cascade_validation_errors.py \
        --results ../../data/validation/cascades/results

Categories for a missed positive pair (first that applies): the name did not resolve; drug A or
drug B is in none of the rule base's classes; both are in classes but no rule links a class of A
(index) to a class of B (marker), i.e. the cascade is not in the rule base; a rule links them but
the engine did not report it (evidence gate, form or timing).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from janus.cascades.load import read_files
from janus.cascades.patterns import class_match
from janus.cascades.rulebase import build_rule_base


def classes_of(codes: list[str], rb: Any) -> set[str]:
    return {name for name, cls in rb.classes.items() if any(class_match(c, cls) for c in codes)}


def linking_rules(a: set[str], b: set[str], rb: Any) -> list[int]:
    return [r.position for r in rb.rules if r.index_class in a and r.marker_class in b]


def category(rec: dict[str, Any], rb: Any) -> tuple[str, list[int]]:
    if rec.get("unresolved"):
        return "name_not_resolved", []
    ca, cb = classes_of(rec["a"]["atc"], rb), classes_of(rec["b"]["atc"], rb)
    rules = linking_rules(ca, cb, rb)
    if rules:
        return "rule_exists_not_reported", rules
    if not ca or not cb:
        return "drug_outside_rule_base_classes", []
    return "cascade_not_in_rule_base", []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, required=True)
    args = ap.parse_args()
    rb = build_rule_base(read_files().inputs())

    pos = json.loads((args.results / "pairs_positive.json").read_text())
    neg = json.loads((args.results / "pairs_negative.json").read_text())
    cases = json.loads((args.results / "cases_cascade.json").read_text())
    comp = json.loads((args.results / "cases_comparison.json").read_text())

    missed: Counter[str] = Counter()
    in_scope = in_scope_hit = 0
    rule_exists: list[dict[str, Any]] = []
    for r in pos:
        cat, rules = ("flagged", []) if r["flagged"] else category(r, rb)
        if not r.get("unresolved"):
            linked = linking_rules(classes_of(r["a"]["atc"], rb), classes_of(r["b"]["atc"], rb), rb)
            if linked:
                in_scope += 1
                in_scope_hit += bool(r["flagged"])
        if not r["flagged"]:
            missed[cat] += 1
            if cat == "rule_exists_not_reported":
                rule_exists.append(
                    {"id": r["id"], "a": r["a"]["name"], "b": r["b"]["name"], "rules": rules}
                )

    false_pos = [
        {
            "id": r["id"],
            "a": r["a"]["name"],
            "b": r["b"]["name"],
            "rules": sorted({f["rule_id"] for f in r.get("findings") or []}),
        }
        for r in neg
        if r["flagged"]
    ]

    case_missed: Counter[str] = Counter()
    for c in cases:
        if c["flagged"]:
            continue
        exp = c.get("expected") or {}
        if not exp.get("a") or not exp.get("b"):
            case_missed["name_not_resolved"] += 1
            continue
        by_qid = {m["qid"]: m for m in c["medications"] if m.get("qid")}
        a, b = by_qid.get(exp["a"]), by_qid.get(exp["b"])
        if a is None or b is None:
            case_missed["expected_drug_not_in_resolved_list"] += 1
            continue
        cat, _ = category({"a": a, "b": b}, rb)
        case_missed[cat] += 1

    comp_rules: Counter[str] = Counter()
    for c in comp:
        for rid in {f["rule_id"] for f in c.get("findings") or []}:
            comp_rules[rid] += 1
    rule_text = {f"pipc:{r.position}": f"{r.drug_a} → {r.drug_b}" for r in rb.rules}

    out = {
        "missed_positive_pairs_by_category": dict(missed),
        "within_rule_base_scope": {"pairs": in_scope, "flagged": in_scope_hit},
        "rule_exists_not_reported": rule_exists,
        "flagged_negative_pairs": false_pos,
        "missed_cascade_cases_by_category": dict(case_missed),
        "comparison_case_rules": [
            {"rule": rid, "text": rule_text.get(rid, ""), "cases": n}
            for rid, n in comp_rules.most_common()
        ],
    }
    (args.results / "errors.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(
        json.dumps(
            {
                k: out[k]
                for k in (
                    "missed_positive_pairs_by_category",
                    "within_rule_base_scope",
                    "missed_cascade_cases_by_category",
                )
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
