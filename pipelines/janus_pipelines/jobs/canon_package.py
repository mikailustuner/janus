"""Assemble the séance claims of the Canon data package (séance design §3.6, Req 1.3-1.5, 4.2).

`python -m janus_pipelines.jobs.canon_package [--package DIR]`

Inputs in `datasets/canon/`: `theme_spans.csv` (the `canon` pipeline), `reader_ai.csv` (the AI
reader), `identifications.csv`, and the two labelled AI review passes (`review_historian.csv`,
`review_pharmacologist.csv`, `review_pharmacologist_identifications.csv`). Outputs:
`claims.csv` and `quality.json`. Pure assembly; the only I/O is in `main`.

No claim is ever marked as expert-reviewed here: `expert_review` stays `pending` until the
experts have reviewed it (Req 1.5).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

CONDITIONS: Final = ("wound", "burn", "ulcer", "infection")
OUT_OF_SCOPE: Final = "out_of_scope"
VERDICTS: Final = frozenset({"accept", "correct", "reject"})
ID_STATUSES: Final = frozenset({"matches_gold", "uncertain", "not_in_gold"})
HAZARDS: Final = frozenset({"", "toxic", "caustic"})
REVIEW_COLUMNS: Final = ("span_id", "verdict", "conditions", "machine_translation_en", "note")
ID_REVIEW_COLUMNS: Final = (
    "substance_id",
    "verdict",
    "status",
    "janus_identification",
    "hazard",
    "note",
)
CLAIM_COLUMNS: Final = (
    "claim_id",
    "span_id",
    "entry_id",
    "substance_id",
    "condition",
    "page",
    "line_start",
    "line_end",
    "arabic_span",
    "machine_translation_en",
    "use_en",
    "historian_verdict",
    "pharmacologist_verdict",
    "ai_review",
    "expert_review",
    "identification_status",
    "hazard",
    "headline_eligible",
)
SUBSTANCE_COLUMNS: Final = (
    "substance_id",
    "entry_id",
    "heading_ar",
    "transliteration",
    "name_en",
    "kind",
    "janus_identification",
    "gold_id",
    "gold_scientific_name",
    "hamdard_ref",
    "hamdard_identification",
    "status",
    "hazard",
    "note",
    "pharmacologist_note",
)
Row = Mapping[str, str]


class PackageError(ValueError):
    """An input file of the package is inconsistent."""


@dataclass(frozen=True)
class Review:
    verdict: str
    conditions: tuple[str, ...] | None  # None: unchanged
    translation: str | None
    note: str


def _split(value: str) -> tuple[str, ...]:
    return tuple(v for v in value.split("|") if v)


def _conditions(value: str, where: str) -> tuple[str, ...]:
    vals = _split(value)
    for v in vals:
        if v not in (*CONDITIONS, OUT_OF_SCOPE):
            raise PackageError(f"{where}: unknown condition {v!r}")
    if OUT_OF_SCOPE in vals and len(vals) > 1:
        raise PackageError(f"{where}: out_of_scope cannot be combined with a condition")
    return vals


def parse_reviews(rows: Sequence[Row], name: str, span_ids: set[str]) -> dict[str, Review]:
    out: dict[str, Review] = {}
    for r in rows:
        sid = r["span_id"]
        where = f"{name}: {sid}"
        if sid not in span_ids:
            raise PackageError(f"{where}: span not in reader_ai.csv")
        if sid in out:
            raise PackageError(f"{where}: reviewed twice")
        verdict = r["verdict"].strip()
        if verdict not in VERDICTS:
            raise PackageError(f"{where}: bad verdict {verdict!r}")
        note = r.get("note", "").strip()
        if verdict != "accept" and not note:
            raise PackageError(f"{where}: a {verdict} needs a note")
        cond = r.get("conditions", "").strip()
        tr = r.get("machine_translation_en", "").strip()
        out[sid] = Review(
            verdict=verdict,
            conditions=_conditions(cond, where) if cond else None,
            translation=tr or None,
            note=note,
        )
    missing = span_ids - set(out)
    if missing:
        raise PackageError(f"{name}: {len(missing)} span(s) not reviewed")
    return out


def final_conditions(reader: tuple[str, ...], a: Review, b: Review) -> tuple[str, ...]:
    """Conditions both passes leave standing: each pass's corrected list, or the reader's;
    a condition is kept only when no pass removed it (intersection)."""
    if "reject" in (a.verdict, b.verdict):
        return ()
    ca = a.conditions if a.conditions is not None else reader
    cb = b.conditions if b.conditions is not None else reader
    return tuple(c for c in CONDITIONS if c in ca and c in cb)


def final_translation(reader: str, historian: Review, pharmacologist: Review) -> str:
    """The historian owns translation fidelity; the pharmacologist's wording applies only when
    the historian left it unchanged."""
    return historian.translation or pharmacologist.translation or reader


@dataclass(frozen=True)
class Assembly:
    claims: list[dict[str, str]]
    substances: list[dict[str, str]]
    quality: dict[str, object]


def substance_rows(
    identifications: Sequence[Row],
    idrev: Mapping[str, Row],
    entries: Sequence[Row],
    gold: Sequence[Row],
) -> list[dict[str, str]]:
    """Identifications after the pharmacologist pass, with the gold name and the heading."""
    heading = {e["entry_id"]: e["heading"] for e in entries}
    gold_name = {g["gold_id"]: g["scientific_name"] for g in gold}
    out: list[dict[str, str]] = []
    for i in identifications:
        sid = i["substance_id"]
        rev = idrev[sid]
        if i["gold_id"] and i["gold_id"] not in gold_name:
            raise PackageError(f"identifications: {sid}: gold row not in the gold table")
        if i["entry_id"] not in heading:
            raise PackageError(f"identifications: {sid}: entry not in entries.csv")
        status = rev.get("status") or i["status"]
        if status == "matches_gold" and not i["gold_id"]:
            raise PackageError(f"identifications: {sid}: matches_gold without a gold row")
        out.append(
            {
                "substance_id": sid,
                "entry_id": i["entry_id"],
                "heading_ar": heading[i["entry_id"]],
                "transliteration": i["transliteration"],
                "name_en": i["name_en"],
                "kind": i["kind"],
                "janus_identification": rev.get("janus_identification")
                or i["janus_identification"],
                "gold_id": i["gold_id"],
                "gold_scientific_name": gold_name.get(i["gold_id"], ""),
                "hamdard_ref": i["hamdard_ref"],
                "hamdard_identification": i["hamdard_identification"],
                "status": status,
                "hazard": rev.get("hazard", ""),
                "note": i["note"],
                "pharmacologist_note": rev.get("note", ""),
            }
        )
    return sorted(out, key=lambda r: r["substance_id"])


def assemble(
    spans: Sequence[Row],
    reader: Sequence[Row],
    identifications: Sequence[Row],
    historian: Sequence[Row],
    pharmacologist: Sequence[Row],
    id_review: Sequence[Row],
    entries: Sequence[Row],
    gold: Sequence[Row] = (),
) -> Assembly:
    span_by_id = {s["span_id"]: s for s in spans}
    page_of = {e["entry_id"]: e["page"] for e in entries}
    ids = {i["substance_id"]: i for i in identifications}
    for i in identifications:
        if i["status"] not in ID_STATUSES:
            raise PackageError(f"identifications: {i['substance_id']}: bad status")
    reader_ids: set[str] = set()
    for r in reader:
        if r["span_id"] not in span_by_id:
            raise PackageError(f"reader_ai: {r['span_id']}: span not in theme_spans.csv")
        if r["substance_id"] not in ids:
            raise PackageError(f"reader_ai: {r['span_id']}: unknown substance")
        if span_by_id[r["span_id"]]["entry_id"] != ids[r["substance_id"]]["entry_id"]:
            raise PackageError(f"reader_ai: {r['span_id']}: substance is from another entry")
        reader_ids.add(r["span_id"])
    hist = parse_reviews(historian, "review_historian", reader_ids)
    pharm = parse_reviews(pharmacologist, "review_pharmacologist", reader_ids)
    idrev: dict[str, Row] = {}
    for r in id_review:
        sid = r["substance_id"]
        if sid not in ids:
            raise PackageError(f"review_pharmacologist_identifications: {sid}: unknown")
        if r["verdict"] not in ("accept", "correct"):
            raise PackageError(f"review_pharmacologist_identifications: {sid}: bad verdict")
        if r.get("status", "") and r["status"] not in ID_STATUSES:
            raise PackageError(f"review_pharmacologist_identifications: {sid}: bad status")
        if r.get("hazard", "") not in HAZARDS:
            raise PackageError(f"review_pharmacologist_identifications: {sid}: bad hazard")
        idrev[sid] = r
    if set(idrev) != set(ids):
        raise PackageError("review_pharmacologist_identifications: not every substance reviewed")

    claims: list[dict[str, str]] = []
    for r in reader:
        sid = r["span_id"]
        span = span_by_id[sid]
        sub = r["substance_id"]
        reader_cond = _conditions(r["conditions"], f"reader_ai: {sid}")
        conds = final_conditions(reader_cond, hist[sid], pharm[sid])
        status = idrev[sub].get("status") or ids[sub]["status"]
        hazard = idrev[sub].get("hazard", "")
        for c in conds:
            claims.append(
                {
                    "claim_id": f"{sid}:{c}",
                    "span_id": sid,
                    "entry_id": span["entry_id"],
                    "substance_id": sub,
                    "condition": c,
                    "page": page_of.get(span["entry_id"], ""),
                    "line_start": span["line_start"],
                    "line_end": span["line_end"],
                    "arabic_span": span["arabic_span"],
                    "machine_translation_en": final_translation(
                        r["machine_translation_en"], hist[sid], pharm[sid]
                    ),
                    "use_en": r["use_en"],
                    "historian_verdict": hist[sid].verdict,
                    "pharmacologist_verdict": pharm[sid].verdict,
                    "ai_review": "passed_both",
                    "expert_review": "pending",
                    "identification_status": status,
                    "hazard": hazard,
                    "headline_eligible": "yes" if not hazard else "no",
                }
            )
    claims.sort(key=lambda c: c["claim_id"])
    subs = substance_rows(identifications, idrev, entries, gold)
    return Assembly(claims, subs, quality(reader, hist, pharm, idrev, ids, claims))


def quality(
    reader: Sequence[Row],
    hist: Mapping[str, Review],
    pharm: Mapping[str, Review],
    idrev: Mapping[str, Row],
    ids: Mapping[str, Row],
    claims: Sequence[Mapping[str, str]],
) -> dict[str, object]:
    """Extraction quality on the AI-reviewed sample (Req 4.2). Counts only; no judgement."""
    both = sum(1 for s in hist if hist[s].verdict == pharm[s].verdict)
    agree_reject = sum(
        1 for s in hist if (hist[s].verdict == "reject") == (pharm[s].verdict == "reject")
    )
    usable = sum(1 for s in hist if "reject" not in (hist[s].verdict, pharm[s].verdict))
    return {
        "sample_spans": len(reader),
        "rule_vs_reader": {
            "theme": dict(Counter(r["rule_theme_agrees"] for r in reader)),
            "use": dict(Counter(r["rule_use_agrees"] for r in reader)),
        },
        "reader_out_of_scope": sum(1 for r in reader if r["conditions"] == OUT_OF_SCOPE),
        "historian": dict(Counter(v.verdict for v in hist.values())),
        "pharmacologist": dict(Counter(v.verdict for v in pharm.values())),
        "passes_same_verdict": both,
        "passes_agree_on_reject": agree_reject,
        "spans_passing_both": usable,
        "condition_corrections": sum(
            1 for s in hist if hist[s].conditions is not None or pharm[s].conditions is not None
        ),
        "translation_corrections": sum(
            1 for s in hist if hist[s].translation is not None or pharm[s].translation is not None
        ),
        "identifications": {
            "substances": len(ids),
            "status_before_review": dict(Counter(i["status"] for i in ids.values())),
            "corrected_by_pharmacologist": sum(
                1 for r in idrev.values() if r["verdict"] == "correct"
            ),
            "hazard_flags": sum(1 for r in idrev.values() if r.get("hazard")),
        },
        "claims": len(claims),
        "claims_by_condition": dict(Counter(c["condition"] for c in claims)),
        "expert_reviewed": 0,
    }


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return [{k: (v or "") for k, v in row.items()} for row in csv.DictReader(f)]


def _write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    os.replace(tmp, path)


def to_csv(rows: Sequence[Mapping[str, str]], columns: tuple[str, ...]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="canon_package")
    repo = Path(__file__).resolve().parents[3]
    p.add_argument("--package", type=Path, default=repo / "datasets" / "canon")
    p.add_argument("--gold", type=Path, default=repo / "data" / "canon_gold_pmc3941892.csv")
    args = p.parse_args(argv)
    pkg: Path = args.package
    try:
        result = assemble(
            _read(pkg / "theme_spans.csv"),
            _read(pkg / "reader_ai.csv"),
            _read(pkg / "identifications.csv"),
            _read(pkg / "review_historian.csv"),
            _read(pkg / "review_pharmacologist.csv"),
            _read(pkg / "review_pharmacologist_identifications.csv"),
            _read(pkg / "entries.csv"),
            _read(args.gold),
        )
    except (PackageError, OSError, KeyError) as exc:
        print(f"canon_package: {exc}", file=sys.stderr)
        return 1
    _write(pkg / "claims.csv", to_csv(result.claims, CLAIM_COLUMNS))
    _write(pkg / "substances.csv", to_csv(result.substances, SUBSTANCE_COLUMNS))
    _write(pkg / "quality.json", json.dumps(result.quality, indent=2, sort_keys=True) + "\n")
    print(f"canon_package: {len(result.claims)} claims written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
