"""Janus event vocabulary (collective-memory design §4.6, Req 6). Pure apart from `load_events`.

`data/memory_events.csv`: one row per Janus event key,

    key,direction,label_en,label_tr,label_de,label_fr,label_es,pts,pipc_positions,status,note

- `pts`: Preferred Terms as published in FAERS, `|`-separated; empty for `benefit` keys.
- `pipc_positions`: the PIPC rows (1-65) whose adverse event the key stands for, `;`-separated.
  Every PIPC row belongs to exactly one adverse key.
- `status`: `proposed` (not reviewed: nothing user-facing may use the key), `active` (reviewed by
  the owner) or `deprecated` (kept for stored donations, never removed).

A key keeps its meaning once released. The placeholder keys of the privacy spec stay valid.
MedDRA® is a registered trademark of ICH; PTs are used as published, with no hierarchy.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections.abc import Mapping, Set
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from janus.memory.model import EVENT_KEY_PATTERN

COLUMNS: Final = (
    "key",
    "direction",
    "label_en",
    "label_tr",
    "label_de",
    "label_fr",
    "label_es",
    "pts",
    "pipc_positions",
    "status",
    "note",
)
LANGUAGES: Final = ("en", "tr", "de", "fr", "es")
DIRECTIONS: Final = ("adverse", "benefit")
STATUSES: Final = ("proposed", "active", "deprecated")
PIPC_ROWS: Final = 65
PLACEHOLDER_KEYS: Final = (
    "peripheral_oedema",
    "cough",
    "dizziness",
    "constipation",
    "urinary_incontinence",
    "insomnia",
    "improvement_pain",
    "improvement_sleep",
)
MAX_LABEL: Final = 200
_KEY = re.compile(EVENT_KEY_PATTERN)


class VocabularyError(ValueError):
    """The vocabulary file is invalid. `code` is a fixed word; `key` names the row (public data)."""

    def __init__(self, code: str, key: str = "") -> None:
        super().__init__(f"{code}: {key}" if key else code)
        self.code = code
        self.key = key


@dataclass(frozen=True)
class EventKey:
    key: str
    direction: str
    labels: Mapping[str, str]
    pts: tuple[str, ...]
    pipc_positions: tuple[int, ...]
    status: str
    note: str


@dataclass(frozen=True)
class EventVocabulary:
    keys: tuple[EventKey, ...]

    def get(self, key: str) -> EventKey | None:
        return next((k for k in self.keys if k.key == key), None)

    def active(self) -> tuple[EventKey, ...]:
        return tuple(k for k in self.keys if k.status == "active")

    def usable(self, key: str) -> EventKey | None:
        """The key only if it is `active`; proposed keys are never used (Req 6.3)."""
        k = self.get(key)
        return k if k is not None and k.status == "active" else None

    def pipc_event_keys(self) -> Mapping[int, str]:
        """PIPC position -> Janus key for active adverse keys (the finding hook, design §6.3)."""
        return {
            p: k.key
            for k in self.keys
            if k.status == "active" and k.direction == "adverse"
            for p in k.pipc_positions
        }


def _nfc(value: str) -> bool:
    return unicodedata.normalize("NFC", value) == value


def _label_ok(value: str) -> bool:
    return bool(value) and value == value.strip() and len(value) <= MAX_LABEL and _nfc(value)


def _parse_positions(raw: str, key: str) -> tuple[int, ...]:
    if not raw:
        return ()
    out: list[int] = []
    for part in raw.split(";"):
        if not re.fullmatch(r"[1-9][0-9]?", part) or not 1 <= int(part) <= PIPC_ROWS:
            raise VocabularyError("bad_position", key)
        out.append(int(part))
    if len(set(out)) != len(out):
        raise VocabularyError("bad_position", key)
    return tuple(out)


def _parse_pts(raw: str, key: str) -> tuple[str, ...]:
    if not raw:
        return ()
    pts = raw.split("|")
    for pt in pts:
        if not pt or pt != pt.strip() or not _nfc(pt) or len(pt) > 200 or "\n" in pt:
            raise VocabularyError("bad_pt", key)
    if len(set(pts)) != len(pts):
        raise VocabularyError("duplicate_pt", key)
    return tuple(pts)


def parse_events(text: str, *, require_full_pipc: bool = True) -> EventVocabulary:
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise VocabularyError("bad_header") from exc
    if tuple(header) != COLUMNS:
        raise VocabularyError("bad_header")
    keys: list[EventKey] = []
    seen: set[str] = set()
    for row in reader:
        if not row:
            continue
        if len(row) != len(COLUMNS):
            raise VocabularyError("bad_row")
        r: dict[str, str] = dict(zip(COLUMNS, row, strict=True))
        key = r["key"]
        if not _KEY.fullmatch(key):
            raise VocabularyError("bad_key", key)
        if key in seen:
            raise VocabularyError("duplicate_key", key)
        seen.add(key)
        if r["direction"] not in DIRECTIONS:
            raise VocabularyError("bad_direction", key)
        if r["status"] not in STATUSES:
            raise VocabularyError("bad_status", key)
        labels = {lang: r[f"label_{lang}"] for lang in LANGUAGES}
        if not all(_label_ok(v) for v in labels.values()):
            raise VocabularyError("missing_label", key)
        pts = _parse_pts(r["pts"], key)
        positions = _parse_positions(r["pipc_positions"], key)
        if r["direction"] == "adverse" and not pts:
            raise VocabularyError("empty_pts", key)
        if r["direction"] == "benefit" and pts:
            raise VocabularyError("benefit_has_pts", key)
        if r["direction"] == "benefit" and positions:
            raise VocabularyError("benefit_has_positions", key)
        keys.append(EventKey(key, r["direction"], labels, pts, positions, r["status"], r["note"]))
    owners: dict[int, str] = {}
    for k in keys:
        for p in k.pipc_positions:
            if p in owners:
                raise VocabularyError("position_covered_twice", k.key)
            owners[p] = k.key
    if require_full_pipc:
        for p in range(1, PIPC_ROWS + 1):
            if p not in owners:
                raise VocabularyError("position_uncovered")
    for placeholder in PLACEHOLDER_KEYS:
        if placeholder not in seen:
            raise VocabularyError("placeholder_key_missing", placeholder)
    return EventVocabulary(tuple(keys))


def load_events(path: Path, *, require_full_pipc: bool = True) -> EventVocabulary:
    return parse_events(path.read_text(encoding="utf-8"), require_full_pipc=require_full_pipc)


def missing_pts(vocab: EventVocabulary, known: Set[str]) -> Mapping[str, tuple[str, ...]]:
    """PTs of the vocabulary that are not in the counts file's PT list (Req 6.5), by key."""
    out: dict[str, tuple[str, ...]] = {}
    for k in vocab.keys:
        gone = tuple(pt for pt in k.pts if pt not in known)
        if gone:
            out[k.key] = gone
    return out
