"""Candidate PTs for the Janus event vocabulary (collective-memory design §4.6, task 4).

`python -m janus.memory.event_proposals [--data-dir PATH] [--top N]` reads the current counts file
read-only and prints, for each proposed Janus event key, the FAERS Preferred Terms that match the
key's search patterns with their report counts (all regions, all deduplicated reports and mapped
reports). It decides nothing: the PT lists are clinical judgement, proposed in the review sheet,
reviewed by the pharmacologist agent and then by the project owner before any use.

Counts are reports, never people. MedDRA® is a registered trademark of ICH; PTs are shown as
published in FAERS.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import duckdb

from janus.memory.faers_build import COUNTS_DB, counts_root


@dataclass(frozen=True)
class Seed:
    """A proposed key: the PIPC rows it stands for and regular expressions over PT strings."""

    key: str
    pipc_positions: tuple[int, ...]
    patterns: tuple[str, ...]


# Hand-written starting points; every hit is a candidate only.
SEEDS: tuple[Seed, ...] = (
    Seed("cough", (1,), (r"^cough$", r"^productive cough$", r"^upper-airway cough")),
    Seed(
        "dizziness",
        (2, 56),
        (r"dizziness", r"orthostatic hypotension", r"presyncope", r"orthostatic intolerance"),
    ),
    Seed("depression", (3, 36, 55), (r"^depress", r"^major depression", r"depressed mood")),
    Seed("erectile_dysfunction", (4,), (r"erectile", r"^sexual dysfunction")),
    Seed(
        "peripheral_oedema", (5, 31), (r"oedema peripheral", r"peripheral swelling", r"^swelling$")
    ),
    Seed(
        "oedema", (43,), (r"^oedema", r"fluid retention", r"generalised oedema", r"fluid overload")
    ),
    Seed("constipation", (6, 34, 65), (r"constipation", r"faecal(oma| impaction)")),
    Seed("gout_hyperuricaemia", (7,), (r"^gout", r"uric acid", r"hyperuricaemia")),
    Seed("urinary_incontinence", (8, 24, 32, 35), (r"incontinence", r"urge")),
    Seed(
        "myalgia_myositis",
        (9, 10, 11),
        (r"^myalgia", r"^myositis", r"muscle pain", r"muscular weakness"),
    ),
    Seed(
        "insomnia",
        (12, 25, 59),
        (r"insomnia", r"sleep disorder", r"poor quality sleep", r"^abnormal sleep"),
    ),
    Seed("nausea", (13, 16, 52), (r"^nausea$", r"^vomiting$", r"^retching")),
    Seed(
        "hypertension",
        (14, 38, 53, 61, 64),
        (
            r"^hypertension$",
            r"blood pressure (increased|abnormal|inadequately|fluctuation)",
            r"hypertensive crisis",
        ),
    ),
    Seed("rash", (15,), (r"^rash", r"^dermatitis", r"^eczema", r"^urticaria")),
    Seed(
        "extrapyramidal_symptoms",
        (17, 18, 19, 37, 46),
        (r"extrapyramidal", r"^parkinsonism", r"^dystonia", r"^bradykinesia", r"^cogwheel"),
    ),
    Seed("akathisia_tardive_movements", (20,), (r"akathisia", r"tardive", r"^dyskinesia")),
    Seed(
        "arrhythmia",
        (21, 63),
        (
            r"^arrhythmia",
            r"^cardiac arrhythmia",
            r"qt",
            r"torsade",
            r"ventricular (tachy|fibrill)",
            r"atrial fibrillation",
        ),
    ),
    Seed(
        "hyperglycaemia",
        (22,),
        (r"hyperglyc", r"blood glucose increased", r"diabetes mellitus inadequate"),
    ),
    Seed(
        "cognitive_impairment",
        (23, 33),
        (r"cognitive", r"^memory impairment", r"^amnesia", r"^confusional", r"^dementia"),
    ),
    Seed(
        "gastrointestinal_upset",
        (26, 27),
        (
            r"^dyspepsia",
            r"gastrointestinal disorder",
            r"abdominal (discomfort|pain)",
            r"^gastrointestinal",
        ),
    ),
    Seed(
        "diarrhoea",
        (28, 42, 47),
        (r"^diarrhoea", r"^frequent bowel", r"^faeces (soft|discoloured)"),
    ),
    Seed("rhinorrhoea", (29,), (r"rhinorrh", r"nasal congestion")),
    Seed(
        "psychosis_hallucinations",
        (30, 60),
        (r"hallucination", r"^psychotic", r"^psychosis", r"^delusion"),
    ),
    Seed("tremor", (39,), (r"^tremor", r"essential tremor")),
    Seed("joint_pain", (40,), (r"^arthralgia", r"^joint (pain|swelling|stiffness)")),
    Seed(
        "genital_fungal_infection",
        (41, 62),
        (r"vulvovaginal", r"genital (candid|infection fungal)", r"balan", r"candida"),
    ),
    Seed(
        "urinary_retention",
        (45,),
        (r"urinary retention", r"^urinary hesitation", r"residual urine"),
    ),
    Seed(
        "osteoporosis_fracture", (48,), (r"osteopor", r"osteopenia", r"fracture", r"bone density")
    ),
    Seed(
        "vitamin_mineral_deficiency",
        (49,),
        (r"vitamin b12", r"hypomagn", r"iron deficiency", r"vitamin d deficiency", r"deficiency"),
    ),
    Seed("gastritis", (50,), (r"^gastritis", r"^oesophagitis")),
    Seed(
        "gastric_ulcer_bleed",
        (51,),
        (
            r"gastric ulcer",
            r"gastrointestinal haemorrhage",
            r"gastric haemorrhage",
            r"peptic ulcer",
            r"duodenal ulcer",
            r"^melaena",
        ),
    ),
    Seed("heart_failure", (44, 54), (r"cardiac failure", r"^pulmonary oedema")),
    Seed("dry_mouth", (57,), (r"^dry mouth", r"^dry throat", r"^hyposalivation")),
    Seed("seizures", (58,), (r"^seizure", r"^convulsion", r"^status epilepticus", r"epilep")),
)


def candidates(con: duckdb.DuckDBPyConnection, seed: Seed, top: int) -> list[tuple[str, int, int]]:
    """PTs matching any pattern: (pt, reports over all deduplicated reports, mapped reports)."""
    rows = con.execute(
        "SELECT pt, reports_all, reports_mapped FROM faers_event_counts WHERE region = 'ALL' "
        "ORDER BY reports_all DESC, pt"
    ).fetchall()
    regexes = [re.compile(p, re.IGNORECASE) for p in seed.patterns]
    hits = [
        (str(pt), int(a), int(m)) for pt, a, m in rows if any(r.search(str(pt)) for r in regexes)
    ]
    return hits[:top]


def propose(counts_db: Path, top: int) -> Mapping[str, list[tuple[str, int, int]]]:
    con = duckdb.connect(str(counts_db), read_only=True)
    try:
        return {s.key: candidates(con, s, top) for s in SEEDS}
    finally:
        con.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m janus.memory.event_proposals")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args(argv)
    current = counts_root(args.data_dir) / "current" / COUNTS_DB
    if not current.exists():
        print("no current counts file", file=sys.stderr)
        return 1
    result = propose(current, args.top)
    for seed in SEEDS:
        print(f"{seed.key}  (PIPC rows {','.join(map(str, seed.pipc_positions))})")
        for pt, all_reports, mapped in result[seed.key]:
            print(f"    {all_reports:>8} {mapped:>8}  {pt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
