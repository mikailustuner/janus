# ruff: noqa: E501 - long help strings and item labels
"""Expert validation packet (plan E, B3b): draw every sample, fix the order, assign the experts.

Follows the pre-registered protocol `docs/research/expert-validation-protocol.md` sections 4 and 5
with Amendment 1: every sample is drawn with seed 20261113 (one stream per draw, named after it), each
section gets one fixed random order (C2: one per source, alternating), items go round-robin to two
experts of the section's groups under the 3 h 45 min cap (A1, A2, B: one geriatrician or family
physician and one clinical pharmacist), and items that cannot get two experts are dropped from the
end of the order. C1 takes ClinicalTrials.gov values from the current release and PubMed Central and
Drugs@FDA values from the B3a fresh samples P2 and D2 (`data/validation/modelkit/items.csv`, excerpts
from the private B3a research data); C2 takes PubMed Central articles of the P2 frame.

    uv run --project pipelines python pipelines/tools/validation_packet_sample.py OUT_DIR \
        [--private-root PATH] [--pharmacologists 2 --clinicians 2 --pharmacists 2] [--reads E03=tr ...]

OUT_DIR (private, never committed) receives:
- items.json   what experts see, per section and item id (blinded: no reference label, source of a
               pair, strict-check level, sampling stratum, automated verdict or confidence);
- key.json     the private key per item (reference label, B1 result, study, automated verdicts, ...);
- mapping.json experts (identifier and group, never a name), items per expert, minutes, assignment,
               dropped items, input hashes;
- answers/E01.csv, answers/E01.xlsx, ... one answer file per expert with only that expert's items.

A sample that its frame cannot fill as the protocol says stops the run with an error; nothing is
ever drawn differently from the protocol.
Research use only. Not for clinical decisions. Expert review has not yet been done.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from janus_pipelines.expert_validation import (
    CAP_MINUTES,
    GROUPS,
    MINUTES,
    PROTOCOL,
    SECTIONS,
    SEED,
    Expert,
    assign,
    columns_for,
    make_experts,
    write_csv,
    write_xlsx,
)

REPO = Path(__file__).resolve().parents[2]
SIZES = {"A1_positive": 60, "A1_negative": 40, "A2": 40, "D": 24, "E_per_country": 30}
C1_QUOTA = {"clinicaltrials_gov": 30, "pmc_oa": 10, "drugsatfda_review": 10}
C1_PER_STUDY = 2
C2_QUOTA = {"clinicaltrials_gov": 10, "pmc_oa": 10}
COUNTRIES = {"ca_dpd": "CA", "eu_it_aifa": "IT"}
# Section B: the texts under review (protocol section 4), each (id, where it is read).
# "web:" keys are in apps/web/messages/<lang>.json, "note:" ids in the note sentences file.
B_TEXTS: list[tuple[str, list[str]]] = [
    ("card_found", ["web:Findings.sections.found", "web:Findings.pattern", "web:Findings.cascade"]),
    ("card_why", ["web:Findings.sections.why", "web:Findings.why"]),
    (
        "card_todo",
        ["web:Findings.sections.todo", "web:Findings.discuss", "web:Findings.selfChange"],
    ),
    ("screening", ["web:Memory.screening"]),
    ("abrupt_patient", ["web:Report.abrupt.title"]),
    ("abrupt_note", ["note:abrupt_stop"]),
    ("emergency_patient", ["web:Emergency.title", "web:Emergency.text"]),
    ("emergency_line", ["web:Emergency.line"]),
    ("emergency_note", ["note:safety.heading", "note:safety.emergency_first"]),
    ("note_purpose", ["note:header.title", "note:header.purpose", "note:disclaimer"]),
    ("note_finding", ["note:findings.heading", "note:finding.cascade"]),
    ("note_timing_within", ["note:finding.timing.within_window"]),
    ("note_timing_after", ["note:finding.timing.after_window"]),
    ("note_review", ["note:finding.review"]),
    (
        "note_form_unconfirmed",
        ["note:findings_form_unconfirmed.heading", "note:findings_form_unconfirmed.explanation"],
    ),
    ("note_reports", ["note:statistics.heading", "note:stat.reports_ratio"]),
    ("note_disproportionate", ["note:stat.assessment.disproportionate"]),
    ("note_not_disproportionate", ["note:stat.assessment.not_disproportionate"]),
    ("note_screening", ["note:stat.screening"]),
    ("note_absence", ["note:stat.absence"]),
    ("note_no_pattern", ["note:scope.heading", "note:scope.no_pattern"]),
    ("outcome_loop", ["note:outcome_loop.heading", "note:outcome_loop.how"]),
    ("outcome_intro", ["note:outcome.heading", "note:outcome.intro"]),
    (
        "outcome_assessment",
        [
            "note:outcome.question.assessment",
            "note:outcome.option.confirmed",
            "note:outcome.option.not_a_cascade",
        ],
    ),
    (
        "outcome_action",
        [
            "note:outcome.question.action",
            "note:outcome.option.dose_changed",
            "note:outcome.option.medicine_changed",
            "note:outcome.option.stopped",
            "note:outcome.option.no_change",
        ],
    ),
]
PROTOCOL_INPUTS = [  # committed inputs that must be as at the commit registering the protocol
    "data/validation/cascades/positive_pairs.csv",
    "data/validation/cascades/negative_pairs.csv",
    "data/validation/cascades/results/pairs_positive.json",
    "data/validation/cascades/results/pairs_negative.json",
    "data/cascade_classes.csv",
    "data/pipc_rules.csv",
    "data/pipc.csv",
    "apps/web/messages/en.json",
    "apps/web/messages/tr.json",
    "apps/api/janus/notes/glossary/sentences.csv",
    "data/validation/modelkit/items.csv",
]


class ShortfallError(Exception):
    """The frame cannot fill a sample as the protocol says."""


@dataclass
class Item:
    section: str
    label: str
    show: dict[str, Any]
    key: dict[str, Any]
    language: str | None = None
    item_id: str = ""


@dataclass
class Draw:
    items: dict[str, list[Item]] = field(default_factory=dict)
    frames: dict[str, Any] = field(default_factory=dict)


def rng(name: str) -> random.Random:
    """One random stream per draw, seeded with the protocol seed and the draw's name."""
    return random.Random(f"{SEED}:{name}")  # noqa: S311 - sampling, not cryptography


