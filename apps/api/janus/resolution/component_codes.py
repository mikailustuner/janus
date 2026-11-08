"""Reviewed (key, combination code) pairs (drug-resolution Req 14, DP43). Pure.

A combination code is never an ingredient code (Req 5.2). The one exception the owner approved
(2026-11-08, option b) is a key whose only WHO code is the combination code that names it: the
WHOCC lists no code for imipenem alone, only `J01DH51` "imipenem and cilastatin" ("Refers to
imipenem"). `data/component_codes.csv` lists such pairs, one reviewed row each. A pair lets that
code reach `rule_input` for that key only; the combination classifier, the leak guard and the
engine's input guard keep refusing the code for every other ingredient.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass

from janus.resolution.atc import CombinationCheck, RulesFileError, is_ingredient_level

COMPONENT_HEADER = ["key", "code", "evidence", "whocc_url", "whocc_date", "note"]
CURATED_KEY = re.compile(r"^J[1-9][0-9]{0,5}$")
WHOCC_URL = re.compile(r"^https://atcddd\.fhi\.no/atc_ddd_index/\?code=[A-Z0-9]+(&[a-z]+=[a-z]+)*$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class ComponentCode:
    key: str
    code: str
    evidence: str
    whocc_url: str
    whocc_date: str
    note: str

    @property
    def pair(self) -> tuple[str, str]:
        return (self.key, self.code)


def parse_component_codes(text: str) -> tuple[ComponentCode, ...]:
    """Pure. Refuses a bad header, a bad key or code, a repeated pair, an empty evidence or note,
    a missing WHOCC address or lookup date. The message names the row, never its content."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != COMPONENT_HEADER:
        raise RulesFileError("component_codes.csv: header is not the expected one")
    rows: list[ComponentCode] = []
    seen: set[tuple[str, str]] = set()
    for n, r in enumerate(reader, start=2):
        key = (r["key"] or "").strip()
        code = (r["code"] or "").strip()
        if not CURATED_KEY.fullmatch(key):
            raise RulesFileError(f"component_codes.csv row {n}: key must be a Janus key")
        if not is_ingredient_level(code):
            raise RulesFileError(f"component_codes.csv row {n}: code must have seven characters")
        if (key, code) in seen:
            raise RulesFileError(f"component_codes.csv row {n}: repeated pair")
        evidence, note = (r["evidence"] or "").strip(), (r["note"] or "").strip()
        if not evidence or not note:
            raise RulesFileError(f"component_codes.csv row {n}: evidence and note are required")
        url, date = (r["whocc_url"] or "").strip(), (r["whocc_date"] or "").strip()
        if not WHOCC_URL.fullmatch(url) or not ISO_DATE.fullmatch(date):
            raise RulesFileError(f"component_codes.csv row {n}: WHOCC address and date required")
        seen.add((key, code))
        rows.append(ComponentCode(key, code, evidence, url, date, note))
    return tuple(rows)


def version_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text.strip() else ""


def validate_against_dataset(
    codes: Iterable[ComponentCode], check: CombinationCheck, curated_keys: Collection[str]
) -> None:
    """Every code must be a combination code of this dataset (otherwise it needs no exception)
    and every key one of the curated Janus keys."""
    for c in codes:
        if c.key not in curated_keys:
            raise RulesFileError("component_codes.csv: a key is not a curated Janus key")
        if not check.is_combination(c.code):
            raise RulesFileError("component_codes.csv: a code is not a combination code")
