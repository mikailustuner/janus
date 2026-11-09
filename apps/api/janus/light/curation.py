"""Loaders of the curated light-face files (design §4, Req 2.1, 5.1; P10). Pure.

Text in, values out.

`data/light/goals.csv`, `data/light/effect_goal_map.csv` and `data/light/validation_cases.csv` are
curated by the project and reviewed by agent passes ("AI-reviewed, pending expert review"). A
defect stops the build: the loader names the file, the line and the defect, and repairs nothing.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Final

from janus.light.model import (
    CASE_ID_RE,
    GOAL_KEY_RE,
    LANGS,
    Case,
    Curated,
    Goal,
    MappingRow,
    MapStatus,
)
from janus.memory.model import INGREDIENT_KEY_PATTERN
from janus.paths import repo_root

DATA_DIR: Final = repo_root() / "data" / "light"
GOALS_FILE: Final = "goals.csv"
MAPPING_FILE: Final = "effect_goal_map.csv"
CASES_FILE: Final = "validation_cases.csv"

GOALS_HEADER: Final = (
    "key",
    *(f"label_{lang}" for lang in LANGS),
    "faers_pts",
    "benefit_keys",
    "note",
)
MAPPING_HEADER: Final = ("term", "goal", "status", "nonspecific", "evidence", "rationale")
CASES_HEADER: Final = (
    "id",
    "ingredient_name",
    "ingredient_key",
    "goal",
    "original_use",
    "later_year",
    "indication_terms",
    "evidence",
    "note",
)
_KEY = re.compile(INGREDIENT_KEY_PATTERN)
_TERM_WORD = re.compile(r"[a-z0-9' ]+")


class CurationError(ValueError):
    def __init__(self, file: str, line: int, defect: str) -> None:
        super().__init__(f"{file}: line {line}: {defect}")
        self.file = file
        self.line = line
        self.defect = defect


def _rows(text: str, file: str, header: tuple[str, ...]) -> list[tuple[int, dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text))
    if tuple(reader.fieldnames or ()) != header:
        raise CurationError(file, 1, "header")
    out: list[tuple[int, dict[str, str]]] = []
    for i, row in enumerate(reader, start=2):
        if None in row or any(v is None for v in row.values()):
            raise CurationError(file, i, "column_count")
        for name, value in row.items():
            if value != value.strip():
                raise CurationError(file, i, f"whitespace:{name}")
            if unicodedata.normalize("NFC", value) != value:
                raise CurationError(file, i, f"not_nfc:{name}")
        out.append((i, {k: v for k, v in row.items() if k is not None}))
    return out


def _split(value: str, sep: str) -> tuple[str, ...]:
    return tuple(value.split(sep)) if value else ()


def parse_goals(text: str, benefit_keys: Collection[str]) -> dict[str, Goal]:
    file = GOALS_FILE
    goals: dict[str, Goal] = {}
    for line, row in _rows(text, file, GOALS_HEADER):
        key = row["key"]
        if GOAL_KEY_RE.fullmatch(key) is None:
            raise CurationError(file, line, "bad_key")
        if key in goals:
            raise CurationError(file, line, "duplicate_key")
        labels = {lang: row[f"label_{lang}"] for lang in LANGS}
        if any(not v for v in labels.values()):
            raise CurationError(file, line, "missing_label")
        pts = _split(row["faers_pts"], "|")
        if any(not p for p in pts) or len(set(pts)) != len(pts) or list(pts) != sorted(pts):
            raise CurationError(file, line, "bad_faers_pts")
        bks = _split(row["benefit_keys"], "|")
        if any(b not in benefit_keys for b in bks) or list(bks) != sorted(set(bks)):
            raise CurationError(file, line, "bad_benefit_keys")
        goals[key] = Goal(key, labels, pts, bks, row["note"])
    if not goals:
        raise CurationError(file, 1, "empty")
    return goals


def parse_mapping(
    text: str,
    goals: Collection[str],
    papers: Collection[str],
    vocabulary: Collection[str] | None = None,
) -> tuple[MappingRow, ...]:
    """`vocabulary` = OnSIDES term names of the run (checked by the build; None in unit tests)."""
    file = MAPPING_FILE
    out: list[MappingRow] = []
    seen: set[str] = set()
    for line, row in _rows(text, file, MAPPING_HEADER):
        term = row["term"]
        if not term:
            raise CurationError(file, line, "empty_term")
        if term in seen:
            raise CurationError(file, line, "duplicate_term")
        seen.add(term)
        if row["goal"] not in goals:
            raise CurationError(file, line, "unknown_goal")
        status = row["status"]
        if status not in ("active", "excluded"):
            raise CurationError(file, line, "bad_status")
        evidence = _split(row["evidence"], ";")
        if any(e not in papers for e in evidence):
            raise CurationError(file, line, "unknown_evidence")
        if status == "active" and not evidence:
            raise CurationError(file, line, "no_evidence")
        if not row["rationale"]:
            raise CurationError(file, line, "no_rationale")
        if row["nonspecific"] not in ("yes", "no"):
            raise CurationError(file, line, "bad_nonspecific")
        if vocabulary is not None and term not in vocabulary:
            raise CurationError(file, line, "term_not_in_onsides")
        st: MapStatus = "active" if status == "active" else "excluded"
        out.append(
            MappingRow(
                term,
                row["goal"],
                st,
                tuple(sorted(evidence)),
                row["rationale"],
                row["nonspecific"] == "yes",
            )
        )
    return tuple(sorted(out, key=lambda m: m.term))


def parse_cases(text: str, goals: Collection[str], papers: Collection[str]) -> tuple[Case, ...]:
    file = CASES_FILE
    out: list[Case] = []
    seen: set[str] = set()
    for line, row in _rows(text, file, CASES_HEADER):
        cid = row["id"]
        if CASE_ID_RE.fullmatch(cid) is None:
            raise CurationError(file, line, "bad_id")
        if cid in seen:
            raise CurationError(file, line, "duplicate_id")
        seen.add(cid)
        name = row["ingredient_name"]
        if not name or name != name.lower():
            raise CurationError(file, line, "bad_ingredient_name")
        if _KEY.fullmatch(row["ingredient_key"]) is None:
            raise CurationError(file, line, "bad_ingredient_key")
        if row["goal"] not in goals:
            raise CurationError(file, line, "unknown_goal")
        try:
            year = int(row["later_year"])
        except ValueError as exc:
            raise CurationError(file, line, "bad_year") from exc
        if not 1900 <= year <= 2100:
            raise CurationError(file, line, "bad_year")
        terms = _split(row["indication_terms"], "|")
        if not terms or any(_TERM_WORD.fullmatch(t) is None for t in terms):
            raise CurationError(file, line, "bad_indication_terms")
        evidence = _split(row["evidence"], ";")
        if not evidence or any(e not in papers for e in evidence):
            raise CurationError(file, line, "bad_evidence")
        for name_ in ("original_use", "note"):
            if not row[name_]:
                raise CurationError(file, line, f"empty:{name_}")
        out.append(
            Case(
                id=cid,
                ingredient_name=name,
                ingredient_key=row["ingredient_key"],
                goal=row["goal"],
                original_use=row["original_use"],
                later_year=year,
                indication_terms=tuple(sorted(set(terms))),
                evidence=tuple(sorted(evidence)),
                note=row["note"],
            )
        )
    return tuple(sorted(out, key=lambda c: c.id))


def parse_all(
    texts: Mapping[str, str],
    *,
    benefit_keys: Collection[str],
    papers: Collection[str],
    vocabulary: Collection[str] | None = None,
) -> Curated:
    goals = parse_goals(texts[GOALS_FILE], benefit_keys)
    mapping = parse_mapping(texts[MAPPING_FILE], goals, papers, vocabulary)
    cases = parse_cases(texts[CASES_FILE], goals, papers)
    return Curated(goals, mapping, cases)


def read_texts(directory: Path = DATA_DIR) -> dict[str, str]:
    return {
        name: (directory / name).read_text(encoding="utf-8")
        for name in (GOALS_FILE, MAPPING_FILE, CASES_FILE)
    }