def ordered(section: str, items: list[Item]) -> list[Item]:
    """The section's fixed random order; item ids follow it (A1-001, A1-002, ...). C2 (Amendment 1):
    each source has its own fixed random order and the section alternates between the sources."""
    if section == "C2":
        queues: list[list[Item]] = []
        for src in C2_QUOTA:
            q = [it for it in items if it.key["source"] == src]
            rng(f"C2:{src}:order").shuffle(q)
            queues.append(q)
        out = [q[i] for i in range(max(map(len, queues), default=0)) for q in queues if i < len(q)]
    else:
        out = list(items)
        rng(f"{section}:order").shuffle(out)
    for i, it in enumerate(out, start=1):
        it.item_id = f"{section}-{i:03d}"
    return out


def sample(name: str, rows: Sequence[Any], n: int) -> list[Any]:
    if len(rows) < n:
        raise ShortfallError(f"{name}: needs {n}, the frame has {len(rows)}")
    return rng(name).sample(list(rows), n)


# ---------------------------------------------------------------- section draws


def draw_a1(
    positives: Sequence[Mapping[str, str]],
    negatives: Sequence[Mapping[str, str]],
    flagged: Mapping[str, bool | None],
) -> list[Item]:
    """60 positives and 40 negatives, simple random, mixed in one order without label or source."""

    def item(r: Mapping[str, str], ref: str, pid: str, b: str, atc_b: str) -> Item:
        show = {"drug_a": r["drug_a"], "atc_a": r["atc_a"], "drug_b": b, "atc_b": atc_b}
        label = f"{r['drug_a']} ({r['atc_a']}) -> {b} ({atc_b})"
        key = {"reference": ref, "pair_id": pid, "b1_flagged": flagged.get(pid)}
        if ref == "positive":
            key |= {"adverse_event": r["adverse_event"], "sources": r["sources"]}
        else:
            key |= {"from_pair_id": r["from_pair_id"]}
        return Item("A1", label, show, key)

    pos = sorted(positives, key=lambda r: r["pair_id"])
    neg = sorted(negatives, key=lambda r: r["neg_id"])
    out = [item(r, "positive", r["pair_id"], r["drug_b"], r["atc_b"])
           for r in sample("A1:positives", pos, SIZES["A1_positive"])]  # fmt: skip
    out += [item(r, "negative", r["neg_id"], r["drug_b_prime"], r["atc_b_prime"])
            for r in sample("A1:negatives", neg, SIZES["A1_negative"])]  # fmt: skip
    return out


