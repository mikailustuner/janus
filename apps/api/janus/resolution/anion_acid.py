"""Anion-to-acid table of the `anion_acid` ladder step (drug-resolution design §15.4, Req 12.7).

`data/anion_acid_forms.csv` (columns `lang,anion,acid,note`) maps the anion form of a salt or
ester name (`mycophenolate`) to the label of its acid (`mycophenolic acid`). The table is reviewed
row by row; there is deliberately no generic "-ate → -ic acid" rewrite (it would turn salicylate
salts into salicylic acid, a different substance). The step only looks the acid up through the
label steps, so it can only land on an existing ingredient key. Pure: no I/O except `load`.
"""

from __future__ import annotations

import csv
import hashlib
import io
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from janus.resolution.atc import DATA_DIR, RulesFileError
from janus.resolution.names import fold

ANION_ACID_FILE = DATA_DIR / "anion_acid_forms.csv"
HEADER = ["lang", "anion", "acid", "note"]
LANGS = frozenset({"tr", "en", "fr", "es", "any"})


def _rows(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != HEADER:
        raise RulesFileError(f"header must be {','.join(HEADER)}")
    return list(reader)


@dataclass(frozen=True)
class AnionAcidRow:
    lang: str
    anion: str  # folded
    acid: str  # folded label of the acid
    note: str


@dataclass(frozen=True)
class AnionAcidTable:
    rows: tuple[AnionAcidRow, ...] = ()
    version: str = ""  # sha256 of the file text; "" for the empty table

    def lookup(self, lang: str, anion: str) -> tuple[str, ...]:
        """Folded acid labels for an anion in `lang` (rows of `any` apply to every language)."""
        return tuple(r.acid for r in self.rows if r.anion == anion and r.lang in (lang, "any"))

    @classmethod
    def from_csv_text(cls, text: str) -> AnionAcidTable:
        rows: list[AnionAcidRow] = []
        seen: set[tuple[str, str]] = set()
        for n, raw in enumerate(_rows(text), start=2):
            lang = (raw["lang"] or "").strip()
            anion, acid = fold(raw["anion"] or ""), fold(raw["acid"] or "")
            note = (raw["note"] or "").strip()
            if lang not in LANGS:
                raise RulesFileError(f"row {n}: lang must be one of {sorted(LANGS)}")
            if not anion or not acid or anion == acid:
                raise RulesFileError(f"row {n}: anion and acid must be non-empty and different")
            if not note:
                raise RulesFileError(f"row {n}: a note with the evidence is required")
            if (lang, anion) in seen:
                raise RulesFileError(f"row {n}: repeated (lang, anion)")
            seen.add((lang, anion))
            rows.append(AnionAcidRow(lang, anion, acid, note))
        return cls(tuple(rows), hashlib.sha256(text.encode()).hexdigest())

    @classmethod
    def load(cls, path: Path = ANION_ACID_FILE) -> AnionAcidTable:
        return cls.from_csv_text(path.read_text(encoding="utf-8")) if path.is_file() else cls()

    def check_acids(self, keys_of: Callable[[str], Iterable[str]]) -> None:
        """Every acid label must resolve to exactly one eligible ingredient key (loader check).

        `keys_of(folded label)` returns the keys the label steps find for it.
        """
        for n, r in enumerate(self.rows, start=2):
            if len(set(keys_of(r.acid))) != 1:
                raise RulesFileError(f"row {n}: the acid does not resolve to exactly one key")
