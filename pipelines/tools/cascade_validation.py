"""Run the cascade detection validation (docs/research/cascade-validation-protocol.md).

Reads the frozen reference set (data/validation/cascades/), runs every pair and case through the
public API exactly as the site does (name search, then cascade evaluation), and writes raw answers
and metrics. Standard library only. The reference set is never changed here.

    python3 pipelines/tools/cascade_validation.py --ref data/validation/cascades \
        --out data/validation/cascades/results --api https://janusmeds.org/api

Name resolution rule (fixed before the run), in order: (1) the highest-scoring candidate of kind
`ingredient` (what a person typing a generic name is offered first); (2) mapped ingredients of
product candidates whose English label equals the name (case and accents ignored); (3) ingredients
of single-ingredient products. In (2) and (3) the Wikidata key seen most often wins (ties: lowest
key). No match is a resolution failure: a positive pair then counts as missed (the person gets no
warning); a negative pair is left out of the specificity denominator and counted separately (it
says nothing about the engine)."""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

A_STARTED = "2025-01"
B_STARTED = "2025-03"
PAUSE_S = 1.0


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.casefold().replace("-", " ").split())


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float | None, float | None, float | None]:
    if n == 0:
        return None, None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


class Api:
    def __init__(self, base: str, cache_path: Path) -> None:
        if not base.startswith(("https://", "http://")):
            raise ValueError("--api must be an http(s) URL")
        self.base = base.rstrip("/")
        self.cache_path = cache_path
        self.cache: dict[str, Any] = (
            json.loads(cache_path.read_text()) if cache_path.exists() else {}
        )
        self.dataset_version: str | None = None

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(body).encode()
        for attempt in range(4):
            req = urllib.request.Request(  # noqa: S310 (scheme checked in __init__)
                self.base + path,
                data=data,
                headers={"content-type": "application/json", "user-agent": "janus-validation"},
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
                    time.sleep(PAUSE_S)
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code in (429, 502, 503, 504) and attempt < 3:
                    time.sleep(5 * (attempt + 1))
                    continue
                return {"http_error": e.code, "body": e.read().decode(errors="replace")[:300]}
            except (urllib.error.URLError, TimeoutError):
                if attempt < 3:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise
        raise RuntimeError("unreachable")

    def resolve(self, name: str) -> dict[str, Any]:
        key = "resolve:" + norm(name)
        if key not in self.cache:
            self.cache[key] = self._post("/resolve/search", {"query": name[:100], "limit": 20})
            self.cache_path.write_text(json.dumps(self.cache))
        ans = self.cache[key]
        self.dataset_version = self.dataset_version or ans.get("dataset_version")
        return pick_ingredient(name, ans)

    def evaluate(self, items: list[dict[str, str]]) -> dict[str, Any]:
        if not self.dataset_version:
            raise RuntimeError("resolve a name before evaluating")
        return self._post(
            "/cascades/evaluate", {"dataset_version": self.dataset_version, "items": items}
        )


def pick_ingredient(name: str, ans: dict[str, Any]) -> dict[str, Any]:
    ingredient_cands = [
        c
        for c in ans.get("candidates") or []
        if c.get("kind") == "ingredient" and c.get("ingredient_key")
    ]
    if ingredient_cands:
        best = max(ingredient_cands, key=lambda c: c.get("score") or 0)
        k = best["ingredient_key"]
        return {
            "name": name,
            "qid": k["qid"],
            "label": k.get("label_en"),
            "atc": sorted({a["code"] for a in best.get("atc_codes") or []}),
            "by": "ingredient_candidate",
        }
    want = norm(name)
    exact: Counter[str] = Counter()
    single: Counter[str] = Counter()
    info: dict[str, dict[str, Any]] = {}
    for cand in ans.get("candidates") or []:
        ings = [i for i in cand.get("ingredients") or [] if i.get("ingredient_key")]
        for ing in ings:
            k = ing["ingredient_key"]
            qid = k["qid"]
            info.setdefault(qid, {"label": k.get("label_en"), "atc": set()})
            info[qid]["atc"].update(a["code"] for a in ing.get("atc_codes") or [])
            if norm(k.get("label_en") or "") == want:
                exact[qid] += 1
            if len(cand.get("ingredients") or []) == 1:
                single[qid] += 1
    pool = exact or single
    if not pool:
        return {"name": name, "qid": None, "why": "no_mapped_ingredient"}
    top = max(pool.values())
    qid = min(q for q, c in pool.items() if c == top)
    return {
        "name": name,
        "qid": qid,
        "label": info[qid]["label"],
        "atc": sorted(info[qid]["atc"]),
        "by": "label" if exact else "single_ingredient_product",
    }


def flagged(result: dict[str, Any], qa: str, qb: str) -> bool:
    for f in result.get("findings") or []:
        if f["index"]["ingredient_key"] == qa and f["marker"]["ingredient_key"] == qb:
            return True
    return False


def summary(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": f["rule_id"],
            "index": f["index"]["ingredient_key"],
            "marker": f["marker"]["ingredient_key"],
            "status": f["status"],
            "timing": f["timing"],
        }
        for f in findings
    ]


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def run_pairs(
    api: Api, rows: list[dict[str, str]], b_col: str, id_col: str
) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        a, b = api.resolve(r["drug_a"]), api.resolve(r[b_col])
        rec: dict[str, Any] = {"id": r[id_col], "a": a, "b": b}
        if a["qid"] and b["qid"]:
            res = api.evaluate(
                [
                    {"ingredient": a["qid"], "started": A_STARTED},
                    {"ingredient": b["qid"], "started": B_STARTED},
                ]
            )
            rec["findings"] = summary(res.get("findings") or [])
            rec["error"] = res.get("http_error") and res
            rec["flagged"] = flagged(res, a["qid"], b["qid"])
        else:
            rec["flagged"] = False
            rec["unresolved"] = True
        out.append(rec)
    return out