def draw_a2(
    classes: Sequence[Mapping[str, str]],
    rules: Sequence[Mapping[str, str]],
    pipc: Sequence[Mapping[str, str]],
) -> list[Item]:
    """40 class rows with match = include; each shown with the PIPC rows that use its class."""
    published = {r["position"]: r for r in pipc}
    frame = sorted((r for r in classes if r["match"] == "include"),
                   key=lambda r: (r["class_id"], r["pattern"]))  # fmt: skip
    out: list[Item] = []
    for r in sample("A2", frame, SIZES["A2"]):
        uses: list[dict[str, str]] = []
        for rule in rules:
            for role, col in (("first", "index_class"), ("second", "marker_class")):
                if rule[col] == r["class_id"]:
                    p = published[rule["position"]]
                    uses.append({"row": rule["position"], "role": role, "drug_a": p["drug_a"],
                                 "adverse_event": p["adverse_event"], "drug_b": p["drug_b"]})  # fmt: skip
        show = {"class_id": r["class_id"], "pattern": r["pattern"], "rows": uses}
        key = {"scope": r["scope"], "basis": r["basis"]}
        out.append(Item("A2", f"{r['class_id']}: {r['pattern']}", show, key))
    return out


def _lookup(
    spec: str, web: Mapping[str, Any], note: Mapping[str, Mapping[str, str]], lang: str
) -> str:
    kind, _, ref = spec.partition(":")
    if kind == "note":
        return note[ref][lang]
    o: Any = web
    for p in ref.split("."):
        o = o[p]
    if not isinstance(o, str):
        raise ValueError(f"{spec}: not a text")
    return o


def texts_b(
    web: Mapping[str, Mapping[str, Any]], note: Mapping[str, Mapping[str, str]]
) -> list[Item]:
    """All texts of section B, once per language."""
    out: list[Item] = []
    for tid, specs in B_TEXTS:
        for lang in ("en", "tr"):
            parts = [_lookup(s, web[lang], note, lang) for s in specs]
            show = {"text_id": tid, "parts": parts}
            out.append(
                Item("B", f"[{lang}] {tid}: {' | '.join(parts)}", show, {"sources": specs}, lang)
            )
    return out


def _link(source: str, study: str, locator: str) -> str:
    if source == "clinicaltrials_gov":
        return f"https://clinicaltrials.gov/study/{study}"
    if source == "pmc_oa":
        return f"https://pmc.ncbi.nlm.nih.gov/articles/{study}/"
    url = locator.split(" ")[0]
    return url.replace("http://", "https://", 1)


C1_SHOW = ["drug_key", "analyte", "parameter", "value", "value_low", "value_high", "statistic", "unit",
           "dose", "dose_unit", "route", "regimen", "interval_h", "population", "n_subjects", "formulation",
           "food", "coadministered", "source_locator", "source_version", "quote", "derivation"]  # fmt: skip


def value_key(r: Mapping[str, Any]) -> str:
    return "|".join(
        str(r.get(k, "")) for k in ("source_id", "source_locator", "parameter", "analyte", "value")
    )


