"""Curated per-key ATC code exclusions (drug-resolution DP45; found by doctor-loop F13). Pure.

An ingredient key can carry the ATC code of another substance, from one of two sources: a
Wikidata item (for example a wrong code on a synthetic cannabinoid) or a TİTCK single-ingredient
product whose published code does not belong to its ingredient (ketoconazole with ketoprofen's
code, mefenamic acid with tramadol's, esomeprazole with an old pregabalin code). Such a code puts
the medicine into the wrong cascade classes and abrupt-stop warnings, and the note prints it.
`data/atc_code_exclusions.csv` lists the reviewed (key, code, source) triples to drop from the
key's codes before anything is selected from them (codes only, no product names). One reviewed
row each, checked by hand on the WHOCC index (address and date in the row; no index text is
copied). The product keeps its published code as published; only the ingredient's codes change.

A row naming a code that its source no longer gives the key is refused (stale entry), so the
file cannot drift silently when a source is corrected.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from janus.resolution.atc import RulesFileError, is_ingredient_level

HEADER: Final = ["key", "code", "source", "reason", "evidence", "whocc_url", "whocc_date", "note"]
SOURCES: Final = ("wikidata", "titck")
REASONS: Final = ("wrong_substance", "old_code", "not_a_medicine")
QID: Final = re.compile(r"^Q[1-9][0-9]{0,9}$")
WHOCC_URL: Final = re.compile(
    r"^https://atcddd\.fhi\.no/atc_ddd_index/\?code=[A-Z0-9]+(&[a-z]+=[a-z]+)*$"
)
ISO_DATE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class CodeExclusion:
    key: str
    code: str
    source: str
    reason: str
    evidence: str
    whocc_url: str
    whocc_date: str
    note: str

    @property
    def triple(self) -> tuple[str, str, str]:
        return (self.key, self.code, self.source)


def parse_code_exclusions(text: str) -> tuple[CodeExclusion, ...]:
    """Refuses a bad header, key, code or reason, a repeated pair, empty evidence or note, and a
    missing WHOCC address or lookup date. Messages name the row, never its content."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != HEADER:
        raise RulesFileError("atc_code_exclusions.csv: header is not the expected one")
    rows: list[CodeExclusion] = []
    seen: set[tuple[str, str, str]] = set()
    for n, r in enumerate(reader, start=2):
        key, code = (r["key"] or "").strip(), (r["code"] or "").strip()
        if not QID.fullmatch(key):
            raise RulesFileError(f"atc_code_exclusions.csv row {n}: key must be a Wikidata item")
        if not is_ingredient_level(code):
            raise RulesFileError(
                f"atc_code_exclusions.csv row {n}: code must have seven characters"
            )
        source = (r["source"] or "").strip()
        if source not in SOURCES:
            raise RulesFileError(f"atc_code_exclusions.csv row {n}: unknown source")
        if (key, code, source) in seen:
            raise RulesFileError(f"atc_code_exclusions.csv row {n}: repeated entry")
        reason = (r["reason"] or "").strip()
        if reason not in REASONS:
            raise RulesFileError(f"atc_code_exclusions.csv row {n}: unknown reason")
        evidence, note = (r["evidence"] or "").strip(), (r["note"] or "").strip()
        if not evidence or not note:
            raise RulesFileError(f"atc_code_exclusions.csv row {n}: evidence and note are required")
        url, date = (r["whocc_url"] or "").strip(), (r["whocc_date"] or "").strip()
        if not WHOCC_URL.fullmatch(url) or not ISO_DATE.fullmatch(date):
            raise RulesFileError(
                f"atc_code_exclusions.csv row {n}: WHOCC address and date required"
            )
        seen.add((key, code, source))
        rows.append(CodeExclusion(key, code, source, reason, evidence, url, date, note))
    return tuple(rows)


def version_of(exclusions: Sequence[CodeExclusion]) -> str:
    if not exclusions:
        return ""
    blob = json.dumps(
        [[e.key, e.code, e.source, e.reason] for e in sorted(exclusions, key=lambda e: e.triple)]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _codes(row: Mapping[str, Any]) -> list[str]:
    raw: Any = row.get("atc_codes") or []
    return [str(c) for c in raw]


def excluded_pairs(exclusions: Iterable[CodeExclusion], source: str) -> frozenset[tuple[str, str]]:
    return frozenset((e.key, e.code) for e in exclusions if e.source == source)


def apply_to_rows(
    rows: Sequence[Mapping[str, Any]], exclusions: Iterable[CodeExclusion]
) -> list[Mapping[str, Any]]:
    """Wikidata rows without the excluded codes (`source == "wikidata"` entries)."""
    drop: dict[str, set[str]] = {}
    for key, code in excluded_pairs(exclusions, "wikidata"):
        drop.setdefault(key, set()).add(code)
    if not drop:
        return list(rows)
    out: list[Mapping[str, Any]] = []
    for row in rows:
        gone = drop.get(str(row["qid"]))
        if gone is None:
            out.append(row)
        else:
            codes = [c for c in _codes(row) if c not in gone]
            out.append({**row, "atc_codes": codes})
    return out


def carried(rows: Sequence[Mapping[str, Any]]) -> frozenset[tuple[str, str]]:
    """(key, code) pairs a list of Wikidata rows carries."""
    return frozenset((str(r["qid"]), c) for r in rows for c in _codes(r))


def check_not_stale(
    exclusions: Iterable[CodeExclusion],
    wikidata: frozenset[tuple[str, str]],
    titck: frozenset[tuple[str, str]],
) -> None:
    """Raise `RulesFileError` if an entry names a code its source does not give the key."""
    stale = [
        e
        for e in exclusions
        if (e.key, e.code) not in (wikidata if e.source == "wikidata" else titck)
    ]
    if stale:
        raise RulesFileError(
            f"atc_code_exclusions.csv: {len(stale)} entries name a code the source does not give"
        )