def meds(field: str) -> list[str]:
    """Medicine names of a case list (deviation 1, results file): split on semicolons outside
    brackets, drop bracketed and parenthesised notes, split "X and Y" into two names."""
    items, depth, cur = [], 0, []
    for ch in field:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            items.append("".join(cur))
            cur = []
            continue
        if depth == 0 and ch not in "])":
            cur.append(ch)
    items.append("".join(cur))
    names = [n.strip() for item in items for n in item.split(" and ")]
    return [n for n in names if n]


def run_cases(api: Api, rows: list[dict[str, str]], expected: bool) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        resolved = [api.resolve(m) for m in meds(r["medications"])]
        rec: dict[str, Any] = {"id": r["case_id"], "medications": resolved}
        ea = eb = None
        if expected:
            ea = api.resolve(r["expected_a"])["qid"]
            eb = api.resolve(r["expected_b"])["qid"]
            rec["expected"] = {"a": ea, "b": eb}
        items, seen = [], set()
        for m in resolved:
            q = m["qid"]
            if not q or q in seen:
                continue
            seen.add(q)
            item = {"ingredient": q}
            if expected and r.get("a_before_b") == "yes" and q in (ea, eb):
                item["started"] = A_STARTED if q == ea else B_STARTED
            items.append(item)
        if not items:
            rec.update(flagged=False, any_finding=False, unresolved=True)
            out.append(rec)
            continue
        res = api.evaluate(items[:20])
        rec["findings"] = summary(res.get("findings") or [])
        rec["error"] = res.get("http_error") and res
        rec["any_finding"] = bool(res.get("findings"))
        rec["flagged"] = bool(ea and eb and flagged(res, ea, eb))
        out.append(rec)
    return out


def metric(name: str, k: int, n: int) -> dict[str, Any]:
    p, lo, hi = wilson(k, n)
    return {"measure": name, "k": k, "n": n, "estimate": p, "ci95_low": lo, "ci95_high": hi}