def draw_c1(
    frame: Sequence[Mapping[str, Any]],
    auto: Mapping[tuple[str, str], tuple[str, str]],
) -> list[Item]:
    """50 values, 30/10/10 by source, at most 2 per study (Amendment 1: ClinicalTrials.gov from the
    current release, PubMed Central and Drugs@FDA from the B3a samples P2 and D2). Per source the
    values are taken in a seeded random order, skipping a value whose study already gave 2. A row
    may carry its own `automated_verdicts` (B3a samples); otherwise they are looked up in `auto`."""
    out: list[Item] = []
    short: list[str] = []
    for src, n in C1_QUOTA.items():
        rows = sorted((r for r in frame if r["source_id"] == src), key=value_key)
        rng(f"C1:{src}").shuffle(rows)
        per: dict[str, int] = {}
        got: list[Mapping[str, Any]] = []
        for r in rows:
            if len(got) == n:
                break
            if per.get(r["study_id"], 0) < C1_PER_STUDY:
                per[r["study_id"]] = per.get(r["study_id"], 0) + 1
                got.append(r)
        if len(got) < n:
            studies = len({r["study_id"] for r in rows})
            short.append(f"C1 {src}: needs {n} values (at most {C1_PER_STUDY} per study); the frame has "
                         f"{len(rows)} values in {studies} studies, so at most {len(got)}")  # fmt: skip
            continue
        for r in got:
            show = {k: r.get(k) for k in C1_SHOW}
            show["link"] = r.get("link") or _link(src, r["study_id"], r["source_locator"])
            v = r.get("automated_verdicts") or auto.get(
                (r["source_locator"], f"{float(r['value']):g}")
            )
            key = {"source": src, "frame": r.get("frame", "release"), "study": r["study_id"],
                   "value_key": value_key(r), "automated_verdicts": list(v) if v else None}  # fmt: skip
            label = f"{r['drug_key']} {r['parameter']} {float(r['value']):g} {r['unit']} ({r['study_id']})"
            out.append(Item("C1", label, show, key))
    if short:
        raise ShortfallError("; ".join(short))
    return out


def draw_c2(frame: Sequence[Mapping[str, Any]]) -> list[Item]:
    """20 documents: 10 ClinicalTrials.gov results records with a confirmed value in the current
    release and 10 PubMed Central articles of the B3a P2 frame (Amendment 1). `frame` holds the
    confirmed values of both; the order (one per source, alternating) is set by `ordered`."""
    docs: dict[str, dict[str, list[Mapping[str, Any]]]] = {s: {} for s in C2_QUOTA}
    for r in frame:
        if r["source_id"] in C2_QUOTA:
            docs[r["source_id"]].setdefault(r["study_id"], []).append(r)
    short = [f"C2 {s}: needs {n} documents with a confirmed value; the frame has {len(docs[s])}"
             for s, n in C2_QUOTA.items() if len(docs[s]) < n]  # fmt: skip
    if short:
        raise ShortfallError("; ".join(short))
    out: list[Item] = []
    for src, n in C2_QUOTA.items():
        for doc in sample(f"C2:{src}", sorted(docs[src]), n):
            rows = docs[src][doc]
            show = {"document": doc, "link": _link(src, doc, str(rows[0]["source_locator"]))}
            key = {"source": src, "confirmed": [
                {"drug": r["drug_key"], "parameter": r["parameter"], "value": r["value"], "unit": r["unit"],
                 "value_key": value_key(r)} for r in sorted(rows, key=value_key)]}  # fmt: skip
            out.append(Item("C2", doc, show, key))
    return out


def _pmc_excerpt(se: Mapping[str, Any]) -> str:
    """Article, table caption, its header rows and the row of the value (B3a excerpt)."""
    rows: list[str] = list(se["table_rows"])
    m = re.search(r"row (\d+)", str(se.get("cell", "")))
    i = int(m.group(1)) if m else len(rows) - 1
    keep = rows[: min(2, i)] + rows[i : i + 1]
    foot = f" | {se['footnotes']}" if se.get("footnotes") else ""
    return f"{se['article']} | {se['table']} | " + " / ".join(keep) + foot


def _fda_excerpt(se: Mapping[str, Any]) -> str:
    """Document, page and the lines up to the value's line (marked >>> in the B3a excerpt)."""
    lines = str(se["page_text"]).splitlines()
    i = next((k for k, x in enumerate(lines) if x.lstrip().startswith(">>>")), len(lines) - 1)
    near = [" ".join(x.replace(">>>", "").split()) for x in lines[max(0, i - 4) : i + 1]]
    return f"{se['document']}, page {se['page']} | " + " / ".join(x for x in near if x)


