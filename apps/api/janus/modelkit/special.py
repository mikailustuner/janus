"""Special populations (spec model-kit, milestone M4, design DP-M26): exposure statements of US
labels.

Read from two committed files: `data/modelkit/special_populations.csv` (statements that two
independent automated readers of the label text agree on; written by the pipeline job
`modelkit_special_populations`) and `data/modelkit/special_populations_atlas.csv` (rows of the
older-adult exposure atlas: one automated extraction that is NOT confirmed by the two-reader rule
and
has not been checked by a person; shown as evidence only), with `special_populations.meta.json`
(coverage and measured precision). Pure reads, cached. No extrapolation to a model, no dose advice.
Research use only. Not for clinical decisions.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from janus.paths import repo_root

POP_CLASSES = ("geriatric", "renal", "hepatic")
MEASURES = ("auc", "cmax")
CONFIRMED_STATUS = "two_readers_agree"
ATLAS_STATUS = "automated_extraction_unconfirmed"


@dataclass(frozen=True)
class Statement:
    pop_class: str
    grade: str
    measure: str
    ratio: float
    ratio_text: str
    definition: str
    reference: str
    quote: str
    set_id: str
    version: str
    effective_date: str
    section: str
    n_labels: int
    from_table: bool


@dataclass(frozen=True)
class AtlasRow:
    measure: str  # auc, cmax, cl, exposure (as the atlas names it)
    ratio: float
    qualitative: bool
    quote: str
    set_id: str
    version: str
    n_labels: int
    quote_checked: bool  # the quote was found verbatim in the label version it cites


@dataclass(frozen=True)
class Special:
    statements: dict[str, tuple[Statement, ...]]
    atlas: dict[str, tuple[AtlasRow, ...]]
    meta: dict[str, Any]


def _read(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@cache
def load(root: Path | None = None) -> Special:
    base = (root or repo_root()) / "data" / "modelkit"
    statements: dict[str, list[Statement]] = {}
    for r in _read(base / "special_populations.csv"):
        statements.setdefault(r["drug_key"], []).append(
            Statement(
                r["pop_class"],
                r["grade"],
                r["measure"],
                float(r["ratio"]),
                r["ratio_text"],
                r["definition"],
                r["reference"],
                r["quote"],
                r["set_id"],
                r["version"],
                r["effective_date"],
                r["section"],
                int(r["n_labels"]),
                r["from_table"] == "true",
            )
        )
    atlas: dict[str, list[AtlasRow]] = {}
    for r in _read(base / "special_populations_atlas.csv"):
        atlas.setdefault(r["drug_key"], []).append(
            AtlasRow(
                r["measure"],
                float(r["ratio"]),
                r["qualitative"] == "true",
                r["quote"],
                r["set_id"],
                r["version"],
                int(r["n_labels"]),
                r["quote_checked"] == "true",
            )
        )
    meta_path = base / "special_populations.meta.json"
    meta: dict[str, Any] = json.loads(meta_path.read_text("utf-8")) if meta_path.is_file() else {}
    order = {c: i for i, c in enumerate(POP_CLASSES)}
    return Special(
        {
            k: tuple(sorted(v, key=lambda s: (order[s.pop_class], s.grade, s.measure, s.ratio)))
            for k, v in statements.items()
        },
        {k: tuple(sorted(v, key=lambda a: (a.measure, a.ratio))) for k, v in atlas.items()},
        meta,
    )


def system_counts(sp: Special) -> dict[str, Any]:
    by_class: dict[str, int] = {}
    for rows in sp.statements.values():
        for s in rows:
            by_class[s.pop_class] = by_class.get(s.pop_class, 0) + 1
    drugs_by_class = {
        c: len({k for k, rows in sp.statements.items() if any(s.pop_class == c for s in rows)})
        for c in POP_CLASSES
    }
    return {
        "drugs": len(sp.statements),
        "statements": sum(len(v) for v in sp.statements.values()),
        "by_class": {c: by_class.get(c, 0) for c in POP_CLASSES},
        "drugs_by_class": drugs_by_class,
        "atlas_drugs": len(sp.atlas),
        "atlas_rows": sum(len(v) for v in sp.atlas.values()),
    }