def compute(
    pos: list[dict[str, Any]],
    neg: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    comp: list[dict[str, Any]],
    dataset_version: str | None,
    api: str,
) -> dict[str, Any]:
    """Every number of the results from the raw answers."""
    tp = sum(r["flagged"] for r in pos)
    neg_resolved = [r for r in neg if not r.get("unresolved")]
    fp = sum(r["flagged"] for r in neg_resolved)
    tn = len(neg_resolved) - fp
    fn = len(pos) - tp
    return {
        "dataset_version": dataset_version,
        "api": api,
        "primary": [
            metric("sensitivity_pairs", tp, len(pos)),
            metric("specificity_pairs", tn, len(neg_resolved)),
        ],
        "secondary": [
            metric("ppv_pairs_at_1_to_2", tp, tp + fp),
            metric("npv_pairs_at_1_to_2", tn, tn + fn),
            metric("case_detection", sum(r["flagged"] for r in cases), len(cases)),
            metric("comparison_alert_rate", sum(r["any_finding"] for r in comp), len(comp)),
        ],
        "unresolved": {
            "positive_pairs": sum(bool(r.get("unresolved")) for r in pos),
            "negative_pairs": sum(bool(r.get("unresolved")) for r in neg),
        },
        "api_errors": sum(bool(r.get("error")) for r in pos + neg + cases + comp),
    }


def verify(out: Path) -> int:
    """Recompute the metrics from the committed raw answers and compare them."""
    load = lambda name: json.loads((out / name).read_text())  # noqa: E731
    want = load("metrics.json")
    got = compute(
        load("pairs_positive.json"),
        load("pairs_negative.json"),
        load("cases_cascade.json"),
        load("cases_comparison.json"),
        want["dataset_version"],
        want["api"],
    )
    ok = json.loads(json.dumps(got)) == want
    print("cascade validation: " + ("reproduced" if ok else "differs"))
    return 0 if ok else 1


def compare(a: Path, b: Path) -> int:
    """Exit 1 when two metrics files differ in any count (live re-run against the recorded one)."""
    x, y = json.loads(a.read_text()), json.loads(b.read_text())
    keys = ("primary", "secondary", "unresolved")
    same = all(x[k] == y[k] for k in keys)
    print("cascade validation live re-run: " + ("same counts" if same else "counts changed"))
    if not same:
        for m_old, m_new in zip(
            x["primary"] + x["secondary"], y["primary"] + y["secondary"], strict=True
        ):
            if m_old != m_new:
                print(
                    f"  {m_old['measure']}: {m_old['k']}/{m_old['n']} -> {m_new['k']}/{m_new['n']}"
                )
    return 0 if same else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--api", default="https://janusmeds.org/api")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    api = Api(args.api, args.out / "api_cache.json")

    pos = run_pairs(api, read(args.ref / "positive_pairs.csv"), "drug_b", "pair_id")
    neg = run_pairs(api, read(args.ref / "negative_pairs.csv"), "drug_b_prime", "neg_id")
    cases = run_cases(api, read(args.ref / "cascade_cases.csv"), expected=True)
    comp = run_cases(api, read(args.ref / "comparison_cases.csv"), expected=False)

    metrics = compute(pos, neg, cases, comp, api.dataset_version, args.api)
    for name, rows in (("pairs_positive", pos), ("pairs_negative", neg)):
        (args.out / f"{name}.json").write_text(json.dumps(rows, indent=1))
    (args.out / "cases_cascade.json").write_text(json.dumps(cases, indent=1))
    (args.out / "cases_comparison.json").write_text(json.dumps(comp, indent=1))
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=1))
    print(json.dumps(metrics, indent=1))


if __name__ == "__main__":
    import sys

    if sys.argv[1:2] == ["--verify"]:
        raise SystemExit(verify(Path(sys.argv[2])))
    if sys.argv[1:2] == ["--compare"]:
        raise SystemExit(compare(Path(sys.argv[2]), Path(sys.argv[3])))
    main()