def load_b3a(items_csv: Path, b3a: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """C1 rows of the B3a fresh samples P2 and D2 (value, context and excerpt as the B3a reviewers
    saw them; the two automated verdicts kept for the key) and the confirmed values of the P2
    frame's articles from the B3a documents run (for C2)."""
    import polars as pl

    verdicts = {r["item_id"]: r for r in read_csv(items_csv) if r["sample"] in ("P2", "D2")}
    c1: list[dict[str, Any]] = []
    for tag, src in (("P2", "pmc_oa"), ("D2", "drugsatfda_review")):
        keys = {k["id"]: k for k in json.loads((b3a / f"{tag}_key.json").read_text("utf-8"))}
        for it in json.loads((b3a / f"{tag}_items.json").read_text("utf-8")):
            k, v, c = keys[it["id"]], verdicts[it["id"]], it["claim"]
            parent = str(c.get("analyte_claimed", "")).startswith("the parent drug")
            c1.append({
                "source_id": src, "frame": tag, "study_id": k["study_id"], "source_locator": k["locator"],
                "drug_key": c["drug"], "analyte": c["drug"] if parent else c.get("analyte_claimed"),
                "parameter": k["parameter"], "value": float(c["value"]), "unit": c["unit_as_stated"],
                "statistic": None, "dose": c.get("dose_mg_claimed"), "dose_unit": "mg" if c.get("dose_mg_claimed") else None,
                "route": c.get("route_claimed"), "regimen": c.get("regimen_claimed"),
                "population": c.get("population_claimed"), "formulation": c.get("formulation_claimed"),
                "food": c.get("food_claimed"), "coadministered": c.get("other_active_drug_in_arm_claimed"),
                "source_version": "", "link": _link(src, k["study_id"], str(k["doc"])) if src == "pmc_oa" else str(k["doc"]),
                "quote": _pmc_excerpt(it["source_excerpt"]) if src == "pmc_oa" else _fda_excerpt(it["source_excerpt"]),
                "automated_verdicts": [v["verdict_1"], v["verdict_2"]],
            })  # fmt: skip
    articles = {r["study"] for r in verdicts.values() if r["sample"] == "P2"}
    run = b3a / "data" / "artifacts" / "modelkit_documents" / "current" / "rows.parquet"
    df = pl.read_parquet(run).filter(pl.col("confirmed") & (pl.col("source_id") == "pmc_oa"))
    c2 = [r for r in df.to_dicts() if str(r["source_locator"]).split("#")[0] in articles]
    for r in c2:
        r["study_id"] = str(r["source_locator"]).split("#")[0]
    return c1, c2


def draw_d(atlas: Sequence[Mapping[str, Any]]) -> list[Item]:
    """24 of the 80 atlas rows; the automated flags stay in the key."""
    out: list[Item] = []
    for r in sample("D", sorted(atlas, key=lambda r: r["row"]), SIZES["D"]):
        show = {k: r[k] for k in ("drug", "quote", "cut", "measure", "kind", "measure_ratio", "measure_change",
                                  "atlas_ratio", "atlas_change", "set_id", "version")}  # fmt: skip
        key = {"row": r["row"], "flags": r["flags"], "numeric": r["numeric"]}
        out.append(Item("D", str(r["drug"]), show, key))
    return out


def draw_e(ca_it: Sequence[Mapping[str, str]], es: Sequence[Mapping[str, Any]]) -> list[Item]:
    """30 proposals per country among the rows with a proposed group."""
    out: list[Item] = []
    for src, country in COUNTRIES.items():
        frame = sorted((r for r in ca_it if r["source_id"] == src and r["group"]),
                       key=lambda r: (r["published_form"], r["route"]))  # fmt: skip
        for r in sample(f"E:{country}", frame, SIZES["E_per_country"]):
            show = {"country": country, "form": r["published_form"], "route": r["route"],
                    "group": r["group"], "examples": r["evidence_examples"]}  # fmt: skip
            key = {"country": country, "confidence": r["confidence"], "rule": r["rule"],
                   "n_products": r["n_products"]}  # fmt: skip
            out.append(
                Item(
                    "E",
                    f"{country}: {r['published_form']} / {r['route']} -> {r['group']}",
                    show,
                    key,
                )
            )
    frame_es = sorted((r for r in es if r["group"]), key=lambda r: (r["form"], r["routes_seen"]))
    for r in sample("E:ES", frame_es, SIZES["E_per_country"]):
        show = {"country": "ES", "form": r["form"], "route": r["routes_seen"], "group": r["group"],
                "examples": ""}  # fmt: skip
        key = {"country": "ES", "reason": r["reason"], "n_products": r["n"]}
        out.append(Item("E", f"ES: {r['form']} / {r['routes_seen']} -> {r['group']}", show, key))
    return out


def all_f(method20: Sequence[Mapping[str, Any]]) -> list[Item]:
    """All 20 drugs; the evidence class of each parameter (a confidence grade) stays in the key."""
    out: list[Item] = []
    for d in sorted(method20, key=lambda d: d["key"]):
        show = {k: v for k, v in d.items() if k != "params"}
        show["params"] = [{k: v for k, v in p.items() if k != "cls"} for p in d["params"]]
        key = {"drug": d["key"], "classes": {p["name"]: p.get("cls") for p in d["params"]}}
        out.append(Item("F", str(d["name"]), show, key))
    return out


# ---------------------------------------------------------------- loading


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_release(release: Path) -> tuple[list[dict[str, Any]], str]:
    """Confirmed values of the evidence release (rows.parquet of a modelkit_evidence run)."""
    import polars as pl

    run = json.loads((release / "manifest.json").read_text("utf-8"))["run_id"]
    df = pl.read_parquet(release / "rows.parquet").filter(pl.col("confirmed"))
    return df.to_dicts(), str(run)


def load_auto(items_csv: Path, keys_dir: Path | None) -> dict[tuple[str, str], tuple[str, str]]:
    """(locator, value) -> the two automated review verdicts of B3a, where a sample reviewed it."""
    if keys_dir is None or not keys_dir.is_dir():
        return {}
    verdicts = {r["item_id"]: (r["verdict_1"], r["verdict_2"]) for r in read_csv(items_csv)}
    out: dict[tuple[str, str], tuple[str, str]] = {}
    for p in sorted(keys_dir.glob("**/*_key.json")):
        for k in json.loads(p.read_text("utf-8")):
            if k.get("id") in verdicts and "locator" in k and "value" in k:
                out[(str(k["locator"]), f"{float(k['value']):g}")] = verdicts[k["id"]]
    return out


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol_commit() -> tuple[str, list[str], str]:
    """The commit that registered the protocol, the committed inputs changed since then, and the
    last commit that changed the protocol (its amendments)."""
    git = ["git", "-C", str(REPO)]
    commit = subprocess.run([*git, "log", "--diff-filter=A", "--format=%H", "--", PROTOCOL],  # noqa: S603
                            capture_output=True, text=True, check=True).stdout.split()  # fmt: skip
    if not commit:
        raise SystemExit(f"{PROTOCOL} is not committed")
    changed = subprocess.run([*git, "diff", "--name-only", commit[-1], "--", *PROTOCOL_INPUTS],  # noqa: S603
                             capture_output=True, text=True, check=True).stdout.split()  # fmt: skip
    return commit[-1], changed, commit_last_change(git)


def commit_last_change(git: list[str]) -> str:
    return subprocess.run([*git, "log", "-1", "--format=%H", "--", PROTOCOL],  # noqa: S603
                          capture_output=True, text=True, check=True).stdout.strip()  # fmt: skip


# ---------------------------------------------------------------- output


def expert_rows(
    eid: str, items: Mapping[str, list[Item]], mine: Mapping[str, list[str]]
) -> list[dict[str, str]]:
    by_id = {it.item_id: it for s in items for it in items[s]}
    return [{"expert_id": eid, "section": s, "item_id": i, "item": by_id[i].label}
            for s in SECTIONS for i in mine.get(s, [])]  # fmt: skip


README_NOTE = (
    "Fill one row per item: choose from the drop-down lists, write comments in the text columns.\n"
    "Section C2: one row per value you mark (drug, parameter, value, unit, population); leave unused rows empty.\n"
    "Her madde için bir satır doldurun: açılır listelerden seçin, yorumları metin sütunlarına yazın.\n"
    "Bölüm C2: işaretlediğiniz her değer için bir satır (ilaç, parametre, değer, birim, popülasyon); kullanılmayan satırları boş bırakın."
)


def build(
    draw: Draw, experts: Sequence[Expert]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """items.json, key.json and mapping.json content."""
    order = {s: [(it.item_id, it.language) for it in draw.items[s]] for s in draw.items}
    res = assign(order, experts, CAP_MINUTES)
    items_json = {
        "protocol": PROTOCOL,
        "sections": {s: [{"item_id": it.item_id, "language": it.language, "label": it.label, "show": it.show}
                         for it in draw.items[s]] for s in SECTIONS if s in draw.items},
    }  # fmt: skip
    key_json = {
        s: {it.item_id: it.key for it in draw.items[s]} for s in SECTIONS if s in draw.items
    }
    per: dict[str, dict[str, list[str]]] = {e.id: {} for e in experts}
    for s, assigned in res.assigned.items():
        for item_id, ids in assigned.items():
            for eid in ids:
                per[eid].setdefault(s, []).append(item_id)
    mapping = {
        "protocol": PROTOCOL,
        "seed": SEED,
        "cap_minutes": CAP_MINUTES,
        "minutes_per_item": MINUTES,
        "frames": draw.frames,
        "drawn": {s: len(draw.items[s]) for s in SECTIONS if s in draw.items},
        "experts": [
            {"id": e.id, "group": e.group, "languages": sorted(e.languages),
             "minutes": round(res.minutes[e.id], 1),
             "items": {s: len(v) for s, v in per[e.id].items()}, "item_ids": per[e.id]}
            for e in experts
        ],
        "assignment": res.assigned,
        "dropped": {s: v for s, v in res.dropped.items() if v},
        "judged": {s: len(v) for s, v in res.assigned.items()},
    }  # fmt: skip
    return items_json, key_json, mapping


def write(out: Path, draw: Draw, experts: Sequence[Expert]) -> dict[str, Any]:
    items_json, key_json, mapping = build(draw, experts)
    (out / "answers").mkdir(parents=True, exist_ok=True)
    for name, obj in (
        ("items.json", items_json),
        ("key.json", key_json),
        ("mapping.json", mapping),
    ):
        (out / name).write_text(
            json.dumps(obj, indent=1, ensure_ascii=False, default=str) + "\n", "utf-8"
        )
    for e in mapping["experts"]:
        rows = expert_rows(e["id"], draw.items, e["item_ids"])
        cols = columns_for([s for s in SECTIONS if s in e["item_ids"]])
        write_csv(out / "answers" / f"{e['id']}.csv", rows, cols)
        write_xlsx(out / "answers" / f"{e['id']}.xlsx", e["id"], rows, README_NOTE)
    return mapping


def parse_reads(specs: Sequence[str]) -> dict[str, frozenset[str]]:
    out: dict[str, frozenset[str]] = {}
    for s in specs:
        eid, _, langs = s.partition("=")
        out[eid] = frozenset(x for x in langs.split(",") if x)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Draw the expert validation packet samples (protocol sections 4-5)."
    )
    ap.add_argument("out", type=Path, help="private output directory (never committed)")
    ap.add_argument("--private-root", type=Path, default=REPO,
                    help="checkout that holds docs/internal and .data (default: this checkout)")  # fmt: skip
    ap.add_argument(
        "--release",
        type=Path,
        help="modelkit_evidence run directory (default: the current release)",
    )
    ap.add_argument("--pharmacologists", type=int, default=2)
    ap.add_argument("--clinicians", type=int, default=2, help="geriatricians or family physicians")
    ap.add_argument("--pharmacists", type=int, default=2)
    ap.add_argument("--reads", action="append", default=[], metavar="E03=en,tr",
                    help="languages an expert reads for section B (default: en and tr)")  # fmt: skip
    a = ap.parse_args(argv)
    priv = a.private_root
    review = priv / "docs" / "internal" / "review"
    release = a.release or priv / ".data" / "artifacts" / "modelkit_evidence" / "current"
    b3a = priv / "docs" / "internal" / "research-data" / "modelkit-precision" / "b3a"
    commit, changed, amended = protocol_commit()
    if changed:
        ap.error(f"inputs changed since the protocol commit {commit[:7]}: {', '.join(changed)}")
    experts = make_experts(
        dict(zip(GROUPS, (a.pharmacologists, a.clinicians, a.pharmacists), strict=True)),
        parse_reads(a.reads),
    )
    paths = {
        "positives": REPO / "data/validation/cascades/positive_pairs.csv",
        "negatives": REPO / "data/validation/cascades/negative_pairs.csv",
        "b1_positive": REPO / "data/validation/cascades/results/pairs_positive.json",
        "b1_negative": REPO / "data/validation/cascades/results/pairs_negative.json",
        "classes": REPO / "data/cascade_classes.csv",
        "pipc_rules": REPO / "data/pipc_rules.csv",
        "pipc": REPO / "data/pipc.csv",
        "messages_en": REPO / "apps/web/messages/en.json",
        "messages_tr": REPO / "apps/web/messages/tr.json",
        "sentences": REPO / "apps/api/janus/notes/glossary/sentences.csv",
        "atlas_high": review / "expert-packet/data/atlas_high.json",
        "forms_ca_it": review / "expert-packet/dose-form-proposals-ca-it.csv",
        "forms_es": review / "expert-packet/data/es_form_proposals.json",
        "method20": review / "modelkit-audit-packet/data/method20.json",
        "release_rows": release / "rows.parquet",
        "b3a_items": REPO / "data/validation/modelkit/items.csv",
        "b3a_p2_items": b3a / "P2_items.json",
        "b3a_p2_key": b3a / "P2_key.json",
        "b3a_d2_items": b3a / "D2_items.json",
        "b3a_d2_key": b3a / "D2_key.json",
        "b3a_documents_rows": b3a / "data/artifacts/modelkit_documents/current/rows.parquet",
    }
    flagged: dict[str, bool | None] = {}
    for k in ("b1_positive", "b1_negative"):
        for p in json.loads(paths[k].read_text("utf-8")):
            flagged[p["id"]] = None if p.get("error") else bool(p["flagged"])
    note = {r["id"]: r for r in read_csv(paths["sentences"])}
    web = {lg: json.loads(paths[f"messages_{lg}"].read_text("utf-8")) for lg in ("en", "tr")}
    frame, run_id = load_release(release)
    b3a_c1, b3a_c2 = load_b3a(paths["b3a_items"], b3a)
    ctgov = [r for r in frame if r["source_id"] == "clinicaltrials_gov"]
    auto = load_auto(paths["b3a_items"], priv / "docs/internal/research-data/modelkit-precision")
    draw = Draw()
    try:
        draw.items["A1"] = draw_a1(
            read_csv(paths["positives"]), read_csv(paths["negatives"]), flagged
        )
        draw.items["A2"] = draw_a2(
            read_csv(paths["classes"]), read_csv(paths["pipc_rules"]), read_csv(paths["pipc"])
        )
        draw.items["B"] = texts_b(web, note)
        draw.items["C1"] = draw_c1(ctgov + b3a_c1, auto)
        draw.items["C2"] = draw_c2(ctgov + b3a_c2)
        draw.items["D"] = draw_d(json.loads(paths["atlas_high"].read_text("utf-8")))
        draw.items["E"] = draw_e(
            read_csv(paths["forms_ca_it"]), json.loads(paths["forms_es"].read_text("utf-8"))
        )
        draw.items["F"] = all_f(json.loads(paths["method20"].read_text("utf-8")))
    except ShortfallError as e:
        print(f"cannot draw as the protocol says: {e}", file=sys.stderr)
        return 2
    for s in list(draw.items):
        draw.items[s] = ordered(s, draw.items[s])
    draw.frames = {
        "protocol_commit": commit,
        "protocol_amended_in": amended,
        "c1_frames": "clinicaltrials_gov: current release; pmc_oa: B3a sample P2; drugsatfda_review: B3a sample D2 (Amendment 1)",
        "c2_frames": "clinicaltrials_gov: current release; pmc_oa: articles of the B3a P2 frame (Amendment 1)",
        "release": run_id,
        "release_confirmed_by_source": {s: sum(r["source_id"] == s for r in frame) for s in sorted({r["source_id"] for r in frame})},
        "inputs": {k: {"path": str(p.relative_to(REPO) if p.is_relative_to(REPO) else p.relative_to(priv)), "sha256": sha256(p)}
                   for k, p in paths.items()},
        "automated_verdicts_known": len(auto),
    }  # fmt: skip
    mapping = write(a.out, draw, experts)
    print(json.dumps({"drawn": mapping["drawn"], "dropped": mapping["dropped"],
                      "minutes": {e["id"]: e["minutes"] for e in mapping["experts"]}}, indent=1))  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
