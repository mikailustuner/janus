# ruff: noqa: E501 - long result keys
"""Score the filled answer files of the expert validation packet (plan E, B3b).

Applies sections 6 and 7 of the pre-registered protocol `docs/research/expert-validation-protocol.md`:
Cohen's kappa per section and question over the items each pair of experts judged (quadratic-weighted
on the 1-5 scales, 95 % interval by resampling items), consensus with a third expert, "not settled"
items, and every primary and secondary result with Wilson intervals. C1 (expert precision, tier 2)
reuses the B3a analysis (`precision_stats.summarise` and `modelkit_precision_report.summary_json`:
study-level cluster bootstrap, cluster-aware lower bound, acceptance >= 0.90); C2 recall gets a
document-level bootstrap. The older model kit audit scorer (`score_modelkit_audit.py`) is unchanged.

    uv run --project pipelines python pipelines/tools/score_validation_packet.py PACKET_DIR OUT_JSON ANSWERS [...]
    uv run --project pipelines python pipelines/tools/score_validation_packet.py PACKET_DIR --fill-synthetic DIR

PACKET_DIR is the private output of `validation_packet_sample.py` (mapping.json, key.json, items.json).
ANSWERS are filled answer files (CSV or XLSX), one or more per expert; answers of an expert who was not
assigned an item count as the third expert. `--fill-synthetic` writes randomly filled copies of every
answer file (a dry run of the scorer, never real answers). Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from janus_pipelines.expert_validation import (
    FIELDS,
    PROTOCOL,
    SCALE,
    SECTION_GROUPS,
    SECTIONS,
    SEED,
    check_value,
    columns_for,
    consensus,
    kappa,
    kappa_interval,
    read_answer_file,
    write_csv,
)
from janus_pipelines.modelkit.audit import wilson
from janus_pipelines.modelkit.precision_stats import Item, accepted, summarise
from janus_pipelines.modelkit.precision_stats import kappa as kappa3

HERE = Path(__file__).resolve().parent
THRESHOLD = 0.90  # B3a decision rule, applied to tier 2 as well (protocol section 7)
Answers = dict[str, dict[str, dict[str, list[dict[str, str]]]]]  # section -> item -> expert -> rows


def _sibling(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec is not None and spec.loader is not None  # noqa: S101 - file next to this one
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def share(k: int, n: int) -> dict[str, Any]:
    iv = wilson(k, n)
    return {"k": k, "n": n, "share": k / n if n else None, "wilson": list(iv) if iv else None}


# ---------------------------------------------------------------- reading


def load_packet(packet: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    def rd(name: str) -> dict[str, Any]:
        return json.loads((packet / name).read_text("utf-8"))

    return rd("mapping.json"), rd("key.json"), rd("items.json")


def load_answers(
    files: Sequence[Path], mapping: Mapping[str, Any], key: Mapping[str, Any]
) -> Answers:
    """Every answer row, checked: known expert and item, an expert of the section's groups, values of
    the scales, an error type for an incorrect C1 value, one row per item except in C2."""
    groups = {e["id"]: e["group"] for e in mapping["experts"]}
    out: Answers = defaultdict(lambda: defaultdict(dict))
    for path in files:
        rows = read_answer_file(path)
        ids = {r.get("expert_id", "").strip() for r in rows}
        if len(ids) != 1:
            raise ValueError(f"{path.name}: one expert_id per file, found {sorted(ids)}")
        eid = ids.pop()
        if eid not in groups:
            raise ValueError(f"{path.name}: unknown expert {eid!r}")
        for i, r in enumerate(rows, start=2):
            where = f"{path.name}:{i}"
            s, item = r.get("section", "").strip(), r.get("item_id", "").strip()
            if s not in SECTIONS or item not in key.get(s, {}):
                raise ValueError(f"{where}: unknown section or item {s!r} {item!r}")
            if groups[eid] not in SECTION_GROUPS[s]:
                raise ValueError(
                    f"{where}: {eid} ({groups[eid]}) is not in the groups of section {s}"
                )
            vals = {f.name: check_value(f, r.get(f.name) or "", where) for f in FIELDS[s]}
            if s == "C1" and vals["verdict"] == "incorrect" and not vals["error"]:
                raise ValueError(f"{where}: an incorrect value needs an error type")
            mine = out[s][item].setdefault(eid, [])
            if s == "C2":
                if vals["parameter"] or vals["value"]:
                    if not (vals["parameter"] and vals["value"]):
                        raise ValueError(f"{where}: a marked value needs a parameter and a value")
                    mine.append(vals)
                continue
            if mine:
                raise ValueError(f"{where}: {eid} answered {item} twice")
            mine.append(vals)
    return out


def answerers(section: str, item: str, mapping: Mapping[str, Any], ans: Answers) -> list[str]:
    """The assigned experts in assignment order, then any third expert (by identifier)."""
    first = list(mapping["assignment"].get(section, {}).get(item, []))
    return first + sorted(e for e in ans.get(section, {}).get(item, {}) if e not in first)


def value_of(section: str, item: str, eid: str, name: str, ans: Answers) -> str:
    rows = ans.get(section, {}).get(item, {}).get(eid, [])
    return rows[0][name] if rows else ""


# ---------------------------------------------------------------- consensus and agreement


def consensus_table(
    mapping: Mapping[str, Any], ans: Answers
) -> dict[str, dict[str, dict[str, tuple[str, str | None]]]]:
    """section -> question -> item -> (status, category) for every judged item."""
    out: dict[str, dict[str, dict[str, tuple[str, str | None]]]] = {}
    for s, assigned in mapping["assignment"].items():
        for f in FIELDS[s]:
            if not f.judged:
                continue
            col: dict[str, tuple[str, str | None]] = {}
            for item in assigned:
                vals = [value_of(s, item, e, f.name, ans) for e in answerers(s, item, mapping, ans)]
                col[item] = consensus([v for v in vals if v], f.kind)
            out.setdefault(s, {})[f.name] = col
    return out


def agreement(mapping: Mapping[str, Any], ans: Answers) -> dict[str, Any]:
    """Kappa per section and question for each pair of assigned experts, over the items both answered."""
    out: dict[str, Any] = {}
    for s, assigned in mapping["assignment"].items():
        by_pair: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for item, ids in assigned.items():
            by_pair[tuple(ids)].append(item)
        for f in FIELDS[s]:
            if not f.judged:
                continue
            res: list[dict[str, Any]] = []
            for pair, items in sorted(by_pair.items()):
                a, b = pair
                pairs = [
                    (value_of(s, i, a, f.name, ans), value_of(s, i, b, f.name, ans)) for i in items
                ]
                pairs = [(x, y) for x, y in pairs if x and y]
                w = f.kind == "scale"
                iv = kappa_interval(pairs, f.choices, w)
                res.append({"experts": list(pair), "n": len(pairs), "weighted": "quadratic" if w else None,
                            "kappa": kappa(pairs, f.choices, w), "ci95": list(iv) if iv else None})  # fmt: skip
            out.setdefault(s, {})[f.name] = res
    return out


def needs_third(
    mapping: Mapping[str, Any], table: Mapping[str, Any], ans: Answers
) -> list[dict[str, Any]]:
    groups = {e["id"]: e["group"] for e in mapping["experts"]}
    out: list[dict[str, Any]] = []
    for s, qs in table.items():
        for q, col in qs.items():
            for item, (status, _) in col.items():
                if status != "not_settled":
                    continue
                done = set(answerers(s, item, mapping, ans))
                free = sorted(
                    e for e, g in groups.items() if g in SECTION_GROUPS[s] and e not in done
                )
                out.append(
                    {"section": s, "item_id": item, "question": q, "eligible_third_experts": free}
                )
    return out


def status_counts(col: Mapping[str, tuple[str, str | None]]) -> dict[str, int]:
    c = Counter(st for st, _ in col.values())
    return {k: c[k] for k in ("agreed", "third", "not_settled")}


def comments(s: str, item: str, ans: Answers, names: Sequence[str]) -> list[str]:
    out: list[str] = []
    for rows in ans.get(s, {}).get(item, {}).values():
        for r in rows:
            out += [r[n] for n in names if r.get(n)]
    return out


# ---------------------------------------------------------------- results per section


def result_a1(table: Mapping[str, Any], key: Mapping[str, Any]) -> dict[str, Any]:
    col = table.get("A1", {}).get("realistic", {})
    pos = [i for i in col if key["A1"][i]["reference"] == "positive"]
    neg = [i for i in col if key["A1"][i]["reference"] == "negative"]
    hi = [i for i in pos if col[i][1] == "high"]
    lo = [i for i in neg if col[i][1] == "low"]
    sens = [i for i in hi if key["A1"][i]["b1_flagged"] is not None]
    spec = [i for i in lo if key["A1"][i]["b1_flagged"] is not None]
    return {
        "primary": {
            "positives_called_realistic": share(len(hi), len(pos))
            | status_counts({i: col[i] for i in pos}),
            "negatives_called_not_realistic": share(len(lo), len(neg))
            | status_counts({i: col[i] for i in neg}),
            "denominator": "all judged pairs of the reference class; not settled and 3 count as not called",
        },
        "secondary": {
            "b1_sensitivity_on_expert_confirmed_positives": share(
                sum(bool(key["A1"][i]["b1_flagged"]) for i in sens), len(sens)
            ),
            "b1_specificity_on_expert_confirmed_negatives": share(
                sum(not key["A1"][i]["b1_flagged"] for i in spec), len(spec)
            ),
            "note": "a sensitivity analysis of B1, not a replacement",
        },
    }


def result_yes(table: Mapping[str, Any], s: str, q: str, yes: str) -> dict[str, Any]:
    col = table.get(s, {}).get(q, {})
    return share(sum(v == yes for _, v in col.values()), len(col)) | status_counts(col)


def result_a2(table: Mapping[str, Any], items: Mapping[str, Any], ans: Answers) -> dict[str, Any]:
    col = table.get("A2", {}).get("describes_class", {})
    label = {it["item_id"]: it["label"] for it in items["sections"].get("A2", [])}
    return {
        "primary": {"rows_judged_correct": result_yes(table, "A2", "describes_class", "yes")},
        "secondary": {
            "rows_to_change": [{"item_id": i, "row": label[i], "comments": comments("A2", i, ans, ["comment"])}
                               for i, (_, v) in sorted(col.items()) if v == "no"],
            "not_settled": sorted(i for i, (st, _) in col.items() if st == "not_settled"),
        },
    }  # fmt: skip


def result_b(mapping: Mapping[str, Any], items: Mapping[str, Any], ans: Answers) -> dict[str, Any]:
    meta = {it["item_id"]: it for it in items["sections"].get("B", [])}
    texts: list[dict[str, Any]] = []
    for item in sorted(mapping["assignment"].get("B", {})):
        rows = [r for rs in ans.get("B", {}).get(item, {}).values() for r in rs]
        rated: dict[str, Any] = {}
        for q in ("accuracy", "harm", "clarity"):
            v = [int(r[q]) for r in rows if r[q]]
            rated[q] = {"n": len(v), "mean": sum(v) / len(v) if v else None,
                        "range": [min(v), max(v)] if v else None}  # fmt: skip
        harm = [int(r["harm"]) for r in rows if r["harm"]]
        texts.append({"item_id": item, "text_id": meta[item]["show"]["text_id"], "language": meta[item]["language"],
                      **rated, "rewrite_before_next_release": any(h >= 3 for h in harm),
                      "suggested_wording": [r["suggested_wording"] for r in rows if r["suggested_wording"]]})  # fmt: skip
    return {"primary": {"texts": texts},
            "secondary": {"rewrite": [t["item_id"] for t in texts if t["rewrite_before_next_release"]],
                          "rule": "every text rated risk of harm >= 3 by any expert is rewritten and goes back to one expert"}}  # fmt: skip


def result_c1(table: Mapping[str, Any], key: Mapping[str, Any], ans: Answers) -> dict[str, Any]:
    report = _sibling("modelkit_precision_report")
    col = table.get("C1", {}).get("verdict", {})
    per: dict[str, list[Item]] = defaultdict(list)
    errors: dict[str, Counter[str]] = defaultdict(Counter)
    auto_pairs: list[tuple[str, str]] = []
    for item, (status, v) in sorted(col.items()):
        k = key["C1"][item]
        if status == "not_settled":
            first = [r[0]["verdict"] for r in ans.get("C1", {}).get(item, {}).values() if r] + [
                "",
                "",
            ]
            per[k["source"]].append(Item(k["study"], k["source"], first[0], first[1]))
            continue
        assert v is not None  # noqa: S101 - settled
        per[k["source"]].append(Item(k["study"], k["source"], v, v))
        if v == "incorrect":
            named = {
                r["error"]
                for rs in ans["C1"][item].values()
                for r in rs
                if r["verdict"] == "incorrect"
            }
            for e in sorted(named - {""}):
                errors[k["source"]][e] += 1  # once per item, whatever the number of experts
        av = k.get("automated_verdicts")
        if av and av[0] == av[1]:
            auto_pairs.append((av[0], v))
    by_source = {}
    for src, its in sorted(per.items()):
        summ = summarise(its)
        res = report.summary_json(summ)
        del res[
            "kappa"
        ]  # both verdicts of an item are the consensus here; agreement is reported above
        by_source[src] = res | {
            "passes_decision_rule": accepted(summ, THRESHOLD),
            "errors_in_consensus": dict(sorted(errors[src].items())),
            "not_settled": sum(not it.agreed and it.verdict_1 != it.verdict_2 for it in its),
        }
    return {
        "primary": {"tier2_precision_by_source": by_source,
                    "rule": f"precision = correct / (correct + incorrect) of the consensus; a source passes if the cluster-aware lower 95 % bound is >= {THRESHOLD:.2f}"},
        "secondary": {"tier1_agreement_with_expert_consensus": {
            "n": len(auto_pairs),
            "kappa": kappa3([a for a, _ in auto_pairs], [b for _, b in auto_pairs]),
            "note": "values with two agreeing automated review verdicts of B3a and a settled expert consensus"}},
    }  # fmt: skip


def _norm(s: str) -> str:
    return "_".join(s.lower().replace("-", " ").split())


def _same(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    if a["parameter"] != b["parameter"]:
        return False
    x, y = float(a["value"]), float(b["value"])
    if abs(x - y) > 0.01 * max(abs(x), abs(y)):
        return False
    da, db = _norm(str(a.get("drug") or "")), _norm(str(b.get("drug") or ""))
    return not da or not db or da in db or db in da


def document_marks(
    marks: Mapping[str, Sequence[Mapping[str, str]]],
) -> tuple[list[set[str]], list[dict[str, str]]]:
    """Group the values the experts marked in one document: one group per value, holding the
    experts who marked it (same parameter, values within 1 %, same drug)."""
    groups: list[tuple[dict[str, str], set[str]]] = []
    for eid in sorted(marks):
        for m in marks[eid]:
            for rep, who in groups:
                if eid not in who and _same(rep, m):
                    who.add(eid)
                    break
            else:
                groups.append((dict(m), {eid}))
    return [who for _, who in groups], [rep for rep, _ in groups]


def result_c2(mapping: Mapping[str, Any], key: Mapping[str, Any], ans: Answers) -> dict[str, Any]:
    docs: dict[str, list[tuple[int, int]]] = defaultdict(list)
    missed: dict[str, Counter[str]] = defaultdict(Counter)
    single: Counter[str] = Counter()
    for item in sorted(mapping["assignment"].get("C2", {})):
        k = key["C2"][item]
        marks = {e: rows for e, rows in ans.get("C2", {}).get(item, {}).items()}
        whos, reps = document_marks(marks)
        confirmed = list(k["confirmed"])
        marked = matched = 0
        for who, rep in zip(whos, reps, strict=True):
            if len(who) < 2:
                single[k["source"]] += 1
                continue
            marked += 1
            hit = next((c for c in confirmed if _same(c, rep)), None)
            if hit is not None:
                confirmed.remove(hit)
                matched += 1
            else:
                missed[k["source"]][rep["parameter"]] += 1
        docs[k["source"]].append((matched, marked))
    out: dict[str, Any] = {}
    for src, rows in sorted(docs.items()):
        k_, n_ = sum(m for m, _ in rows), sum(n for _, n in rows)
        rnd = random.Random(SEED)  # noqa: S311 - resampling, not cryptography
        stats: list[float] = []
        for _ in range(4000):
            draw = [rows[rnd.randrange(len(rows))] for _ in rows]
            n = sum(x for _, x in draw)
            if n:
                stats.append(sum(x for x, _ in draw) / n)
        stats.sort()
        boot = (
            [
                stats[math.floor(0.025 * (len(stats) - 1))],
                stats[math.ceil(0.975 * (len(stats) - 1))],
            ]
            if stats
            else None
        )
        out[src] = share(k_, n_) | {"documents": len(rows), "document_bootstrap": boot,
                                    "marked_by_one_expert_only": single[src]}  # fmt: skip
    return {"primary": {"recall_by_source": out,
                        "rule": "values the readers confirmed / values two experts marked (same parameter, value within 1 %, same drug)"},
            "secondary": {"kinds_missed": {s: dict(sorted(c.items())) for s, c in sorted(missed.items())}}}  # fmt: skip


def result_e(
    table: Mapping[str, Any], key: Mapping[str, Any], items: Mapping[str, Any]
) -> dict[str, Any]:
    col = table.get("E", {}).get("decision", {})
    label = {it["item_id"]: it["label"] for it in items["sections"].get("E", [])}
    per: dict[str, Counter[str]] = defaultdict(Counter)
    acc: list[dict[str, str]] = []
    for item, (st, v) in sorted(col.items()):
        c = key["E"][item]["country"]
        per[c]["not_settled" if st == "not_settled" else str(v)] += 1
        if v == "accept":
            acc.append({"item_id": item, "proposal": label[item]})
    return {"primary": {c: {k: per[c][k] for k in ("accept", "reject", "unsure", "not_settled")} for c in sorted(per)},
            "secondary": {"accepted_rows_enter_product_data": acc}}  # fmt: skip


def result_f(table: Mapping[str, Any], key: Mapping[str, Any], ans: Answers) -> dict[str, Any]:
    ms = table.get("F", {}).get("method_sound", {})
    sj = table.get("F", {}).get("status_justified", {})
    drugs = [{"item_id": i, "drug": key["F"][i]["drug"], "method_sound": ms[i][1], "status_justified": sj.get(i, ("", None))[1]}
             for i in sorted(ms)]  # fmt: skip
    return {"primary": {"drugs": drugs},
            "secondary": {"open_questions": {i: comments("F", i, ans, ["unsound_parameters", "comment"]) for i in sorted(ms)
                                             if comments("F", i, ans, ["unsound_parameters", "comment"])}}}  # fmt: skip


def score(packet: Path, files: Sequence[Path]) -> dict[str, Any]:
    mapping, key, items = load_packet(packet)
    ans = load_answers(files, mapping, key)
    table = consensus_table(mapping, ans)
    out: dict[str, Any] = {
        "protocol": PROTOCOL,
        "note": "Scored from expert answer files. Results are reported next to B1, B2 and B3a; they do not change them.",
        "experts": dict(Counter(e["group"] for e in mapping["experts"])),
        "answer_files": len(files),
        "judged": mapping["judged"],
        "dropped": {s: len(v) for s, v in mapping["dropped"].items()},
        "held": mapping["held"],
        "agreement": agreement(mapping, ans),
        "consensus": {s: {q: status_counts(c) for q, c in qs.items()} for s, qs in table.items()},
        "needs_third_expert": needs_third(mapping, table, ans),
    }
    if "A1" in table:
        out["A1"] = result_a1(table, key)
    if "A2" in table:
        out["A2"] = result_a2(table, items, ans)
    if "B" in mapping["assignment"]:
        out["B"] = result_b(mapping, items, ans)
    if "C1" in table:
        out["C1"] = result_c1(table, key, ans)
    if "C2" in mapping["assignment"]:
        out["C2"] = result_c2(mapping, key, ans)
    if "D" in table:
        out["D"] = {"primary": {"sentences_judged_correct": result_yes(table, "D", "says_label", "yes"),
                                "right_direction": result_yes(table, "D", "direction", "yes")}}  # fmt: skip
    if "E" in table:
        out["E"] = result_e(table, key, items)
    if "F" in table:
        out["F"] = result_f(table, key, ans)
    return out


# ---------------------------------------------------------------- synthetic fill (dry run)


def synthetic_fill(packet: Path, out: Path, seed: int = SEED) -> list[Path]:
    """Randomly filled copies of every answer CSV of the packet (valid values only). C2 marks reuse
    some confirmed values of the key so that recall is not trivially 0. A dry run, never answers."""
    mapping, key, _ = load_packet(packet)
    rnd = random.Random(seed)  # noqa: S311 - test data
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for e in mapping["experts"]:
        src = packet / "answers" / f"{e['id']}.csv"
        rows = read_answer_file(src)
        filled: list[dict[str, str]] = []
        for r in rows:
            s = r["section"]
            if s == "C2":
                for c in key["C2"][r["item_id"]]["confirmed"][:4]:
                    if rnd.random() < 0.8:
                        filled.append(r | {"drug": c["drug"], "parameter": c["parameter"],
                                           "value": str(c["value"]), "unit": c["unit"], "population": ""})  # fmt: skip
                filled.append(r | {"drug": "x", "parameter": "tmax", "value": "1.5", "unit": "h"})
                continue
            v = dict(r)
            for f in FIELDS[s]:
                if f.kind == "scale":
                    v[f.name] = rnd.choice(SCALE[2:] if rnd.random() < 0.7 else SCALE)
                elif f.kind == "choice" and f.judged:
                    v[f.name] = f.choices[0] if rnd.random() < 0.75 else rnd.choice(f.choices)
            if s == "C1" and v["verdict"] == "incorrect":
                v["error"] = "value"
            filled.append(v)
        p = out / src.name
        sections = sorted({r["section"] for r in rows}, key=SECTIONS.index)
        write_csv(p, filled, columns_for(sections))
        written.append(p)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Score the expert validation packet (protocol sections 6-7)."
    )
    ap.add_argument("packet", type=Path)
    ap.add_argument("out", type=Path, nargs="?")
    ap.add_argument("answers", type=Path, nargs="*")
    ap.add_argument("--fill-synthetic", type=Path, metavar="DIR")
    a = ap.parse_args(argv)
    if a.fill_synthetic:
        for p in synthetic_fill(a.packet, a.fill_synthetic):
            print(p)
        return 0
    if not a.out or not a.answers:
        ap.error("give OUT_JSON and at least one answer file")
    result = score(a.packet, a.answers)
    a.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", "utf-8")
    print(
        json.dumps({s: result[s]["primary"] for s in SECTIONS if s in result}, ensure_ascii=False)[
            :3000
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
