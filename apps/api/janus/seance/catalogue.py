"""Séance catalogue: the Canon data package and the curated séance tables (séance design §5).

Files:
- `datasets/canon/` (CC BY-NC-SA 4.0 data package): `entries.csv`, `claims.csv`, `substances.csv`.
- `data/seance_conditions.csv`: condition → MedDRA Preferred Terms (the present witness).
- `data/seance_present.csv`: substance → ingredient key and how well the exposure matches.
- `data/seance_science.csv`: (substance, condition) → listed studies (`data/evidence_papers.csv`).

Everything is validated when it is read; a broken file stops startup with a message naming the
file and the row, never a medical value from a request.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from janus.integrity.records import make_id
from janus.resolution.atc import DATA_DIR
from janus.seance.model import CONDITIONS, IdStatus, Locator

PACKAGE_DIR: Final = DATA_DIR.parent / "datasets" / "canon"
CONDITIONS_FILE: Final = DATA_DIR / "seance_conditions.csv"
PRESENT_FILE: Final = DATA_DIR / "seance_present.csv"
SCIENCE_FILE: Final = DATA_DIR / "seance_science.csv"
PAPERS_FILE: Final = DATA_DIR / "evidence_papers.csv"
SCIENCE_SOURCE: Final = "seance_science"
BOOK: Final = 2
STUDY_TYPES: Final = frozenset(
    {"systematic_review", "rct", "clinical_other", "animal", "in_vitro", "narrative_review"}
)
DIRECTIONS: Final = frozenset({"supports", "mixed", "no_effect"})


class CatalogueError(ValueError):
    """A séance file is missing or inconsistent."""


@dataclass(frozen=True)
class Claim:
    claim_id: str
    substance_id: str
    condition: str
    locator: Locator
    arabic_span: str
    machine_translation_en: str
    use_en: str
    ai_review: str
    expert_review: str
    headline_eligible: bool


@dataclass(frozen=True)
class Substance:
    substance_id: str
    name_en: str
    transliteration: str
    heading_ar: str
    entry_id: str
    kind: str
    identification: str
    identification_status: IdStatus
    gold_id: str | None
    gold_scientific_name: str | None
    hamdard_ref: str | None
    hazard: str | None
    note: str


@dataclass(frozen=True)
class PresentLink:
    ingredient_key: str
    exposure_match: Literal["same", "component", "different"]
    note: str


@dataclass(frozen=True)
class Study:
    evidence_id: str
    doi: str
    title: str
    study_type: str
    direction: str
    finding_en: str


@dataclass(frozen=True)
class Catalogue:
    entries: Mapping[str, tuple[int, int]]  # entry_id -> (line_start, line_end)
    substances: Mapping[str, Substance]
    claims: tuple[Claim, ...]
    condition_pts: Mapping[str, tuple[str, ...]]
    present: Mapping[str, PresentLink]
    science: Mapping[tuple[str, str], tuple[Study, ...]]
    package_source: Mapping[str, str]


def _read(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as f:
            return [{k: (v or "") for k, v in r.items()} for r in csv.DictReader(f)]
    except OSError as exc:
        raise CatalogueError(f"{path.name}: cannot be read") from exc


def _need(rows: list[dict[str, str]], cols: tuple[str, ...], name: str) -> None:
    if rows and not set(cols) <= set(rows[0]):
        raise CatalogueError(f"{name}: missing columns")


def _int(value: str, where: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise CatalogueError(f"{where}: not an integer") from exc


def _status(value: str, where: str) -> IdStatus:
    if value == "matches_gold":
        return "matches_gold"
    if value == "uncertain":
        return "uncertain"
    if value == "not_in_gold":
        return "not_in_gold"
    raise CatalogueError(f"{where}: bad identification status")


def _match(value: str, where: str) -> Literal["same", "component", "different"]:
    if value == "same":
        return "same"
    if value == "component":
        return "component"
    if value == "different":
        return "different"
    raise CatalogueError(f"{where}: bad exposure_match")


def load_catalogue(
    package: Path = PACKAGE_DIR,
    conditions: Path = CONDITIONS_FILE,
    present: Path = PRESENT_FILE,
    science: Path = SCIENCE_FILE,
    papers: Path = PAPERS_FILE,
) -> Catalogue:
    entries: dict[str, tuple[int, int]] = {}
    for r in _read(package / "entries.csv"):
        where = f"entries.csv: {r.get('entry_id', '?')}"
        entries[r["entry_id"]] = (_int(r["line_start"], where), _int(r["line_end"], where))

    subs: dict[str, Substance] = {}
    rows = _read(package / "substances.csv")
    _need(rows, ("substance_id", "entry_id", "status"), "substances.csv")
    for r in rows:
        where = f"substances.csv: {r['substance_id']}"
        if r["entry_id"] not in entries:
            raise CatalogueError(f"{where}: entry not in the package")
        subs[r["substance_id"]] = Substance(
            substance_id=r["substance_id"],
            name_en=r["name_en"],
            transliteration=r["transliteration"],
            heading_ar=r["heading_ar"],
            entry_id=r["entry_id"],
            kind=r["kind"],
            identification=r["janus_identification"],
            identification_status=_status(r["status"], where),
            gold_id=r["gold_id"] or None,
            gold_scientific_name=r["gold_scientific_name"] or None,
            hamdard_ref=r["hamdard_ref"] or None,
            hazard=r["hazard"] or None,
            note=r["note"],
        )

    claims: list[Claim] = []
    for r in _read(package / "claims.csv"):
        where = f"claims.csv: {r['claim_id']}"
        if r["substance_id"] not in subs:
            raise CatalogueError(f"{where}: unknown substance")
        if r["condition"] not in CONDITIONS:
            raise CatalogueError(f"{where}: unknown condition")
        if r["entry_id"] not in entries:
            raise CatalogueError(f"{where}: entry not in the package")
        lo, hi = entries[r["entry_id"]]
        ls, le = _int(r["line_start"], where), _int(r["line_end"], where)
        if not (lo <= ls <= le <= hi):
            raise CatalogueError(f"{where}: lines outside the entry")
        claims.append(
            Claim(
                claim_id=r["claim_id"],
                substance_id=r["substance_id"],
                condition=r["condition"],
                locator=Locator(r["entry_id"], r["span_id"], BOOK, r["page"] or None, ls, le),
                arabic_span=r["arabic_span"],
                machine_translation_en=r["machine_translation_en"],
                use_en=r["use_en"],
                ai_review=r["ai_review"],
                expert_review=r["expert_review"],
                headline_eligible=r["headline_eligible"] == "yes",
            )
        )

    pts: dict[str, tuple[str, ...]] = {}
    for r in _read(conditions):
        if r["condition"] not in CONDITIONS:
            raise CatalogueError(f"{conditions.name}: unknown condition")
        values = tuple(p for p in r["pts"].split("|") if p)
        if not values:
            raise CatalogueError(f"{conditions.name}: {r['condition']}: no terms")
        pts[r["condition"]] = values
    if set(pts) != set(CONDITIONS):
        raise CatalogueError(f"{conditions.name}: every condition needs a row")

    links: dict[str, PresentLink] = {}
    for r in _read(present):
        where = f"{present.name}: {r['substance_id']}"
        if r["substance_id"] not in subs:
            raise CatalogueError(f"{where}: unknown substance")
        if not r["note"].strip():
            raise CatalogueError(f"{where}: a link needs a note")
        links[r["substance_id"]] = PresentLink(
            r["ingredient_key"], _match(r["exposure_match"], where), r["note"]
        )

    paper_rows = {r["key"]: r for r in _read(papers) if r["source_id"] == SCIENCE_SOURCE}
    studies: dict[tuple[str, str], list[Study]] = {}
    for r in _read(science):
        where = f"{science.name}: {r['substance_id']}/{r['condition']}/{r['paper_key']}"
        if r["substance_id"] not in subs or r["condition"] not in CONDITIONS:
            raise CatalogueError(f"{where}: unknown substance or condition")
        if r["study_type"] not in STUDY_TYPES or r["direction"] not in DIRECTIONS:
            raise CatalogueError(f"{where}: bad study type or direction")
        paper = paper_rows.get(r["paper_key"])
        if paper is None:
            raise CatalogueError(f"{where}: paper not in evidence_papers.csv")
        studies.setdefault((r["substance_id"], r["condition"]), []).append(
            Study(
                evidence_id=make_id("paper", SCIENCE_SOURCE, r["paper_key"]),
                doi=paper["doi"].lower(),
                title=paper["title"],
                study_type=r["study_type"],
                direction=r["direction"],
                finding_en=r["finding_en"],
            )
        )
    source = {"package": "datasets/canon", "license": "CC BY-NC-SA 4.0"}
    return Catalogue(
        entries=entries,
        substances=subs,
        claims=tuple(sorted(claims, key=lambda c: c.claim_id)),
        condition_pts=pts,
        present=links,
        science={k: tuple(v) for k, v in studies.items()},
        package_source=source,
    )
